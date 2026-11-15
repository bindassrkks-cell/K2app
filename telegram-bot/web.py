"""FastAPI webhook frontend and bounded, sequential Telegram update worker."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import signal
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from bot import (
    BotState, Config, ConfigurationError, K2TelegramBot, TelegramApi,
    _resolve_media_with_deadline, is_safe_http_url,
)

LOGGER = logging.getLogger("k2app.telegram_webhook")
MAX_BODY_BYTES = 1_000_000
MAX_PENDING_UPDATES = 100
PROCESSING_TIMEOUT_SECONDS = 840
DONE_UPDATE_RETENTION = 1000
WEBHOOK_PATH = "/telegram/webhook"
LITE_REQUEST_MAX_BYTES = 8192


def _valid_update(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("update_id"), int)
        and not isinstance(value.get("update_id"), bool)
        and value["update_id"] >= 0
        and ("message" not in value or isinstance(value["message"], dict))
        and ("callback_query" not in value or isinstance(value["callback_query"], dict))
        and ("message" in value or "callback_query" in value)
    )


class UpdateStore:
    """SQLite inbox. Its durability is limited to the lifetime of the host filesystem."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS webhook_updates (update_id INTEGER PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            # A process killed mid-handler retries the update after its next start.
            db.execute("UPDATE webhook_updates SET state='queued' WHERE state='processing'")

    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.execute("PRAGMA busy_timeout = 10000")
        return db

    def insert(self, update: dict) -> bool:
        encoded = json.dumps(update, separators=(",", ":"))
        with self._connect() as db:
            found = db.execute("SELECT 1 FROM webhook_updates WHERE update_id=?", (update["update_id"],)).fetchone()
            if found:
                return True
            count = db.execute("SELECT COUNT(*) FROM webhook_updates WHERE state IN ('queued','processing')").fetchone()[0]
            if count >= MAX_PENDING_UPDATES:
                return False
            db.execute("INSERT INTO webhook_updates(update_id,payload,state) VALUES(?,?,'queued')", (update["update_id"], encoded))
            return True

    def next(self) -> tuple[int, dict] | None:
        with self._connect() as db:
            row = db.execute("SELECT update_id,payload FROM webhook_updates WHERE state='queued' ORDER BY update_id LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE webhook_updates SET state='processing' WHERE update_id=?", (row[0],))
            return int(row[0]), json.loads(row[1])

    def complete(self, update_id: int) -> None:
        with self._connect() as db:
            db.execute("UPDATE webhook_updates SET state='done', payload='' WHERE update_id=?", (update_id,))
            db.execute(
                "DELETE FROM webhook_updates WHERE state='done' AND update_id NOT IN "
                "(SELECT update_id FROM webhook_updates WHERE state='done' ORDER BY update_id DESC LIMIT ?)",
                (DONE_UPDATE_RETENTION,),
            )

    def retry(self, update_id: int) -> None:
        with self._connect() as db:
            db.execute("UPDATE webhook_updates SET state='queued' WHERE update_id=?", (update_id,))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config = Config.from_env()
    if not config.owner_chat_id:
        raise ConfigurationError("Webhook mode requires OWNER_CHAT_ID; set it in the deployment environment")
    base_url = (os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
    if not re.fullmatch(r"https://[^\s/]+(?::\d+)?", base_url, flags=re.IGNORECASE):
        raise ConfigurationError("Set PUBLIC_BASE_URL or RENDER_EXTERNAL_URL to the public HTTPS service URL")
    secret = os.getenv("WEBHOOK_SECRET", "").strip()
    if not secret:
        secret = hmac.new(config.token.encode(), b"k2app-telegram-webhook-secret-v1", hashlib.sha256).hexdigest()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", secret):
        raise ConfigurationError("WEBHOOK_SECRET must contain 1-256 letters, digits, underscores, or hyphens")

    api = TelegramApi(config.token, config.api_base)
    try:
        identity = await api.call("getMe")
        username = str(identity.get("username") or "")
        link = f"https://t.me/{quote(username)}" if username else None
        await api.call("setWebhook", {
            "url": base_url + WEBHOOK_PATH,
            "secret_token": secret,
            "allowed_updates": ["message", "callback_query"],
            "max_connections": 1,
            "drop_pending_updates": False,
        })
    except Exception:
        await api.close()
        raise

    store = UpdateStore(config.state_file)
    app.state.store = store
    state = BotState(config.state_file, config.owner_chat_id)
    bot = K2TelegramBot(config, state, api)
    app.state.bot = bot
    app.state.bot_state = state
    app.state.job_tasks = {}
    stop = asyncio.Event()
    app.state.status = {"service": "k2app", "mode": "webhook", "bot_username": username or None, "bot_url": link}

    async def worker():
        while not stop.is_set():
            item = store.next()
            if item is None:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=1)
                except asyncio.TimeoutError:
                    pass
                continue
            update_id, update = item
            try:
                message = update.get("message")
                if isinstance(message, dict):
                    await asyncio.wait_for(bot.handle_message(message), timeout=PROCESSING_TIMEOUT_SECONDS)
                callback_query = update.get("callback_query")
                if isinstance(callback_query, dict):
                    await asyncio.wait_for(bot.handle_callback_query(callback_query), timeout=PROCESSING_TIMEOUT_SECONDS)
                store.complete(update_id)
            except asyncio.CancelledError:
                store.retry(update_id)
                raise
            except asyncio.TimeoutError:
                LOGGER.warning("Update processing deadline exceeded (update_id=%s)", update_id)
                try:
                    await bot.api.send_message(config.owner_chat_id, "K2App couldn't finish processing that request before its time limit. Please try again.")
                except Exception as send_error:
                    LOGGER.warning("Could not send timeout notice (error_type=%s)", type(send_error).__name__)
                store.complete(update_id)
            except Exception as error:
                LOGGER.warning("Update processing failed (update_id=%s,error_type=%s)", update_id, type(error).__name__)
                # Keep it persisted for a retry, but avoid a tight retry loop.
                store.retry(update_id)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass

    task = asyncio.create_task(worker(), name="telegram-update-worker")
    app.state.webhook_secret = secret
    try:
        yield
    finally:
        stop.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        jobs = set(getattr(app.state, "job_tasks", {}).values())
        jobs.update(getattr(bot, "_background_downloads", set()))
        for job_task in jobs:
            job_task.cancel()
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)
        await api.close()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
@app.get("/api/status")
async def public_status(request: Request):
    return getattr(request.app.state, "status", {"service": "k2app", "mode": "webhook", "bot_username": None, "bot_url": None})


def _require_lite_auth(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    supplied = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
    state = getattr(request.app.state, "bot_state", None)
    if not supplied or state is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    chat_id = state.authenticate_api_token(supplied)
    if chat_id is None or chat_id != state.owner_chat_id():
        raise HTTPException(status_code=401, detail="Unauthorized")
    return chat_id


async def _read_lite_json(request: Request) -> dict:
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > LITE_REQUEST_MAX_BYTES:
                raise HTTPException(status_code=413, detail="Request too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid content length") from None
    body = await request.body()
    if len(body) > LITE_REQUEST_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Request too large")
    try:
        value = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON") from None
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    return value


@app.post("/api/v1/auth/pair")
async def pair_lite_device(request: Request):
    body = await _read_lite_json(request)
    code = body.get("code")
    if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,32}", code):
        raise HTTPException(status_code=400, detail="A valid one-time pairing code is required")
    state = getattr(request.app.state, "bot_state", None)
    if state is None:
        raise HTTPException(status_code=503, detail="Bot is not ready")
    paired = state.exchange_api_pair_code(code)
    if paired is None or paired[0] != state.owner_chat_id():
        raise HTTPException(status_code=401, detail="Pairing code is invalid, expired, or already used")
    return JSONResponse(
        {"access_token": paired[1], "token_type": "Bearer", "expires_in_seconds": 90 * 86400},
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/v1/jobs", status_code=202)
async def create_lite_job(request: Request):
    _require_lite_auth(request)
    body = await _read_lite_json(request)
    url = body.get("url")
    if not isinstance(url, str) or len(url) > 2048 or not is_safe_http_url(url):
        raise HTTPException(status_code=400, detail="A public http(s) media URL is required")
    state = getattr(request.app.state, "bot_state", None)
    if state is None:
        raise HTTPException(status_code=503, detail="Bot is not ready")
    owner = state.owner_chat_id()
    if owner is None:
        raise HTTPException(status_code=503, detail="Telegram owner is not configured")
    try:
        media = await _resolve_media_with_deadline(url)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Media lookup timed out") from None
    except Exception:
        raise HTTPException(status_code=422, detail="This URL could not be inspected") from None
    media["url"] = url
    job_id = state.save_media_choices(owner, media)
    status = getattr(request.app.state, "status", {})
    bot_url = status.get("bot_url")
    chooser_url = f"{bot_url}?start=dl_{job_id}" if bot_url else None
    return {
        "job_id": job_id,
        "status": "chooser_ready",
        "expires_in_seconds": 1800,
        "media": {
            "title": media.get("title"),
            "duration_seconds": media.get("duration_seconds"),
            "thumbnail_url": media.get("thumbnail_url"),
        },
        "choices": media.get("choices", []),
        "chooser_url": chooser_url,
    }


@app.get("/api/v1/jobs/{job_id}")
async def get_lite_job(job_id: str, request: Request):
    _require_lite_auth(request)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    state = getattr(request.app.state, "bot_state", None)
    if state is None:
        raise HTTPException(status_code=503, detail="Bot is not ready")
    owner = state.owner_chat_id()
    job = state.media_job_status(job_id, owner or "")
    media = state.get_media_choices(job_id, owner or "")
    if job is None or media is None:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    return {
        "job_id": job_id,
        **job,
        "media": {
            "title": media.get("title"),
            "duration_seconds": media.get("duration_seconds"),
            "thumbnail_url": media.get("thumbnail_url"),
        },
        "choices": media.get("choices", []),
    }


@app.post("/api/v1/jobs/{job_id}/choose", status_code=202)
async def choose_lite_job(job_id: str, request: Request):
    _require_lite_auth(request)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    body = await _read_lite_json(request)
    choice_index = body.get("choice_index")
    if not isinstance(choice_index, int) or isinstance(choice_index, bool) or not 0 <= choice_index < 10:
        raise HTTPException(status_code=400, detail="choice_index must be an integer from 0 to 9")
    state = getattr(request.app.state, "bot_state", None)
    bot = getattr(request.app.state, "bot", None)
    if state is None or bot is None:
        raise HTTPException(status_code=503, detail="Bot is not ready")
    owner = state.owner_chat_id()
    if owner is None:
        raise HTTPException(status_code=503, detail="Telegram owner is not configured")
    if bot.has_active_download():
        raise HTTPException(status_code=429, detail="Another media job is already running")
    selected = state.consume_media_choice(job_id, owner, choice_index)
    if selected is None:
        raise HTTPException(status_code=409, detail="Job is missing, expired, or already selected")
    media, choice = selected
    if choice.get("kind") == "thumbnail":
        thumbnail = media.get("thumbnail_url")
        if not isinstance(thumbnail, str):
            state.set_media_job_status(job_id, "failed", 0, "Thumbnail unavailable")
            raise HTTPException(status_code=422, detail="Thumbnail unavailable")
        try:
            await bot.api.send_photo_url(owner, thumbnail, f"Thumbnail: {str(media.get('title') or 'Media')[:160]}")
            state.set_media_job_status(job_id, "done", 100, "Thumbnail sent")
            return {"job_id": job_id, "status": "done", "progress": 100}
        except Exception:
            state.set_media_job_status(job_id, "failed", 0, "Thumbnail delivery failed")
            raise HTTPException(status_code=502, detail="Thumbnail delivery failed") from None
    task = bot.start_background_download(owner, job_id, media, choice)
    if task is None:
        state.set_media_job_status(job_id, "failed", 0, "Another media job is active")
        raise HTTPException(status_code=429, detail="Another media job is already running")
    request.app.state.job_tasks[job_id] = task

    def _forget_task(done_task):
        request.app.state.job_tasks.pop(job_id, None)
        try:
            error = done_task.exception()
        except asyncio.CancelledError:
            return
        if error:
            LOGGER.warning("Lite job task failed (job_id=%s,error_type=%s)", job_id, type(error).__name__)

    task.add_done_callback(_forget_task)
    return {"job_id": job_id, "status": "queued", "progress": 0}


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    secret = getattr(request.app.state, "webhook_secret", None)
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not secret or not hmac.compare_digest(supplied, secret):
        raise HTTPException(status_code=403, detail="Forbidden")
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > MAX_BODY_BYTES:
                raise HTTPException(status_code=413, detail="Payload too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid content length") from None
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Payload too large")
        chunks.extend(chunk)
    body = bytes(chunks)
    try:
        update = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON") from None
    if not _valid_update(update):
        raise HTTPException(status_code=400, detail="Invalid update")
    store = getattr(request.app.state, "store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Service unavailable")
    if not store.insert(update):
        raise HTTPException(status_code=503, detail="Update queue full")
    return JSONResponse({"ok": True})
