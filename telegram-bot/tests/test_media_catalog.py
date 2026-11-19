import sys
import types
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from media_catalog import (
    MediaResolutionError,
    build_choices,
    classify_extraction_error,
    resolve_media,
    summarize_info,
)


class MediaCatalogTests(unittest.TestCase):
    def setUp(self):
        self.info = {
            "title": "Sample title",
            "duration": 125.9,
            "extractor_key": "Example",
            "thumbnail": "https://cdn.example/video.jpg",
            "formats": [
                {"format_id": "v1080", "height": 1080, "vcodec": "avc1", "acodec": "none", "ext": "mp4", "tbr": 4000},
                {"format_id": "v720", "height": 720, "vcodec": "avc1", "acodec": "none", "ext": "mp4", "tbr": 2200},
                {"format_id": "v480", "height": 480, "vcodec": "vp9", "acodec": "none", "ext": "webm", "tbr": 1000},
                {"format_id": "a128", "vcodec": "none", "acodec": "mp4a.40.2", "ext": "m4a", "abr": 128},
                {"format_id": "a256", "vcodec": "none", "acodec": "opus", "ext": "webm", "abr": 256},
            ],
        }

    def test_video_choices_use_available_resolutions_and_pair_audio(self):
        choices = build_choices(self.info)
        videos = [choice for choice in choices if choice["kind"] == "video"]
        self.assertEqual([choice["height"] for choice in videos], [1080, 720, 480])
        self.assertEqual(videos[0]["format_selector"], "v1080+a256")
        self.assertTrue(all(choice["label"].startswith("MP4") for choice in videos))
        self.assertGreater(videos[0]["estimated_size_bytes"], 0)

    def test_audio_choices_expose_bounded_mp3_bitrates(self):
        choices = build_choices(self.info)
        audio = [choice for choice in choices if choice["kind"] == "audio"]
        self.assertEqual([choice["audio_quality"] for choice in audio], [320, 192, 128])
        self.assertTrue(all(choice["format_selector"] == "a256" for choice in audio))
        self.assertGreater(audio[0]["estimated_size_bytes"], 0)

    def test_thumbnail_is_included_only_for_https_url(self):
        self.assertIn("thumbnail", [choice["kind"] for choice in build_choices(self.info)])
        insecure = dict(self.info, thumbnail="http://cdn.example/video.jpg")
        self.assertNotIn("thumbnail", [choice["kind"] for choice in build_choices(insecure)])
        private = dict(self.info, thumbnail="https://127.0.0.1/private.jpg")
        self.assertNotIn("thumbnail", [choice["kind"] for choice in build_choices(private)])

    def test_safe_fallback_thumbnail_is_exposed_as_a_choice(self):
        info = dict(self.info, thumbnail=None, thumbnails=[{"url": "https://cdn.example/fallback.jpg"}])
        summary = summarize_info(info)
        self.assertEqual(summary["thumbnail_url"], "https://cdn.example/fallback.jpg")
        self.assertIn("thumbnail", [choice["kind"] for choice in summary["choices"]])

    def test_summary_contains_only_bounded_display_fields(self):
        result = summarize_info(self.info)
        self.assertEqual(result["title"], "Sample title")
        self.assertEqual(result["duration_seconds"], 125)
        self.assertEqual(result["extractor"], "Example")
        self.assertEqual(result["thumbnail_url"], "https://cdn.example/video.jpg")

    def test_invalid_format_ids_are_not_returned(self):
        malformed = {
            "formats": [
                {"format_id": "x+system", "height": 720, "vcodec": "avc1", "acodec": "none"},
                {"format_id": "audio", "vcodec": "none", "acodec": "aac", "abr": 128},
            ],
        }
        choices = build_choices(malformed)
        self.assertFalse(any(choice.get("format_selector", "").startswith("x+system") for choice in choices))

    def test_video_without_height_metadata_gets_best_available_fallback(self):
        info = {
            "formats": [
                {"format_id": "generic-video", "vcodec": "h264", "acodec": "aac", "ext": "mp4", "tbr": 1200}
            ]
        }
        videos = [choice for choice in build_choices(info) if choice["kind"] == "video"]
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]["label"], "MP4 · Best available")
        self.assertIsNone(videos[0]["height"])
        self.assertEqual(videos[0]["format_selector"], "generic-video")

    def test_unknown_public_url_uses_default_ytdlp_extractors_and_safe_formats(self):
        captured = {}
        url = "https://media.example/watch?id=clip-1&share=token"

        class FakeYoutubeDL:
            def __init__(self, options):
                captured["options"] = options

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def extract_info(self, value, download=False):
                captured["url"] = value
                captured["download"] = download
                return {
                    "title": "Generic video",
                    "extractor_key": "Generic",
                    "formats": [
                        {"format_id": "http-360p", "height": 360, "vcodec": "h264", "acodec": "aac", "ext": "mp4"}
                    ],
                }

        fake_module = types.ModuleType("yt_dlp")
        fake_module.YoutubeDL = FakeYoutubeDL
        with patch.dict(sys.modules, {"yt_dlp": fake_module}), \
                patch("bot.is_safe_http_url", return_value=True), \
                patch("bot._public_dns_only", return_value=nullcontext()):
            result = resolve_media(url)

        self.assertEqual(captured["url"], url)
        self.assertFalse(captured["download"])
        self.assertTrue(captured["options"]["noplaylist"])
        self.assertFalse(captured["options"]["extract_flat"])
        self.assertNotIn("extractor_ies", captured["options"])
        self.assertNotIn("allowed_extractors", captured["options"])
        self.assertEqual(result["extractor"], "Generic")
        self.assertTrue(result["choices"])

    def test_extractor_failures_get_safe_non_url_bearing_messages(self):
        cases = [
            ("login required for this video", "access"),
            ("This video is geo-restricted", "region"),
            ("HTTP Error 429: Too Many Requests", "blocked"),
            ("Unsupported URL: https://example.com/private?token=secret", "unsupported"),
        ]
        for detail, expected_code in cases:
            with self.subTest(detail=detail):
                error = MediaResolutionError(classify_extraction_error(RuntimeError(detail)))
                self.assertEqual(error.code, expected_code)
                self.assertNotIn("example.com", str(error))
                self.assertNotIn("secret", str(error))


if __name__ == "__main__":
    unittest.main()
