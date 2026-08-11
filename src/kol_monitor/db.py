from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

class DatabaseError(RuntimeError):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS kols (
  id INTEGER PRIMARY KEY,
  screen_name TEXT UNIQUE NOT NULL,
  display_name TEXT,
  twitter_user_id TEXT,
  last_seen_tweet_id TEXT,
  last_fetched_at TIMESTAMP,
  incomplete BOOLEAN DEFAULT 0,
  active BOOLEAN DEFAULT 1,
  inactive_reason TEXT,
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tweets (
  tweet_id TEXT PRIMARY KEY,
  kol_id INTEGER REFERENCES kols(id),
  text TEXT,
  created_at TIMESTAMP,
  language TEXT,
  is_retweet BOOLEAN DEFAULT 0,
  is_quote BOOLEAN DEFAULT 0,
  is_reply BOOLEAN DEFAULT 0,
  conversation_id TEXT,
  reply_count INTEGER,
  retweet_count INTEGER,
  favorite_count INTEGER,
  view_count INTEGER,
  quote_count INTEGER,
  url TEXT,
  raw_json TEXT,
  fetched_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tweets_kol_created ON tweets(kol_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tweets_created ON tweets(created_at DESC);

CREATE TABLE IF NOT EXISTS media (
  id INTEGER PRIMARY KEY,
  tweet_id TEXT REFERENCES tweets(tweet_id),
  type TEXT,
  orig_url TEXT,
  thumb_url TEXT,
  local_path TEXT,
  download_status TEXT DEFAULT 'pending',
  downloaded_at TIMESTAMP,
  UNIQUE(tweet_id, orig_url)
);

CREATE TABLE IF NOT EXISTS digests (
  date DATE PRIMARY KEY,
  kol_count INTEGER,
  tweet_count INTEGER,
  summary_md TEXT,
  layer2_json TEXT,
  model TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER,
  status TEXT DEFAULT 'ok',
  generated_at TIMESTAMP,
  published_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fetch_runs (
  id INTEGER PRIMARY KEY,
  started_at TIMESTAMP,
  finished_at TIMESTAMP,
  trigger TEXT,
  kols_total INTEGER,
  kols_ok INTEGER,
  kols_failed INTEGER,
  tweets_new INTEGER,
  error_log TEXT
);
"""


_DB_PATH: Path | None = None


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_db_path() -> Path:
    env_path = os.getenv("KOL_MONITOR_DB")
    if env_path:
        return Path(env_path)
    from kol_monitor.config import settings

    return Path(settings.db_path)


def _connect(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path else (_DB_PATH or _default_db_path())
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def init_db(path: str | Path | None = None) -> None:
    global _DB_PATH
    _DB_PATH = Path(path) if path else _default_db_path()
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect(_DB_PATH) as conn:
        conn.executescript(SCHEMA)
        _normalize_existing_tweet_dates(conn)


def upsert_kol(
    screen_name: str,
    display_name: str | None = None,
    twitter_user_id: str | None = None,
) -> int:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO kols (screen_name, display_name, twitter_user_id)
            VALUES (?, ?, ?)
            ON CONFLICT(screen_name) DO UPDATE SET
              display_name = COALESCE(excluded.display_name, kols.display_name),
              twitter_user_id = COALESCE(excluded.twitter_user_id, kols.twitter_user_id),
              active = 1,
              inactive_reason = NULL
            """,
            (screen_name, display_name, twitter_user_id),
        )
        row = conn.execute("SELECT id FROM kols WHERE screen_name = ?", (screen_name,)).fetchone()
    if row is None:
        raise DatabaseError(f"failed to upsert KOL: {screen_name}")
    return int(row["id"])


def sync_config_kols(handles: list[str]) -> None:
    for handle in handles:
        upsert_kol(handle)


def get_kol(screen_name: str) -> dict[str, Any] | None:
    with _connect() as conn:
        return _row(conn.execute("SELECT * FROM kols WHERE screen_name = ?", (screen_name,)).fetchone())


def get_kol_by_id(kol_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        return _row(conn.execute("SELECT * FROM kols WHERE id = ?", (kol_id,)).fetchone())


def get_tweet(tweet_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        return _row(conn.execute("SELECT * FROM tweets WHERE tweet_id = ?", (tweet_id,)).fetchone())


def list_active_kols() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM kols WHERE active = 1 ORDER BY lower(screen_name)").fetchall()
    return [dict(row) for row in rows]


def list_incomplete_kols() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM kols WHERE active = 1 AND incomplete = 1 ORDER BY lower(screen_name)"
        ).fetchall()
    return [dict(row) for row in rows]


def update_kol_anchor(
    kol_id: int,
    last_seen_tweet_id: str | None,
    last_fetched_at: datetime | str | None,
    incomplete: bool,
) -> None:
    fetched_at = _as_iso(last_fetched_at) if last_fetched_at else _utcnow()
    with _connect() as conn:
        if last_seen_tweet_id is None:
            conn.execute(
                """
                UPDATE kols
                SET last_fetched_at = ?, incomplete = ?
                WHERE id = ?
                """,
                (fetched_at, int(incomplete), kol_id),
            )
        else:
            conn.execute(
                """
                UPDATE kols
                SET last_seen_tweet_id = ?, last_fetched_at = ?, incomplete = ?
                WHERE id = ?
                """,
                (str(last_seen_tweet_id), fetched_at, int(incomplete), kol_id),
            )


def mark_kol_inactive(screen_name: str, reason: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE kols SET active = 0, inactive_reason = ? WHERE screen_name = ?",
            (reason, screen_name),
        )


def _as_iso(value: Any) -> str:
    if value is None:
        return _utcnow()
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).isoformat()
    except ValueError:
        pass
    try:
        return datetime.strptime(text, "%a %b %d %H:%M:%S %z %Y").isoformat()
    except ValueError:
        pass
    return text


def _normalize_existing_tweet_dates(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT tweet_id, created_at
        FROM tweets
        WHERE created_at IS NOT NULL
          AND created_at NOT LIKE '____-__-__T%'
        """
    ).fetchall()
    for row in rows:
        normalized = _as_iso(row["created_at"])
        if normalized != row["created_at"]:
            conn.execute(
                "UPDATE tweets SET created_at = ? WHERE tweet_id = ?",
                (normalized, row["tweet_id"]),
            )


def _bool(value: Any) -> int:
    return int(bool(value))


def _tweet_id(tweet: dict[str, Any]) -> str:
    value = tweet.get("tweet_id") or tweet.get("id") or tweet.get("id_str")
    if value is None:
        raise DatabaseError("tweet is missing id/tweet_id")
    return str(value)


def _tweet_screen_name(tweet: dict[str, Any]) -> str | None:
    return tweet.get("screen_name") or tweet.get("userScreenName") or tweet.get("user_screen_name")


def _normalize_tweet(tweet: dict[str, Any]) -> dict[str, Any]:
    tweet_id = _tweet_id(tweet)
    screen_name = _tweet_screen_name(tweet)
    url = tweet.get("url")
    if not url and screen_name:
        url = f"https://x.com/{screen_name}/status/{tweet_id}"
    return {
        "tweet_id": tweet_id,
        "kol_id": tweet.get("kol_id"),
        "text": tweet.get("text") or tweet.get("full_text") or "",
        "created_at": _as_iso(tweet.get("created_at") or tweet.get("createdAt")),
        "language": tweet.get("language") or tweet.get("lang"),
        "is_retweet": _bool(tweet.get("is_retweet") or tweet.get("isRetweet")),
        "is_quote": _bool(tweet.get("is_quote") or tweet.get("isQuote")),
        "is_reply": _bool(tweet.get("is_reply") or tweet.get("isReply")),
        "conversation_id": tweet.get("conversation_id") or tweet.get("conversationId"),
        "reply_count": tweet.get("reply_count") or tweet.get("replyCount") or 0,
        "retweet_count": tweet.get("retweet_count") or tweet.get("retweetCount") or 0,
        "favorite_count": tweet.get("favorite_count") or tweet.get("favoriteCount") or 0,
        "view_count": tweet.get("view_count") or tweet.get("viewCount") or 0,
        "quote_count": tweet.get("quote_count") or tweet.get("quoteCount") or 0,
        "url": url,
        "raw_json": json.dumps(tweet, ensure_ascii=False, default=str),
        "fetched_at": _utcnow(),
    }


def insert_tweet(tweet_dict: dict[str, Any]) -> bool:
    tweet = _normalize_tweet(tweet_dict)
    if tweet["kol_id"] is None:
        screen_name = _tweet_screen_name(tweet_dict)
        if not screen_name:
            raise DatabaseError("tweet needs kol_id or screen_name")
        tweet["kol_id"] = upsert_kol(screen_name)

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO tweets (
              tweet_id, kol_id, text, created_at, language, is_retweet, is_quote, is_reply,
              conversation_id, reply_count, retweet_count, favorite_count, view_count,
              quote_count, url, raw_json, fetched_at
            )
            VALUES (
              :tweet_id, :kol_id, :text, :created_at, :language, :is_retweet, :is_quote,
              :is_reply, :conversation_id, :reply_count, :retweet_count, :favorite_count,
              :view_count, :quote_count, :url, :raw_json, :fetched_at
            )
            """,
            tweet,
        )
        inserted = cur.rowcount == 1
        if inserted:
            _mark_digest_stale_for_tweet(conn, tweet["created_at"])
        for item in tweet_dict.get("media") or []:
            insert_media_row(conn, tweet["tweet_id"], item)
    return inserted


def _mark_digest_stale_for_tweet(conn: sqlite3.Connection, created_at: str) -> None:
    report_date = _report_date_for_timestamp(created_at)
    conn.execute(
        """
        UPDATE digests
        SET status = 'stale'
        WHERE date = ?
          AND status <> 'stale'
        """,
        (report_date,),
    )


def _report_date_for_timestamp(value: Any) -> str:
    from kol_monitor.config import settings

    parsed = datetime.fromisoformat(_as_iso(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    report_timezone = ZoneInfo(settings.schedule.timezone)
    local_time = parsed.astimezone(report_timezone)
    cutoff = datetime.combine(
        local_time.date(),
        time(settings.schedule.hour, settings.schedule.minute),
        tzinfo=report_timezone,
    )
    report_date = local_time.date()
    if local_time > cutoff:
        report_date += timedelta(days=1)
    return report_date.isoformat()


def insert_media_row(conn: sqlite3.Connection, tweet_id: str, media: dict[str, Any]) -> None:
    orig_url = media.get("orig_url") or media.get("url")
    if not orig_url:
        return
    conn.execute(
        """
        INSERT OR IGNORE INTO media (tweet_id, type, orig_url, thumb_url)
        VALUES (?, ?, ?, ?)
        """,
        (
            tweet_id,
            media.get("type") or "photo",
            orig_url,
            media.get("thumb_url") or media.get("thumbUrl"),
        ),
    )


def insert_media(tweet_id: str, media: dict[str, Any]) -> None:
    with _connect() as conn:
        insert_media_row(conn, tweet_id, media)


def report_window_bounds(date: str) -> tuple[str, str]:
    from kol_monitor.config import settings

    report_date = datetime.strptime(date, "%Y-%m-%d").date()
    report_timezone = ZoneInfo(settings.schedule.timezone)
    window_end = datetime.combine(
        report_date,
        time(settings.schedule.hour, settings.schedule.minute),
        tzinfo=report_timezone,
    )
    window_start = window_end - timedelta(days=1)
    return (
        window_start.astimezone(timezone.utc).isoformat(),
        window_end.astimezone(timezone.utc).isoformat(),
    )


def tweets_on_date(date: str) -> list[dict[str, Any]]:
    window_start, window_end = report_window_bounds(date)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT tweets.*, kols.screen_name
            FROM tweets
            JOIN kols ON kols.id = tweets.kol_id
            WHERE julianday(tweets.created_at) > julianday(?)
              AND julianday(tweets.created_at) <= julianday(?)
            ORDER BY tweets.created_at DESC, CAST(tweets.tweet_id AS INTEGER) DESC
            """,
            (window_start, window_end),
        ).fetchall()
    return [dict(row) for row in rows]


def tweets_by_kol_on_date(kol_id: int, date: str) -> list[dict[str, Any]]:
    window_start, window_end = report_window_bounds(date)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT tweets.*, kols.screen_name
            FROM tweets
            JOIN kols ON kols.id = tweets.kol_id
            WHERE tweets.kol_id = ?
              AND julianday(tweets.created_at) > julianday(?)
              AND julianday(tweets.created_at) <= julianday(?)
            ORDER BY tweets.created_at DESC, CAST(tweets.tweet_id AS INTEGER) DESC
            """,
            (kol_id, window_start, window_end),
        ).fetchall()
    return [dict(row) for row in rows]


def pending_media_for_date(date: str) -> list[dict[str, Any]]:
    window_start, window_end = report_window_bounds(date)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT media.*, tweets.created_at, kols.screen_name
            FROM media
            JOIN tweets ON tweets.tweet_id = media.tweet_id
            JOIN kols ON kols.id = tweets.kol_id
            WHERE julianday(tweets.created_at) > julianday(?)
              AND julianday(tweets.created_at) <= julianday(?)
              AND media.download_status = 'pending'
            ORDER BY tweets.created_at DESC, media.id
            """,
            (window_start, window_end),
        ).fetchall()
    return [dict(row) for row in rows]


def downloaded_media_for_date(date: str) -> list[dict[str, Any]]:
    window_start, window_end = report_window_bounds(date)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT media.*, tweets.created_at, kols.screen_name
            FROM media
            JOIN tweets ON tweets.tweet_id = media.tweet_id
            JOIN kols ON kols.id = tweets.kol_id
            WHERE julianday(tweets.created_at) > julianday(?)
              AND julianday(tweets.created_at) <= julianday(?)
              AND media.download_status = 'done'
              AND media.local_path IS NOT NULL
            ORDER BY tweets.created_at DESC, media.id
            """,
            (window_start, window_end),
        ).fetchall()
    return [dict(row) for row in rows]


def mark_media_downloaded(media_id: int, local_path: str | Path) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE media
            SET local_path = ?, download_status = 'done', downloaded_at = ?
            WHERE id = ?
            """,
            (str(local_path), _utcnow(), media_id),
        )


def mark_media_failed(media_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE media SET download_status = 'failed' WHERE id = ?", (media_id,))


def save_digest(
    date: str,
    summary_md: str,
    layer2_json: str,
    kol_count: int,
    tweet_count: int,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    status: str = "ok",
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO digests (
              date, kol_count, tweet_count, summary_md, layer2_json, model,
              input_tokens, output_tokens, status, generated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
              kol_count = excluded.kol_count,
              tweet_count = excluded.tweet_count,
              summary_md = excluded.summary_md,
              layer2_json = excluded.layer2_json,
              model = excluded.model,
              input_tokens = excluded.input_tokens,
              output_tokens = excluded.output_tokens,
              status = excluded.status,
              generated_at = excluded.generated_at
            """,
            (
                date,
                kol_count,
                tweet_count,
                summary_md,
                layer2_json,
                model,
                input_tokens,
                output_tokens,
                status,
                _utcnow(),
            ),
        )


def get_digest(date: str) -> dict[str, Any] | None:
    with _connect() as conn:
        return _row(conn.execute("SELECT * FROM digests WHERE date = ?", (date,)).fetchone())


def mark_digest_published(date: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE digests SET published_at = ? WHERE date = ?", (_utcnow(), date))


def start_run(trigger: str, kols_total: int = 0) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO fetch_runs (started_at, trigger, kols_total) VALUES (?, ?, ?)",
            (_utcnow(), trigger, kols_total),
        )
        return int(cur.lastrowid)


def finish_run(
    run_id: int,
    kols_ok: int,
    kols_failed: int,
    tweets_new: int,
    error_log: str = "",
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE fetch_runs
            SET finished_at = ?, kols_ok = ?, kols_failed = ?, tweets_new = ?, error_log = ?
            WHERE id = ?
            """,
            (_utcnow(), kols_ok, kols_failed, tweets_new, error_log, run_id),
        )
