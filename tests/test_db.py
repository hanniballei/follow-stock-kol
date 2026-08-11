from __future__ import annotations

from datetime import datetime, timezone

from kol_monitor.db import (
    downloaded_media_for_date,
    get_digest,
    get_kol,
    init_db,
    insert_tweet,
    list_active_kols,
    pending_media_for_date,
    report_window_bounds,
    save_digest,
    mark_media_downloaded,
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
    assert len(tweets_on_date("2026-05-30")) == 1
    media = pending_media_for_date("2026-05-30")
    assert len(media) == 1
    assert media[0]["orig_url"] == "https://pbs.twimg.com/media/abc.jpg"

    mark_media_downloaded(media[0]["id"], "/tmp/sample.jpg")
    downloaded = downloaded_media_for_date("2026-05-30")
    assert len(downloaded) == 1
    assert downloaded[0]["screen_name"] == "qinbafrank"
    assert downloaded[0]["local_path"] == "/tmp/sample.jpg"


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

    tweets = tweets_on_date("2026-05-31")
    assert len(tweets) == 1
    assert tweets[0]["created_at"] == "2026-05-30T13:00:00+00:00"


def test_new_tweet_marks_existing_digest_stale_but_duplicate_does_not(tmp_db, sample_tweet):
    kid = upsert_kol("qinbafrank")
    save_digest(
        date="2026-05-30",
        summary_md="summary",
        layer2_json="[]",
        kol_count=0,
        tweet_count=0,
        model="test",
    )

    assert insert_tweet({**sample_tweet, "kol_id": kid}) is True
    assert get_digest("2026-05-30")["status"] == "stale"

    save_digest(
        date="2026-05-30",
        summary_md="updated",
        layer2_json="[]",
        kol_count=1,
        tweet_count=1,
        model="test",
    )
    assert insert_tweet({**sample_tweet, "kol_id": kid}) is False
    assert get_digest("2026-05-30")["status"] == "ok"


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

    tweets = tweets_on_date("2026-05-31")
    assert len(tweets) == 1
    assert tweets[0]["created_at"] == "2026-05-30T14:00:00+00:00"


def test_report_window_uses_configured_shanghai_schedule():
    assert report_window_bounds("2026-05-30") == (
        "2026-05-29T12:30:00+00:00",
        "2026-05-30T12:30:00+00:00",
    )


def test_report_window_handles_mixed_offsets_and_boundaries(tmp_db, sample_tweet):
    kid = upsert_kol("qinbafrank")
    timestamps = [
        ("101", "2026-05-29T12:30:00+00:00"),
        ("102", "2026-05-29T12:30:01+00:00"),
        ("103", "2026-05-30T20:29:59+08:00"),
        ("104", "2026-05-30T20:30:00+08:00"),
        ("105", "2026-05-30T20:30:01+08:00"),
    ]
    for tweet_id, created_at in timestamps:
        insert_tweet(
            {
                **sample_tweet,
                "id": tweet_id,
                "kol_id": kid,
                "createdAt": created_at,
            }
        )

    tweets = tweets_on_date("2026-05-30")
    assert {tweet["tweet_id"] for tweet in tweets} == {"102", "103", "104"}
    assert {row["tweet_id"] for row in pending_media_for_date("2026-05-30")} == {
        "102",
        "103",
        "104",
    }


def test_anchor_update_and_active_filter(tmp_db):
    kid = upsert_kol("qinbafrank")

    update_kol_anchor(kid, "1800000000000000050", datetime.now(timezone.utc), incomplete=False)

    row = get_kol("qinbafrank")
    assert row["last_seen_tweet_id"] == "1800000000000000050"
    assert row["incomplete"] == 0
    assert [kol["screen_name"] for kol in list_active_kols()] == ["qinbafrank"]
