from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kol_monitor.db import get_kol, update_kol_anchor, upsert_kol
from kol_monitor.fetcher import backfill_incomplete, fetch_one_kol


class FakeClient:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = 0
        self.search_calls = 0
        self.search_result = []

    async def user_tweets(self, username, max_results=50, **kwargs):
        idx = min(self.calls, len(self.pages) - 1)
        self.calls += 1
        return self.pages[idx]

    async def search(self, **kwargs):
        self.search_calls += 1
        return self.search_result


@pytest.mark.asyncio
async def test_first_time_fetch_inserts_all(tmp_db, make_tweet):
    upsert_kol("qinbafrank")
    kol = get_kol("qinbafrank")
    client = FakeClient(
        pages=[[make_tweet(offset=10), make_tweet(offset=11), make_tweet(offset=12)]]
    )

    res = await fetch_one_kol(client, kol)

    assert res.inserted == 3
    assert res.incomplete is False
    assert get_kol("qinbafrank")["last_seen_tweet_id"] == str(1800000000000000012)


@pytest.mark.asyncio
async def test_first_time_fetch_accepts_prefixed_numeric_ids(tmp_db, make_tweet):
    upsert_kol("realDonaldTrump")
    kol = get_kol("realDonaldTrump")
    client = FakeClient(
        pages=[
            [
                make_tweet(
                    handle="realDonaldTrump",
                    id="truth_1780116388200996844",
                ),
                make_tweet(
                    handle="realDonaldTrump",
                    id="truth_1780116388200996847",
                ),
            ]
        ]
    )

    res = await fetch_one_kol(client, kol)

    assert res.inserted == 2
    assert res.incomplete is False
    assert get_kol("realDonaldTrump")["last_seen_tweet_id"] == "truth_1780116388200996847"


@pytest.mark.asyncio
async def test_incremental_with_overlap(tmp_db, make_tweet):
    upsert_kol("qinbafrank")
    update_kol_anchor(
        get_kol("qinbafrank")["id"],
        str(1800000000000000100),
        datetime.now(timezone.utc),
        incomplete=False,
    )
    kol = get_kol("qinbafrank")
    client = FakeClient(
        pages=[
            [
                make_tweet(offset=102),
                make_tweet(offset=101),
                make_tweet(offset=100),
                make_tweet(offset=99),
            ]
        ]
    )

    res = await fetch_one_kol(client, kol)

    assert res.inserted == 2
    assert res.incomplete is False
    assert get_kol("qinbafrank")["last_seen_tweet_id"] == str(1800000000000000102)


@pytest.mark.asyncio
async def test_incremental_fetch_accepts_prefixed_numeric_anchor(tmp_db, make_tweet):
    upsert_kol("realDonaldTrump")
    update_kol_anchor(
        get_kol("realDonaldTrump")["id"],
        "truth_1780116388200996844",
        datetime.now(timezone.utc),
        incomplete=False,
    )
    kol = get_kol("realDonaldTrump")
    client = FakeClient(
        pages=[
            [
                make_tweet(handle="realDonaldTrump", id="truth_1780116388200996847"),
                make_tweet(handle="realDonaldTrump", id="truth_1780116388200996844"),
            ]
        ]
    )

    res = await fetch_one_kol(client, kol)

    assert res.inserted == 1
    assert res.incomplete is False
    assert get_kol("realDonaldTrump")["last_seen_tweet_id"] == "truth_1780116388200996847"


@pytest.mark.asyncio
async def test_no_overlap_marks_incomplete(tmp_db, make_tweet):
    upsert_kol("qinbafrank")
    update_kol_anchor(
        get_kol("qinbafrank")["id"],
        str(1800000000000000050),
        datetime.now(timezone.utc),
        incomplete=False,
    )
    kol = get_kol("qinbafrank")
    pages = [[make_tweet(offset=200 + round_idx * 10 + i) for i in range(10)] for round_idx in range(5)]
    client = FakeClient(pages=pages)

    res = await fetch_one_kol(client, kol)

    assert res.incomplete is True
    assert get_kol("qinbafrank")["incomplete"] == 1


@pytest.mark.asyncio
async def test_search_backfill_clears_incomplete(tmp_db, make_tweet):
    upsert_kol("qinbafrank")
    kid = get_kol("qinbafrank")["id"]
    update_kol_anchor(kid, str(1800000000000000050), datetime.now(timezone.utc), incomplete=True)
    client = FakeClient(pages=[])
    client.search_result = [make_tweet(offset=51), make_tweet(offset=52)]

    await backfill_incomplete(client)

    after = get_kol("qinbafrank")
    assert after["incomplete"] == 0
    assert after["last_seen_tweet_id"] == str(1800000000000000052)
    assert client.search_calls == 1
