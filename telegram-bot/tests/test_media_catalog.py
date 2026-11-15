import unittest

from media_catalog import build_choices, summarize_info


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

    def test_audio_choices_expose_bounded_mp3_bitrates(self):
        choices = build_choices(self.info)
        audio = [choice for choice in choices if choice["kind"] == "audio"]
        self.assertEqual([choice["audio_quality"] for choice in audio], [320, 192, 128])
        self.assertTrue(all(choice["format_selector"] == "a256" for choice in audio))

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


if __name__ == "__main__":
    unittest.main()
