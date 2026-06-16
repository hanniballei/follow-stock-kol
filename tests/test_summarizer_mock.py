from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kol_monitor.summarizer import (
    _anthropic_sdk_base_url,
    _clean_layer1_markdown,
    _fallback_layer1_markdown,
    _is_valid_layer1_markdown,
    _line_has_suspicious_model_company_conflict,
    _layer2_needs_chinese_retry,
    _layer2_prompt,
    _normalize_layer2_result,
    _response_text,
    call_claude_with_retry,
    build_layer1_prompt,
    normalize_layer1_source_links,
    parse_layer2,
    summarize_one_kol,
    summarize_day,
)


def test_parse_clean_json():
    res = parse_layer2('{"core_view":"x","bullets":[],"sentiment":"neutral"}')
    assert res["sentiment"] == "neutral"


def test_parse_markdown_fenced():
    raw = '```json\n{"core_view":"x","bullets":[],"sentiment":"bullish"}\n```'
    assert parse_layer2(raw)["sentiment"] == "bullish"


def test_parse_text_with_prelude():
    raw = '好的，我来分析：\n\n{"core_view":"x","bullets":[],"sentiment":"bearish"}\n\n说明'
    assert parse_layer2(raw)["sentiment"] == "bearish"


def test_parse_layer2_repairs_unescaped_quotes_in_point():
    raw = '''```json
{
  "core_view": "特朗普聚焦政策争议",
  "bullets": [
    {
      "point": "法院要求撤除"TRUMP"冠名，特朗普批评项目被阻挠",
      "tickers": [],
      "tweet_url": "https://x.com/realDonaldTrump/status/truth_1"
    },
    {
      "point": "强调"小费免税"政策不会被废除",
      "tickers": [],
      "tweet_url": "https://x.com/realDonaldTrump/status/truth_2"
    }
  ],
  "sentiment": "neutral"
}
```'''

    parsed = parse_layer2(raw)

    assert parsed is not None
    assert parsed["core_view"] == "特朗普聚焦政策争议"
    assert parsed["sentiment"] == "neutral"
    assert parsed["bullets"][0]["point"] == '法院要求撤除"TRUMP"冠名，特朗普批评项目被阻挠'
    assert parsed["bullets"][1]["tweet_url"].endswith("truth_2")


def test_parse_invalid_returns_none():
    assert parse_layer2("totally not json") is None


def test_fallback_layer1_markdown_keeps_sections_sources_and_tickers():
    md = _fallback_layer1_markdown(
        [
            {
                "screen_name": "realDonaldTrump",
                "tweet_count": 2,
                "core_view": "关税与产业政策表态",
                "bullets": [
                    {
                        "point": "提到汽车关税可能影响整车厂",
                        "tickers": ["TSLA", "$F"],
                        "tweet_url": "https://x.com/realDonaldTrump/status/truth_1",
                    }
                ],
                "sentiment": "neutral",
            },
            {
                "screen_name": "macroKOL",
                "tweet_count": 1,
                "core_view": "AI 资本开支仍是主线",
                "bullets": [
                    {
                        "point": "继续看好 AI 算力链需求",
                        "tickers": ["nvda"],
                        "tweet_url": "https://x.com/macroKOL/status/1",
                    }
                ],
                "sentiment": "bullish",
            },
        ],
        trump_summary={
            "screen_name": "realDonaldTrump",
            "tweet_count": 2,
            "core_view": "关税与产业政策表态",
            "bullets": [
                {
                    "point": "提到汽车关税可能影响整车厂",
                    "tickers": ["TSLA", "$F"],
                    "tweet_url": "https://x.com/realDonaldTrump/status/truth_1",
                }
            ],
            "sentiment": "neutral",
        },
    )

    assert "## 特朗普相关" in md
    assert "## 今日关键词" in md
    assert "## 产业/个股焦点" in md
    assert "[@realDonaldTrump 原文](https://x.com/realDonaldTrump/status/truth_1)" in md
    assert "[@macroKOL](https://x.com/macroKOL/status/1)" in md
    assert "$TSLA" in md
    assert "$F" in md
    assert "$NVDA" in md


def test_layer1_validation_accepts_complete_digest():
    md = """## 特朗普相关

- 暂无直接市场信号。

## 今日关键词

- AI 算力、非农、关税

## 重要新闻

- $NVDA 供应链需求仍强。[@kol](https://x.com/kol/status/1)

## 宏观判断

- 非农数据偏强但消费信心走弱。[@macro](https://x.com/macro/status/1)

## 产业/个股焦点

- $MU 存储涨价线索继续发酵。[@kol](https://x.com/kol/status/2)

## 交易信号

| 标的 | 线索 | 来源 |
|---|---|---|
| $MU | DRAM 涨价 | [@kol](https://x.com/kol/status/2) |

## 投资理念

- 高共识方向要控制仓位。[@macro](https://x.com/macro/status/2)
"""

    assert _is_valid_layer1_markdown(md) is True


def test_layer1_validation_rejects_missing_required_sections():
    md = """## 特朗普相关

- 暂无直接市场信号。

## 今日关键词

- AI 算力

## 重要新闻

- $NVDA 需求仍强。

## 宏观判断

- 原油库存逼近"操作性

## 各 KOL 详细总结
"""

    assert _is_valid_layer1_markdown(md) is False


def test_layer1_validation_rejects_truncated_ending():
    md = """## 特朗普相关

- 暂无直接市场信号。

## 今日关键词

- AI 算力

## 重要新闻

- $NVDA 需求仍强。

## 宏观判断

- 非农数据偏强。

## 产业/个股焦点

- $MU 存储涨价。

## 交易信号

- $SPY 关注关键位置。

## 投资理念

- 霍尔木兹海峡持续中断正快速消耗全球原油缓冲库存，库存逼近"操作性
"""

    assert _is_valid_layer1_markdown(md) is False


@pytest.mark.asyncio
async def test_summarize_day_saves_digest_when_layer1_fails(monkeypatch):
    saved = {}

    monkeypatch.setattr(
        "kol_monitor.summarizer.db.tweets_on_date",
        lambda _date: [
            {
                "screen_name": "macroKOL",
                "kol_id": 1,
                "tweet_id": "1",
                "text": "AI demand supports NVDA",
                "url": "https://x.com/macroKOL/status/1",
            }
        ],
    )

    async def fake_summarize_one_kol(kol, tweets, media_files):
        return {
            "screen_name": kol["screen_name"],
            "tweet_count": len(tweets),
            "core_view": "AI 需求仍强",
            "bullets": [
                {
                    "point": "AI 算力需求支撑",
                    "tickers": ["NVDA"],
                    "tweet_url": "https://x.com/macroKOL/status/1",
                }
            ],
            "sentiment": "bullish",
            "input_tokens": 10,
            "output_tokens": 5,
        }

    async def fake_layer1(*_args, **_kwargs):
        raise RuntimeError("all layer1 backends failed")

    def fake_save_digest(**kwargs):
        saved.update(kwargs)

    monkeypatch.setattr("kol_monitor.summarizer.summarize_one_kol", fake_summarize_one_kol)
    monkeypatch.setattr("kol_monitor.summarizer.call_layer1_with_validation", fake_layer1)
    monkeypatch.setattr("kol_monitor.summarizer.db.save_digest", fake_save_digest)

    result = await summarize_day("2026-06-02")

    assert "本地兜底模板" in saved["summary_md"]
    assert "[@macroKOL](https://x.com/macroKOL/status/1)" in saved["summary_md"]
    assert "$NVDA" in saved["summary_md"]
    assert saved["kol_count"] == 1
    assert saved["tweet_count"] == 1
    assert result["summary_md"] == saved["summary_md"]


@pytest.mark.asyncio
async def test_summarize_day_uses_fallback_when_layer1_is_incomplete(monkeypatch):
    saved = {}

    monkeypatch.setattr(
        "kol_monitor.summarizer.db.tweets_on_date",
        lambda _date: [
            {
                "screen_name": "macroKOL",
                "kol_id": 1,
                "tweet_id": "1",
                "text": "AI demand supports NVDA",
                "url": "https://x.com/macroKOL/status/1",
            }
        ],
    )

    async def fake_summarize_one_kol(kol, tweets, media_files):
        return {
            "screen_name": kol["screen_name"],
            "tweet_count": len(tweets),
            "core_view": "AI 需求仍强",
            "bullets": [
                {
                    "point": "AI 算力需求支撑",
                    "tickers": ["NVDA"],
                    "tweet_url": "https://x.com/macroKOL/status/1",
                }
            ],
            "sentiment": "bullish",
            "input_tokens": 10,
            "output_tokens": 5,
        }

    async def incomplete_layer1(*_args, **_kwargs):
        return SimpleNamespace(
            content=[
                SimpleNamespace(
                    text=(
                        "## 特朗普相关\n\n- 暂无。\n\n"
                        "## 今日关键词\n\n- AI。\n\n"
                        "## 重要新闻\n\n- $NVDA 需求仍强。\n\n"
                        "## 宏观判断\n\n- 库存逼近\"操作性"
                    )
                )
            ],
            usage=SimpleNamespace(input_tokens=100, output_tokens=4000),
        )

    def fake_save_digest(**kwargs):
        saved.update(kwargs)

    monkeypatch.setattr("kol_monitor.summarizer.summarize_one_kol", fake_summarize_one_kol)
    monkeypatch.setattr("kol_monitor.summarizer.call_layer1_with_validation", incomplete_layer1)
    monkeypatch.setattr("kol_monitor.summarizer.db.save_digest", fake_save_digest)

    result = await summarize_day("2026-06-09")

    assert "本地兜底模板" in saved["summary_md"]
    assert "## 产业/个股焦点" in saved["summary_md"]
    assert "## 投资理念" in saved["summary_md"]
    assert "$NVDA" in saved["summary_md"]
    assert result["summary_md"] == saved["summary_md"]


@pytest.mark.asyncio
async def test_summarize_day_saves_digest_when_layer2_and_layer1_fail(monkeypatch):
    saved = {}

    monkeypatch.setattr(
        "kol_monitor.summarizer.db.tweets_on_date",
        lambda _date: [
            {
                "screen_name": "macroKOL",
                "kol_id": 1,
                "tweet_id": "1",
                "text": "NVDA demand strong while $TSLA lags",
                "url": "https://x.com/macroKOL/status/1",
            }
        ],
    )

    async def failing_summarize_one_kol(*_args, **_kwargs):
        raise RuntimeError("all layer2 backends failed")

    async def failing_layer1(*_args, **_kwargs):
        raise RuntimeError("all layer1 backends failed")

    def fake_save_digest(**kwargs):
        saved.update(kwargs)

    monkeypatch.setattr("kol_monitor.summarizer.summarize_one_kol", failing_summarize_one_kol)
    monkeypatch.setattr("kol_monitor.summarizer.call_layer1_with_validation", failing_layer1)
    monkeypatch.setattr("kol_monitor.summarizer.db.save_digest", fake_save_digest)

    result = await summarize_day("2026-06-02")

    assert "NVDA demand strong" in saved["summary_md"]
    assert "$NVDA" in saved["summary_md"]
    assert "$TSLA" in saved["summary_md"]
    assert saved["kol_count"] == 1
    assert saved["tweet_count"] == 1
    assert result["layer2"][0]["core_view"].startswith("NVDA demand")


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
async def test_summarize_one_kol_uses_next_backend_when_json_parse_fails(monkeypatch):
    events = []

    class FakeClient:
        def __init__(self, api_key, base_url):
            self.api_key = api_key
            self.base_url = base_url
            self.messages = SimpleNamespace(create=AsyncMock(side_effect=self._create))

        async def _create(self, **kwargs):
            events.append(self.api_key)
            if self.api_key == "primary":
                return SimpleNamespace(content=[SimpleNamespace(text="not json")])
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        text='{"core_view":"fallback ok","bullets":[],"sentiment":"neutral"}'
                    )
                ],
                usage=SimpleNamespace(input_tokens=10, output_tokens=5),
            )

    monkeypatch.setattr("kol_monitor.summarizer._client", None)
    monkeypatch.setattr("kol_monitor.summarizer.AsyncAnthropic", FakeClient)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_api_key", "primary")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_base_url", "https://primary.example")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fallback_api_key", "fallback")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fallback_base_url", "https://fallback.example")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_third_api_key", None)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fourth_api_key", None, raising=False)

    res = await summarize_one_kol(
        kol={"screen_name": "realDonaldTrump", "id": 1},
        tweets=[
            {
                "tweet_id": "truth_1",
                "text": "Policy comments",
                "url": "https://x.com/realDonaldTrump/status/truth_1",
                "favorite_count": 1,
                "retweet_count": 0,
            }
        ],
        media_files=[],
    )

    assert events == ["primary", "primary", "fallback"]
    assert res["core_view"] == "fallback ok"
    assert res["input_tokens"] == 10


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
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_third_api_key", None)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fourth_api_key", None, raising=False)

    response = await call_claude_with_retry(
        messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        max_tokens=10,
    )

    assert response.content[0].text == "ok"


@pytest.mark.asyncio
async def test_call_claude_falls_through_to_third_client(monkeypatch):
    events = []

    class FakeClient:
        def __init__(self, api_key, base_url):
            self.api_key = api_key
            self.base_url = base_url
            self.messages = SimpleNamespace(create=AsyncMock(side_effect=self._create))

        async def _create(self, **kwargs):
            events.append(
                (
                    self.api_key,
                    self.base_url,
                    kwargs["model"],
                    kwargs["temperature"],
                    kwargs.get("thinking"),
                )
            )
            if self.api_key != "third":
                raise RuntimeError(f"{self.api_key} failed")
            return SimpleNamespace(content=[SimpleNamespace(text="ok-third")])

    monkeypatch.setattr("kol_monitor.summarizer._client", None)
    monkeypatch.setattr("kol_monitor.summarizer.AsyncAnthropic", FakeClient)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_api_key", "primary")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_base_url", "https://primary.example")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fallback_api_key", "fallback")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fallback_base_url", "https://fallback.example")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_third_api_key", "third")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_third_base_url", "https://third.example")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_third_model", "anthropic/claude-sonnet-4.6")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fourth_api_key", None, raising=False)

    response = await call_claude_with_retry(
        messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        max_tokens=10,
    )

    assert response.content[0].text == "ok-third"
    assert [event[0] for event in events] == ["primary", "fallback", "third"]
    assert events[0][2] == "claude-sonnet-4-6"
    assert events[0][3] == 0.3
    assert events[1][2] == "claude-sonnet-4-6"
    assert events[1][3] == 0.3
    assert events[2][1] == "https://third.example"
    assert events[2][2] == "anthropic/claude-sonnet-4.6"
    assert events[2][3] == 1
    assert events[2][4] == {"type": "disabled"}


@pytest.mark.asyncio
async def test_third_backend_retries_temperature_thinking_error_with_provider_defaults(monkeypatch):
    events = []

    class FakeClient:
        def __init__(self, api_key, base_url):
            self.api_key = api_key
            self.base_url = base_url
            self.messages = SimpleNamespace(create=AsyncMock(side_effect=self._create))

        async def _create(self, **kwargs):
            events.append(
                (
                    self.api_key,
                    kwargs.get("temperature", "missing"),
                    kwargs.get("thinking"),
                )
            )
            if kwargs.get("thinking") == {"type": "disabled"}:
                raise RuntimeError(
                    "ValidationException: `temperature` may only be set to 1 "
                    "when thinking is enabled or in adaptive mode."
                )
            return SimpleNamespace(content=[SimpleNamespace(text="ok-defaults")])

    monkeypatch.setattr("kol_monitor.summarizer._client", None)
    monkeypatch.setattr("kol_monitor.summarizer.AsyncAnthropic", FakeClient)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_api_key", None)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fallback_api_key", None)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_third_api_key", "third")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_third_base_url", "https://third.example")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_third_model", "anthropic/claude-sonnet-4.6")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fourth_api_key", None, raising=False)

    response = await call_claude_with_retry(
        messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        max_tokens=10,
    )

    assert response.content[0].text == "ok-defaults"
    assert events == [
        ("third", 1, {"type": "disabled"}),
        ("third", "missing", None),
    ]


@pytest.mark.asyncio
async def test_call_claude_falls_through_to_fourth_client(monkeypatch):
    events = []

    class FakeClient:
        def __init__(self, api_key, base_url):
            self.api_key = api_key
            self.base_url = base_url
            self.messages = SimpleNamespace(create=AsyncMock(side_effect=self._create))

        async def _create(self, **kwargs):
            events.append(
                (
                    self.api_key,
                    self.base_url,
                    kwargs["model"],
                    kwargs["temperature"],
                    kwargs.get("thinking"),
                )
            )
            if self.api_key != "fourth":
                raise RuntimeError(f"{self.api_key} failed")
            return SimpleNamespace(content=[SimpleNamespace(text="ok-fourth")])

    monkeypatch.setattr("kol_monitor.summarizer._client", None)
    monkeypatch.setattr("kol_monitor.summarizer.AsyncAnthropic", FakeClient)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_api_key", "primary")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_base_url", "https://primary.example")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fallback_api_key", "fallback")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fallback_base_url", "https://fallback.example")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_third_api_key", "third")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_third_base_url", "https://third.example")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_third_model", "anthropic/claude-sonnet-4.6")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fourth_api_key", "fourth", raising=False)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fourth_base_url", "https://fourth.example", raising=False)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fourth_model", "claude-sonnet-4-6", raising=False)

    response = await call_claude_with_retry(
        messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        max_tokens=10,
    )

    assert response.content[0].text == "ok-fourth"
    assert [event[0] for event in events] == ["primary", "fallback", "fourth"]
    assert events[2][1] == "https://fourth.example"
    assert events[2][2] == "claude-sonnet-4-6"
    assert events[2][3] == 0.3
    assert events[2][4] is None


@pytest.mark.asyncio
async def test_call_claude_uses_third_after_fourth_fails(monkeypatch):
    events = []

    class FakeClient:
        def __init__(self, api_key, base_url):
            self.api_key = api_key
            self.base_url = base_url
            self.messages = SimpleNamespace(create=AsyncMock(side_effect=self._create))

        async def _create(self, **kwargs):
            events.append(
                (
                    self.api_key,
                    self.base_url,
                    kwargs["model"],
                    kwargs["temperature"],
                    kwargs.get("thinking"),
                )
            )
            if self.api_key != "third":
                raise RuntimeError(f"{self.api_key} failed")
            return SimpleNamespace(content=[SimpleNamespace(text="ok-third")])

    monkeypatch.setattr("kol_monitor.summarizer._client", None)
    monkeypatch.setattr("kol_monitor.summarizer.AsyncAnthropic", FakeClient)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_api_key", "primary")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_base_url", "https://primary.example")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fallback_api_key", "fallback")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fallback_base_url", "https://fallback.example")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_third_api_key", "third")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_third_base_url", "https://third.example")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_third_model", "anthropic/claude-sonnet-4.6")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fourth_api_key", "fourth", raising=False)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fourth_base_url", "https://fourth.example", raising=False)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fourth_model", "claude-sonnet-4-6", raising=False)

    response = await call_claude_with_retry(
        messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        max_tokens=10,
    )

    assert response.content[0].text == "ok-third"
    assert [event[0] for event in events] == ["primary", "fallback", "fourth", "third"]
    assert events[2][1] == "https://fourth.example"
    assert events[2][3] == 0.3
    assert events[2][4] is None
    assert events[3][1] == "https://third.example"
    assert events[3][2] == "anthropic/claude-sonnet-4.6"
    assert events[3][3] == 1
    assert events[3][4] == {"type": "disabled"}


def test_anthropic_sdk_base_url_keeps_clean_provider_root():
    assert _anthropic_sdk_base_url("https://third.example") == "https://third.example"
    assert _anthropic_sdk_base_url("https://third.example/v1") == "https://third.example"


def test_response_text_uses_text_blocks_after_thinking_blocks():
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking="hidden"),
            SimpleNamespace(type="text", text="正文一"),
            SimpleNamespace(type="text", text="正文二"),
        ]
    )

    assert _response_text(response) == "正文一\n正文二"


def test_build_layer1_prompt_includes_trump_section():
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
    assert "$TSLA" in text
    assert "不要使用 [来源]" in text
    assert "[@screen_name]" in text
    assert "总长度控制在 1800-2600 汉字" in text


def test_layer2_prompt_requires_dollar_ticker_display():
    text = _layer2_prompt(
        {"screen_name": "qinbafrank"},
        [{"text": "NVDA earnings", "favorite_count": 1, "retweet_count": 0, "url": "https://x.com/a/status/1"}],
        had_media=False,
    )

    assert "$NVDA" in text
    assert "tickers" in text


def test_normalize_layer1_source_links_uses_handles():
    md = (
        "- **$SIVE** 管道增长 77%。[来源](https://x.com/aleabitoreddit/status/1)\n"
        "| $NVDA | 多 | 调仓砸盘 | [链接](https://x.com/ArtofSpecuycky/status/2) |\n"
        "- 多条来源：[来源1](https://x.com/jukan05/status/3) [来源2](https://x.com/jukan05/status/4)\n"
        "- 特朗普本人：[原文](https://x.com/realDonaldTrump/status/truth_1)\n"
        "[阅读今日完整报告](digests/2026/05/30.md)"
    )

    normalized = normalize_layer1_source_links(md)

    assert "[@aleabitoreddit](https://x.com/aleabitoreddit/status/1)" in normalized
    assert "[@ArtofSpecuycky](https://x.com/ArtofSpecuycky/status/2)" in normalized
    assert "[@jukan05 · 1](https://x.com/jukan05/status/3)" in normalized
    assert "[@jukan05 · 2](https://x.com/jukan05/status/4)" in normalized
    assert "[@realDonaldTrump 原文](https://x.com/realDonaldTrump/status/truth_1)" in normalized
    assert "[阅读今日完整报告](digests/2026/05/30.md)" in normalized
    assert "[来源]" not in normalized
    assert "[链接]" not in normalized


def test_clean_layer1_markdown_removes_internal_artifacts_and_unlinked_sources():
    md = (
        "## 投资理念\n\n"
        "- 有效来源保留 [@qinbafrank](https://x.com/qinbafrank/status/1)\n"
        "- **调查先于行动**：读代码再下判断，确认系统行为后再做决策 [@investigate_before_answering 原则]\n"
        "- **失败两次应诊断根因而非增量修补**：持续探索不同路径，放弃需求特性是最后手段\n"
        "- 没有 URL 的伪来源应删除 [@fake_source]\n"
        "普通正文提到 @realDonaldTrump 但不是来源标签"
    )

    cleaned = _clean_layer1_markdown(md)

    assert "有效来源保留" in cleaned
    assert "https://x.com/qinbafrank/status/1" in cleaned
    assert "investigate_before_answering" not in cleaned
    assert "诊断根因" not in cleaned
    assert "@fake_source" not in cleaned
    assert "普通正文提到 @realDonaldTrump" in cleaned


def test_clean_layer1_markdown_removes_unsourced_key_section_bullets_and_fills_empty():
    md = (
        "## 今日关键词\n\n"
        "- 可以无链接\n\n"
        "## 重要新闻\n\n"
        "- 无来源新闻应删除\n\n"
        "## 宏观判断\n\n"
        "- 有来源宏观保留 [@macro](https://x.com/macro/status/1)\n\n"
        "## 投资理念\n\n"
        "- 无来源理念应删除"
    )

    cleaned = _clean_layer1_markdown(md)

    assert "- 可以无链接" in cleaned
    assert "无来源新闻应删除" not in cleaned
    assert "无来源理念应删除" not in cleaned
    assert "- 暂无有来源的高质量信号。" in cleaned
    assert "有来源宏观保留" in cleaned


def test_clean_layer1_markdown_removes_suspicious_model_company_conflicts():
    md = (
        "## 重要新闻\n\n"
        "- OpenAI计划6月23日发布claude-sonnet-4-6。"
        "[@kol](https://x.com/kol/status/1)\n\n"
        "## 宏观判断\n\n"
        "- 作者认为通胀影响收益率。[@macro](https://x.com/macro/status/1)"
    )

    cleaned = _clean_layer1_markdown(md)

    assert "OpenAI计划" not in cleaned
    assert "claude-sonnet-4-6" not in cleaned
    assert "- 暂无有来源的高质量信号。" in cleaned
    assert "通胀影响收益率" in cleaned


def test_clean_layer1_markdown_removes_non_chinese_residue_and_empty_table():
    md = (
        "## 交易信号\n\n"
        "| 标的 | 线索 | 来源 |\n"
        "|---|---|---|\n"
        "| $000660 | 100조 주주환원 추진 단독보도 | "
        "[@bees](https://x.com/bees/status/1) |\n"
    )

    cleaned = _clean_layer1_markdown(md)

    assert "주주환원" not in cleaned
    assert "| 标的 |" in cleaned
    assert "- 暂无有来源的高质量信号。" in cleaned


def test_normalize_layer2_result_filters_missing_urls_and_defaults_metadata():
    parsed = {
        "core_view": "作者看多半导体",
        "sentiment": "excited",
        "bullets": [
            {
                "point": "作者认为 $NVDA 需求强",
                "tickers": ["$nvda"],
                "tweet_url": "https://x.com/a/status/1",
            },
            {"point": "没有来源", "tickers": ["TSLA"]},
        ],
    }

    normalized = _normalize_layer2_result(parsed)

    assert normalized["sentiment"] == "unclear"
    assert len(normalized["bullets"]) == 1
    assert normalized["bullets"][0]["tickers"] == ["NVDA"]
    assert normalized["bullets"][0]["claim_type"] == "opinion"
    assert normalized["bullets"][0]["confidence"] == "medium"


def test_normalize_layer2_result_filters_non_chinese_and_company_conflict():
    parsed = {
        "core_view": "OpenAI计划发布claude-sonnet-4-6",
        "sentiment": "neutral",
        "bullets": [
            {
                "point": "OpenAI计划发布claude-sonnet-4-6",
                "tickers": ["AI"],
                "tweet_url": "https://x.com/a/status/1",
            },
            {
                "point": "$000660 100조 주주환원 추진 단독보도",
                "tickers": ["000660"],
                "tweet_url": "https://x.com/a/status/2",
            },
            {
                "point": "作者称 $NVDA 需求仍强",
                "tickers": ["NVDA"],
                "tweet_url": "https://x.com/a/status/3",
            },
        ],
    }

    normalized = _normalize_layer2_result(parsed)

    assert _line_has_suspicious_model_company_conflict(
        "OpenAI计划6月23日发布claude-sonnet-4-6"
    )
    assert not _line_has_suspicious_model_company_conflict(
        "作者比较 OpenAI 与 Claude 在代码任务上的差异"
    )
    assert normalized["core_view"] == "作者称 $NVDA 需求仍强"
    assert len(normalized["bullets"]) == 1
    assert normalized["bullets"][0]["tickers"] == ["NVDA"]


def test_layer2_needs_chinese_retry_detects_hangul_points():
    assert _layer2_needs_chinese_retry(
        {
            "core_view": "SK하이닉스 주주환원 단독보도",
            "bullets": [{"point": "이란 합의로 유가 급락"}],
        }
    )
    assert not _layer2_needs_chinese_retry(
        {"core_view": "作者认为存储板块走强", "bullets": [{"point": "作者称 $MU 需求强"}]}
    )
