from __future__ import annotations

from datetime import datetime, timezone

from kol_monitor.db import (
    get_kol,
    init_db,
    insert_tweet,
    list_active_kols,
    pending_media_for_date,
    tweets_on_date,
    update_kol_anchor,
    upsert_kol,
)


def test_upsert_and_get_kol(tmp_db):
    kid = upsert_kol("qinbafrank")

    assert kid > 0
    assert upsert_kol("qinbafrank", display_name="秦伯") == kid
    row = get_kol("qinbafrank")
    assert row["display_name"] == "秦伯"


def test_insert_tweet_idempotent_and_media(tmp_db, sample_tweet):
    kid = upsert_kol("qinbafrank")

    inserted1 = insert_tweet({**sample_tweet, "kol_id": kid})
    inserted2 = insert_tweet({**sample_tweet, "kol_id": kid})

    assert inserted1 is True
    assert inserted2 is False
    assert len(tweets_on_date("2026-05-29")) == 1
    media = pending_media_for_date("2026-05-29")
    assert len(media) == 1
    assert media[0]["orig_url"] == "https://pbs.twimg.com/media/abc.jpg"


def test_insert_tweet_normalizes_twitter_created_at(tmp_db, sample_tweet):
    kid = upsert_kol("qinbafrank")

    insert_tweet(
        {
            **sample_tweet,
            "id": "1800000000000000099",
            "kol_id": kid,
            "createdAt": "Sat May 30 13:00:00 +0000 2026",
        }
    )

    tweets = tweets_on_date("2026-05-30")
    assert len(tweets) == 1
    assert tweets[0]["created_at"] == "2026-05-30T13:00:00+00:00"


def test_init_db_normalizes_existing_twitter_created_at(tmp_db, sample_tweet):
    kid = upsert_kol("qinbafrank")
    import sqlite3

    with sqlite3.connect(tmp_db) as conn:
        conn.execute(
            """
            INSERT INTO tweets (tweet_id, kol_id, text, created_at, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "1800000000000000100",
                kid,
                "hello",
                "Sat May 30 14:00:00 +0000 2026",
                "2026-05-30T14:00:01+00:00",
            ),
        )

    init_db(tmp_db)

    tweets = tweets_on_date("2026-05-30")
    assert len(tweets) == 1
    assert tweets[0]["created_at"] == "2026-05-30T14:00:00+00:00"


def test_anchor_update_and_active_filter(tmp_db):
    kid = upsert_kol("qinbafrank")

    update_kol_anchor(kid, "1800000000000000050", datetime.now(timezone.utc), incomplete=False)

    row = get_kol("qinbafrank")
    assert row["last_seen_tweet_id"] == "1800000000000000050"
    assert row["incomplete"] == 0
    assert [kol["screen_name"] for kol in list_active_kols()] == ["qinbafrank"]
