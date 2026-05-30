from __future__ import annotations

import asyncio
import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from kol_monitor import db
from kol_monitor.config import settings
from kol_monitor.client import OpenTwitterClient

logger = logging.getLogger(__name__)
NUMERIC_SUFFIX_RE = re.compile(r"(\d+)$")


@dataclass
class KolFetchResult:
    screen_name: str
    inserted: int
    fetched: int
    incomplete: bool
    error: str | None = None


@dataclass
class RunStats:
    kols_total: int
    kols_ok: int
    kols_failed: int
    tweets_new: int
    errors: list[str]


def _tweet_id(tweet: dict[str, Any]) -> str:
    value = tweet.get("tweet_id") or tweet.get("id") or tweet.get("id_str")
    if value is None:
        raise ValueError("tweet missing id")
    return str(value)


def _tweet_id_int(tweet: dict[str, Any]) -> int:
    return _tweet_id_sort_value(_tweet_id(tweet))


def _tweet_id_sort_value(tweet_id: str) -> int:
    try:
        return int(tweet_id)
    except ValueError:
        match = NUMERIC_SUFFIX_RE.search(tweet_id)
        if match:
            return int(match.group(1))
        raise


def _attach_kol(tweet: dict[str, Any], kol: dict[str, Any]) -> dict[str, Any]:
    return {
        **tweet,
        "kol_id": kol["id"],
        "screen_name": tweet.get("screen_name") or tweet.get("userScreenName") or kol["screen_name"],
        "userScreenName": tweet.get("userScreenName") or tweet.get("screen_name") or kol["screen_name"],
    }


def _max_id(tweets: list[dict[str, Any]]) -> str | None:
    if not tweets:
        return None
    return _tweet_id(max(tweets, key=_tweet_id_int))


def _insert_tweets(tweets: list[dict[str, Any]], kol: dict[str, Any]) -> int:
    inserted = 0
    for tweet in tweets:
        if db.insert_tweet(_attach_kol(tweet, kol)):
            inserted += 1
    return inserted


async def fetch_one_kol(
    client: Any,
    kol: dict[str, Any],
    initial_pull_size: int | None = None,
    max_rounds: int | None = None,
    max_results_per_request: int | None = None,
) -> KolFetchResult:
    handle = kol["screen_name"]
    initial_pull_size = initial_pull_size or settings.fetcher.initial_pull_size
    max_rounds = max_rounds or settings.fetcher.max_rounds
    max_results_per_request = max_results_per_request or settings.fetcher.max_results_per_request
    last_id = kol.get("last_seen_tweet_id")

    if last_id is None:
        batch = await client.user_tweets(handle, max_results=initial_pull_size)
        inserted = _insert_tweets(batch, kol)
        newest_id = _max_id(batch)
        db.update_kol_anchor(kol["id"], newest_id, datetime.now(timezone.utc), incomplete=False)
        return KolFetchResult(handle, inserted=inserted, fetched=len(batch), incomplete=False)

    last_id_int = _tweet_id_sort_value(str(last_id))
    page_size = initial_pull_size
    fetched_by_id: dict[str, dict[str, Any]] = {}
    overlap = False

    for _ in range(max_rounds):
        batch = await client.user_tweets(handle, max_results=page_size)
        for tweet in batch:
            fetched_by_id[_tweet_id(tweet)] = tweet
        if not batch:
            overlap = True
            break
        ids = [_tweet_id_int(tweet) for tweet in batch]
        if last_id_int in ids or min(ids) < last_id_int:
            overlap = True
            break
        page_size = min(page_size * 2, max_results_per_request)

    new_tweets = [tweet for tweet in fetched_by_id.values() if _tweet_id_int(tweet) > last_id_int]
    inserted = _insert_tweets(new_tweets, kol)
    newest_id = _max_id(new_tweets) if new_tweets else None
    db.update_kol_anchor(kol["id"], newest_id, datetime.now(timezone.utc), incomplete=not overlap)
    if not overlap:
        logger.warning("gap suspected for @%s", handle)
    return KolFetchResult(handle, inserted=inserted, fetched=len(fetched_by_id), incomplete=not overlap)


async def backfill_incomplete(client: Any) -> None:
    for kol in db.list_incomplete_kols():
        last_fetched_at = kol.get("last_fetched_at")
        since_date = _since_date(last_fetched_at)
        tweets = await client.search(from_user=kol["screen_name"], since_date=since_date, max_results=100)
        new_tweets = [
            tweet
            for tweet in tweets
            if kol.get("last_seen_tweet_id") is None
            or _tweet_id_int(tweet) > _tweet_id_sort_value(str(kol["last_seen_tweet_id"]))
        ]
        _insert_tweets(new_tweets, kol)
        newest_id = _max_id(new_tweets)
        db.update_kol_anchor(kol["id"], newest_id, datetime.now(timezone.utc), incomplete=False)


def _since_date(last_fetched_at: str | None) -> str:
    if not last_fetched_at:
        return (datetime.now(timezone.utc) - timedelta(days=settings.fetcher.search_backfill_days)).date().isoformat()
    try:
        parsed = datetime.fromisoformat(last_fetched_at.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(timezone.utc)
    return (parsed - timedelta(days=1)).date().isoformat()


async def validate_handle(client: Any, handle: str) -> dict[str, Any] | None:
    return await client.user_info(handle)


async def daily_fetch(trigger: str = "scheduled") -> RunStats:
    db.init_db(settings.db_path)
    db.sync_config_kols(settings.kols)
    kols = db.list_active_kols()
    run_id = db.start_run(trigger, kols_total=len(kols))
    if not settings.opentwitter_token:
        raise RuntimeError("OPENTWITTER_TOKEN is required")

    client = OpenTwitterClient(
        token=settings.opentwitter_token,
        base_url=settings.opentwitter_base_url,
        timeout=settings.fetcher.request_timeout,
        retry_attempts=settings.fetcher.retry_attempts,
    )
    ok = 0
    failed = 0
    tweets_new = 0
    errors: list[str] = []
    try:
        for index, kol in enumerate(kols):
            if index:
                await asyncio.sleep(random.uniform(settings.fetcher.per_kol_sleep_min, settings.fetcher.per_kol_sleep_max))
            try:
                result = await fetch_one_kol(client, kol)
                ok += 1
                tweets_new += result.inserted
            except Exception as exc:
                failed += 1
                message = f"@{kol['screen_name']}: {exc}"
                logger.exception("failed to fetch %s", message)
                errors.append(message)
        await backfill_incomplete(client)
    finally:
        await client.close()
        db.finish_run(run_id, ok, failed, tweets_new, "\n".join(errors))

    return RunStats(
        kols_total=len(kols),
        kols_ok=ok,
        kols_failed=failed,
        tweets_new=tweets_new,
        errors=errors,
    )
