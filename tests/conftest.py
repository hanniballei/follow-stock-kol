from __future__ import annotations

import os
import tempfile

import pytest

from kol_monitor.db import init_db


@pytest.fixture
def tmp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("KOL_MONITOR_DB", path)
    init_db(path)
    yield path
    os.unlink(path)


@pytest.fixture
def sample_tweet():
    return {
        "id": "1800000000000000001",
        "text": "$NVDA earnings tonight, watching for guidance",
        "createdAt": "2026-05-29T18:00:00Z",
        "language": "en",
        "userScreenName": "qinbafrank",
        "userIdStr": "12345",
        "retweetCount": 5,
        "favoriteCount": 50,
        "replyCount": 3,
        "quoteCount": 1,
        "viewCount": 2000,
        "isReply": False,
        "isQuote": False,
        "media": [
            {
                "type": "photo",
                "url": "https://pbs.twimg.com/media/abc.jpg",
                "thumbUrl": "https://pbs.twimg.com/media/abc.jpg:thumb",
            }
        ],
        "urls": [],
        "mentions": [],
    }


@pytest.fixture
def make_tweet(sample_tweet):
    base_id = 1800000000000000000
    counter = {"i": 0}

    def _make(handle="qinbafrank", text="hello", offset=None, **overrides):
        counter["i"] += 1
        tid = base_id + (offset if offset is not None else counter["i"])
        return {
            **sample_tweet,
            "id": str(tid),
            "userScreenName": handle,
            "text": text,
            **overrides,
        }

    return _make
