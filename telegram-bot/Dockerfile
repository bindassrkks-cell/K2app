FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    BOT_STATE_FILE=/data/k2app-telegram.sqlite3 \
    DENO_NO_UPDATE_CHECK=1

COPY --from=denoland/deno:bin-2.9.8 /deno /usr/local/bin/deno

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 k2bot \
    && mkdir -p /app /data \
    && chown -R k2bot:k2bot /app /data

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=k2bot:k2bot . .

USER k2bot
CMD ["python", "bot.py"]
