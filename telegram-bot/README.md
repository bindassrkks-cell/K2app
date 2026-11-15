# K2App Telegram downloader

K2App is a standalone Telegram media downloader served by FastAPI/Uvicorn. It does not need the Android app: a user can send a supported public URL directly to the bot, choose MP4/MP3/thumbnail options, and receive the result in Telegram. `bot.py` also retains optional long-polling mode; do not run polling and webhook mode at the same time for one bot token.

## Telegram flow

Send a public media URL in the bot's private chat. K2App resolves the available formats and shows an inline chooser with MP4 resolution options, MP3 bitrates, and a thumbnail option when available. `/video URL` narrows the chooser to video and thumbnail; `/audio URL` narrows it to MP3. The download message displays a progress bar and updates during download and upload.

Videos are encoded as H.264/AAC MP4. If delivery requires multiple files, FFmpeg creates time-trimmed, independently playable segments under 48,000,000 bytes each; the service does not divide video into raw binary chunks. Audio is delivered as MP3 and can also be emitted as short, playable segments. Segment duration is measured after encoding, and oversized attempts are retried at a shorter duration. Segment files are checked against the byte cap before upload.

The selector can only offer formats exposed by the source. yt-dlp-supported public sites may work, but there is no promise that every website, private/login-only source, DRM-protected media, or each codec will work. Large downloads and re-encoding can take a long time on Render Free; the service caps source downloads at 1 GB, but Render Free is not a guarantee that every 1 GB job will finish. Only one media job is processed at a time to avoid competing for the free instance's resources. Telegram's hosted Bot API has a 50 MB per-file ceiling, so segments are kept below it. Free Render storage is ephemeral: temporary media, queued updates, pairing tokens, and recent job state may be lost when the service restarts or redeploys.

## K2App Lite API

K2App Lite uses a direct, anonymous device session. Its API jobs and downloadable files are isolated by a random per-installation identity. This flow does not send Lite downloads to Telegram and does not share the bot owner's identity. The Telegram bot and its owner-only commands remain separate. The former `/api/v1/auth/pair` endpoint returns `410 Gone`.

Create an anonymous session:

```http
POST /api/v1/auth/session
Content-Type: application/json

{}
```

The response contains a random Bearer `access_token` valid for 90 days. The server stores only its hash. The Android app encrypts the token with Android Keystore and excludes it from backups; there is no login or account recovery if app data is cleared or the app is reinstalled. `GET /api/v1/auth/session` validates the saved token. `POST /api/v1/auth/revoke` ends the session and deletes only that session's server-side jobs and result files; files already saved on the phone remain.

Create a media job and obtain available choices:

```http
POST /api/v1/jobs
Authorization: Bearer <access-token>
Content-Type: application/json

{"url":"https://public.example/video"}
```

The response includes `job_id`, `status: "chooser_ready"`, bounded media metadata and an indexed `choices` array with optional size estimates. To start a choice directly from the app, post its zero-based index:

```http
POST /api/v1/jobs/<job_id>/choose
Authorization: Bearer <access-token>
Content-Type: application/json

{"choice_index":0}
```

Poll `GET /api/v1/jobs/<job_id>` with the same Bearer token. States include `chooser_ready`, `queued`, `downloading`, `preparing`, `done` and `failed`; `progress` is an integer from 0 to 100. A completed response includes an authenticated relative `download_url` for each result. The app's Android DownloadManager sends the same Bearer token when it streams that file to the phone. A different session cannot inspect, choose, revoke or download another session's jobs/files.

Lite sessions can analyze up to five links per hour. Session issuance is capped globally at 100 new sessions per hour across all devices. Lite source and result data are capped at 300 MB, server-side jobs/files expire after six hours, and the media worker processes one job at a time. The API accepts only public HTTP(S) media URLs, bounds request bodies, blocks private/reserved DNS destinations and returns only allowlisted media metadata and format fields. Render Free storage is ephemeral, so a restart can invalidate sessions and jobs; the app can create a new anonymous session, but old server jobs cannot be recovered.

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
