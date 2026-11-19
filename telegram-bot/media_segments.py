"""Create independently playable media segments using ffprobe and ffmpeg.

No shell is involved. Video is normalized to H.264/AAC in MP4; audio can be
exported as standalone MP3 files. Existing output files are never overwritten.
"""
from __future__ import annotations

import json
import math
import os
import re
import signal
import subprocess
import time
from pathlib import Path
from typing import Callable

DEFAULT_MAX_BYTES = 48_000_000
HARD_MAX_BYTES = 50_000_000
PROFILES = {
    "360p": (640, 360),
    "480p": (854, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
}


class MediaSegmentError(RuntimeError):
    """Raised when probing or producing playable segments fails."""


_ACTIVE_PROCESSES: dict[int, subprocess.Popen] = {}


def _terminate_active_processes(signum, _frame) -> None:
    for process in list(_ACTIVE_PROCESSES.values()):
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and any(p.poll() is None for p in _ACTIVE_PROCESSES.values()):
        time.sleep(0.05)
    for process in list(_ACTIVE_PROCESSES.values()):
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    raise SystemExit(128 + int(signum))


def install_termination_handler() -> None:
    """Install in a worker process so cancellation cleans up its FFmpeg process group."""
    signal.signal(signal.SIGTERM, _terminate_active_processes)


def _run(command: list[str]) -> subprocess.CompletedProcess:
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True
    )
    _ACTIVE_PROCESSES[process.pid] = process
    try:
        stdout, stderr = process.communicate()
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command, output=stdout, stderr=stderr)
        return result
    finally:
        _ACTIVE_PROCESSES.pop(process.pid, None)


def probe_duration(path: str | Path, *, ffprobe: str = "ffprobe",
                   runner: Callable = _run) -> float:
    """Return media duration in seconds as reported by ffprobe."""
    try:
        result = runner([ffprobe, "-v", "error", "-show_entries", "format=duration",
                         "-of", "json", str(path)])
        duration = float(json.loads(result.stdout)["format"]["duration"])
    except (subprocess.SubprocessError, KeyError, ValueError, TypeError,
            json.JSONDecodeError) as exc:
        raise MediaSegmentError(f"Could not determine duration for {path}: {exc}") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise MediaSegmentError(f"Invalid media duration for {path}: {duration}")
    return duration


def probe_dimensions(path: str | Path, *, ffprobe: str = "ffprobe",
                     runner: Callable = _run) -> tuple[int, int] | None:
    """Return the first video stream's dimensions, if ffprobe can read them."""
    try:
        result = runner([ffprobe, "-v", "error", "-select_streams", "v:0",
                         "-show_entries", "stream=width,height", "-of", "json", str(path)])
        streams = json.loads(result.stdout).get("streams", [])
        if not streams:
            return None
        width, height = int(streams[0]["width"]), int(streams[0]["height"])
        return (width, height) if width > 0 and height > 0 else None
    except (subprocess.SubprocessError, KeyError, ValueError, TypeError,
            json.JSONDecodeError):
        return None


def _safe_stem(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", path.stem).strip("._-")
    return stem or "media"


def split_media(input_path: str | Path, output_dir: str | Path | None = None, *,
                profile: str = "720p", max_bytes: int = DEFAULT_MAX_BYTES,
                segment_seconds: float = 600, mode: str = "video", audio_bitrate: int = 192,
                max_retries: int = 5, ffmpeg: str = "ffmpeg",
                ffprobe: str = "ffprobe", runner: Callable = _run) -> list[Path]:
    """Encode an input into independently playable, size-bounded segments.

    ``mode`` is ``video`` or ``audio``. Each oversized attempt is removed and
    retried at 80% of its attempted duration. The next segment starts at the
    previous output's *measured* duration, not the requested duration.
    On any failure, all files created by this call are removed.
    """
    source = Path(input_path)
    destination = Path(output_dir) if output_dir is not None else source.parent
    if mode not in ("video", "audio"):
        raise ValueError("mode must be 'video' or 'audio'")
    if mode == "video" and profile not in PROFILES:
        raise ValueError(f"profile must be one of: {', '.join(PROFILES)}")
    if mode == "audio" and audio_bitrate not in (128, 192, 320):
        raise ValueError("audio_bitrate must be 128, 192, or 320")
    if not isinstance(max_bytes, int) or not 0 < max_bytes < HARD_MAX_BYTES:
        raise ValueError(f"max_bytes must be a positive integer below {HARD_MAX_BYTES}")
    if not math.isfinite(segment_seconds) or segment_seconds <= 0:
        raise ValueError("segment_seconds must be positive")
    if max_retries < 0:
        raise ValueError("max_retries cannot be negative")

    destination.mkdir(parents=True, exist_ok=True)
    duration = probe_duration(source, ffprobe=ffprobe, runner=runner)
    source_dimensions = probe_dimensions(source, ffprobe=ffprobe, runner=runner) if mode == "video" else None
    extension = ".mp4" if mode == "video" else ".mp3"
    stem = _safe_stem(source)
    outputs: list[Path] = []
    current_output: Path | None = None
    start = 0.0
    index = 1
    try:
        while start < duration - 1e-6:
            planned = min(float(segment_seconds), duration - start)
            output = destination / f"{stem}.part{index:03d}{extension}"
            if output.exists():
                raise MediaSegmentError(f"Output already exists: {output}")
            current_output = output
            for retry in range(max_retries + 1):
                command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-n",
                           "-ss", f"{start:.6f}", "-i", str(source), "-t", f"{planned:.6f}"]
                if mode == "video":
                    target_width, target_height = PROFILES[profile]
                    if source_dimensions:
                        source_width, source_height = source_dimensions
                        scale = min(target_width / source_width, target_height / source_height, 1.0)
                        output_width = max(2, int(source_width * scale) // 2 * 2)
                        output_height = max(2, int(source_height * scale) // 2 * 2)
                        command += ["-vf", f"scale={output_width}:{output_height}"]
                    command += ["-map", "0:v:0", "-map", "0:a:0?",
                                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]
                else:
                    command += ["-vn", "-c:a", "libmp3lame", "-b:a", f"{audio_bitrate}k"]
                command += [str(output)]
                try:
                    runner(command)
                except subprocess.SubprocessError as exc:
                    output.unlink(missing_ok=True)
                    raise MediaSegmentError(f"ffmpeg failed for segment {index}: {exc}") from exc
                if not output.is_file():
                    raise MediaSegmentError(f"ffmpeg did not create segment {index}")
                actual_bytes = output.stat().st_size
                if actual_bytes < max_bytes:
                    break
                output.unlink(missing_ok=True)
                if retry == max_retries:
                    raise MediaSegmentError(
                        f"Segment {index} remains over the {max_bytes}-byte cap after {max_retries} retries")
                planned *= 0.8
                if planned < 0.01:
                    raise MediaSegmentError(f"Cannot shorten segment {index} enough to meet byte cap")
            segment_duration = probe_duration(output, ffprobe=ffprobe, runner=runner)
            if segment_duration <= 0 or segment_duration > planned + max(0.25, planned * 0.02):
                raise MediaSegmentError(f"Unexpected duration for output segment {index}: {segment_duration}")
            outputs.append(output)
            current_output = None
            start += segment_duration
            index += 1
        return outputs
    except BaseException:
        if current_output is not None:
            current_output.unlink(missing_ok=True)
        for output in outputs:
            output.unlink(missing_ok=True)
        raise
