import asyncio
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot import (
    BotState,
    Config,
    ConfigurationError,
    K2TelegramBot,
    _public_dns_only,
    extract_urls,
    is_safe_http_url,
    parse_command,
)


TOKEN = "12345:" + "A" * 30
SETUP_CODE = "a-long-random-setup-secret-123456"


class FakeApi:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text):
        self.messages.append((str(chat_id), text))


class UrlParsingTests(unittest.TestCase):
    def test_extracts_and_trims_url_punctuation(self):
        self.assertEqual(
            extract_urls("Please download https://example.com/video?id=7)."),
            ["https://example.com/video?id=7"],
        )

    def test_deduplicates_urls_and_limits_count(self):
        text = "https://a.example/v https://b.example/v https://a.example/v https://c.example/v https://d.example/v"
        self.assertEqual(
            extract_urls(text),
            ["https://a.example/v", "https://b.example/v", "https://c.example/v"],
        )

    def test_rejects_unsafe_or_non_http_urls(self):
        for url in (
            "file:///etc/passwd",
            "http://127.0.0.1/admin",
            "http://169.254.169.254/latest/meta-data",
            "http://localhost/",
            "https://user:password@example.com/video",
        ):
            with self.subTest(url=url):
                self.assertFalse(is_safe_http_url(url))

    def test_accepts_public_http_url(self):
        self.assertTrue(is_safe_http_url("https://www.example.com/watch?v=123"))

    def test_parses_audio_command_with_bot_username(self):
        self.assertEqual(
            parse_command("/audio@k2app_bot https://example.com/song"),
            ("audio", "https://example.com/song"),
        )

    def test_regular_message_is_not_a_command(self):
        self.assertEqual(parse_command("https://example.com/video"), (None, "https://example.com/video"))


class NetworkGuardTests(unittest.TestCase):
    def test_blocks_dns_results_with_private_addresses(self):
        def private_result(host, port, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.0.0.7", port))]

        with patch("bot.socket.getaddrinfo", private_result):
            with _public_dns_only():
                with self.assertRaises(OSError):
                    socket.getaddrinfo("attacker.example", 443)

    def test_allows_public_dns_results(self):
        def public_result(host, port, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port))]

        with patch("bot.socket.getaddrinfo", public_result):
            with _public_dns_only():
                self.assertTrue(socket.getaddrinfo("example.com", 443))


class ConfigTests(unittest.TestCase):
    def test_owner_or_setup_code_is_required(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": TOKEN}, clear=True):
            with self.assertRaises(ConfigurationError):
                Config.from_env()

    def test_default_hosted_api_limit_is_safe_with_setup_code(self):
        env = {"TELEGRAM_BOT_TOKEN": TOKEN, "BOT_SETUP_CODE": SETUP_CODE}
        with patch.dict(os.environ, env, clear=True):
            config = Config.from_env()
        self.assertEqual(config.max_upload_bytes, 49_000_000)
        self.assertEqual(config.max_download_bytes, 1_024_000_000)

    def test_download_limit_is_independent_and_capped_at_1024_mb(self):
        env = {"TELEGRAM_BOT_TOKEN": TOKEN, "BOT_SETUP_CODE": SETUP_CODE, "MAX_DOWNLOAD_MB": "1024"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(Config.from_env().max_download_bytes, 1_024_000_000)
        for value in ("0", "1025", "invalid"):
            with self.subTest(value=value), patch.dict(os.environ, {**env, "MAX_DOWNLOAD_MB": value}, clear=True):
                with self.assertRaises(ConfigurationError):
                    Config.from_env()

    def test_hosted_api_rejects_limit_above_50_mb(self):
        env = {"TELEGRAM_BOT_TOKEN": TOKEN, "BOT_SETUP_CODE": SETUP_CODE, "MAX_UPLOAD_MB": "51"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfigurationError):
                Config.from_env()

    def test_remote_bot_api_requires_https(self):
        env = {
            "TELEGRAM_BOT_TOKEN": TOKEN,
            "BOT_SETUP_CODE": SETUP_CODE,
            "TELEGRAM_API_BASE": "http://api.example.com",
            "ALLOW_HTTP_LOCAL_API": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfigurationError):
                Config.from_env()

    def test_non_private_http_api_addresses_are_rejected(self):
        hosts = (
            "169.254.169.254",
            "0.0.0.0",
            "0.0.0.1",
            "224.0.0.1",
            "192.0.2.1",
            "100.64.0.1",
            "[fe80::1]",
            "[::]",
        )
        for host in hosts:
            env = {
                "TELEGRAM_BOT_TOKEN": TOKEN,
                "BOT_SETUP_CODE": SETUP_CODE,
                "TELEGRAM_API_BASE": f"http://{host}",
                "ALLOW_HTTP_LOCAL_API": "true",
            }
            with self.subTest(host=host), patch.dict(os.environ, env, clear=True):
                with self.assertRaises(ConfigurationError):
                    Config.from_env()

    def test_private_rfc1918_http_api_requires_and_accepts_opt_in(self):
        env = {
            "TELEGRAM_BOT_TOKEN": TOKEN,
            "BOT_SETUP_CODE": SETUP_CODE,
            "TELEGRAM_API_BASE": "http://10.1.2.3:8081",
            "ALLOW_HTTP_LOCAL_API": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(Config.from_env().api_base, "http://10.1.2.3:8081")

    def test_malformed_bot_api_port_is_rejected(self):
        env = {
            "TELEGRAM_BOT_TOKEN": TOKEN,
            "BOT_SETUP_CODE": SETUP_CODE,
            "TELEGRAM_API_BASE": "https://api.example.com:bad",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfigurationError):
                Config.from_env()

    def test_setup_code_must_use_supported_random_secret_characters(self):
        env = {"TELEGRAM_BOT_TOKEN": TOKEN, "BOT_SETUP_CODE": "too short"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfigurationError):
                Config.from_env()

    def test_custom_local_bot_api_allows_larger_cap_only_with_opt_in(self):
        env = {
            "TELEGRAM_BOT_TOKEN": TOKEN,
            "BOT_SETUP_CODE": SETUP_CODE,
            "TELEGRAM_API_BASE": "http://telegram-bot-api:8081",
            "ALLOW_HTTP_LOCAL_API": "true",
            "MAX_UPLOAD_MB": "1900",
        }
        with patch.dict(os.environ, env, clear=True):
            config = Config.from_env()
        self.assertEqual(config.max_upload_bytes, 1_900_000_000)


class BotStateTests(unittest.TestCase):
    def test_first_owner_claim_wins_and_offset_persists(self):
        with tempfile.TemporaryDirectory() as folder:
            state_path = Path(folder) / "state.sqlite3"
            state = BotState(state_path)
            self.assertIsNone(state.owner_chat_id())
            self.assertEqual(state.claim_owner("12345"), "12345")
            self.assertEqual(state.claim_owner("67890"), "12345")
            state.save_offset(345)
            self.assertEqual(BotState(state_path).next_offset(), 345)

    def test_configured_owner_cannot_be_claimed_over(self):
        with tempfile.TemporaryDirectory() as folder:
            state = BotState(Path(folder) / "state.sqlite3", configured_owner="12345")
            self.assertEqual(state.owner_chat_id(), "12345")
            self.assertEqual(state.claim_owner("67890"), "12345")

    def test_setup_code_is_required_and_first_valid_claim_wins(self):
        with tempfile.TemporaryDirectory() as folder:
            state = BotState(Path(folder) / "state.sqlite3")
            config = Config(
                token=TOKEN,
                api_base="https://api.telegram.org",
                state_file=state.path,
                max_upload_bytes=49_000_000,
                max_download_bytes=1_024_000_000,
                owner_chat_id=None,
                setup_code=SETUP_CODE,
            )
            api = FakeApi()
            bot = K2TelegramBot(config, state, api)

            asyncio.run(bot.handle_message({"chat": {"id": 111, "type": "private"}, "text": "/start wrong"}))
            self.assertIsNone(state.owner_chat_id())
            asyncio.run(bot.handle_message({"chat": {"id": 111, "type": "private"}, "text": f"/start {SETUP_CODE}"}))
            self.assertEqual(state.owner_chat_id(), "111")
            asyncio.run(bot.handle_message({"chat": {"id": 222, "type": "private"}, "text": f"/start {SETUP_CODE}"}))
            self.assertEqual(state.owner_chat_id(), "111")
            self.assertIn("already connected", api.messages[-1][1])

    def test_media_choice_session_is_owner_bound_and_single_use(self):
        with tempfile.TemporaryDirectory() as folder:
            state = BotState(Path(folder) / "state.sqlite3", configured_owner="12345")
            media = {"url": "https://example.com/video", "title": "clip", "choices": [
                {"kind": "video", "label": "MP4 720p", "format_selector": "v1+a1", "height": 720},
            ]}
            token = state.save_media_choices("12345", media)
            self.assertEqual(state.media_job_status(token, "12345")["status"], "chooser_ready")
            self.assertIsNone(state.consume_media_choice(token, "99999", 0))
            self.assertIsNone(state.consume_media_choice(token, "12345", 4))
            selected = state.consume_media_choice(token, "12345", 0)
            self.assertEqual(selected[1]["label"], "MP4 720p")
            self.assertIsNone(state.consume_media_choice(token, "12345", 0))
            self.assertEqual(state.media_job_status(token, "12345")["status"], "queued")

    def test_expired_media_choice_cannot_be_opened_or_selected(self):
        with tempfile.TemporaryDirectory() as folder:
            state = BotState(Path(folder) / "state.sqlite3", configured_owner="12345")
            token = state.save_media_choices("12345", {"choices": [{"kind": "audio"}]}, ttl_seconds=-1)
            self.assertIsNone(state.get_media_choices(token, "12345"))
            self.assertIsNone(state.consume_media_choice(token, "12345", 0))


class MediaDeliveryTests(unittest.TestCase):

    def test_selected_audio_is_sent_as_playable_mp3_segments(self):
        from unittest.mock import AsyncMock

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "movie.mkv"
            source.write_bytes(b"source")
            part1, part2 = root / "movie.part001.mp3", root / "movie.part002.mp3"
            part1.write_bytes(b"one")
            part2.write_bytes(b"two")
            config = Config(TOKEN, "https://api.telegram.org", root / "state.db", 3, 100,
                            "123", None)
            api = FakeApi()
            api.send_media = AsyncMock(side_effect=lambda chat, path, mode: api.messages.append(("media", path.name, mode)))
            state = BotState(root / "state.db", "123")
            bot = K2TelegramBot(config, state, api)
            token = state.save_media_choices("123", {"url": "https://example.com/movie", "choices": []})
            media = {"url": "https://example.com/movie", "title": "Movie"}
            choice = {"kind": "audio", "label": "MP3 · 192 kbps", "format_selector": "a1", "audio_quality": 192}
            with patch("bot._download_with_deadline", new=AsyncMock(return_value=(source, "Movie"))), \
                 patch("bot._split_media_with_deadline", new=AsyncMock(return_value=[part1, part2])):
                asyncio.run(bot._download_and_send("123", token, media, choice))
            self.assertEqual([item for item in api.messages if item[0] == "media"], [
                ("media", "movie.part001.mp3", "audio"),
                ("media", "movie.part002.mp3", "audio"),
            ])
            self.assertTrue(any("independently playable" in item[1] for item in api.messages if item[0] == "123"))
            self.assertEqual(state.media_job_status(token, "123")["status"], "done")


if __name__ == "__main__":
    unittest.main()
