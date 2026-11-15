import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from media_segments import MediaSegmentError, split_media


class MediaSegmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source clip.mp4"
        self.source.write_bytes(b"source")
        self.commands = []

    def tearDown(self):
        self.temp.cleanup()

    def runner(self, command):
        self.commands.append(command)
        if command[0] == "ffprobe":
            path = Path(command[-1])
            if "-select_streams" in command:
                return subprocess.CompletedProcess(command, 0,
                    json.dumps({"streams": [{"width": 320, "height": 240}]}), "")
            seconds = 12.0 if path == self.source else float(path.read_text())
            return subprocess.CompletedProcess(command, 0,
                json.dumps({"format": {"duration": str(seconds)}}), "")
        output = Path(command[-1])
        start = float(command[command.index("-ss") + 1])
        requested = float(command[command.index("-t") + 1])
        output.write_text(str(min(requested, 4.0)))
        return subprocess.CompletedProcess(command, 0, "", "")

    def test_safe_command_and_duration_continuity(self):
        outputs = split_media(self.source, profile="360p", segment_seconds=5,
                              runner=self.runner)
        self.assertEqual([p.name for p in outputs], [
            "source_clip.part001.mp4", "source_clip.part002.mp4", "source_clip.part003.mp4"])
        encodes = [c for c in self.commands if c[0] == "ffmpeg"]
        self.assertTrue(all(isinstance(c, list) and "-fs" not in c and "-y" not in c for c in encodes))
        self.assertEqual([float(c[c.index("-ss") + 1]) for c in encodes], [0, 4, 8])
        self.assertTrue(all(any(arg == "scale=320:240" for arg in c) for c in encodes))

    def test_oversized_output_retries_shorter_and_checks_strict_cap(self):
        calls = 0
        durations = {}
        def runner(command):
            nonlocal calls
            self.commands.append(command)
            if command[0] == "ffprobe":
                path = Path(command[-1])
                duration = 1.0 if path == self.source else durations[path]
                return subprocess.CompletedProcess(command, 0,
                    json.dumps({"format": {"duration": str(duration)}}), "")
            calls += 1
            output = Path(command[-1])
            requested = float(command[command.index("-t") + 1])
            # First attempt exceeds the eight-byte cap; retry is under it.
            output.write_bytes(b"x" * (10 if calls == 1 else 4))
            durations[output] = min(requested, 0.2)
            return subprocess.CompletedProcess(command, 0, "", "")
        outputs = split_media(self.source, self.root / "out", max_bytes=8,
                              segment_seconds=1, max_retries=2, runner=runner)
        encodes = [c for c in self.commands if c[0] == "ffmpeg"]
        self.assertEqual(len(encodes), 6)  # failed attempt, retry, then remaining short segments
        self.assertLess(float(encodes[1][encodes[1].index("-t") + 1]),
                        float(encodes[0][encodes[0].index("-t") + 1]))
        self.assertTrue(all(p.stat().st_size < 8 for p in outputs))

    def test_cleanup_on_retry_exhaustion(self):
        def runner(command):
            if command[0] == "ffprobe":
                return subprocess.CompletedProcess(command, 0,
                    json.dumps({"format": {"duration": "1"}}), "")
            Path(command[-1]).write_bytes(b"x" * 10)
            return subprocess.CompletedProcess(command, 0, "", "")
        with self.assertRaises(MediaSegmentError):
            split_media(self.source, self.root / "out", max_bytes=5,
                        segment_seconds=1, max_retries=1, runner=runner)
        self.assertEqual(list((self.root / "out").iterdir()), [])

    def test_existing_colliding_output_is_never_removed(self):
        output_dir = self.root / "out"
        output_dir.mkdir()
        existing = output_dir / "source_clip.part001.mp4"
        existing.write_bytes(b"keep this file")
        with self.assertRaises(MediaSegmentError):
            split_media(self.source, output_dir, runner=self.runner)
        self.assertEqual(existing.read_bytes(), b"keep this file")

    def test_audio_mode_emits_standalone_mp3_command(self):
        outputs = split_media(self.source, self.root / "audio", mode="audio", audio_bitrate=320, runner=self.runner)
        self.assertEqual(outputs[0].suffix, ".mp3")
        cmd = next(c for c in self.commands if c[0] == "ffmpeg")
        self.assertIn("libmp3lame", cmd)
        self.assertIn("-vn", cmd)
        self.assertEqual(cmd[cmd.index("-b:a") + 1], "320k")

    def test_optional_real_ffmpeg_smoke(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("ffmpeg/ffprobe not installed")
        source = self.root / "tiny.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                        "-i", "color=c=black:s=160x120:d=1", "-f", "lavfi",
                        "-i", "sine=frequency=1000:duration=1", "-shortest", "-c:v", "libx264",
                        "-c:a", "aac", str(source)], check=True, capture_output=True)
        outputs = split_media(source, self.root / "smoke", segment_seconds=1,
                              profile="360p", max_bytes=1_000_000)
        self.assertEqual(len(outputs), 1)
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "json", str(outputs[0])], check=True, capture_output=True, text=True)
        self.assertGreater(float(json.loads(probe.stdout)["format"]["duration"]), 0)
        dimensions = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                     "-show_entries", "stream=width,height", "-of", "json", str(outputs[0])],
                                    check=True, capture_output=True, text=True)
        self.assertEqual((json.loads(dimensions.stdout)["streams"][0]["width"],
                          json.loads(dimensions.stdout)["streams"][0]["height"]), (160, 120))
        self.assertLess(outputs[0].stat().st_size, 1_000_000)

        silent = self.root / "silent.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                        "-i", "color=c=blue:s=160x120:d=1", "-an", "-c:v", "libx264", str(silent)],
                       check=True, capture_output=True)
        silent_outputs = split_media(silent, self.root / "silent-smoke", profile="360p",
                                     max_bytes=1_000_000)
        self.assertEqual(len(silent_outputs), 1)


if __name__ == "__main__":
    unittest.main()
