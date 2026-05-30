from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kol_monitor.summarizer import call_claude_with_retry, parse_layer2, summarize_one_kol


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


@pytest.mark.asyncio
async def test_call_claude_uses_fallback_client(monkeypatch):
    class FakeClient:
        def __init__(self, api_key, base_url):
            self.api_key = api_key
            self.base_url = base_url
            self.messages = SimpleNamespace(create=AsyncMock(side_effect=self._create))

        async def _create(self, **kwargs):
            if self.api_key == "primary":
                raise RuntimeError("primary failed")
            return SimpleNamespace(content=[SimpleNamespace(text="ok")])

    monkeypatch.setattr("kol_monitor.summarizer._client", None)
    monkeypatch.setattr("kol_monitor.summarizer.AsyncAnthropic", FakeClient)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_api_key", "primary")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_base_url", "https://same.example")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fallback_api_key", "fallback")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fallback_base_url", "https://same.example")

    response = await call_claude_with_retry(
        messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        max_tokens=10,
    )

    assert response.content[0].text == "ok"


def test_build_layer1_prompt_includes_trump_section():
    from kol_monitor.summarizer import build_layer1_prompt

    prompt = build_layer1_prompt(
        [{"screen_name": "qinbafrank", "tweet_count": 1, "core_view": "x", "bullets": [], "sentiment": "neutral"}],
        trump_summary={
            "screen_name": "realDonaldTrump",
            "tweet_count": 2,
            "core_view": "tariff talk",
            "bullets": [],
            "sentiment": "neutral",
        },
    )

    text = prompt[0]["content"][0]["text"]
    assert "特朗普相关" in text
    assert "realDonaldTrump" in text
