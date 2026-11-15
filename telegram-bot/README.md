# K2App Telegram downloader

K2App is a standalone Telegram media downloader served by FastAPI/Uvicorn. It does not need the Android app: a user can send a supported public URL directly to the bot, choose MP4/MP3/thumbnail options, and receive the result in Telegram. `bot.py` also retains optional long-polling mode; do not run polling and webhook mode at the same time for one bot token.

## Telegram flow

Send a public media URL in the bot's private chat. K2App resolves the available formats and shows an inline chooser with MP4 resolution options, MP3 bitrates, and a thumbnail option when available. `/video URL` narrows the chooser to video and thumbnail; `/audio URL` narrows it to MP3. The download message displays a progress bar and updates during download and upload.

Videos are encoded as H.264/AAC MP4. If delivery requires multiple files, FFmpeg creates time-trimmed, independently playable segments under 48,000,000 bytes each; the service does not divide video into raw binary chunks. Audio is delivered as MP3 and can also be emitted as short, playable segments. Segment duration is measured after encoding, and oversized attempts are retried at a shorter duration. Segment files are checked against the byte cap before upload.

The selector can only offer formats exposed by the source. yt-dlp-supported public sites may work, but there is no promise that every website, private/login-only source, DRM-protected media, or each codec will work. Large downloads and re-encoding can take a long time on Render Free; the service caps source downloads at 1 GB, but Render Free is not a guarantee that every 1 GB job will finish. Only one media job is processed at a time to avoid competing for the free instance's resources. Telegram's hosted Bot API has a 50 MB per-file ceiling, so segments are kept below it. Free Render storage is ephemeral: temporary media, queued updates, pairing tokens, and recent job state may be lost when the service restarts or redeploys.

## K2App Lite API

The API is designed for the Lite client to request a chooser or start a selected download that is delivered to the owner's Telegram chat. It does not expose unauthenticated media files. Pair the Lite client first:

1. Send `/pair` to the private bot. It returns a random code valid for five minutes and one use.
2. The Lite client exchanges the code once:

```http
POST /api/v1/auth/pair
Content-Type: application/json

{"code":"<one-time-code>"}
```

The response contains an `access_token` (Bearer token) valid for 90 days. Store it securely in the app and do not include a fixed server credential in the APK. The server stores only a hash of the issued token.

Create a media job and obtain options plus a Telegram deep link:

```http
POST /api/v1/jobs
Authorization: Bearer <access-token>
Content-Type: application/json

{"url":"https://public.example/video"}
```

The response includes `job_id`, `status: "chooser_ready"`, metadata, the indexed `choices` array, and `chooser_url`. Opening `chooser_url` sends the user to the bot's inline chooser. To start a choice directly from the app, post its zero-based index:

```http
POST /api/v1/jobs/<job_id>/choose
Authorization: Bearer <access-token>
Content-Type: application/json

{"choice_index":0}
```

Poll status with `GET /api/v1/jobs/<job_id>` and the same Bearer token. Job states include `chooser_ready`, `queued`, `downloading`, `preparing`, `uploading`, `done`, and `failed`; `progress` is an integer from 0 to 100. Job sessions expire after 30 minutes. A token expires after 90 days and requires pairing again. Since Render Free has ephemeral storage, a restart can invalidate existing tokens and jobs; the user can pair again with `/pair`.

Only the configured bot owner can create and receive jobs. The API accepts public HTTP(S) URLs, bounds request sizes, checks private/reserved destinations during DNS resolution, and returns only an allowlisted set of media metadata and format fields.

## Webhook deployment

Configure these host environment variables/secrets:

| Variable | Required | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | BotFather token; deployment secret only. |
| `OWNER_CHAT_ID` | Yes | Private Telegram chat allowed to use the bot and receive API-created jobs. |
| `PUBLIC_BASE_URL` or `RENDER_EXTERNAL_URL` | Yes | Public HTTPS service origin. Render normally provides `RENDER_EXTERNAL_URL`. |
| `WEBHOOK_SECRET` | Recommended | Telegram webhook header secret; if omitted, a stable server-only value is derived from the bot token. |
| `TELEGRAM_API_BASE` | No | Defaults to `https://api.telegram.org`. |
| `BOT_STATE_FILE` | No | Defaults to `data/k2app-telegram.sqlite3`; set a mounted disk path only if the host provides a persistent disk. |
| `MAX_UPLOAD_MB` | No | Hosted Bot API file cap, defaults to 49 MB. Final encoded segments use a safer 48,000,000-byte ceiling. |
| `MAX_DOWNLOAD_MB` | No | Source download cap, defaults to 1024 MB and cannot exceed 1024 MB. |
| `LOG_LEVEL` | No | Defaults to `INFO`. |

The service registers `/telegram/webhook` with message and callback-query updates. Webhook requests require Telegram's `X-Telegram-Bot-Api-Secret-Token`; request bodies are streamed and capped at 1 MB. A bounded SQLite inbox deduplicates updates and runs one update at a time. yt-dlp and FFmpeg run in separate deadline-bounded processes. Public `/health` and `/api/status` expose only basic service status and the bot link.

## Local run and tests

```sh
cd telegram-bot
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
uvicorn web:app --host 0.0.0.0 --port 8000
```

The local webhook server needs `TELEGRAM_BOT_TOKEN`, `OWNER_CHAT_ID`, and `PUBLIC_BASE_URL` set. To use polling instead, run `python bot.py`; do not run both modes concurrently for one token.

## Docker

```sh
docker build -t k2app-telegram-bot ./telegram-bot
docker run --rm -p 10000:10000 \
  -e TELEGRAM_BOT_TOKEN -e OWNER_CHAT_ID -e PUBLIC_BASE_URL \
  -e WEBHOOK_SECRET -e PORT=10000 k2app-telegram-bot
```

Keep all bot credentials and owner settings in the host's secret/environment settings. The code does not configure hosting on its own.
