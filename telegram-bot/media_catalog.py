"""Bounded, UI-safe media metadata and yt-dlp format choices."""
from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlsplit


FORMAT_ID = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
QUALITY_LEVELS = (1080, 720, 480, 360)
AUDIO_QUALITIES = (320, 192, 128)
MEDIA_ERROR_MESSAGES = {
    "unsupported": "No downloadable video or audio formats were found for this link.",
    "access": "This video requires login or permission that Lite does not have.",
    "protected": "This source uses protected media that Lite cannot download.",
    "region": "This source is unavailable from the server's region.",
    "blocked": "The source blocked or rate-limited the server. Try again later.",
    "timeout": "The source took too long to respond. Try again.",
    "extractor": "The server video extractor is not configured correctly. Please try later.",
    "temporary": "This link could not be inspected. It may be unsupported or temporarily unavailable.",
}


class MediaResolutionError(RuntimeError):
    def __init__(self, code: str):
        self.code = code if code in MEDIA_ERROR_MESSAGES else "temporary"
        super().__init__(MEDIA_ERROR_MESSAGES[self.code])


def classify_extraction_error(error: BaseException) -> str:
    if isinstance(error, MediaResolutionError):
        return error.code
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, (ImportError, ModuleNotFoundError)):
        return "extractor"
    text = str(error).lower()
    if any(term in text for term in ("drm", "widevine", "fairplay", "playready", "protected stream")):
        return "protected"
    if any(term in text for term in ("geo-restricted", "not available in your country", "unavailable in your region")):
        return "region"
    if any(term in text for term in (
        "login required", "log in", "sign in", "authentication required", "private video",
        "members-only", "subscriber-only", "age-restricted", "not authorized",
    )):
        return "access"
    if any(term in text for term in (
        "unsupported url", "no downloadable", "no suitable formats", "no formats found",
        "requested format is not available",
    )):
        return "unsupported"
    if any(term in text for term in (
        "captcha", "bot detection", "ip blocked", "rate limit", "too many requests",
        "http error 403", "http error 429", "forbidden",
    )):
        return "blocked"
    if any(term in text for term in ("timed out", "timeout", "temporary failure", "connection reset")):
        return "timeout"
    if "yt-dlp is not installed" in text or "ffmpeg not found" in text:
        return "extractor"
    return "temporary"


def _safe_thumbnail(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or not host or parsed.username is not None or parsed.password is not None:
            return False
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return "." in host
    except (ValueError, UnicodeError):
        return False


def _format_id(fmt: dict[str, Any]) -> str | None:
    value = str(fmt.get("format_id") or "")
    return value if FORMAT_ID.fullmatch(value) else None


def _number(fmt: dict[str, Any], key: str) -> float:
    value = fmt.get(key)
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _has_audio(fmt: dict[str, Any]) -> bool:
    return fmt.get("acodec") not in (None, "none")


def _has_video(fmt: dict[str, Any]) -> bool:
    return fmt.get("vcodec") not in (None, "none")


def _format_selector(video: dict[str, Any], audio_formats: list[dict[str, Any]]) -> str | None:
    video_id = _format_id(video)
    if not video_id:
        return None
    if _has_audio(video):
        return video_id
    audio = next((f for f in audio_formats if _format_id(f)), None)
    if audio is None:
        return video_id
    return f"{video_id}+{_format_id(audio)}"


def _estimated_format_bytes(fmt: dict[str, Any], duration: float) -> int:
    for key in ("filesize", "filesize_approx"):
        size = _number(fmt, key)
        if size > 0:
            return int(size)
    bitrate_kbps = _number(fmt, "tbr") or _number(fmt, "abr")
    if duration > 0 and bitrate_kbps > 0:
        return int(bitrate_kbps * 1000 * duration / 8)
    return 0


def _estimated_video_bytes(video: dict[str, Any], audio_formats: list[dict[str, Any]], duration: float) -> int:
    size = _estimated_format_bytes(video, duration)
    if not _has_audio(video):
        audio = next((fmt for fmt in audio_formats if _format_id(fmt)), None)
        if audio is not None:
            size += _estimated_format_bytes(audio, duration)
    return size


def build_choices(info: dict[str, Any]) -> list[dict[str, Any]]:
    """Return bounded MP4 resolution, MP3 bitrate, and thumbnail choices."""
    formats = [fmt for fmt in info.get("formats", []) if isinstance(fmt, dict)]
    video_formats = [
        f for f in formats
        if _has_video(f) and _format_id(f)
    ]
    height_formats = [
        f for f in video_formats
        if isinstance(f.get("height"), (int, float)) and not isinstance(f.get("height"), bool)
    ]
    audio_formats = [
        f for f in formats
        if _has_audio(f) and not _has_video(f) and _format_id(f)
    ]
    audio_formats.sort(
        key=lambda f: (
            _number(f, "abr"),
            str(f.get("ext") or "") in {"m4a", "mp3"},
            _number(f, "asr"),
        ),
        reverse=True,
    )

    choices: list[dict[str, Any]] = []
    seen_heights: set[int] = set()
    duration = _number(info, "duration")
    for target in QUALITY_LEVELS:
        candidates = [f for f in height_formats if 0 < int(f["height"]) <= target]
        if not candidates:
            continue
        candidates.sort(
            key=lambda f: (
                int(f["height"]),
                str(f.get("ext") or "") == "mp4",
                str(f.get("vcodec") or "").startswith(("avc1", "h264")),
                _number(f, "fps"),
                _number(f, "tbr"),
            ),
            reverse=True,
        )
        chosen = candidates[0]
        height = int(chosen["height"])
        if height in seen_heights:
            continue
        selector = _format_selector(chosen, audio_formats)
        if not selector:
            continue
        seen_heights.add(height)
        choices.append({
            "kind": "video",
            "label": f"MP4 · {height}p",
            "format_selector": selector,
            "height": height,
            "audio_quality": None,
            "estimated_size_bytes": _estimated_video_bytes(chosen, audio_formats, duration),
        })

    # Keep a video fallback for extractors that expose formats without height metadata.
    if not choices:
        candidates = [f for f in video_formats if _format_id(f)]
        if candidates:
            chosen = max(candidates, key=lambda f: (_number(f, "tbr"), str(f.get("ext") or "") == "mp4"))
            selector = _format_selector(chosen, audio_formats)
            if selector:
                choices.append({
                    "kind": "video",
                    "label": "MP4 · Best available",
                    "format_selector": selector,
                    "height": None,
                    "audio_quality": None,
                    "estimated_size_bytes": _estimated_video_bytes(chosen, audio_formats, duration),
                })

    if audio_formats or video_formats:
        selector = _format_id(audio_formats[0]) if audio_formats else "bestaudio/best"
        for bitrate in AUDIO_QUALITIES:
            choices.append({
                "kind": "audio",
                "label": f"MP3 · {bitrate} kbps",
                "format_selector": selector,
                "height": None,
                "audio_quality": bitrate,
                "estimated_size_bytes": _estimated_format_bytes(audio_formats[0], duration)
                if audio_formats else 0,
            })

    thumbnail = info.get("thumbnail")
    if _safe_thumbnail(thumbnail):
        choices.append({
            "kind": "thumbnail",
            "label": "Thumbnail",
            "format_selector": None,
            "height": None,
            "audio_quality": None,
        })
    return choices[:10]


def summarize_info(info: dict[str, Any]) -> dict[str, Any]:
    duration = _number(info, "duration")
    thumbnails = info.get("thumbnails") or []
    thumb = info.get("thumbnail")
    if not _safe_thumbnail(thumb):
        thumb = next((t.get("url") for t in reversed(thumbnails)
                      if isinstance(t, dict) and _safe_thumbnail(t.get("url"))), None)
    choice_info = dict(info)
    if not _safe_thumbnail(choice_info.get("thumbnail")) and thumb:
        choice_info["thumbnail"] = thumb
    return {
        "title": str(info.get("title") or "Media")[:200],
        "duration_seconds": int(duration) if duration > 0 else None,
        "thumbnail_url": thumb[:2048] if isinstance(thumb, str) else None,
        "extractor": str(info.get("extractor_key") or info.get("extractor") or "")[:80],
        "choices": build_choices(choice_info),
    }


def resolve_media(url: str) -> dict[str, Any]:
    """Resolve a public URL without downloading media and return only bounded UI fields."""
    from bot import _public_dns_only, is_safe_http_url

    if not is_safe_http_url(url):
        raise MediaResolutionError("unsupported")
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 1,
        "extract_flat": False,
    }
    try:
        from yt_dlp import YoutubeDL

        with YoutubeDL(options) as downloader:
            with _public_dns_only():
                info = downloader.extract_info(url, download=False)
        if not isinstance(info, dict):
            raise MediaResolutionError("unsupported")
        result = summarize_info(info)
        if not result["choices"]:
            raise MediaResolutionError("unsupported")
        return result
    except MediaResolutionError:
        raise
    except Exception as error:
        raise MediaResolutionError(classify_extraction_error(error)) from None
