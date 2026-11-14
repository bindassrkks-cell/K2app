# K2App Telegram downloader

This is a standalone Telegram bot worker. It polls Telegram itself, downloads public media URLs with `yt-dlp` and FFmpeg, and sends the result back into the same Telegram chat. After setup, the Android app does not need to be installed or running.

## How to use it

1. Create a bot with Telegram's [@BotFather](https://t.me/BotFather) and keep its token private.
2. Run this container as an always-on worker and provide `TELEGRAM_BOT_TOKEN` as a host secret/environment variable. Also set either `OWNER_CHAT_ID` to your private Telegram chat ID, or set a random `BOT_SETUP_CODE` with at least 20 letters/digits/underscores/hyphens.
3. Open the bot in a **private** Telegram chat. If you set `OWNER_CHAT_ID`, send `/start`. If you set `BOT_SETUP_CODE`, send `/start YOUR_SETUP_CODE`; the first valid private claim is stored in SQLite.
4. Send a public media URL. The bot replies while processing and then sends the downloaded file. `/video URL`, `/audio URL`, `/download URL`, `/help`, and `/status` are supported.

The bot is single-owner. Set `OWNER_CHAT_ID` to pre-authorize a specific private chat; otherwise, keep `BOT_SETUP_CODE` secret and use it only for the first claim. Mount persistent storage at `/data` so the owner binding and update offset survive restarts. If the state file is lost, a setup code still present in the environment can be used to claim the bot again.

## Moving from the Android poller

The current K2App Android settings and encrypted local bot configuration are preserved for migration, but that device-side poller is optional—the server bot works independently. Telegram allows only one active `getUpdates` poller per bot token. Before starting the server with the same token, use the existing app's **Disconnect** control or otherwise stop its polling service; if both run, Telegram can return a polling conflict. The Android app's locally encrypted token is not migrated to the server automatically; add the BotFather token separately as a secret in the hosting environment. Once the server bot is running, you do not need the app for downloads.

## Run with Docker

Build the image, then create a private environment file **outside the repository** from the sample. Fill `TELEGRAM_BOT_TOKEN` and either `OWNER_CHAT_ID` or `BOT_SETUP_CODE`; keep the file restricted to your OS user. On managed hosting, enter these values in the provider's secret/environment settings instead.

```sh
docker build -t k2app-telegram-bot ./telegram-bot
mkdir -p "$HOME/.config" "$HOME/.local/share/k2app-telegram-bot"
cp telegram-bot/.env.example "$HOME/.config/k2app-telegram-bot.env"
chmod 600 "$HOME/.config/k2app-telegram-bot.env"
# Edit the private env file on the host before starting the container.
docker run -d --name k2app-telegram-bot --restart unless-stopped \
  --env-file "$HOME/.config/k2app-telegram-bot.env" \
  -v "$HOME/.local/share/k2app-telegram-bot:/data" \
  k2app-telegram-bot
```

Never commit a real bot token or setup code or put them in a public GitHub file. This worker uses Telegram long polling and removes a previously configured webhook at startup. Only one polling process should use a bot token at a time. The downloader rejects non-public DNS destinations during extraction; still run it in an isolated host/container without access to cloud metadata or private services.

## Supported media and limits

Downloads use the current `yt-dlp` extractors, FFmpeg, and Deno/EJS support. This covers public URLs supported by `yt-dlp`, but does not bypass DRM or provide login cookies from the Android app. A site may change and temporarily stop working until `yt-dlp` updates.

The regular Telegram Bot API accepts uploaded files up to **50 MB**. The default worker cap is 49 MB to leave margin. Larger uploads require a self-hosted Telegram Bot API server; Telegram's [official Bot API documentation](https://core.telegram.org/bots/api) says a local server can upload files up to 2000 MB. If you configure such a server, set `TELEGRAM_API_BASE` to its API base URL and raise `MAX_UPLOAD_MB` to a safe value. For an HTTP endpoint, `ALLOW_HTTP_LOCAL_API=true` is required and the host must be loopback/private or a local service name; use HTTPS for a remote Bot API server. Hosting that extra service also needs additional compute/storage.

## Hosting note

Long polling needs a continuously running worker. Render's [free-instance documentation](https://render.com/docs/free) says background workers are not among its free service types; free web services spin down after 15 minutes without inbound traffic. Use an already-running server or choose an always-on worker plan. This repository adds the worker code and Docker image only; it does not create a hosting service, add a payment method, or deploy a token.

## Environment

| Variable | Required | Default | Purpose |
|---|---:|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | — | BotFather token; keep it in host secrets. |
| `OWNER_CHAT_ID` | One of these two | — | Pre-authorize a positive private Telegram chat ID. |
| `BOT_SETUP_CODE` | One of these two | — | Secret of 20+ allowed characters for the first private `/start CODE` claim. |
| `TELEGRAM_API_BASE` | No | `https://api.telegram.org` | Bot API server base URL. |
| `ALLOW_HTTP_LOCAL_API` | No | `false` | Explicit opt-in for HTTP to a trusted local/private Bot API endpoint only. |
| `BOT_STATE_FILE` | No | `data/k2app-telegram.sqlite3` | SQLite file storing owner binding and update offset. |
| `MAX_UPLOAD_MB` | No | `49` | Max downloaded size; at most 50 MB with Telegram's hosted Bot API. |
| `LOG_LEVEL` | No | `INFO` | Log level. Tokens and message URLs are not logged. |

## Local checks

```sh
cd telegram-bot
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m py_compile bot.py
```
