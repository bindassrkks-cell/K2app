#!/usr/bin/env python3
"""Standalone K2App Telegram downloader. Runs independently of the Android app."""
from __future__ import annotations

import asyncio
import hmac
import ipaddress
import logging
import mimetypes
import os
import re
import sqlite3
import socket
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx

LOGGER = logging.getLogger("k2app.telegram_bot")
URL_PATTERN = re.compile(r"https?://[^\s<>\[\]]+", re.IGNORECASE)
COMMAND_PATTERN = re.compile(r"^/([A-Za-z0-9_]+)(?:@[A-Za-z0-9_]+)?$")
MAX_URLS_PER_MESSAGE = 3
MAX_URL_LENGTH = 2048
PUBLIC_BOT_API_MAX_BYTES = 50_000_000
EXCLUDED_SUFFIXES = {
    ".part", ".ytdl", ".json", ".description", ".jpg", ".jpeg", ".png",
    ".webp", ".vtt", ".srt", ".ass", ".lrc", ".temp",
}


class ConfigurationError(ValueError):
    pass


class TelegramApiError(RuntimeError):
    def __init__(self, error_code: int | None, description: str):
        self.error_code = error_code
        self.description = description
        super().__init__(f"Telegram API error {error_code or 'unknown'}")


class MediaTooLargeError(RuntimeError):
    def __init__(self, size_bytes: int, limit_bytes: int):
        self.size_bytes = size_bytes
        self.limit_bytes = limit_bytes
        super().__init__("Media exceeds the configured Telegram upload limit")


def _is_local_api_host(host: str) -> bool:
    host = host.lower().rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "." not in host
    if address.is_loopback:
        return True
    if address.version == 4:
        return any(
            address in ipaddress.ip_network(network)
            for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
        )
    return address in ipaddress.ip_network("fc00::/7")


@dataclass(frozen=True)
class Config:
    token: str
    api_base: str
    state_file: Path
    max_upload_bytes: int
    owner_chat_id: str | None
    setup_code: str | None

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{20,}", token):
            raise ConfigurationError("Set TELEGRAM_BOT_TOKEN to a valid BotFather token")

        api_base = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org").strip().rstrip("/")
        parsed_base = urlsplit(api_base)
        if parsed_base.scheme not in {"http", "https"} or not parsed_base.netloc:
            raise ConfigurationError("TELEGRAM_API_BASE must be an http(s) URL")
        api_host = (parsed_base.hostname or "").lower()
        if not api_host or parsed_base.username is not None or parsed_base.password is not None:
            raise ConfigurationError("TELEGRAM_API_BASE must have a host and must not contain credentials")
        try:
            _ = parsed_base.port
        except ValueError as error:
            raise ConfigurationError("TELEGRAM_API_BASE has an invalid port") from error
        allow_http_local = os.getenv("ALLOW_HTTP_LOCAL_API", "").strip().lower() in {"1", "true", "yes"}
        if parsed_base.scheme == "http" and (
            not allow_http_local or not _is_local_api_host(api_host)
        ):
            raise ConfigurationError(
                "Use HTTPS for remote Bot API servers; plain HTTP requires ALLOW_HTTP_LOCAL_API=true "
                "and a local/private endpoint"
            )

        try:
            max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "49"))
        except ValueError as error:
            raise ConfigurationError("MAX_UPLOAD_MB must be an integer") from error
        if not 1 <= max_upload_mb <= 2000:
            raise ConfigurationError("MAX_UPLOAD_MB must be between 1 and 2000")
        if (
            api_host == "api.telegram.org"
            and max_upload_mb * 1_000_000 > PUBLIC_BOT_API_MAX_BYTES
        ):
            raise ConfigurationError(
                "MAX_UPLOAD_MB cannot exceed 50 with Telegram's hosted Bot API; "
                "configure a self-hosted Bot API server for larger uploads"
            )

        owner_chat_id = os.getenv("OWNER_CHAT_ID", "").strip() or None
        if owner_chat_id is not None and (
            not re.fullmatch(r"[0-9]+", owner_chat_id) or int(owner_chat_id) <= 0
        ):
            raise ConfigurationError("OWNER_CHAT_ID must be a numeric private Telegram chat ID")
        setup_code = os.getenv("BOT_SETUP_CODE", "").strip() or None
        if owner_chat_id is None and setup_code is None:
            raise ConfigurationError("Set OWNER_CHAT_ID or BOT_SETUP_CODE before starting the private bot")
        if setup_code is not None and not re.fullmatch(r"[A-Za-z0-9_-]{20,}", setup_code):
            raise ConfigurationError("BOT_SETUP_CODE must be at least 20 letters, digits, underscores, or hyphens")

        state_file = Path(os.getenv("BOT_STATE_FILE", "data/k2app-telegram.sqlite3"))
        return cls(
            token=token,
            api_base=api_base,
            state_file=state_file,
            max_upload_bytes=max_upload_mb * 1_000_000,
            owner_chat_id=owner_chat_id,
            setup_code=setup_code,
        )


class BotState:
    """Stores the first private /start owner and polling offset in SQLite."""

    def __init__(self, path: Path | str, configured_owner: str | None = None):
        self.path = Path(path)
        self.configured_owner = configured_owner
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect()
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS bot_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.commit()
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def owner_chat_id(self) -> str | None:
        if self.configured_owner is not None:
            return self.configured_owner
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT value FROM bot_state WHERE key = 'owner_chat_id'"
            ).fetchone()
            return str(row[0]) if row else None
        finally:
            connection.close()

    def claim_owner(self, chat_id: str) -> str:
        if self.configured_owner is not None:
            return self.configured_owner
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    "INSERT OR IGNORE INTO bot_state(key, value) VALUES('owner_chat_id', ?)",
                    (str(chat_id),),
                )
                row = connection.execute(
                    "SELECT value FROM bot_state WHERE key = 'owner_chat_id'"
                ).fetchone()
                return str(row[0])
        finally:
            connection.close()

    def next_offset(self) -> int:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT value FROM bot_state WHERE key = 'next_offset'"
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            connection.close()

    def save_offset(self, offset: int) -> None:
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    "INSERT INTO bot_state(key, value) VALUES('next_offset', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (str(int(offset)),),
                )
        finally:
            connection.close()


class TelegramApi:
    def __init__(self, token: str, base_url: str):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=20.0))

    async def close(self) -> None:
        await self.client.aclose()

    def _url(self, method: str) -> str:
        return f"{self.base_url}/bot{self.token}/{method}"

    async def call(
        self,
        method: str,
        payload: dict | None = None,
        *,
        files: dict | None = None,
        timeout: httpx.Timeout | None = None,
    ):
        url = self._url(method)
        if files is None:
            response = await self.client.post(url, json=payload or {}, timeout=timeout)
        else:
            response = await self.client.post(
                url, data=payload or {}, files=files, timeout=timeout
            )
        try:
            result = response.json()
        except ValueError as error:
            raise TelegramApiError(response.status_code, "Telegram returned an unreadable response") from error
        if not response.is_success or not result.get("ok", False):
            raise TelegramApiError(
                result.get("error_code", response.status_code),
                str(result.get("description", "Telegram request failed")),
            )
        return result.get("result")

    async def send_message(self, chat_id: str, text: str) -> None:
        await self.call("sendMessage", {"chat_id": chat_id, "text": text})

    async def send_media(self, chat_id: str, path: Path, mode: str) -> None:
        method = "sendAudio" if mode == "audio" else "sendDocument"
        field = "audio" if mode == "audio" else "document"
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        upload_timeout = httpx.Timeout(240.0, connect=20.0)
        with path.open("rb") as media_file:
            await self.call(
                method,
                {"chat_id": chat_id, "caption": path.name[:900]},
                files={field: (path.name, media_file, mime_type)},
                timeout=upload_timeout,
            )


def parse_command(text: str) -> tuple[str | None, str]:
    """Return a bot command without its optional @username suffix and its payload."""
    parts = text.strip().split(maxsplit=1)
    if not parts:
        return None, ""
    match = COMMAND_PATTERN.fullmatch(parts[0])
    if not match:
        return None, text.strip()
    return match.group(1).lower(), parts[1].strip() if len(parts) == 2 else ""


def is_safe_http_url(url: str) -> bool:
    if len(url) > MAX_URL_LENGTH:
        return False
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme.lower() not in {"http", "https"} or not host:
            return False
        if parsed.username is not None or parsed.password is not None:
            return False
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return False
        if host in {"metadata.google.internal", "metadata.google"}:
            return False
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return "." in host
        return address.is_global
    except (ValueError, UnicodeError):
        return False


@contextmanager
def _public_dns_only():
    """Reject private/reserved destinations on every Python DNS resolution during yt-dlp."""
    original_getaddrinfo = socket.getaddrinfo

    def guarded_getaddrinfo(host, port, *args, **kwargs):
        records = original_getaddrinfo(host, port, *args, **kwargs)
        for family, _socktype, _protocol, _canonical_name, sockaddr in records:
            if family not in {socket.AF_INET, socket.AF_INET6} or not isinstance(sockaddr, tuple):
                continue
            try:
                address = ipaddress.ip_address(str(sockaddr[0]).split("%", 1)[0])
            except ValueError:
                raise OSError("Blocked an invalid network destination") from None
            if not address.is_global:
                raise OSError("Blocked a non-public network destination")
        return records

    # The bot processes one update at a time, so no Telegram API request runs concurrently here.
    socket.getaddrinfo = guarded_getaddrinfo
    try:
        yield
    finally:
        socket.getaddrinfo = original_getaddrinfo


def extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for match in URL_PATTERN.finditer(text):
        candidate = match.group(0).rstrip(".,;:!?)]}\"'")
        if is_safe_http_url(candidate) and candidate not in urls:
            urls.append(candidate)
    return urls[:MAX_URLS_PER_MESSAGE]


def _download_media(url: str, work_dir: Path, mode: str, max_bytes: int) -> tuple[Path, str]:
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ImportError as error:
        raise RuntimeError("yt-dlp is not installed") from error

    options = {
        "format": "bestaudio/best" if mode == "audio" else "bestvideo*+bestaudio/best",
        "outtmpl": str(work_dir / "%(title).80B-%(id)s.%(ext)s"),
        "noplaylist": True,
        "max_filesize": max_bytes,
        "merge_output_format": "mp4",
        "hls_prefer_native": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "socket_timeout": 30,
        "retries": 2,
        "fragment_retries": 2,
        "overwrites": True,
    }
    if mode == "audio":
        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]

    try:
        with YoutubeDL(options) as downloader:
            with _public_dns_only():
                info = downloader.extract_info(url, download=True)
            if not isinstance(info, dict):
                raise RuntimeError("No media information was returned")

            candidates: list[Path] = []
            for key in ("filepath", "_filename"):
                value = info.get(key)
                if isinstance(value, str):
                    candidates.append(Path(value))
            for requested in info.get("requested_downloads", []):
                value = requested.get("filepath") if isinstance(requested, dict) else None
                if isinstance(value, str):
                    candidates.append(Path(value))
            candidates.extend(
                path for path in work_dir.rglob("*")
                if path.is_file() and path.suffix.lower() not in EXCLUDED_SUFFIXES
            )
            existing = list(dict.fromkeys(path for path in candidates if path.is_file()))
            if mode == "audio":
                mp3_files = [path for path in existing if path.suffix.lower() == ".mp3"]
                if mp3_files:
                    existing = mp3_files
            if not existing:
                raise RuntimeError("yt-dlp produced no media file")
            media_path = max(existing, key=lambda path: path.stat().st_size)
    except DownloadError as error:
        message = str(error).lower()
        if "max-filesize" in message or "larger than max" in message:
            raise MediaTooLargeError(0, max_bytes) from None
        raise RuntimeError("yt-dlp could not download this URL") from None

    size = media_path.stat().st_size
    if size > max_bytes:
        raise MediaTooLargeError(size, max_bytes)
    return media_path, str(info.get("title") or media_path.name)


class K2TelegramBot:
    def __init__(self, config: Config, state: BotState, api: TelegramApi):
        self.config = config
        self.state = state
        self.api = api

    async def handle_message(self, message: dict) -> None:
        chat = message.get("chat") or {}
        chat_id_value = chat.get("id")
        chat_id = str(chat_id_value) if chat_id_value is not None else ""
        if not chat_id:
            return

        if chat.get("type") != "private":
            await self.api.send_message(chat_id, "Open a private chat with this bot and send /start.")
            return

        text = str(message.get("text") or message.get("caption") or "").strip()
        command, payload = parse_command(text)
        owner = self.state.owner_chat_id()

        if command == "start":
            if owner is None:
                if self.config.setup_code is None or not hmac.compare_digest(payload, self.config.setup_code):
                    await self.api.send_message(
                        chat_id,
                        "To claim this bot, send /start followed by the one-time setup code configured by its owner.",
                    )
                    return
                owner = self.state.claim_owner(chat_id)
            if owner != chat_id:
                await self.api.send_message(chat_id, "This is a private K2App bot and is already connected to its owner.")
                return
            await self.api.send_message(
                chat_id,
                "K2App bot is ready. Send a public media URL to download it here.\n\n"
                "Commands: /video URL, /audio URL, /help.\n"
                f"Current upload limit: {self.config.max_upload_bytes // 1_000_000} MB.",
            )
            return

        if owner is None:
            await self.api.send_message(chat_id, "This bot is not connected yet. Its owner must complete the private setup first.")
            return
        if chat_id != owner:
            await self.api.send_message(chat_id, "This is a private K2App bot.")
            return

        if command in {"help", "start"}:
            await self.api.send_message(
                chat_id,
                "Send a public media URL, or use /video URL or /audio URL. "
                "The bot uses yt-dlp-supported sites; login-only or DRM-protected media is not supported. "
                f"Files must fit the configured {self.config.max_upload_bytes // 1_000_000} MB upload limit.",
            )
            return
        if command == "status":
            await self.api.send_message(chat_id, "K2App Telegram downloader is running and ready.")
            return
        if command not in {None, "video", "audio", "download"}:
            await self.api.send_message(chat_id, "Unknown command. Send /help for usage.")
            return

        mode = "audio" if command == "audio" else "video"
        urls = extract_urls(payload if command else text)
        if not urls:
            await self.api.send_message(chat_id, "I couldn't find a public http(s) media URL. Send /help for usage.")
            return

        for url in urls:
            await self._download_and_send(chat_id, url, mode)

    async def _download_and_send(self, chat_id: str, url: str, mode: str) -> None:
        await self.api.send_message(chat_id, "Processing your link. I’ll send the file here when it’s ready.")
        try:
            with tempfile.TemporaryDirectory(prefix="k2app-telegram-") as directory:
                media_path, title = await asyncio.to_thread(
                    _download_media,
                    url,
                    Path(directory),
                    mode,
                    self.config.max_upload_bytes,
                )
                await self.api.send_media(chat_id, media_path, mode)
            await self.api.send_message(chat_id, f"Sent: {title[:180]}")
        except MediaTooLargeError as error:
            actual = f" ({error.size_bytes / 1_000_000:.1f} MB)" if error.size_bytes else ""
            await self.api.send_message(
                chat_id,
                f"The file{actual} exceeds the configured {error.limit_bytes // 1_000_000} MB limit. "
                "The regular Telegram Bot API accepts uploads up to 50 MB; larger uploads require a self-hosted Bot API server.",
            )
        except TelegramApiError as error:
            LOGGER.warning("Telegram send failed (code=%s)", error.error_code)
            await self.api.send_message(
                chat_id,
                "Telegram could not accept the file. It may exceed the Bot API limit; "
                "use a lower-size format or configure a self-hosted Bot API server for larger files.",
            )
        except Exception as error:
            LOGGER.warning("Media processing failed (error_type=%s)", type(error).__name__)
            await self.api.send_message(
                chat_id,
                "I couldn't download that link. It may be unsupported, private, login-protected, or larger than the upload limit.",
            )


async def run_bot(config: Config) -> None:
    state = BotState(config.state_file, config.owner_chat_id)
    api = TelegramApi(config.token, config.api_base)
    bot = K2TelegramBot(config, state, api)
    try:
        # Polling and webhooks are mutually exclusive. Keep pending updates when switching to polling.
        await api.call("deleteWebhook", {"drop_pending_updates": False})
        identity = await api.call("getMe")
        LOGGER.info("Telegram polling started for @%s", identity.get("username", "bot"))
        offset = state.next_offset()
        while True:
            try:
                updates = await api.call(
                    "getUpdates",
                    {"offset": offset, "timeout": 30, "allowed_updates": ["message"]},
                    timeout=httpx.Timeout(45.0, connect=20.0),
                )
                for update in updates or []:
                    update_id = int(update.get("update_id", offset))
                    try:
                        message = update.get("message")
                        if isinstance(message, dict):
                            await bot.handle_message(message)
                        next_offset = max(offset, update_id + 1)
                        state.save_offset(next_offset)
                        offset = next_offset
                    except Exception as error:
                        LOGGER.warning(
                            "Update processing failed (update_id=%s, error_type=%s)",
                            update_id,
                            type(error).__name__,
                        )
                        await asyncio.sleep(5)
                        break
            except TelegramApiError as error:
                LOGGER.error("Telegram polling error (code=%s)", error.error_code)
                if error.error_code == 401:
                    raise ConfigurationError("Telegram rejected TELEGRAM_BOT_TOKEN") from None
                await asyncio.sleep(8 if error.error_code == 409 else 5)
            except (httpx.HTTPError, OSError) as error:
                LOGGER.warning("Polling connection failed (error_type=%s)", type(error).__name__)
                await asyncio.sleep(5)
    finally:
        await api.close()


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        asyncio.run(run_bot(Config.from_env()))
    except KeyboardInterrupt:
        LOGGER.info("Telegram bot stopped")
    except ConfigurationError as error:
        LOGGER.error("Bot configuration/startup error: %s", error)
        raise SystemExit(2) from None
    except Exception as error:
        # HTTP client exceptions may include a request URL containing the bot token.
        LOGGER.error("Bot stopped (error_type=%s)", type(error).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
