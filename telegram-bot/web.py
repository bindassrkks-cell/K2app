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

from bot import BotState, Config, ConfigurationError, K2TelegramBot, TelegramApi

LOGGER = logging.getLogger("k2app.telegram_webhook")
MAX_BODY_BYTES = 1_000_000
MAX_PENDING_UPDATES = 100
PROCESSING_TIMEOUT_SECONDS = 840
DONE_UPDATE_RETENTION = 1000
WEBHOOK_PATH = "/telegram/webhook"


def _valid_update(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("update_id"), int)
        and not isinstance(value.get("update_id"), bool)
        and value["update_id"] >= 0
        and ("message" not in value or isinstance(value["message"], dict))
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
            "allowed_updates": ["message"],
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
        await api.close()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
@app.get("/api/status")
async def public_status(request: Request):
    return getattr(request.app.state, "status", {"service": "k2app", "mode": "webhook", "bot_username": None, "bot_url": None})


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
