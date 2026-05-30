from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image

from kol_monitor import db
from kol_monitor.config import settings

logger = logging.getLogger(__name__)


CONTENT_TYPE_EXT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "video/mp4": "mp4",
}


def detect_ext(url: str, content_type: str | None) -> str:
    if content_type:
        media_type = content_type.split(";")[0].strip().lower()
        if media_type in CONTENT_TYPE_EXT:
            return CONTENT_TYPE_EXT[media_type]

    path = urlparse(url).path.lower()
    for ext in ("jpg", "jpeg", "png", "webp", "gif", "mp4"):
        if path.endswith(f".{ext}"):
            return "jpg" if ext == "jpeg" else ext
    return "jpg"


def media_path(
    date: str,
    handle: str,
    tweet_id: str,
    idx: int,
    ext: str,
    root: str | Path | None = None,
) -> Path:
    base = Path(root) if root else settings.media_dir
    return base / date / handle / f"{tweet_id}_{idx}.{ext}"


def validate_image(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


async def download_one(media_id: int, url: str, dest_path: Path, timeout: float | None = None) -> Path | None:
    timeout = timeout or settings.media.download_timeout
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = dest_path.with_suffix(dest_path.suffix + ".part")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            ext = detect_ext(url, response.headers.get("content-type"))
            final_path = dest_path.with_suffix(f".{ext}")
            part_path = final_path.with_suffix(final_path.suffix + ".part")
            part_path.write_bytes(response.content)
            if ext != "mp4" and not validate_image(part_path):
                db.mark_media_failed(media_id)
                part_path.unlink(missing_ok=True)
                return None
            part_path.replace(final_path)
            db.mark_media_downloaded(media_id, final_path)
            return final_path
    except Exception as exc:
        logger.warning("media download failed for %s: %s", url, exc)
        part_path.unlink(missing_ok=True)
        db.mark_media_failed(media_id)
        return None


async def download_pending_media(date: str) -> tuple[int, int]:
    pending = db.pending_media_for_date(date)
    semaphore = asyncio.Semaphore(settings.media.download_concurrency)
    ok = 0
    failed = 0

    async def _download(row: dict) -> bool:
        media_type = row["type"]
        if media_type == "video" or (media_type == "gif" and not settings.media.download_gif):
            db.mark_media_failed(row["id"])
            return False
        if media_type == "photo" and not settings.media.download_photos:
            db.mark_media_failed(row["id"])
            return False
        index = _media_index(row, pending)
        ext = detect_ext(row["orig_url"], None)
        dest = media_path(date, row["screen_name"], row["tweet_id"], index, ext)
        async with semaphore:
            return await download_one(row["id"], row["orig_url"], dest) is not None

    results = await asyncio.gather(*(_download(row) for row in pending))
    for result in results:
        if result:
            ok += 1
        else:
            failed += 1
    return ok, failed


def _media_index(row: dict, rows: list[dict]) -> int:
    same_tweet = [item for item in rows if item["tweet_id"] == row["tweet_id"]]
    return same_tweet.index(row)
