from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kol_monitor.summarizer import (
    _llm_backends,
    _llm_sdk_base_url,
    _clean_layer1_markdown,
    _expand_tco_urls,
    _fallback_layer1_markdown,
    _is_valid_layer1_markdown,
    _line_has_suspicious_model_company_conflict,
    _layer1_symbol_validation_error,
    _layer2_needs_chinese_retry,
    _layer2_prompt,
    _layer2_symbol_validation_error,
    _sanitize_layer2_symbols_to_sources,
    _source_market_symbols,
    _normalize_layer2_result,
    _prepare_layer1_markdown,
    _response_text,
    _usage_input_tokens,
    _validate_layer2_response,
    call_llm_with_retry,
    build_layer1_prompt,
    normalize_layer1_source_links,
    parse_layer2,
    settings,
    summarize_one_kol,
    _ground_layer2_sources,
    _layer1_source_validation_error,
    summarize_day,
)


@pytest.fixture(autouse=True)
def disable_deepseek_backend_by_default(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", None, raising=False)


def test_parse_clean_json():
    res = parse_layer2('{"core_view":"x","bullets":[],"sentiment":"neutral"}')
    assert res["sentiment"] == "neutral"


def test_parse_markdown_fenced():
    raw = '```json\n{"core_view":"x","bullets":[],"sentiment":"bullish"}\n```'
    assert parse_layer2(raw)["sentiment"] == "bullish"


def test_parse_text_with_prelude():
    raw = '好的，我来分析：\n\n{"core_view":"x","bullets":[],"sentiment":"bearish"}\n\n说明'
    assert parse_layer2(raw)["sentiment"] == "bearish"


def test_ground_layer2_sources_repairs_handle_and_drops_unknown_id():
    parsed = {
        "bullets": [
            {
                "point": "作者认为 $NVDA 需求强",
                "tweet_url": "https://x.com/wrong/status/123",
            },
            {
                "point": "作者认为 $AMD 需求强",
                "tweet_url": "https://x.com/right/status/999",
            },
        ]
    }
    tweets = [
        {
            "screen_name": "right",
            "tweet_id": "123",
            "url": "https://x.com/right/status/123",
        }
    ]

    grounded = _ground_layer2_sources(parsed, tweets)

    assert grounded["bullets"] == [
        {
            "point": "作者认为 $NVDA 需求强",
            "tweet_url": "https://x.com/right/status/123",
        }
    ]


def test_layer1_source_validation_requires_exact_layer2_url():
    layer2 = [
        {
            "bullets": [
                {
                    "point": "作者认为 $NVDA 需求强",
                    "tweet_url": "https://x.com/right/status/123",
                }
            ]
        }
    ]

    assert _layer1_source_validation_error(
        "- [@right](https://x.com/right/status/123)", layer2
    ) is None
    assert "expected https://x.com/right/status/123" in _layer1_source_validation_error(
        "- [@wrong](https://x.com/wrong/status/123)", layer2
    )
    assert "not found in layer2" in _layer1_source_validation_error(
        "- [@right](https://x.com/right/status/999)", layer2
    )


@pytest.mark.asyncio
async def test_summarize_day_retries_layer1_source_mismatch(monkeypatch):
    saved = {}
    calls = {"count": 0}
    correct_url = "https://x.com/macroKOL/status/1"

    monkeypatch.setattr(
        "kol_monitor.summarizer.db.tweets_on_date",
        lambda _date: [
            {
                "screen_name": "macroKOL",
                "kol_id": 1,
                "tweet_id": "1",
                "text": "$NVDA demand supports AI",
                "url": correct_url,
            }
        ],
    )
    monkeypatch.setattr("kol_monitor.summarizer.db.downloaded_media_for_date", lambda _date: [])

    async def fake_summarize_one_kol(*_args, **_kwargs):
        return {
            "screen_name": "macroKOL",
            "tweet_count": 1,
            "core_view": "作者认为 $NVDA 需求仍强",
            "bullets": [
                {
                    "point": "作者认为 $NVDA 需求仍强",
                    "tickers": ["NVDA"],
                    "tweet_url": correct_url,
                    "claim_type": "opinion",
                }
            ],
            "sentiment": "bullish",
            "input_tokens": 10,
            "output_tokens": 5,
        }

    def layer1(url: str) -> str:
        return (
            "## 特朗普相关\n\n- 暂无高质量信号。\n\n"
            "## 今日关键词\n\n- AI\n\n"
            f"## 重要新闻\n\n- 作者认为需求强 [@macroKOL]({url})\n\n"
            f"## 宏观判断\n\n- 作者认为需求强 [@macroKOL]({url})\n\n"
            f"## 产业/个股焦点\n\n- 作者认为 $NVDA 需求强 [@macroKOL]({url})\n\n"
            "## 交易信号\n\n| 标的 | 线索 | 来源 |\n|---|---|---|\n"
            f"| $NVDA | 需求强 | [@macroKOL]({url}) |\n\n"
            f"## 投资理念\n\n- 作者认为长期持有更重要 [@macroKOL]({url})。"
        )

    async def fake_layer1(*_args, **_kwargs):
        calls["count"] += 1
        url = "https://x.com/wrong/status/1" if calls["count"] == 1 else correct_url
        return SimpleNamespace(
            content=[SimpleNamespace(text=layer1(url))],
            usage=SimpleNamespace(input_tokens=100, output_tokens=100),
            stop_reason="end_turn",
        )

    monkeypatch.setattr("kol_monitor.summarizer.summarize_one_kol", fake_summarize_one_kol)
    monkeypatch.setattr("kol_monitor.summarizer.call_layer1_with_validation", fake_layer1)
    monkeypatch.setattr("kol_monitor.summarizer.db.save_digest", lambda **kwargs: saved.update(kwargs))

    await summarize_day("2026-06-02")

    assert calls["count"] == 2
    assert "https://x.com/wrong/status/1" not in saved["summary_md"]
    assert correct_url in saved["summary_md"]


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


def test_prepare_layer1_markdown_normalizes_plain_paragraph_layout_and_punctuation():
    md = """## 特朗普相关

[@realDonaldTrump 原文](https://x.com/realDonaldTrump/status/truth_1) 称美股很好,油价下降。[@kol](https://x.com/kol/status/2) 认为 $INTC 受益;但仍需观察。

## 今日关键词

AI, 半导体

## 重要新闻

[@kol](https://x.com/kol/status/3) 称供应链紧张,价格上涨。

## 宏观判断

[@macro](https://x.com/macro/status/1) 认为利率仍是核心变量,但不影响长期趋势。

## 产业/个股焦点

[@kol](https://x.com/kol/status/4) 称 $NVDA 需求仍强。

## 交易信号

| 标的 | 线索 | 来源 |
|---|---|---|
| $NVDA | 需求仍强,关注回调 | [@kol](https://x.com/kol/status/4) |

## 投资理念

[@macro](https://x.com/macro/status/2) 认为不要因短期波动破坏系统。
"""

    prepared = _prepare_layer1_markdown(md)

    assert "- [@realDonaldTrump 原文](https://x.com/realDonaldTrump/status/truth_1)" in prepared
    assert "- [@kol](https://x.com/kol/status/2)" in prepared
    assert "- AI， 半导体" in prepared
    assert "很好，油价下降" in prepared
    assert "受益；但仍需观察" in prepared
    assert "需求仍强，关注回调" in prepared


def test_prepare_layer1_markdown_drops_model_horizontal_rules():
    prepared = _prepare_layer1_markdown(
        "## 今日关键词\n\n- AI\n\n---\n\n## 重要新闻\n\n"
        "- 作者称需求强 [@foo](https://x.com/foo/status/1)"
    )

    assert "- ---" not in prepared
    assert "\n---\n" not in prepared


def test_prepare_layer1_markdown_fixes_boe_ticker_only_in_jingdongfang_context():
    prepared = _prepare_layer1_markdown(
        "## 产业/个股焦点\n\n"
        "- $BOE（京东方 A）获机构调研 [@foo](https://x.com/foo/status/1)\n"
        "- 美股 $BOE 保持原样 [@bar](https://x.com/bar/status/2)"
    )

    assert "$000725（京东方 A）" in prepared
    assert "美股 $BOE 保持原样" in prepared


def test_expand_tco_urls_uses_raw_json_display_url_when_provider_key_differs():
    tweet = {
        "raw_json": json.dumps(
            {"urls": [{"url": "https://t.co/other", "displayUrl": "Z.ai"}]}
        )
    }

    assert _expand_tco_urls("Zhipu https://t.co/opaque and Minimax", tweet) == "Zhipu Z.ai and Minimax"


def test_prepare_layer1_markdown_keeps_parenthetical_source_links_together():
    md = """## 特朗普相关

[@realDonaldTrump](https://x.com/realDonaldTrump/status/1) 当天推文聚焦军事行动，未直接涉及股市。不过，模型事件被多位 KOL 提及（[@nft_hu](https://x.com/nft_hu/status/2) [@LinQingV](https://x.com/LinQingV/status/3)），部分观点认为可能影响 AI 硬件链；[@jukan05](https://x.com/jukan05/status/4) 强调该事件引发主权 AI 竞赛。

## 今日关键词

- AI

## 重要新闻

- 作者认为 $NVDA 强势 [@foo](https://x.com/foo/status/123)

## 宏观判断

- 作者认为流动性仍是核心变量 [@foo](https://x.com/foo/status/124)

## 产业/个股焦点

- 作者认为 $MU 需求仍强 [@foo](https://x.com/foo/status/125)

## 交易信号

| 标的 | 线索 | 来源 |
|---|---|---|
| $NVDA | 强势延续 | [@foo](https://x.com/foo/status/126) |

## 投资理念

- 作者认为长期持有优于频繁交易 [@foo](https://x.com/foo/status/127)
"""

    prepared = _prepare_layer1_markdown(md)

    assert "- [@nft_hu](https://x.com/nft_hu/status/2)" not in prepared
    assert "- [@LinQingV](https://x.com/LinQingV/status/3)" not in prepared
    assert "（[@nft_hu](https://x.com/nft_hu/status/2) [@LinQingV](https://x.com/LinQingV/status/3)）" in prepared
    assert "- [@jukan05](https://x.com/jukan05/status/4)" in prepared


def test_llm_backends_use_requested_priority(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "deepseek-key", raising=False)
    monkeypatch.setattr(
        settings,
        "deepseek_base_url",
        "https://api.deepseek.example/anthropic",
        raising=False,
    )
    monkeypatch.setattr(settings, "deepseek_model", "deepseek-v4-pro", raising=False)
    monkeypatch.setattr(settings, "deepseek_reasoning_effort", "max", raising=False)
    monkeypatch.setattr(settings, "anthropic_api_key", "primary-key", raising=False)
    monkeypatch.setattr(settings, "anthropic_base_url", "https://primary.example/v1", raising=False)
    monkeypatch.setattr(settings, "anthropic_fallback_api_key", "fallback-key", raising=False)
    monkeypatch.setattr(settings, "anthropic_fallback_base_url", "https://fallback.example/v1", raising=False)
    monkeypatch.setattr(settings, "anthropic_fourth_api_key", "fourth-key", raising=False)
    monkeypatch.setattr(settings, "anthropic_fourth_base_url", "https://fourth.example/v1", raising=False)
    monkeypatch.setattr(settings, "anthropic_fourth_model", "fourth-model", raising=False)
    monkeypatch.setattr(settings, "anthropic_third_api_key", "third-key", raising=False)
    monkeypatch.setattr(settings, "anthropic_third_base_url", "https://third.example/v1", raising=False)
    monkeypatch.setattr(settings, "anthropic_third_model", "third-model", raising=False)

    backends = _llm_backends()

    assert [backend.label for backend in backends] == [
        "deepseek",
        "fallback",
        "fourth",
        "third",
        "primary",
    ]
    assert [backend.model for backend in backends] == [
        "deepseek-v4-pro",
        settings.ai.model,
        "fourth-model",
        "third-model",
        settings.ai.model,
    ]
    assert backends[0].temperature is None
    assert backends[0].thinking == {"type": "enabled", "budget_tokens": 1024}
    assert backends[0].output_config == {"effort": "max"}
    assert backends[0].timeout_seconds == 10800
    assert backends[0].max_tokens_cap is None
    assert backends[3].temperature == 1
    assert backends[3].thinking == {"type": "disabled"}
    assert all(backend.max_tokens_cap == 8000 for backend in backends[1:])


def test_layer2_validation_rejects_truncation_even_when_json_is_parseable():
    response = SimpleNamespace(
        content=[
            SimpleNamespace(
                text='{"core_view":"x","bullets":[],"sentiment":"neutral"}'
            )
        ],
        stop_reason="max_tokens",
    )

    parsed, error = _validate_layer2_response(response)

    assert parsed is None
    assert error == "response stopped at max_tokens"


def test_layer2_symbol_validation_uses_source_scope():
    tweets = [
        {
            "text": "Samsung Electronics (005930), Bitcoin $BTC, and C3.ai stock $AI",
            "url": "https://x.com/a/status/1",
        },
        {
            "text": "NVIDIA discussed DRAM, GPT, FDA, SK, LG, SHS, SHHS, BIT, GOLD, MSCI, KOSPI and PTFE; I and A are prose",
            "url": "https://x.com/a/status/2",
        },
        {
            "text": "Barrick $GOLD and MSCI stock $MSCI moved higher",
            "url": "https://x.com/a/status/3",
        },
    ]
    valid = {
        "bullets": [
            {
                "point": "作者关注三星电子 $005930、$BTC 和 C3.ai $AI。",
                "tickers": ["005930", "BTC", "AI"],
                "tweet_url": "https://x.com/a/status/1",
            }
        ]
    }
    inferred = {
        "bullets": [
            {
                "point": "作者关注 $NVDA、$DRAM、$GPT、$FDA、$SK、$LG、$SHS、$SHHS、$BIT、$GOLD、$MSCI、$KOSPI、$PTFE、$I 和 $A。",
                "tickers": [
                    "NVDA",
                    "DRAM",
                    "GPT",
                    "FDA",
                    "SK",
                    "LG",
                    "SHS",
                    "SHHS",
                    "BIT",
                    "GOLD",
                    "MSCI",
                    "KOSPI",
                    "PTFE",
                    "I",
                    "A",
                ],
                "tweet_url": "https://x.com/a/status/2",
            },
            {
                "point": "作者关注 $GOLD 和 $MSCI。",
                "tickers": ["GOLD", "MSCI"],
                "tweet_url": "https://x.com/a/status/3",
            }
        ]
    }

    assert _layer2_symbol_validation_error(valid, tweets) is None
    error = _layer2_symbol_validation_error(inferred, tweets)
    assert "NVDA" in error
    assert "DRAM" in error
    assert "GPT" in error
    assert "FDA" in error
    assert "SHHS" in error
    assert "BIT" in error
    assert "GOLD" in error
    assert "MSCI" in error
    assert "KOSPI" in error
    assert "PTFE" in error


def test_source_symbols_keep_explicit_year_like_codes_and_ignore_parenthetical_words():
    tweets = [
        {
            "text": "$2027 rallied after results (earnings), while $AI also moved",
            "url": "https://x.com/a/status/1",
        }
    ]
    parsed = {
        "core_view": "作者关注 $2027 和 $AI",
        "bullets": [
            {
                "point": "作者称 $2027 和 $AI 上涨",
                "tickers": ["2027", "AI"],
                "tweet_url": "https://x.com/a/status/1",
            }
        ],
    }

    assert _layer2_symbol_validation_error(parsed, tweets) is None
    assert _source_market_symbols(tweets[0]) == {"2027", "AI"}
    assert _source_market_symbols({"text": "FABLE, NATO, MAGA, NYSE and OPEC"}) == set()
    assert _source_market_symbols(
        {"text": "BUY NOW, TURN ON AI, BE CAREFUL, APP and ARM"}
    ) == set()
    assert _source_market_symbols(
        {"text": "$NOW $ON $BE $APP $ARM are explicit symbols"}
    ) == {"NOW", "ON", "BE", "APP", "ARM"}
    assert _source_market_symbols(
        {"text": "BTC ETH SPX VIX remain unambiguous short symbols"}
    ) == {"BTC", "ETH", "SPX", "VIX"}


def test_layer2_symbol_postprocessing_closes_translation_boundary():
    tweets = [
        {
            "text": "NVIDIA discussed DRAM supply without a stock symbol",
            "url": "https://x.com/a/status/1",
        }
    ]
    parsed = {
        "core_view": "作者关注 $NVDA",
        "bullets": [
            {
                "point": "翻译步骤补入了 $NVDA 和 $DRAM",
                "tickers": ["NVDA", "DRAM"],
                "tweet_url": "https://x.com/a/status/1",
            }
        ],
    }

    sanitized = _sanitize_layer2_symbols_to_sources(parsed, tweets)

    assert sanitized["core_view"] == "无市场相关内容"
    assert sanitized["bullets"] == []
    assert _layer2_symbol_validation_error(sanitized, tweets) is None


def test_layer2_symbol_postprocessing_formats_allowed_bare_symbols():
    tweets = [
        {
            "text": "NVDA and Samsung Electronics (005930) moved higher",
            "url": "https://x.com/a/status/1",
        }
    ]
    parsed = {
        "core_view": "NVDA 与 005930 走强",
        "bullets": [
            {
                "point": "NVDA 与三星电子（005930）走强",
                "tickers": ["NVDA", "005930"],
                "tweet_url": "https://x.com/a/status/1",
            }
        ],
    }

    assert _layer2_symbol_validation_error(parsed, tweets) is None
    assert "missing_dollar_display" in _layer2_symbol_validation_error(
        parsed, tweets, require_dollar_display=True
    )

    sanitized = _sanitize_layer2_symbols_to_sources(parsed, tweets)

    assert sanitized["core_view"] == "$NVDA 与 $005930 走强"
    assert sanitized["bullets"][0]["point"] == "$NVDA 与三星电子（$005930）走强"
    assert sanitized["bullets"][0]["tickers"] == ["005930", "NVDA"]
    assert (
        _layer2_symbol_validation_error(
            sanitized, tweets, require_dollar_display=True
        )
        is None
    )


def test_layer1_symbol_validation_is_scoped_to_cited_sources():
    layer2 = [
        {
            "bullets": [
                {
                    "point": "作者关注英伟达，但原推没有代码。",
                    "tickers": [],
                    "tweet_url": "https://x.com/a/status/1",
                },
                {
                    "point": "作者关注 $BTC。",
                    "tickers": ["BTC"],
                    "tweet_url": "https://x.com/a/status/2",
                },
            ]
        }
    ]

    assert _layer1_symbol_validation_error(
        "- 英伟达需求强 [@a](https://x.com/a/status/1)", layer2
    ) is None
    assert "NVDA" in _layer1_symbol_validation_error(
        "- $NVDA 需求强 [@a](https://x.com/a/status/1)", layer2
    )
    assert _layer1_symbol_validation_error(
        "- $BTC 走强 [@a](https://x.com/a/status/2)", layer2
    ) is None
    assert _layer1_symbol_validation_error(
        "- NATO 与 OPEC 成为焦点 [@a](https://x.com/a/status/1)", layer2
    ) is None
    assert "NVDA" in _layer1_symbol_validation_error("- 今日关键词：$NVDA", layer2)
    assert "NVDA" in _layer1_symbol_validation_error("- 今日关键词：NVDA", layer2)


def test_layer1_symbol_validation_rejects_bare_numeric_codes():
    layer2 = [
        {
            "bullets": [
                {
                    "point": "作者关注三星电子 $005930。",
                    "tickers": ["005930"],
                    "tweet_url": "https://x.com/a/status/1",
                }
            ]
        }
    ]

    error = _layer1_symbol_validation_error(
        "- 三星电子（005930）需求强 [@a](https://x.com/a/status/1)", layer2
    )

    assert "005930" in error


def test_usage_input_tokens_includes_automatic_cache_tokens():
    usage = SimpleNamespace(
        input_tokens=10,
        cache_read_input_tokens=20,
        cache_creation_input_tokens=30,
    )

    assert _usage_input_tokens(usage) == 60


@pytest.mark.asyncio
async def test_summarize_day_respects_layer2_concurrency(monkeypatch):
    active = 0
    peak = 0

    monkeypatch.setattr(settings.ai, "layer2_concurrency", 2)
    monkeypatch.setattr(
        "kol_monitor.summarizer.db.tweets_on_date",
        lambda _date: [
            {
                "screen_name": f"kol{index}",
                "kol_id": index,
                "tweet_id": str(index),
                "text": "market update",
                "url": f"https://x.com/kol{index}/status/{index}",
            }
            for index in range(4)
        ],
    )
    monkeypatch.setattr(
        "kol_monitor.summarizer.db.downloaded_media_for_date", lambda _date: []
    )

    async def fake_summarize(kol, tweets, media_files):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {
            "screen_name": kol["screen_name"],
            "tweet_count": len(tweets),
            "core_view": "无市场相关内容",
            "bullets": [],
            "sentiment": "unclear",
            "input_tokens": 1,
            "output_tokens": 1,
        }

    async def failing_layer1(*_args, **_kwargs):
        raise RuntimeError("force local fallback")

    monkeypatch.setattr("kol_monitor.summarizer.summarize_one_kol", fake_summarize)
    monkeypatch.setattr(
        "kol_monitor.summarizer.call_layer1_with_validation", failing_layer1
    )
    monkeypatch.setattr("kol_monitor.summarizer.db.save_digest", lambda **_kwargs: None)

    await summarize_day("2026-09-01")

    assert peak == 2


@pytest.mark.asyncio
async def test_summarize_day_saves_digest_when_layer1_fails(monkeypatch, tmp_path):
    saved = {}
    image_path = tmp_path / "chart.jpg"
    image_path.write_bytes(b"image")

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
    monkeypatch.setattr(
        "kol_monitor.summarizer.db.downloaded_media_for_date",
        lambda _date: [{"screen_name": "macroKOL", "local_path": str(image_path)}],
    )

    async def fake_summarize_one_kol(kol, tweets, media_files):
        assert media_files == [image_path]
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
    monkeypatch.setattr(
        "kol_monitor.summarizer.db.downloaded_media_for_date", lambda _date: []
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
    monkeypatch.setattr(
        "kol_monitor.summarizer.db.downloaded_media_for_date", lambda _date: []
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
async def test_summarize_day_keeps_billable_usage_when_layer2_postprocess_fails(
    monkeypatch,
):
    saved = {}
    fake = SimpleNamespace()
    fake.messages = SimpleNamespace(
        create=AsyncMock(
            return_value=SimpleNamespace(
                content=[
                    SimpleNamespace(
                        text='{"core_view":"x","bullets":[],"sentiment":"neutral"}'
                    )
                ],
                usage=SimpleNamespace(input_tokens=40, output_tokens=20),
                stop_reason="end_turn",
            )
        )
    )
    monkeypatch.setattr("kol_monitor.summarizer._client", fake)
    monkeypatch.setattr(
        "kol_monitor.summarizer.db.tweets_on_date",
        lambda _date: [
            {
                "screen_name": "macroKOL",
                "kol_id": 1,
                "tweet_id": "1",
                "text": "market update",
                "url": "https://x.com/macroKOL/status/1",
            }
        ],
    )
    monkeypatch.setattr(
        "kol_monitor.summarizer.db.downloaded_media_for_date", lambda _date: []
    )
    monkeypatch.setattr(
        "kol_monitor.summarizer._sanitize_layer2_symbols_to_sources",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("postprocess failed")),
    )

    async def failing_layer1(*_args, **_kwargs):
        raise RuntimeError("force local fallback")

    monkeypatch.setattr(
        "kol_monitor.summarizer.call_layer1_with_validation", failing_layer1
    )
    monkeypatch.setattr(
        "kol_monitor.summarizer.db.save_digest", lambda **kwargs: saved.update(kwargs)
    )

    result = await summarize_day("2026-09-01")

    assert result["layer2"][0]["input_tokens"] == 40
    assert result["layer2"][0]["output_tokens"] == 20
    assert saved["input_tokens"] == 40
    assert saved["output_tokens"] == 20


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
async def test_summarize_one_kol_skips_images_when_limit_is_zero(monkeypatch, tmp_path):
    fake = SimpleNamespace()
    fake.messages = SimpleNamespace(
        create=AsyncMock(
            return_value=SimpleNamespace(
                content=[
                    SimpleNamespace(text='{"core_view":"v","bullets":[],"sentiment":"neutral"}')
                ],
                usage=SimpleNamespace(input_tokens=10, output_tokens=2),
            )
        )
    )
    image_path = tmp_path / "chart.jpg"
    image_path.write_bytes(b"image")
    monkeypatch.setattr("kol_monitor.summarizer._client", fake)
    monkeypatch.setattr(
        "kol_monitor.summarizer.settings.media.max_photos_per_kol_for_ai", 0
    )

    await summarize_one_kol(
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
        media_files=[image_path],
    )

    content = fake.messages.create.call_args.kwargs["messages"][0]["content"]
    assert [block["type"] for block in content] == ["text"]
    assert "部分推文包含配图" not in content[0]["text"]


@pytest.mark.asyncio
async def test_summarize_one_kol_uses_next_backend_when_json_parse_fails(monkeypatch):
    events = []

    class FakeClient:
        def __init__(self, api_key, base_url, **kwargs):
            self.api_key = api_key
            self.base_url = base_url
            self.timeout = kwargs.get("timeout")
            self.messages = SimpleNamespace(create=AsyncMock(side_effect=self._create))

        async def _create(self, **kwargs):
            events.append(self.api_key)
            if self.api_key == "fallback":
                return SimpleNamespace(
                    content=[SimpleNamespace(text="not json")],
                    usage=SimpleNamespace(input_tokens=7, output_tokens=3),
                )
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        text='{"core_view":"primary ok","bullets":[],"sentiment":"neutral"}'
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

    assert events == ["fallback", "fallback", "primary"]
    assert res["core_view"] == "primary ok"
    assert res["input_tokens"] == 24
    assert res["output_tokens"] == 11


@pytest.mark.asyncio
async def test_call_llm_uses_fallback_client(monkeypatch):
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

    response = await call_llm_with_retry(
        messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        max_tokens=10,
    )

    assert response.content[0].text == "ok"


@pytest.mark.asyncio
async def test_call_llm_falls_back_from_deepseek_to_claude(monkeypatch):
    events = []

    class FakeClient:
        def __init__(self, api_key, base_url, **kwargs):
            self.api_key = api_key
            self.base_url = base_url
            self.timeout = kwargs.get("timeout")
            self.messages = SimpleNamespace(create=AsyncMock(side_effect=self._create))

        async def _create(self, **kwargs):
            events.append(
                (
                    self.api_key,
                    self.base_url,
                    kwargs["model"],
                    kwargs.get("thinking"),
                    kwargs.get("output_config"),
                    self.timeout,
                    kwargs.get("max_tokens"),
                )
            )
            if self.api_key == "deepseek":
                raise RuntimeError("deepseek unavailable")
            return SimpleNamespace(content=[SimpleNamespace(text="ok-claude")])

    monkeypatch.setattr("kol_monitor.summarizer._client", None)
    monkeypatch.setattr("kol_monitor.summarizer.AsyncAnthropic", FakeClient)
    monkeypatch.setattr(settings, "deepseek_api_key", "deepseek", raising=False)
    monkeypatch.setattr(
        settings,
        "deepseek_base_url",
        "https://api.deepseek.example/anthropic",
        raising=False,
    )
    monkeypatch.setattr(settings, "deepseek_model", "deepseek-v4-pro", raising=False)
    monkeypatch.setattr(settings, "deepseek_reasoning_effort", "max", raising=False)
    monkeypatch.setattr(settings, "anthropic_fallback_api_key", "fallback", raising=False)
    monkeypatch.setattr(
        settings, "anthropic_fallback_base_url", "https://claude.example", raising=False
    )
    monkeypatch.setattr(settings, "anthropic_fourth_api_key", None, raising=False)
    monkeypatch.setattr(settings, "anthropic_third_api_key", None, raising=False)
    monkeypatch.setattr(settings, "anthropic_api_key", None, raising=False)

    response = await call_llm_with_retry(
        messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        max_tokens=384000,
    )

    assert response.content[0].text == "ok-claude"
    assert [event[0] for event in events] == ["deepseek", "fallback"]
    assert events[0][1] == "https://api.deepseek.example/anthropic"
    assert events[0][2] == "deepseek-v4-pro"
    assert events[0][3] == {"type": "enabled", "budget_tokens": 1024}
    assert events[0][4] == {"effort": "max"}
    assert events[0][5] == 10800
    assert events[0][6] == 384000
    assert events[1][2] == settings.ai.model
    assert events[1][3] is None
    assert events[1][4] is None
    assert events[1][5] is None
    assert events[1][6] == 8000


@pytest.mark.asyncio
async def test_call_llm_closes_each_backend_client(monkeypatch):
    closed = []

    class FakeClient:
        def __init__(self, api_key, base_url):
            self.api_key = api_key
            self.messages = SimpleNamespace(create=AsyncMock(side_effect=self._create))

        async def _create(self, **kwargs):
            if self.api_key == "fallback":
                raise RuntimeError("fallback failed")
            return SimpleNamespace(content=[SimpleNamespace(text="ok")])

        async def close(self):
            closed.append(self.api_key)

    monkeypatch.setattr("kol_monitor.summarizer._client", None)
    monkeypatch.setattr("kol_monitor.summarizer.AsyncAnthropic", FakeClient)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_api_key", "primary")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_base_url", "https://primary.example")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fallback_api_key", "fallback")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fallback_base_url", "https://fallback.example")
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_third_api_key", None)
    monkeypatch.setattr("kol_monitor.summarizer.settings.anthropic_fourth_api_key", None, raising=False)

    await call_llm_with_retry(
        messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        max_tokens=10,
    )

    assert closed == ["fallback", "primary"]


@pytest.mark.asyncio
async def test_call_llm_falls_through_to_third_client(monkeypatch):
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

    response = await call_llm_with_retry(
        messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        max_tokens=10,
    )

    assert response.content[0].text == "ok-third"
    assert [event[0] for event in events] == ["fallback", "third"]
    assert events[0][2] == "claude-sonnet-4-6"
    assert events[0][3] == 0.3
    assert events[1][1] == "https://third.example"
    assert events[1][2] == "anthropic/claude-sonnet-4.6"
    assert events[1][3] == 1
    assert events[1][4] == {"type": "disabled"}


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

    response = await call_llm_with_retry(
        messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        max_tokens=10,
    )

    assert response.content[0].text == "ok-defaults"
    assert events == [
        ("third", 1, {"type": "disabled"}),
        ("third", "missing", None),
    ]


@pytest.mark.asyncio
async def test_call_llm_falls_through_to_fourth_client(monkeypatch):
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

    response = await call_llm_with_retry(
        messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        max_tokens=10,
    )

    assert response.content[0].text == "ok-fourth"
    assert [event[0] for event in events] == ["fallback", "fourth"]
    assert events[1][1] == "https://fourth.example"
    assert events[1][2] == "claude-sonnet-4-6"
    assert events[1][3] == 0.3
    assert events[1][4] is None


@pytest.mark.asyncio
async def test_call_llm_uses_third_after_fourth_fails(monkeypatch):
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

    response = await call_llm_with_retry(
        messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        max_tokens=10,
    )

    assert response.content[0].text == "ok-third"
    assert [event[0] for event in events] == ["fallback", "fourth", "third"]
    assert events[1][1] == "https://fourth.example"
    assert events[1][3] == 0.3
    assert events[1][4] is None
    assert events[2][1] == "https://third.example"
    assert events[2][2] == "anthropic/claude-sonnet-4.6"
    assert events[2][3] == 1
    assert events[2][4] == {"type": "disabled"}


def test_llm_sdk_base_url_keeps_clean_provider_root():
    assert _llm_sdk_base_url("https://third.example") == "https://third.example"
    assert _llm_sdk_base_url("https://third.example/v1") == "https://third.example"


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


def test_build_layer1_prompt_defines_cross_market_symbol_scope():
    prompt = build_layer1_prompt(
        [
            {
                "screen_name": "globalKOL",
                "tweet_count": 1,
                "core_view": "x",
                "bullets": [],
                "sentiment": "neutral",
            }
        ]
    )

    text = prompt[0]["content"][0]["text"]
    assert "市场交易标识符" in text
    assert "A 股 $688981" in text
    assert "韩股 $005930" in text
    assert "台股 $2330" in text
    assert "日股 $8035" in text
    assert "港股 $03308" in text
    assert "加密资产 $BTC" in text
    assert "商品/外汇交易符号 $WTI、$XAUUSD、$DXY、$USDJPY" in text
    assert "DRAM" in text and "不能仅因大写" in text
    assert "只是分类示例" in text
    assert "多个机构、公司或人物" in text
    assert "各自动作" in text


def test_layer2_prompt_requires_dollar_ticker_display():
    text = _layer2_prompt(
        {"screen_name": "qinbafrank"},
        [{"text": "NVDA earnings", "favorite_count": 1, "retweet_count": 0, "url": "https://x.com/a/status/1"}],
        had_media=False,
    )

    assert "$NVDA" in text
    assert "tickers" in text


def test_layer2_prompt_distinguishes_symbols_from_market_terms():
    text = _layer2_prompt(
        {"screen_name": "globalKOL"},
        [
            {
                "text": "$005930 and $BTC; HBM and RSI are context only",
                "favorite_count": 1,
                "retweet_count": 0,
                "url": "https://x.com/a/status/1",
            }
        ],
        had_media=False,
    )

    assert "不只是美股" in text
    assert "加密资产不得描述为公司股票" in text
    assert "HBM" in text and "RSI" in text
    assert "非美股数字代码必须同时保留市场或公司语境" in text
    assert "三星电子（$005930）" in text
    assert "禁止裸写 `005930`" in text
    assert "C3.ai 股票时的 $AI" in text
    assert "多个机构、公司或人物" in text
    assert "各自动作" in text


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


def test_normalize_layer2_result_fixes_boe_ticker_for_jingdongfang():
    normalized = _normalize_layer2_result(
        {
            "core_view": "作者关注京东方",
            "sentiment": "neutral",
            "bullets": [
                {
                    "point": "作者称 $BOE（京东方 A）获机构调研",
                    "tickers": ["BOE"],
                    "tweet_url": "https://x.com/a/status/1",
                }
            ],
        }
    )

    assert normalized["bullets"][0]["point"] == "作者称 $000725（京东方 A）获机构调研"
    assert normalized["bullets"][0]["tickers"] == ["000725"]


def test_normalize_layer2_result_formats_or_drops_undisplayed_symbols():
    normalized = _normalize_layer2_result(
        {
            "core_view": "作者关注跨市场标的",
            "sentiment": "neutral",
            "bullets": [
                {
                    "point": "作者称三星电子（005930）需求增长。",
                    "tickers": ["005930"],
                    "tweet_url": "https://x.com/a/status/1",
                },
                {
                    "point": "作者只写了英伟达公司名。",
                    "tickers": ["NVDA"],
                    "tweet_url": "https://x.com/a/status/2",
                },
            ],
        }
    )

    assert normalized["bullets"][0]["point"] == "作者称三星电子（$005930）需求增长。"
    assert normalized["bullets"][0]["tickers"] == ["005930"]
    assert normalized["bullets"][1]["tickers"] == []


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


def test_sanitize_tweet_url_strips_trailing_json_pollution():
    from kol_monitor.summarizer import sanitize_tweet_url

    polluted = (
        'https://x.com/blazingbees/status/2067202446859145715",\n'
        '      "claim_type": "news",\n      "confidence": "medium'
    )
    assert sanitize_tweet_url(polluted) == "https://x.com/blazingbees/status/2067202446859145715"
    # Truth Social-style ids for realDonaldTrump survive.
    assert (
        sanitize_tweet_url("https://x.com/realDonaldTrump/status/truth_1781180529245152768")
        == "https://x.com/realDonaldTrump/status/truth_1781180529245152768"
    )
    # No valid status URL -> empty (bullet gets dropped downstream).
    assert sanitize_tweet_url("not a url") == ""
    assert sanitize_tweet_url("") == ""


def test_normalize_layer2_drops_polluted_url_bullet():
    from kol_monitor.summarizer import _normalize_layer2_result

    item = {
        "core_view": "x",
        "sentiment": "bullish",
        "bullets": [
            {
                "point": "干净要点",
                "tickers": [],
                "tweet_url": "https://x.com/foo/status/123",
            },
            {
                "point": "另一要点",
                "tickers": [],
                "tweet_url": "garbage-no-url",
            },
        ],
    }
    out = _normalize_layer2_result(dict(item))
    assert len(out["bullets"]) == 1
    assert out["bullets"][0]["tweet_url"] == "https://x.com/foo/status/123"


def test_parse_string_array_handles_fences_and_prelude():
    from kol_monitor.summarizer import _parse_string_array

    assert _parse_string_array('["a","b"]') == ["a", "b"]
    assert _parse_string_array('```json\n["x","y"]\n```') == ["x", "y"]
    assert _parse_string_array('好的：\n["只", "中文"]\n') == ["只", "中文"]
    assert _parse_string_array("not json") is None
    assert _parse_string_array('[1, 2]') is None  # non-string array rejected


@pytest.mark.asyncio
async def test_translate_residual_layer2_preserves_info(monkeypatch):
    from kol_monitor import summarizer

    async def fake_call(messages, max_tokens):
        # Return Chinese translations in the same order/length as input.
        class R:
            content = [SimpleNamespace(type="text", text='["日本央行加息至1%创31年新高", "SK海力士ADR七月上市"]')]
        return R()

    monkeypatch.setattr(summarizer, "call_llm_with_retry", fake_call)

    parsed = {
        "core_view": "强势",  # already Chinese -> not a target
        "sentiment": "bullish",
        "bullets": [
            {"point": "일본은행이 기준금리를 1프로로 인상했다", "tickers": [], "tweet_url": "https://x.com/a/status/1"},
            {"point": "SK하이닉스 ADR이 칠월에 상장된다는 소식", "tickers": [], "tweet_url": "https://x.com/a/status/2"},
        ],
    }
    out = await summarizer._translate_residual_layer2(parsed)
    assert out["bullets"][0]["point"] == "日本央行加息至1%创31年新高"
    assert out["bullets"][1]["point"] == "SK海力士ADR七月上市"
    # After translation, normalize keeps them instead of dropping.
    normalized = summarizer._normalize_layer2_result(dict(out))
    assert len(normalized["bullets"]) == 2


@pytest.mark.asyncio
async def test_translate_residual_failure_leaves_bullets_for_drop(monkeypatch):
    from kol_monitor import summarizer

    async def failing_call(messages, max_tokens):
        raise RuntimeError("backend down")

    monkeypatch.setattr(summarizer, "call_llm_with_retry", failing_call)

    parsed = {
        "core_view": "x",
        "sentiment": "bullish",
        "bullets": [
            {"point": "일본은행이 기준금리를 1프로로 인상했다", "tickers": [], "tweet_url": "https://x.com/a/status/1"},
        ],
    }
    out = await summarizer._translate_residual_layer2(parsed)
    # Untouched on failure; normalize then drops the residual bullet (no regression).
    assert out["bullets"][0]["point"] == "일본은행이 기준금리를 1프로로 인상했다"
    normalized = summarizer._normalize_layer2_result(dict(out))
    assert len(normalized["bullets"]) == 0


def test_build_layer3_prompt_has_constraints_and_content():
    from kol_monitor.summarizer import build_layer3_prompt

    msgs = build_layer3_prompt("2026-06-18", "## 今日关键词\n\n- $NVDA 强势")
    text = msgs[0]["content"][0]["text"]
    assert "美股盘前快报" in text
    assert "2026-06-18" in text
    assert "$NVDA 强势" in text
    assert "非投资建议" in text  # disclaimer instruction present


@pytest.mark.asyncio
async def test_generate_layer3_tweet_uses_cleaned_layer1(monkeypatch):
    from kol_monitor import summarizer

    captured = {}

    async def fake_call(messages, max_tokens):
        captured["text"] = messages[0]["content"][0]["text"]

        class R:
            content = [SimpleNamespace(type="text", text="盘前快报正文……\n非投资建议。")]

        return R()

    monkeypatch.setattr(summarizer, "call_llm_with_retry", fake_call)
    monkeypatch.setattr(
        summarizer.db,
        "get_digest",
        lambda date: {"summary_md": "## 今日关键词\n\n- 失败两次诊断根因\n- $NVDA 真实要点"},
    )

    out = await summarizer.generate_layer3_tweet("2026-06-18")
    assert out.startswith("盘前快报正文")
    # internal-artifact line is cleaned before being fed to the premarket prompt
    assert "失败两次" not in captured["text"]
    assert "$NVDA 真实要点" in captured["text"]
