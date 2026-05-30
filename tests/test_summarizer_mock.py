from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kol_monitor.summarizer import parse_layer2, summarize_one_kol


def test_parse_clean_json():
    res = parse_layer2('{"core_view":"x","bullets":[],"sentiment":"neutral"}')
    assert res["sentiment"] == "neutral"


def test_parse_markdown_fenced():
    raw = '```json\n{"core_view":"x","bullets":[],"sentiment":"bullish"}\n```'
    assert parse_layer2(raw)["sentiment"] == "bullish"


def test_parse_text_with_prelude():
    raw = '好的，我来分析：\n\n{"core_view":"x","bullets":[],"sentiment":"bearish"}\n\n说明'
    assert parse_layer2(raw)["sentiment"] == "bearish"


def test_parse_invalid_returns_none():
    assert parse_layer2("totally not json") is None


@pytest.mark.asyncio
async def test_summarize_one_kol_builds_message(monkeypatch):
    fake = SimpleNamespace()
    fake.messages = SimpleNamespace(
        create=AsyncMock(
            return_value=SimpleNamespace(
                content=[
                    SimpleNamespace(text='{"core_view":"v","bullets":[],"sentiment":"neutral"}')
                ],
                usage=SimpleNamespace(input_tokens=100, output_tokens=20),
            )
        )
    )
    monkeypatch.setattr("kol_monitor.summarizer._client", fake)

    res = await summarize_one_kol(
        kol={"screen_name": "qinbafrank", "id": 1},
        tweets=[
            {
                "tweet_id": "1",
                "text": "hi",
                "url": "https://x.com/qinbafrank/status/1",
                "favorite_count": 1,
                "retweet_count": 0,
            }
        ],
        media_files=[],
    )

    assert res["sentiment"] == "neutral"
    assert res["input_tokens"] == 100
    fake.messages.create.assert_called_once()
