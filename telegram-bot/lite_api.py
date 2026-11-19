"""Direct K2App Lite API: anonymous device sessions and private server-to-device downloads.

The Telegram bot remains a separate interface. This module never sends Lite media
results to Telegram and keeps Lite session/job state in its own SQLite database.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import mimetypes
import multiprocessing
import os
import re
import secrets
import shutil
import sqlite3
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse

from bot import (
    Config,
    DownloadTimeoutError,
    MediaResolutionError,
    MediaTooLargeError,
    _download_with_deadline,
    _public_dns_only,
    _resolve_media_with_deadline,
    _split_media_with_deadline,
    is_safe_http_url,
)

LOGGER = logging.getLogger("k2app.lite_api")
router = APIRouter(prefix="/api/v1")

REQUEST_MAX_BYTES = 8192
SESSION_TTL_SECONDS = 90 * 86400
JOB_TTL_SECONDS = 6 * 3600
SESSION_CREATIONS_PER_HOUR = 100
JOBS_PER_SESSION_PER_HOUR = 5
MAX_LIVE_JOBS = 50
MAX_RESULT_BYTES = 300_000_000
MAX_THUMBNAIL_BYTES = 8_000_000
JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{12,32}$")
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{40,100}$")
ALLOWED_MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _release_job_reservation(app, job_id: str) -> None:
    if getattr(app.state, "api_job_reserved_job", None) == job_id:
        app.state.api_job_reserved = False
        app.state.api_job_reserved_job = None


class LiteResultTooLargeError(RuntimeError):
    pass


class _HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        absolute = urljoin(req.full_url, newurl)
        if urlsplit(absolute).scheme.lower() != "https" or not is_safe_http_url(absolute):
            raise urllib.error.URLError("Blocked unsafe thumbnail redirect")
        return super().redirect_request(req, fp, code, msg, headers, absolute)


class LiteApiStore:
    """SQLite-backed Lite identities and jobs, isolated from Telegram chat state."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS lite_sessions ("
                "token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS lite_sessions_user ON lite_sessions(user_id)")
            db.execute("CREATE TABLE IF NOT EXISTS lite_session_issuance (created_at INTEGER NOT NULL)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS lite_job_events (user_id TEXT NOT NULL, created_at INTEGER NOT NULL)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS lite_job_events_user ON lite_job_events(user_id,created_at)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS lite_jobs ("
                "job_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, source_url TEXT, media_json TEXT NOT NULL, "
                "choice_json TEXT, status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0, "
                "status_text TEXT NOT NULL DEFAULT '', files_json TEXT NOT NULL DEFAULT '[]', "
                "created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS lite_jobs_user ON lite_jobs(user_id,created_at)")
            db.execute("CREATE INDEX IF NOT EXISTS lite_jobs_expiry ON lite_jobs(expires_at)")

    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = 10000")
        return db

    def create_session(self) -> tuple[str, int] | None:
        now = int(time.time())
        expires_at = now + SESSION_TTL_SECONDS
        token = secrets.token_urlsafe(32)
        user_id = secrets.token_urlsafe(18)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM lite_session_issuance WHERE created_at < ?", (now - 3600,))
            count = db.execute("SELECT COUNT(*) FROM lite_session_issuance").fetchone()[0]
            if count >= SESSION_CREATIONS_PER_HOUR:
                return None
            db.execute(
                "INSERT INTO lite_sessions(token_hash,user_id,created_at,expires_at) VALUES(?,?,?,?)",
                (token_hash, user_id, now, expires_at),
            )
            db.execute("INSERT INTO lite_session_issuance(created_at) VALUES(?)", (now,))
        return token, expires_at

    def authenticate(self, token: str) -> str | None:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = int(time.time())
        with self._connect() as db:
            row = db.execute(
                "SELECT user_id,expires_at FROM lite_sessions WHERE token_hash=?", (digest,)
            ).fetchone()
            if row is None:
                return None
            if int(row["expires_at"]) <= now:
                db.execute("DELETE FROM lite_sessions WHERE token_hash=?", (digest,))
                return None
            return str(row["user_id"])

    def revoke(self, token: str) -> tuple[str, list[str]] | None:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            session = db.execute("SELECT user_id FROM lite_sessions WHERE token_hash=?", (digest,)).fetchone()
            if session is None:
                return None
            user_id = str(session["user_id"])
            jobs = [str(row["job_id"]) for row in db.execute(
                "SELECT job_id FROM lite_jobs WHERE user_id=?", (user_id,)
            ).fetchall()]
            db.execute("DELETE FROM lite_sessions WHERE token_hash=?", (digest,))
            db.execute("DELETE FROM lite_jobs WHERE user_id=?", (user_id,))
            db.execute("DELETE FROM lite_job_events WHERE user_id=?", (user_id,))
            return user_id, jobs

    def record_job_attempt(self, user_id: str) -> str | None:
        """Reserve analysis quota before network metadata lookup; return a reason if blocked."""
        now = int(time.time())
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM lite_job_events WHERE created_at < ?", (now - 86400,))
            user_count = db.execute(
                "SELECT COUNT(*) FROM lite_job_events WHERE user_id=? AND created_at>=?",
                (user_id, now - 3600),
            ).fetchone()[0]
            if user_count >= JOBS_PER_SESSION_PER_HOUR:
                return "rate_limited"
            live_count = db.execute(
                "SELECT COUNT(*) FROM lite_jobs WHERE expires_at>=?", (now,)
            ).fetchone()[0]
            if live_count >= MAX_LIVE_JOBS:
                return "service_busy"
            db.execute("INSERT INTO lite_job_events(user_id,created_at) VALUES(?,?)", (user_id, now))
        return None

    def create_job(self, user_id: str, source_url: str, media: dict[str, Any]) -> tuple[str, int]:
        now = int(time.time())
        job_id = secrets.token_urlsafe(12)
        expires_at = now + JOB_TTL_SECONDS
        safe_media = {
            "title": str(media.get("title") or "Media")[:200],
            "duration_seconds": media.get("duration_seconds"),
            "thumbnail_url": media.get("thumbnail_url"),
            "extractor": str(media.get("extractor") or "")[:80],
            "choices": media.get("choices") if isinstance(media.get("choices"), list) else [],
        }
        with self._connect() as db:
            db.execute(
                "INSERT INTO lite_jobs(job_id,user_id,source_url,media_json,status,progress,status_text,created_at,expires_at) "
                "VALUES(?,?,?,?, 'chooser_ready',0,'Choose a format',?,?)",
                (job_id, user_id, source_url, json.dumps(safe_media, separators=(",", ":")), now, expires_at),
            )
        return job_id, expires_at

    def get_job(self, job_id: str, user_id: str) -> dict[str, Any] | None:
        now = int(time.time())
        with self._connect() as db:
            row = db.execute(
                "SELECT job_id,status,progress,status_text,media_json,files_json,expires_at "
                "FROM lite_jobs WHERE job_id=? AND user_id=? AND expires_at>=?",
                (job_id, user_id, now),
            ).fetchone()
        if row is None:
            return None
        media = json.loads(row["media_json"])
        stored_files = json.loads(row["files_json"] or "[]")
        files = []
        for index, item in enumerate(stored_files):
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or Path(name).name != name:
                continue
            files.append({
                "index": index,
                "name": name,
                "size_bytes": max(0, int(item.get("size_bytes") or 0)),
                "mime_type": str(item.get("mime_type") or "application/octet-stream"),
                "download_url": f"/api/v1/jobs/{job_id}/files/{index}",
            })
        return {
            "job_id": str(row["job_id"]),
            "status": str(row["status"]),
            "progress": max(0, min(100, int(row["progress"]))),
            "status_text": str(row["status_text"] or ""),
            "media": {
                "title": media.get("title"),
                "duration_seconds": media.get("duration_seconds"),
                "thumbnail_url": media.get("thumbnail_url"),
            },
            "choices": media.get("choices", []),
            "files": files,
            "expires_in_seconds": max(0, int(row["expires_at"]) - now),
        }

    def consume_choice(self, job_id: str, user_id: str, choice_index: int) -> dict[str, Any] | None:
        now = int(time.time())
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT source_url,media_json,status FROM lite_jobs "
                "WHERE job_id=? AND user_id=? AND expires_at>=?",
                (job_id, user_id, now),
            ).fetchone()
            if row is None or row["status"] != "chooser_ready":
                return None
            media = json.loads(row["media_json"])
            choices = media.get("choices")
            if not isinstance(choices, list) or not 0 <= choice_index < len(choices):
                return None
            choice = choices[choice_index]
            if not isinstance(choice, dict) or choice.get("kind") not in {"video", "audio", "thumbnail"}:
                return None
            cursor = db.execute(
                "UPDATE lite_jobs SET choice_json=?,status='queued',progress=0,status_text='Waiting for the server worker' "
                "WHERE job_id=? AND user_id=? AND status='chooser_ready'",
                (json.dumps(choice, separators=(",", ":")), job_id, user_id),
            )
            if cursor.rowcount != 1:
                return None
            return {
                "source_url": str(row["source_url"] or ""),
                "media": media,
                "choice": choice,
            }

    def set_job_status(
        self,
        job_id: str,
        user_id: str,
        status: str,
        progress: int,
        status_text: str,
        files: list[dict[str, Any]] | None = None,
    ) -> None:
        progress = max(0, min(100, int(progress)))
        final = status in {"done", "failed"}
        with self._connect() as db:
            if files is None:
                db.execute(
                    "UPDATE lite_jobs SET status=?,progress=?,status_text=?,source_url=CASE WHEN ? THEN NULL ELSE source_url END "
                    "WHERE job_id=? AND user_id=?",
                    (status, progress, status_text[:200], int(final), job_id, user_id),
                )
            else:
                db.execute(
                    "UPDATE lite_jobs SET status=?,progress=?,status_text=?,files_json=?,source_url=NULL "
                    "WHERE job_id=? AND user_id=?",
                    (status, progress, status_text[:200], json.dumps(files, separators=(",", ":")), job_id, user_id),
                )

    def get_file(
        self, job_id: str, user_id: str, file_index: int, output_dir: Path
    ) -> tuple[str, str, Path] | None:
        now = int(time.time())
        with self._connect() as db:
            row = db.execute(
                "SELECT status,files_json,expires_at FROM lite_jobs WHERE job_id=? AND user_id=?",
                (job_id, user_id),
            ).fetchone()
        if row is None or int(row["expires_at"]) <= now or row["status"] != "done":
            return None
        try:
            files = json.loads(row["files_json"] or "[]")
            item = files[file_index]
            name = str(item["name"])
            mime_type = str(item["mime_type"])
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,150}", name) or Path(name).name != name:
            return None
        root = Path(output_dir).resolve()
        path = root / job_id / name
        job_dir = (root / job_id).resolve()
        resolved = path.resolve()
        if resolved.parent != job_dir or not resolved.is_file():
            return None
        return name, mime_type, resolved

    def delete_job(self, job_id: str, user_id: str) -> str | None:
        now = int(time.time())
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status FROM lite_jobs WHERE job_id=? AND user_id=? AND expires_at>=?",
                (job_id, user_id, now),
            ).fetchone()
            if row is None:
                return None
            if row["status"] in {"queued", "downloading", "preparing"}:
                return "active"
            db.execute("DELETE FROM lite_jobs WHERE job_id=? AND user_id=?", (job_id, user_id))
        return "deleted"

    def recover_interrupted(self, output_dir: Path) -> None:
        output_dir = Path(output_dir)
        with self._connect() as db:
            rows = db.execute(
                "SELECT job_id FROM lite_jobs WHERE status IN ('queued','downloading','preparing')"
            ).fetchall()
            db.execute(
                "UPDATE lite_jobs SET status='failed',progress=0,status_text='Server restarted; start a new download',source_url=NULL "
                "WHERE status IN ('queued','downloading','preparing')"
            )
        for row in rows:
            shutil.rmtree(output_dir / str(row["job_id"]), ignore_errors=True)

    def cleanup_expired(self, output_dir: Path) -> None:
        now = int(time.time())
        output_dir = Path(output_dir)
        with self._connect() as db:
            rows = db.execute("SELECT job_id FROM lite_jobs WHERE expires_at<?", (now,)).fetchall()
            db.execute("DELETE FROM lite_jobs WHERE expires_at<?", (now,))
            db.execute("DELETE FROM lite_sessions WHERE expires_at<?", (now,))
            db.execute("DELETE FROM lite_session_issuance WHERE created_at<?", (now - 3600,))
            db.execute("DELETE FROM lite_job_events WHERE created_at<?", (now - 86400,))
        for row in rows:
            shutil.rmtree(output_dir / str(row["job_id"]), ignore_errors=True)


async def cleanup_loop(store: LiteApiStore, output_dir: Path, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.to_thread(store.cleanup_expired, output_dir)
        except Exception as error:
            LOGGER.warning("Lite cleanup failed (error_type=%s)", type(error).__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=300)
        except asyncio.TimeoutError:
            pass


def _get_store(request: Request) -> LiteApiStore:
    store = getattr(request.app.state, "lite_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Lite API is not ready")
    return store


def _bearer_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    supplied = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
    if not TOKEN_PATTERN.fullmatch(supplied):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return supplied


def _require_session(request: Request) -> str:
    token = _bearer_token(request)
    user_id = _get_store(request).authenticate(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_id


async def _read_json(request: Request) -> dict[str, Any]:
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > REQUEST_MAX_BYTES:
                raise HTTPException(status_code=413, detail="Request too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid content length") from None
    body = await request.body()
    if len(body) > REQUEST_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Request too large")
    try:
        value = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON") from None
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    return value


def _thumbnail_process_entry(send_conn, url: str, work_dir: str, max_bytes: int) -> None:
    try:
        if urlsplit(url).scheme.lower() != "https" or not is_safe_http_url(url):
            raise ValueError("Unsafe thumbnail URL")
        request = urllib.request.Request(url, headers={"User-Agent": "K2AppLite/1.0"})
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _HttpsOnlyRedirectHandler(),
        )
        with _public_dns_only():
            with opener.open(request, timeout=20) as response:
                content_type = response.headers.get_content_type().lower()
                suffix = ALLOWED_MIME_EXTENSIONS.get(content_type)
                if suffix is None:
                    raise ValueError("Unsupported thumbnail type")
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > max_bytes:
                    raise LiteResultTooLargeError("Thumbnail exceeds its size limit")
                destination = Path(work_dir) / ("thumbnail" + suffix)
                total = 0
                with destination.open("wb") as output:
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            raise LiteResultTooLargeError("Thumbnail exceeds its size limit")
                        output.write(chunk)
                if total == 0:
                    raise ValueError("Empty thumbnail")
        send_conn.send(("ok", str(destination), content_type))
    except BaseException as error:
        send_conn.send(("error", type(error).__name__))
    finally:
        send_conn.close()


async def _download_thumbnail_with_deadline(url: str, work_dir: Path) -> tuple[Path, str]:
    context = multiprocessing.get_context("spawn")
    receive_conn, send_conn = context.Pipe(duplex=False)
    process = context.Process(
        target=_thumbnail_process_entry,
        args=(send_conn, url, str(work_dir), MAX_THUMBNAIL_BYTES),
        daemon=True,
    )
    process.start()
    send_conn.close()
    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 30
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
                raise DownloadTimeoutError("Thumbnail download exceeded its time limit")
            if process.is_alive():
                await asyncio.sleep(0.1)
            else:
                break
        process.join()
        if result is None or result[0] != "ok":
            if result and result[1] == "LiteResultTooLargeError":
                raise LiteResultTooLargeError("Thumbnail exceeds its size limit")
            raise RuntimeError("Thumbnail download failed")
        return Path(result[1]), str(result[2])
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


def _safe_stem(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "Media"))
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", normalized).strip("._-")[:90]
    return stem or "K2App_media"


def _file_mime(path: Path, override: str | None = None) -> str:
    if override and override in ALLOWED_MIME_EXTENSIONS:
        return override
    suffix = path.suffix.lower()
    return {
        ".mp4": "video/mp4",
        ".mp3": "audio/mpeg",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, mimetypes.guess_type(path.name)[0] or "application/octet-stream")


async def _run_lite_job(
    request: Request,
    job_id: str,
    user_id: str,
    source_url: str,
    media: dict[str, Any],
    choice: dict[str, Any],
) -> None:
    app = request.app
    store: LiteApiStore = app.state.lite_store
    output_dir = Path(app.state.lite_output_dir)
    config: Config = app.state.lite_config
    lock: asyncio.Lock = app.state.media_worker_lock
    job_dir = output_dir / job_id
    try:
        async with lock:
            job_dir.mkdir(parents=True, exist_ok=False)
            store.set_job_status(job_id, user_id, "downloading", 2, "Downloading from source")
            files: list[Path] = []
            overrides: dict[int, str] = {}
            with tempfile.TemporaryDirectory(prefix="work-", dir=str(job_dir)) as temp_name:
                work_dir = Path(temp_name)
                if choice.get("kind") == "thumbnail":
                    thumbnail_url = media.get("thumbnail_url")
                    if not isinstance(thumbnail_url, str):
                        raise RuntimeError("Thumbnail unavailable")
                    image_path, mime_type = await _download_thumbnail_with_deadline(thumbnail_url, work_dir)
                    files = [image_path]
                    overrides[0] = mime_type
                else:
                    mode = "audio" if choice.get("kind") == "audio" else "video"
                    selector = choice.get("format_selector")
                    if not isinstance(selector, str) or not selector:
                        selector = None
                    audio_quality = choice.get("audio_quality")
                    if audio_quality not in (128, 192, 320):
                        audio_quality = 192

                    async def on_progress(kind: str, downloaded: int, total: int, percent: int | None):
                        if percent is None:
                            progress = 5
                            text = "Downloading on server"
                        else:
                            progress = min(65, 5 + int(percent * 0.6))
                            text = f"Downloading on server · {percent}%"
                        store.set_job_status(job_id, user_id, "downloading", progress, text)

                    source_path, _downloaded_title = await _download_with_deadline(
                        source_url,
                        work_dir,
                        mode,
                        min(config.max_download_bytes, MAX_RESULT_BYTES),
                        selector,
                        int(audio_quality),
                        on_progress,
                    )
                    if source_path.stat().st_size > MAX_RESULT_BYTES:
                        raise LiteResultTooLargeError("Source exceeds the Lite result limit")
                    store.set_job_status(job_id, user_id, "preparing", 70, "Preparing files for your device")
                    height = choice.get("height")
                    profile = f"{height}p" if height in (360, 480, 720, 1080) else "720p"
                    parts = await _split_media_with_deadline(
                        source_path,
                        work_dir / "segments",
                        mode,
                        profile,
                        MAX_RESULT_BYTES,
                        int(audio_quality),
                    )
                    files = list(parts)
                if not files:
                    raise RuntimeError("No result files were produced")
                total_bytes = sum(path.stat().st_size for path in files)
                if total_bytes > MAX_RESULT_BYTES:
                    raise LiteResultTooLargeError("Result exceeds the Lite storage limit")
                if len(files) != 1:
                    raise LiteResultTooLargeError("This result needs multiple segments")

                stem = _safe_stem(str(media.get("title") or "Media"))
                stored_files: list[dict[str, Any]] = []
                for index, source_path in enumerate(files, start=1):
                    suffix = source_path.suffix.lower()
                    if suffix not in {".mp4", ".mp3", ".jpg", ".jpeg", ".png", ".webp", ".gif"}:
                        suffix = ".mp3" if choice.get("kind") == "audio" else ".mp4"
                    if len(files) == 1:
                        filename = f"{stem}{suffix}"
                    else:
                        filename = f"{stem}.part{index:03d}{suffix}"
                    destination = job_dir / filename
                    source_path.replace(destination)
                    stored_files.append({
                        "name": filename,
                        "size_bytes": destination.stat().st_size,
                        "mime_type": _file_mime(destination, overrides.get(index - 1)),
                    })
            store.set_job_status(
                job_id,
                user_id,
                "done",
                100,
                "Ready to save to your device",
                stored_files,
            )
    except asyncio.CancelledError:
        store.set_job_status(job_id, user_id, "failed", 0, "Server stopped; start a new download")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except DownloadTimeoutError:
        store.set_job_status(job_id, user_id, "failed", 0, "The server timed out. Try again or choose a lower quality.")
        shutil.rmtree(job_dir, ignore_errors=True)
    except MediaTooLargeError:
        store.set_job_status(job_id, user_id, "failed", 0, "This result is too large for the Lite server. Choose a lower quality.")
        shutil.rmtree(job_dir, ignore_errors=True)
    except MediaResolutionError as error:
        store.set_job_status(job_id, user_id, "failed", 0, str(error))
        shutil.rmtree(job_dir, ignore_errors=True)
    except LiteResultTooLargeError:
        store.set_job_status(job_id, user_id, "failed", 0, "This result is too large for the Lite server. Choose a lower quality.")
        shutil.rmtree(job_dir, ignore_errors=True)
    except Exception as error:
        LOGGER.warning("Lite media job failed (job_id=%s,error_type=%s)", job_id, type(error).__name__)
        store.set_job_status(job_id, user_id, "failed", 0, "The server could not prepare this media. Try another format.")
        shutil.rmtree(job_dir, ignore_errors=True)
    finally:
        _release_job_reservation(app, job_id)


@router.post("/auth/session")
async def create_anonymous_session(request: Request):
    created = _get_store(request).create_session()
    if created is None:
        raise HTTPException(status_code=429, detail="Too many new sessions. Try again later.")
    token, expires_at = created
    return JSONResponse(
        {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in_seconds": max(0, expires_at - int(time.time())),
            "session_type": "device",
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get("/auth/session")
async def inspect_anonymous_session(request: Request):
    _require_session(request)
    return JSONResponse(
        {"session_type": "device", "active": True},
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/auth/revoke")
async def revoke_anonymous_session(request: Request):
    token = _bearer_token(request)
    _require_session(request)
    app = request.app
    store = _get_store(request)
    revoked = store.revoke(token)
    if revoked is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    _user_id, job_ids = revoked
    cancelled = []
    output_paths = []
    for job_id in job_ids:
        task = app.state.job_tasks.pop(job_id, None)
        if task is not None:
            task.cancel()
            cancelled.append(task)
        output_paths.append(Path(app.state.lite_output_dir) / job_id)
    if cancelled:
        await asyncio.gather(*cancelled, return_exceptions=True)
    reserved_job = getattr(app.state, "api_job_reserved_job", None)
    if reserved_job in job_ids:
        _release_job_reservation(app, reserved_job)
    for output_path in output_paths:
        shutil.rmtree(output_path, ignore_errors=True)
    return JSONResponse({"revoked": True}, headers={"Cache-Control": "no-store"})


@router.post("/auth/pair")
async def legacy_pairing_disabled():
    raise HTTPException(status_code=410, detail="Telegram pairing is no longer used. Create a device session instead.")


@router.post("/jobs", status_code=202)
async def create_lite_job(request: Request):
    user_id = _require_session(request)
    body = await _read_json(request)
    url = body.get("url")
    if not isinstance(url, str) or len(url) > 2048 or not is_safe_http_url(url):
        raise HTTPException(status_code=400, detail="A public http(s) media URL is required")

    analysis_lock: asyncio.Lock = request.app.state.lite_analysis_lock
    if analysis_lock.locked():
        raise HTTPException(status_code=429, detail="The server is busy analyzing another link. Try again shortly.")
    await analysis_lock.acquire()
    store = _get_store(request)
    try:
        reason = store.record_job_attempt(user_id)
        if reason == "rate_limited":
            raise HTTPException(status_code=429, detail="This device has reached its analysis limit. Try again later.")
        if reason == "service_busy":
            raise HTTPException(status_code=503, detail="The Lite service is busy. Try again later.")
        try:
            media = await _resolve_media_with_deadline(url)
        except TimeoutError:
            raise HTTPException(status_code=504, detail="Media lookup timed out") from None
        except MediaResolutionError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        except Exception:
            raise HTTPException(status_code=422, detail="This URL could not be inspected") from None
        if not isinstance(media, dict) or not media.get("choices"):
            raise HTTPException(status_code=422, detail="No supported media formats were found")
        job_id, expires_at = store.create_job(user_id, url, media)
        return JSONResponse(
            {
                "job_id": job_id,
                "status": "chooser_ready",
                "expires_in_seconds": max(0, expires_at - int(time.time())),
                "media": {
                    "title": str(media.get("title") or "Media")[:200],
                    "duration_seconds": media.get("duration_seconds"),
                    "thumbnail_url": media.get("thumbnail_url"),
                },
                "choices": media.get("choices", []),
            },
            status_code=202,
            headers={"Cache-Control": "no-store"},
        )
    finally:
        analysis_lock.release()


@router.get("/jobs/{job_id}")
async def get_lite_job(job_id: str, request: Request):
    user_id = _require_session(request)
    if not JOB_ID_PATTERN.fullmatch(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    job = _get_store(request).get_job(job_id, user_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    return JSONResponse(job, headers={"Cache-Control": "private, no-store"})


@router.post("/jobs/{job_id}/choose", status_code=202)
async def choose_lite_job(job_id: str, request: Request):
    user_id = _require_session(request)
    if not JOB_ID_PATTERN.fullmatch(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    body = await _read_json(request)
    choice_index = body.get("choice_index")
    if not isinstance(choice_index, int) or isinstance(choice_index, bool) or not 0 <= choice_index < 10:
        raise HTTPException(status_code=400, detail="choice_index must be an integer from 0 to 9")

    app = request.app
    bot = getattr(app.state, "bot", None)
    lock: asyncio.Lock = app.state.media_worker_lock
    store = _get_store(request)
    if store.get_job(job_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    if app.state.api_job_reserved or lock.locked() or (bot is not None and bot.has_active_download()):
        raise HTTPException(status_code=429, detail="The server is busy with another media download. Try again shortly.")
    app.state.api_job_reserved = True
    app.state.api_job_reserved_job = job_id
    try:
        selected = store.consume_choice(job_id, user_id, choice_index)
        if selected is None:
            raise HTTPException(status_code=409, detail="Job is missing, expired, or already selected")
        task = asyncio.create_task(
            _run_lite_job(
                request,
                job_id,
                user_id,
                selected["source_url"],
                selected["media"],
                selected["choice"],
            ),
            name=f"lite-media-{job_id}",
        )
    except BaseException:
        _release_job_reservation(app, job_id)
        raise
    app.state.job_tasks[job_id] = task

    def _forget_task(done_task):
        app.state.job_tasks.pop(job_id, None)
        _release_job_reservation(app, job_id)
        try:
            error = done_task.exception()
        except asyncio.CancelledError:
            return
        if error:
            LOGGER.warning("Lite job task failed (job_id=%s,error_type=%s)", job_id, type(error).__name__)

    task.add_done_callback(_forget_task)
    return JSONResponse(
        {"job_id": job_id, "status": "queued", "progress": 0},
        status_code=202,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/jobs/{job_id}/files/{file_index}")
async def download_lite_file(job_id: str, file_index: int, request: Request):
    user_id = _require_session(request)
    if not JOB_ID_PATTERN.fullmatch(job_id) or not 0 <= file_index < 100:
        raise HTTPException(status_code=404, detail="File not found")
    store = _get_store(request)
    result = store.get_file(job_id, user_id, file_index, Path(request.app.state.lite_output_dir))
    if result is None:
        raise HTTPException(status_code=404, detail="File not found or expired")
    name, mime_type, path = result
    return FileResponse(
        path,
        media_type=mime_type,
        filename=name,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_lite_job(job_id: str, request: Request):
    user_id = _require_session(request)
    if not JOB_ID_PATTERN.fullmatch(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    store = _get_store(request)
    result = store.delete_job(job_id, user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    if result == "active":
        raise HTTPException(status_code=409, detail="An active job cannot be removed")
    output_dir = Path(request.app.state.lite_output_dir)
    shutil.rmtree(output_dir / job_id, ignore_errors=True)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
