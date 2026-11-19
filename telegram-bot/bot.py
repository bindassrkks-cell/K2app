#!/usr/bin/env python3
"""Standalone K2App Telegram downloader. Runs independently of the Android app."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import mimetypes
import multiprocessing
import os
import re
import secrets
import sqlite3
import socket
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from media_catalog import MediaResolutionError, classify_extraction_error

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
DOWNLOAD_TIMEOUT_SECONDS = 270


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
    max_download_bytes: int
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
                "MAX_UPLOAD_MB cannot exceed 50 with Telegram's hosted Bot API"
            )

        try:
            max_download_mb = int(os.getenv("MAX_DOWNLOAD_MB", "1024"))
        except ValueError as error:
            raise ConfigurationError("MAX_DOWNLOAD_MB must be an integer") from error
        if not 1 <= max_download_mb <= 1024:
            raise ConfigurationError("MAX_DOWNLOAD_MB must be between 1 and 1024")

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
            max_download_bytes=max_download_mb * 1_000_000,
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
            connection.execute(
                "CREATE TABLE IF NOT EXISTS media_choices (token TEXT PRIMARY KEY, chat_id TEXT NOT NULL, "
                "media_json TEXT NOT NULL, expires_at INTEGER NOT NULL, consumed INTEGER NOT NULL DEFAULT 0, "
                "status TEXT NOT NULL DEFAULT 'chooser_ready', progress INTEGER NOT NULL DEFAULT 0, "
                "status_text TEXT NOT NULL DEFAULT '')"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS api_pair_codes (code_hash TEXT PRIMARY KEY, chat_id TEXT NOT NULL, expires_at INTEGER NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS api_access_tokens (token_hash TEXT PRIMARY KEY, chat_id TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL)"
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

    def create_api_pair_code(self, chat_id: str, ttl_seconds: int = 300) -> str:
        code = secrets.token_urlsafe(8)
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        now = int(time.time())
        connection = self._connect()
        try:
            with connection:
                connection.execute("DELETE FROM api_pair_codes WHERE expires_at < ?", (now,))
                connection.execute(
                    "INSERT INTO api_pair_codes(code_hash,chat_id,expires_at) VALUES(?,?,?)",
                    (code_hash, str(chat_id), now + ttl_seconds),
                )
            return code
        finally:
            connection.close()

    def exchange_api_pair_code(self, code: str) -> tuple[str, str] | None:
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        now = int(time.time())
        token = secrets.token_urlsafe(32)
        connection = self._connect()
        try:
            with connection:
                row = connection.execute(
                    "SELECT chat_id FROM api_pair_codes WHERE code_hash=? AND expires_at>=?",
                    (code_hash, now),
                ).fetchone()
                if row is None:
                    return None
                chat_id = str(row[0])
                connection.execute("DELETE FROM api_pair_codes WHERE code_hash=?", (code_hash,))
                connection.execute(
                    "INSERT INTO api_access_tokens(token_hash,chat_id,created_at,expires_at) VALUES(?,?,?,?)",
                    (hashlib.sha256(token.encode()).hexdigest(), chat_id, now, now + 90 * 86400),
                )
                return chat_id, token
        finally:
            connection.close()

    def authenticate_api_token(self, token: str) -> str | None:
        digest = hashlib.sha256(token.encode()).hexdigest()
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT chat_id FROM api_access_tokens WHERE token_hash=? AND expires_at>=?",
                (digest, int(time.time())),
            ).fetchone()
            return str(row[0]) if row else None
        finally:
            connection.close()

    def save_media_choices(self, chat_id: str, media: dict, ttl_seconds: int = 1800) -> str:
        token = secrets.token_urlsafe(8)
        now = int(time.time())
        connection = self._connect()
        try:
            with connection:
                connection.execute("DELETE FROM media_choices WHERE expires_at < ? OR consumed = 1", (now,))
                connection.execute(
                    "INSERT INTO media_choices(token,chat_id,media_json,expires_at,consumed,status,progress,status_text) "
                    "VALUES(?,?,?,?,0,'chooser_ready',0,'')",
                    (token, str(chat_id), json.dumps(media, separators=(",", ":")), now + ttl_seconds),
                )
            return token
        finally:
            connection.close()

    def get_media_choices(self, token: str, chat_id: str) -> dict | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT media_json FROM media_choices WHERE token=? AND chat_id=? AND expires_at>=?",
                (token, str(chat_id), int(time.time())),
            ).fetchone()
            return json.loads(row[0]) if row else None
        finally:
            connection.close()

    def media_job_status(self, token: str, chat_id: str) -> dict | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT status,progress,status_text,expires_at FROM media_choices "
                "WHERE token=? AND chat_id=? AND expires_at>=?",
                (token, str(chat_id), int(time.time())),
            ).fetchone()
            if row is None:
                return None
            return {"status": row[0], "progress": row[1], "status_text": row[2], "expires_at": row[3]}
        finally:
            connection.close()

    def set_media_job_status(self, token: str, status: str, progress: int = 0, text: str = "") -> None:
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    "UPDATE media_choices SET status=?,progress=?,status_text=? WHERE token=?",
                    (str(status)[:40], max(0, min(100, int(progress))), str(text)[:120], token),
                )
        finally:
            connection.close()

    def consume_media_choice(self, token: str, chat_id: str, choice_index: int) -> tuple[dict, dict] | None:
        now = int(time.time())
        connection = self._connect()
        try:
            with connection:
                row = connection.execute(
                    "SELECT media_json FROM media_choices WHERE token=? AND chat_id=? "
                    "AND expires_at>=? AND consumed=0",
                    (token, str(chat_id), now),
                ).fetchone()
                if row is None:
                    return None
                media = json.loads(row[0])
                choices = media.get("choices", [])
                if not isinstance(choice_index, int) or not 0 <= choice_index < len(choices):
                    return None
                updated = connection.execute(
                    "UPDATE media_choices SET consumed=1,status='queued',progress=0,status_text='Queued' "
                    "WHERE token=? AND chat_id=? AND consumed=0",
                    (token, str(chat_id)),
                )
                if updated.rowcount != 1:
                    return None
                return media, choices[choice_index]
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

    async def send_message(self, chat_id: str, text: str, reply_markup: dict | None = None):
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self.call("sendMessage", payload)

    async def edit_message_text(self, chat_id: str, message_id: int, text: str,
                                reply_markup: dict | None = None):
        payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self.call("editMessageText", payload)

    async def answer_callback_query(self, callback_query_id: str, text: str = "") -> None:
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text[:180]
        await self.call("answerCallbackQuery", payload)

    async def send_photo_url(self, chat_id: str, photo_url: str, caption: str = ""):
        return await self.call("sendPhoto", {
            "chat_id": chat_id, "photo": photo_url, "caption": caption[:900],
        })

    async def send_media(self, chat_id: str, path: Path, mode: str) -> None:
        if path.suffix.lower() == ".mp4":
            method, field = "sendVideo", "video"
            extra = {"supports_streaming": True}
        elif path.suffix.lower() == ".mp3":
            method, field, extra = "sendAudio", "audio", {}
        else:
            method, field, extra = "sendDocument", "document", {}
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        upload_timeout = httpx.Timeout(240.0, connect=20.0)
        with path.open("rb") as media_file:
            await self.call(
                method,
                {"chat_id": chat_id, "caption": path.name[:900], **extra},
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


def _download_media(
    url: str,
    work_dir: Path,
    mode: str,
    max_bytes: int,
    format_selector: str | None = None,
    audio_quality: int = 192,
    progress_conn=None,
) -> tuple[Path, str]:
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ImportError as error:
        raise RuntimeError("yt-dlp is not installed") from error

    options = {
        "format": format_selector or ("bestaudio/best" if mode == "audio" else "bestvideo*+bestaudio/best"),
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
                "preferredquality": str(audio_quality),
            }
        ]
    if progress_conn is not None:
        def progress_hook(status):
            try:
                progress_conn.send((
                    "progress",
                    str(status.get("status") or "downloading"),
                    int(status.get("downloaded_bytes") or 0),
                    int(status.get("total_bytes") or status.get("total_bytes_estimate") or 0),
                ))
            except (BrokenPipeError, EOFError, OSError):
                pass
        options["progress_hooks"] = [progress_hook]

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
        raise MediaResolutionError(classify_extraction_error(error)) from None

    size = media_path.stat().st_size
    if size > max_bytes:
        raise MediaTooLargeError(size, max_bytes)
    return media_path, str(info.get("title") or media_path.name)


def _download_process_entry(
    send_conn,
    url: str,
    work_dir: str,
    mode: str,
    max_bytes: int,
    format_selector: str | None = None,
    audio_quality: int = 192,
) -> None:
    try:
        path, title = _download_media(
            url, Path(work_dir), mode, max_bytes, format_selector, audio_quality, send_conn
        )
        send_conn.send(("ok", str(path), title))
    except MediaTooLargeError as error:
        send_conn.send(("too_large", error.size_bytes, error.limit_bytes))
    except MediaResolutionError as error:
        send_conn.send(("media_error", error.code))
    except BaseException as error:
        send_conn.send(("error", type(error).__name__))
    finally:
        send_conn.close()


class DownloadTimeoutError(TimeoutError):
    pass


async def _download_with_deadline(
    url: str,
    work_dir: Path,
    mode: str,
    max_bytes: int,
    format_selector: str | None = None,
    audio_quality: int = 192,
    progress_callback=None,
) -> tuple[Path, str]:
    """Run yt-dlp in a killable process; coroutine cancellation cannot orphan the downloader."""
    context = multiprocessing.get_context("spawn")
    receive_conn, send_conn = context.Pipe(duplex=False)
    process = context.Process(
        target=_download_process_entry,
        args=(send_conn, url, str(work_dir), mode, max_bytes, format_selector, audio_quality),
        daemon=True,
    )
    process.start()
    send_conn.close()
    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + DOWNLOAD_TIMEOUT_SECONDS
        result = None
        last_progress_time = 0.0
        last_percent = -1
        while process.is_alive() or receive_conn.poll():
            while receive_conn.poll():
                item = receive_conn.recv()
                if item and item[0] == "progress":
                    _kind, status, downloaded, total = item
                    percent = min(100, int(downloaded * 100 / total)) if total else None
                    now = loop.time()
                    if progress_callback and (
                        now - last_progress_time >= 3 or (percent is not None and percent >= last_percent + 5)
                        or status == "finished"
                    ):
                        await progress_callback(status, downloaded, total, percent)
                        last_progress_time = now
                        if percent is not None:
                            last_percent = percent
                else:
                    result = item
            if loop.time() >= deadline and process.is_alive():
                process.terminate()
                await asyncio.to_thread(process.join, 5)
                if process.is_alive():
                    process.kill()
                    await asyncio.to_thread(process.join)
                raise DownloadTimeoutError("Media download exceeded its time limit")
            if process.is_alive():
                await asyncio.sleep(0.1)
            else:
                break
        process.join()
        if result is None:
            raise RuntimeError("Media downloader exited without a result")
        if result[0] == "ok":
            return Path(result[1]), result[2]
        if result[0] == "too_large":
            raise MediaTooLargeError(result[1], result[2])
        if result[0] == "media_error":
            raise MediaResolutionError(result[1])
        raise RuntimeError("Media download failed")
    except asyncio.CancelledError:
        if process.is_alive():
            process.terminate()
            await asyncio.to_thread(process.join, 5)
            if process.is_alive():
                process.kill()
                await asyncio.to_thread(process.join)
        raise
    finally:
        receive_conn.close()


def _resolve_process_entry(send_conn, url: str) -> None:
    try:
        from media_catalog import resolve_media
        send_conn.send(("ok", resolve_media(url)))
    except BaseException as error:
        send_conn.send(("media_error", classify_extraction_error(error)))
    finally:
        send_conn.close()


async def _resolve_media_with_deadline(url: str, timeout_seconds: int = 90) -> dict:
    context = multiprocessing.get_context("spawn")
    receive_conn, send_conn = context.Pipe(duplex=False)
    process = context.Process(target=_resolve_process_entry, args=(send_conn, url), daemon=True)
    process.start()
    send_conn.close()
    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        result = None
        while process.is_alive() or receive_conn.poll():
            while receive_conn.poll():
                result = receive_conn.recv()
            if loop.time() >= deadline and process.is_alive():
                process.terminate()
                await asyncio.to_thread(process.join, 5)
                if process.is_alive():
                    process.kill()
                    await asyncio.to_thread(process.join)
                raise DownloadTimeoutError("Metadata lookup exceeded its time limit")
            if process.is_alive():
                await asyncio.sleep(0.1)
            else:
                break
        process.join()
        if result is None:
            raise MediaResolutionError("temporary")
        if result[0] == "media_error":
            raise MediaResolutionError(result[1])
        if result[0] != "ok":
            raise MediaResolutionError("temporary")
        return result[1]
    except asyncio.CancelledError:
        if process.is_alive():
            process.terminate()
            await asyncio.to_thread(process.join, 5)
            if process.is_alive():
                process.kill()
                await asyncio.to_thread(process.join)
        raise
    finally:
        receive_conn.close()


def _segment_process_entry(send_conn, input_path: str, output_dir: str, mode: str,
                          profile: str, max_bytes: int, audio_bitrate: int) -> None:
    try:
        from media_segments import install_termination_handler, split_media
        install_termination_handler()
        outputs = split_media(
            input_path, output_dir, mode=mode, profile=profile,
            max_bytes=max_bytes, audio_bitrate=audio_bitrate,
        )
        send_conn.send(("ok", [str(path) for path in outputs]))
    except BaseException as error:
        send_conn.send(("error", type(error).__name__))
    finally:
        send_conn.close()


async def _split_media_with_deadline(
    input_path: Path,
    output_dir: Path,
    mode: str,
    profile: str,
    max_bytes: int,
    audio_bitrate: int = 192,
    timeout_seconds: int = 600,
) -> list[Path]:
    context = multiprocessing.get_context("spawn")
    receive_conn, send_conn = context.Pipe(duplex=False)
    process = context.Process(
        target=_segment_process_entry,
        args=(send_conn, str(input_path), str(output_dir), mode, profile, max_bytes, audio_bitrate),
        daemon=True,
    )
    process.start()
    send_conn.close()
    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        result = None
        while process.is_alive() or receive_conn.poll():
            while receive_conn.poll():
                result = receive_conn.recv()
            if loop.time() >= deadline and process.is_alive():
                process.terminate()
                await asyncio.to_thread(process.join, 5)
                if process.is_alive():
                    process.kill()
                    await asyncio.to_thread(process.join)
                raise DownloadTimeoutError("Media encoding exceeded its time limit")
            if process.is_alive():
                await asyncio.sleep(0.2)
            else:
                break
        process.join()
        if result is None or result[0] != "ok":
            raise RuntimeError("Playable media encoding failed")
        return [Path(path) for path in result[1]]
    except asyncio.CancelledError:
        if process.is_alive():
            process.terminate()
            await asyncio.to_thread(process.join, 5)
            if process.is_alive():
                process.kill()
                await asyncio.to_thread(process.join)
        raise
    finally:
        receive_conn.close()


class K2TelegramBot:
    def __init__(self, config: Config, state: BotState, api: TelegramApi):
        self.config = config
        self.state = state
        self.api = api
        self._download_lock = asyncio.Lock()
        self._background_downloads: set[asyncio.Task] = set()

    def has_active_download(self) -> bool:
        return any(not task.done() for task in self._background_downloads)

    def start_background_download(self, chat_id: str, token: str, media: dict, choice: dict):
        if self.has_active_download():
            return None
        task = asyncio.create_task(
            self._download_and_send(chat_id, token, media, choice),
            name=f"k2app-media-{token}",
        )
        self._background_downloads.add(task)
        task.add_done_callback(self._background_downloads.discard)
        return task

    @staticmethod
    def _keyboard(token: str, choices: list[dict]) -> dict:
        buttons = [
            {"text": str(choice.get("label") or "Download")[:60],
             "callback_data": f"k2:{token}:{index}"}
            for index, choice in enumerate(choices)
        ]
        rows = [buttons[index:index + 2] for index in range(0, len(buttons), 2)]
        return {"inline_keyboard": rows}

    @staticmethod
    def _duration_text(seconds: int | None) -> str:
        if not seconds or seconds < 0:
            return "duration unknown"
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"

    @staticmethod
    def _progress_bar(percent: int | None) -> str:
        if percent is None:
            return "[----------]"
        filled = max(0, min(10, int(percent) // 10))
        return "[" + "#" * filled + "-" * (10 - filled) + "]"

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
            if payload.startswith("dl_") and re.fullmatch(r"dl_[A-Za-z0-9_-]{1,32}", payload):
                token = payload[3:]
                media = self.state.get_media_choices(token, chat_id)
                if media is None:
                    await self.api.send_message(chat_id, "This chooser link has expired. Send the URL again to get a fresh one.")
                else:
                    await self._present_chooser(chat_id, token, media)
                return
            await self.api.send_message(
                chat_id,
                "K2App bot is ready. Send a public media URL and choose MP4 resolution, MP3 bitrate, or thumbnail.\n\n"
                "Commands: /video URL, /audio URL, /pair, /help. Large videos are re-encoded into separate playable MP4 segments "
                "under 48 MB each; they are not raw binary chunks.",
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
                "Send a public media URL to open the format chooser, or use /video URL or /audio URL to narrow it. "
                "Use /pair to connect the future K2App Lite client with a one-use 5-minute code. "
                "The bot uses yt-dlp-supported sites; login-only or DRM-protected media is not supported. "
                f"Downloads are limited to {self.config.max_download_bytes // 1_000_000} MB. Oversized media is encoded "
                "as ordered, independently playable MP4 or MP3 segments under 48 MB each. Processing may take longer "
                "for large files on the free hosting service.",
            )
            return
        if command == "status":
            await self.api.send_message(chat_id, "K2App Telegram downloader is running and ready.")
            return
        if command == "pair":
            code = self.state.create_api_pair_code(chat_id)
            await self.api.send_message(
                chat_id,
                f"K2App Lite pairing code: {code}\nEnter it in the Lite app within 5 minutes. It can be used once.",
            )
            return
        if command not in {None, "video", "audio", "download"}:
            await self.api.send_message(chat_id, "Unknown command. Send /help for usage.")
            return

        mode_filter = "audio" if command == "audio" else ("video" if command == "video" else None)
        urls = extract_urls(payload if command else text)
        if not urls:
            await self.api.send_message(chat_id, "I couldn't find a public http(s) media URL. Send /help for usage.")
            return

        for url in urls:
            await self._show_chooser(chat_id, url, mode_filter)

    async def _show_chooser(self, chat_id: str, url: str, mode_filter: str | None = None) -> str | None:
        initial = await self.api.send_message(chat_id, "Checking this link and finding available formats…")
        message_id = initial.get("message_id") if isinstance(initial, dict) else None
        try:
            from media_catalog import resolve_media
            media = await _resolve_media_with_deadline(url)
            media["url"] = url
            if mode_filter == "audio":
                media["choices"] = [choice for choice in media["choices"] if choice["kind"] == "audio"]
            elif mode_filter == "video":
                media["choices"] = [choice for choice in media["choices"] if choice["kind"] in {"video", "thumbnail"}]
            if not media["choices"]:
                raise RuntimeError("No formats are available for this selection")
            token = self.state.save_media_choices(chat_id, media)
            await self._present_chooser(chat_id, token, media, message_id=message_id)
            return token
        except Exception as error:
            LOGGER.warning("Media metadata lookup failed (error_type=%s)", type(error).__name__)
            text = "I couldn't inspect this link. It may be unsupported, private, login-protected, DRM-protected, or temporarily unavailable."
            if message_id:
                try:
                    await self.api.edit_message_text(chat_id, message_id, text)
                except Exception:
                    await self.api.send_message(chat_id, text)
            else:
                await self.api.send_message(chat_id, text)
            return None

    async def _present_chooser(self, chat_id: str, token: str, media: dict, message_id: int | None = None) -> None:
        title = str(media.get("title") or "Media")[:180]
        duration = self._duration_text(media.get("duration_seconds"))
        text = f"Choose a format and quality for: {title}\nDuration: {duration}\nOptions expire in 30 minutes."
        keyboard = self._keyboard(token, media.get("choices") or [])
        if message_id:
            await self.api.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
        else:
            await self.api.send_message(chat_id, text, reply_markup=keyboard)
        thumbnail = media.get("thumbnail_url")
        if isinstance(thumbnail, str) and thumbnail.startswith("https://"):
            try:
                await self.api.send_photo_url(chat_id, thumbnail, f"Preview: {title}")
            except Exception as error:
                LOGGER.info("Preview image unavailable (error_type=%s)", type(error).__name__)

    async def handle_callback_query(self, query: dict) -> None:
        callback_id = str(query.get("id") or "")
        data = str(query.get("data") or "")
        message = query.get("message") if isinstance(query.get("message"), dict) else {}
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id") or "")
        owner = self.state.owner_chat_id()
        match = re.fullmatch(r"k2:([A-Za-z0-9_-]{1,32}):([0-9]{1,2})", data)
        if chat.get("type") != "private" or not chat_id or chat_id != owner or not match:
            if callback_id:
                await self.api.answer_callback_query(callback_id, "This button is invalid or belongs to another chat.")
            return
        token, choice_index = match.group(1), int(match.group(2))
        if self.has_active_download():
            if callback_id:
                await self.api.answer_callback_query(callback_id, "One media job is already running. Please wait, then tap again.")
            return
        selected = self.state.consume_media_choice(token, chat_id, choice_index)
        if selected is None:
            if callback_id:
                await self.api.answer_callback_query(callback_id, "This chooser expired or was already used.")
            return
        media, choice = selected
        if choice.get("kind") == "thumbnail":
            if callback_id:
                await self.api.answer_callback_query(callback_id, "Sending thumbnail…")
            thumb = media.get("thumbnail_url")
            try:
                if not isinstance(thumb, str):
                    raise ValueError("Thumbnail URL unavailable")
                await self.api.send_photo_url(chat_id, thumb, f"Thumbnail: {str(media.get('title') or 'Media')[:160]}")
                self.state.set_media_job_status(token, "done", 100, "Thumbnail sent")
            except Exception as error:
                self.state.set_media_job_status(token, "failed", 0, "Thumbnail delivery failed")
                LOGGER.info("Thumbnail delivery failed (error_type=%s)", type(error).__name__)
                await self.api.send_message(chat_id, "Could not send the thumbnail. Please resend the link to try again.")
            return
        task = self.start_background_download(chat_id, token, media, choice)
        if callback_id:
            await self.api.answer_callback_query(callback_id, "Starting your selection…")
        if task is None:
            self.state.set_media_job_status(token, "failed", 0, "Another media job is active")
            await self.api.send_message(chat_id, "One media job is already running. Please try again after it completes.")

    async def _download_and_send(self, chat_id: str, token: str, media: dict, choice: dict) -> None:
        async with self._download_lock:
            await self._download_and_send_locked(chat_id, token, media, choice)

    async def _download_and_send_locked(self, chat_id: str, token: str, media: dict, choice: dict) -> None:
        kind = str(choice.get("kind") or "video")
        mode = "audio" if kind == "audio" else "video"
        title = str(media.get("title") or "Media")[:180]
        label = str(choice.get("label") or mode.upper())
        progress_message = await self.api.send_message(chat_id, f"Starting {label}: {title}")
        message_id = progress_message.get("message_id") if isinstance(progress_message, dict) else None
        self.state.set_media_job_status(token, "downloading", 0, "Downloading")

        async def report_progress(status: str, downloaded: int, total: int, percent: int | None) -> None:
            if percent is not None:
                job_progress = min(70, int(percent * 0.7))
                progress_text = f"Downloading {label}\n{self._progress_bar(percent)} {percent}%"
            else:
                job_progress = 0
                progress_text = f"Downloading {label}\n{downloaded / 1_000_000:.1f} MB received"
            self.state.set_media_job_status(token, "downloading", job_progress, "Downloading")
            if message_id:
                try:
                    await self.api.edit_message_text(chat_id, message_id, progress_text)
                except Exception:
                    pass

        try:
            with tempfile.TemporaryDirectory(prefix="k2app-telegram-") as directory:
                work_dir = Path(directory)
                media_path, downloaded_title = await _download_with_deadline(
                    str(media["url"]), work_dir, mode, self.config.max_download_bytes,
                    str(choice.get("format_selector") or "bestvideo*+bestaudio/best"),
                    int(choice.get("audio_quality") or 192), report_progress,
                )
                self.state.set_media_job_status(token, "preparing", 75, "Preparing playable segments")
                if message_id:
                    try:
                        await self.api.edit_message_text(chat_id, message_id, "Preparing independently playable media segments…")
                    except Exception:
                        pass
                height = int(choice.get("height") or 720)
                profile = "1080p" if height >= 1080 else "720p" if height >= 720 else "480p" if height >= 480 else "360p"
                max_segment_bytes = min(self.config.max_upload_bytes, 48_000_000)
                parts = await _split_media_with_deadline(
                    media_path, work_dir, mode, profile, max_segment_bytes,
                    int(choice.get("audio_quality") or 192),
                )
                if len(parts) == 1:
                    ready = parts[0].with_name(parts[0].stem.rsplit(".part", 1)[0] + "-ready" + parts[0].suffix)
                    parts[0].rename(ready)
                    parts = [ready]
                if len(parts) > 1:
                    await self.api.send_message(
                        chat_id,
                        f"Prepared {len(parts)} independently playable {'.mp3' if mode == 'audio' else '.mp4'} segments. "
                        "Each is below 48 MB; these are trimmed/encoded media files, not raw binary pieces.",
                    )
                for index, part in enumerate(parts, start=1):
                    upload_progress = 75 + int(25 * index / len(parts))
                    self.state.set_media_job_status(token, "uploading", upload_progress, f"Uploading {index}/{len(parts)}")
                    if message_id:
                        try:
                            await self.api.edit_message_text(
                                chat_id, message_id, f"Uploading playable segment {index}/{len(parts)}\n"
                                f"{self._progress_bar(upload_progress)} {upload_progress}%",
                            )
                        except Exception:
                            pass
                    await self.api.send_media(chat_id, part, mode)
            self.state.set_media_job_status(token, "done", 100, "Complete")
            if message_id:
                try:
                    await self.api.edit_message_text(chat_id, message_id, f"Complete: {downloaded_title[:180]}")
                except Exception:
                    pass
            else:
                await self.api.send_message(chat_id, f"Sent: {downloaded_title[:180]}")
        except MediaTooLargeError as error:
            self.state.set_media_job_status(token, "failed", 0, "Download limit exceeded")
            actual = f" ({error.size_bytes / 1_000_000:.1f} MB)" if error.size_bytes else ""
            await self.api.send_message(chat_id, f"The file{actual} exceeds the configured {error.limit_bytes // 1_000_000} MB download limit. Try a smaller quality.")
        except DownloadTimeoutError:
            self.state.set_media_job_status(token, "failed", 0, "Processing timed out")
            await self.api.send_message(chat_id, "Processing took too long for the current free server. Try a lower resolution or shorter video.")
        except TelegramApiError as error:
            self.state.set_media_job_status(token, "failed", 0, "Telegram upload failed")
            LOGGER.warning("Telegram send failed (code=%s)", error.error_code)
            await self.api.send_message(chat_id, "Telegram could not accept this file. Try a lower resolution or shorter segment.")
        except Exception as error:
            self.state.set_media_job_status(token, "failed", 0, "Media processing failed")
            LOGGER.warning("Media processing failed (error_type=%s)", type(error).__name__)
            await self.api.send_message(chat_id, "I couldn't finish this media conversion. Try a lower resolution or a shorter source.")


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
                    {"offset": offset, "timeout": 30, "allowed_updates": ["message", "callback_query"]},
                    timeout=httpx.Timeout(45.0, connect=20.0),
                )
                for update in updates or []:
                    update_id = int(update.get("update_id", offset))
                    try:
                        message = update.get("message")
                        if isinstance(message, dict):
                            await bot.handle_message(message)
                        callback_query = update.get("callback_query")
                        if isinstance(callback_query, dict):
                            await bot.handle_callback_query(callback_query)
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
