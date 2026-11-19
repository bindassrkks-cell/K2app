"""API-only FastAPI service for K2App Lite; no Telegram startup or credentials."""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request

from lite_api import LiteApiConfig, LiteApiStore, cleanup_loop, router as lite_api_router

LOGGER = logging.getLogger("k2app.lite_web")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger("httpx").setLevel(logging.WARNING)
    database_path = Path(os.getenv("LITE_API_DB_FILE", "/data/k2app-lite-api.sqlite3"))
    output_dir = Path(os.getenv("LITE_DOWNLOAD_DIR", "/data/lite-downloads"))
    output_dir.mkdir(parents=True, exist_ok=True)

    store = LiteApiStore(database_path)
    store.recover_interrupted(output_dir)
    app.state.lite_store = store
    app.state.lite_output_dir = output_dir
    app.state.lite_config = LiteApiConfig()
    app.state.lite_analysis_lock = asyncio.Lock()
    app.state.media_worker_lock = asyncio.Lock()
    app.state.api_job_reserved = False
    app.state.api_job_reserved_job = None
    app.state.job_tasks = {}
    app.state.status = {"service": "k2app-lite-api", "mode": "api"}

    stop = asyncio.Event()
    cleanup_task = asyncio.create_task(
        cleanup_loop(store, output_dir, stop), name="lite-expiry-cleanup"
    )
    try:
        yield
    finally:
        stop.set()
        cleanup_task.cancel()
        jobs = set(app.state.job_tasks.values())
        for job_task in jobs:
            job_task.cancel()
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)
        await asyncio.gather(cleanup_task, return_exceptions=True)


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(lite_api_router)


@app.get("/health")
@app.get("/api/status")
async def public_status(request: Request):
    return getattr(
        request.app.state,
        "status",
        {"service": "k2app-lite-api", "mode": "api"},
    )
