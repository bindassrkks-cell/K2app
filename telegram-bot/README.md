# K2App Telegram downloader

Standalone Telegram media downloader. The container now serves Telegram webhooks through FastAPI/Uvicorn; `bot.py` remains available for optional manual long-polling via `python bot.py` (do not run polling and webhook mode simultaneously for one token).

## Webhook deployment

Create a Telegram bot with [@BotFather](https://t.me/BotFather), then deploy this directory as a Docker web service. Configure these deployment environment variables/secrets:

| Variable | Required | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | BotFather token; secret only, never place in source/docs. |
| `OWNER_CHAT_ID` | Yes, webhook mode | Private Telegram chat permitted to use the bot. Set the owner ID in deployment environment; it is not embedded in this repository. |
| `PUBLIC_BASE_URL` or `RENDER_EXTERNAL_URL` | Yes | Public HTTPS service origin, e.g. `https://your-service.onrender.com`. Render normally provides `RENDER_EXTERNAL_URL`. |
| `WEBHOOK_SECRET` | Recommended | 1–256 letters/digits/underscore/hyphen. If omitted, a stable server-only value is derived from the bot token. |
| `TELEGRAM_API_BASE` | No | Defaults to `https://api.telegram.org`. |
| `BOT_STATE_FILE` | No | Defaults to `data/k2app-telegram.sqlite3`; set `/data/k2app-telegram.sqlite3` on a host with a persistent disk. |
| `MAX_UPLOAD_MB` | No | Defaults to 49 MB; hosted Telegram Bot API limit is 50 MB. |
| `LOG_LEVEL` | No | Defaults to `INFO`. |

The container binds `0.0.0.0:$PORT` (default 10000). Startup validates configuration, calls `getMe`, then registers `/telegram/webhook` with `allowed_updates=["message"]`, `max_connections=1`, and `drop_pending_updates=false`. Public `/health` and `/api/status` expose only `service`, `mode`, bot username, and the `bot_url` Telegram deep link expected by Android; they never include owner IDs or credentials.

Webhook requests require Telegram's `X-Telegram-Bot-Api-Secret-Token`; request bodies are streamed and capped at 1 MB, including chunked requests, then checked for a valid update shape. A SQLite inbox deduplicates update IDs and stores each accepted update before returning HTTP success. A single sequential worker processes the inbox, recovers queued/in-progress updates at startup, bounds outstanding work to 100 updates, and limits each handler to five minutes. yt-dlp runs in a separate killable process with a 270-second deadline, preventing a timed-out download thread from continuing after retry. Deadline failures are finalized instead of retried indefinitely; the owner receives a safe timeout notice if Telegram is reachable. Completed payloads are wiped and done-ID deduplication history is capped at the latest 1,000 records.

**Important hosting limitation:** SQLite provides local, process-lifetime persistence only unless the hosting service has a persistent disk. On an ephemeral Render free web service, deploys/restarts can erase queued updates and deduplication history, including in-flight work; this is not a durable queue and no delivery guarantee is implied. Telegram retries failed webhook deliveries, but once an update has been acknowledged and the ephemeral filesystem is lost, that update may be lost. Do not expose downloaded files through an unauthenticated API; this service has no such endpoint. Free web instances may spin down when idle, so webhook latency/availability follows the host's free-tier behavior.

The downloader restricts media URLs and DNS resolutions to public destinations, caps files at the configured upload limit, and uses FFmpeg/yt-dlp. Login-only and DRM-protected media are unsupported.

## Local run and checks

```sh
cd telegram-bot
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
uvicorn web:app --host 0.0.0.0 --port 8000
```

For local webhook startup also set `TELEGRAM_BOT_TOKEN`, `OWNER_CHAT_ID`, and an HTTPS public tunnel URL in `PUBLIC_BASE_URL`. To explicitly run the retained polling CLI, use `python bot.py` with its existing environment requirements; do not run it alongside webhook mode using the same token.

## Docker

```sh
docker build -t k2app-telegram-bot ./telegram-bot
docker run --rm -p 10000:10000 \
  -e TELEGRAM_BOT_TOKEN -e OWNER_CHAT_ID -e PUBLIC_BASE_URL \
  -e WEBHOOK_SECRET -e PORT=10000 k2app-telegram-bot
```

Keep bot credentials in host secret/environment settings. The project changes here add code only; they do not configure, commit, or deploy hosting resources.
