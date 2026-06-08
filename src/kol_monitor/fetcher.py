from __future__ import annotations

import asyncio
import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from kol_monitor import db
from kol_monitor.config import settings
from kol_monitor.client import OpenTwitterClient

logger = logging.getLogger(__name__)
NUMERIC_SUFFIX_RE = re.compile(r"(\d+)$")
MIN_DATETIME = datetime.min.replace(tzinfo=timezone.utc)


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


def _tweet_id_family(tweet_id: str) -> str:
    match = NUMERIC_SUFFIX_RE.search(tweet_id)
    if not match:
        return tweet_id
    return tweet_id[: match.start(1)] or "numeric"


def _tweet_ids_are_comparable(left: str, right: str) -> bool:
    return _tweet_id_family(left) == _tweet_id_family(right)


def _tweet_id_sort_value(tweet_id: str) -> int:
    try:
        return int(tweet_id)
    except ValueError:
        match = NUMERIC_SUFFIX_RE.search(tweet_id)
        if match:
            return int(match.group(1))
        raise


def _tweet_created_at(tweet: dict[str, Any]) -> datetime | None:
    value = tweet.get("created_at") or tweet.get("createdAt")
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            try:
                parsed = datetime.strptime(text, "%a %b %d %H:%M:%S %z %Y")
            except ValueError:
                return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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
    families = {_tweet_id_family(_tweet_id(tweet)) for tweet in tweets}
    if len(families) == 1:
        return _tweet_id(max(tweets, key=_tweet_id_int))
    return _tweet_id(max(tweets, key=lambda tweet: _tweet_created_at(tweet) or MIN_DATETIME))


def _insert_tweets(tweets: list[dict[str, Any]], kol: dict[str, Any]) -> int:
    inserted = 0
    for tweet in tweets:
        if db.insert_tweet(_attach_kol(tweet, kol)):
            inserted += 1
    return inserted


def _last_seen_created_at(last_id: str | None) -> datetime | None:
    if not last_id:
        return None
    tweet = db.get_tweet(last_id)
    if not tweet:
        return None
    return _tweet_created_at(tweet)


def _is_newer_than_anchor(
    tweet: dict[str, Any],
    last_id: str,
    last_id_int: int,
    last_seen_created_at: datetime | None,
) -> bool:
    tweet_id = _tweet_id(tweet)
    if _tweet_ids_are_comparable(tweet_id, last_id):
        return _tweet_id_int(tweet) > last_id_int
    tweet_created_at = _tweet_created_at(tweet)
    return bool(tweet_created_at and last_seen_created_at and tweet_created_at > last_seen_created_at)


def _batch_overlaps_anchor(
    batch: list[dict[str, Any]],
    last_id: str,
    last_id_int: int,
    last_seen_created_at: datetime | None,
) -> bool:
    if any(_tweet_id(tweet) == last_id for tweet in batch):
        return True
    comparable_ids = [
        _tweet_id_int(tweet)
        for tweet in batch
        if _tweet_ids_are_comparable(_tweet_id(tweet), last_id)
    ]
    if comparable_ids and min(comparable_ids) < last_id_int:
        return True
    if last_seen_created_at is None:
        return False
    created_values = [_tweet_created_at(tweet) for tweet in batch]
    return any(value is not None and value <= last_seen_created_at for value in created_values)


async def _latest_tweets(client: Any, handle: str, max_results: int) -> list[dict[str, Any]]:
    try:
        return await client.user_tweets(handle, max_results=max_results)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            logger.warning(
                "user_tweets returned 400 for @%s; falling back to twitter_search",
                handle,
            )
            return await client.search(from_user=handle, max_results=max_results)
        raise


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
        batch = await _latest_tweets(client, handle, initial_pull_size)
        inserted = _insert_tweets(batch, kol)
        newest_id = _max_id(batch)
        db.update_kol_anchor(kol["id"], newest_id, datetime.now(timezone.utc), incomplete=False)
        return KolFetchResult(handle, inserted=inserted, fetched=len(batch), incomplete=False)

    last_id_int = _tweet_id_sort_value(str(last_id))
    last_seen_created_at = _last_seen_created_at(str(last_id))
    page_size = initial_pull_size
    fetched_by_id: dict[str, dict[str, Any]] = {}
    overlap = False

    for _ in range(max_rounds):
        batch = await _latest_tweets(client, handle, page_size)
        for tweet in batch:
            fetched_by_id[_tweet_id(tweet)] = tweet
        if not batch:
            overlap = True
            break
        if _batch_overlaps_anchor(batch, str(last_id), last_id_int, last_seen_created_at):
            overlap = True
            break
        page_size = min(page_size * 2, max_results_per_request)

    new_tweets = [
        tweet
        for tweet in fetched_by_id.values()
        if _is_newer_than_anchor(tweet, str(last_id), last_id_int, last_seen_created_at)
    ]
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
