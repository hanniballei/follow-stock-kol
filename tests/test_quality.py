from __future__ import annotations

import json
from pathlib import Path

from kol_monitor import db
from kol_monitor.quality import (
    scan_layer2_quality,
    scan_summary_quality,
    write_quality_draft,
)
from kol_monitor.summarizer import _prepare_layer1_markdown


def test_scan_summary_quality_flags_known_bad_patterns():
    md = """## 特朗普相关

- 暂无高质量信号。

## 今日关键词

- AI

## 重要新闻

- OpenAI计划6月23日发布claude-sonnet-4-6。[@kol](https://x.com/kol/status/1)

## 宏观判断

- 无来源宏观判断

## 产业/个股焦点

- $000660 100조 주주환원 추진 단독보도。[@bees](https://x.com/bees/status/1)

## 交易信号

| 标的 | 线索 | 来源 |
|---|---|---|
| $NVDA | 作者认为需求仍强 | [@kol](https://x.com/kol/status/2) |

## 投资理念

- 失败两次应诊断根因而非增量修补。
"""

    report = scan_summary_quality(md)

    assert report["status"] == "fail"
    codes = report["issue_counts_by_code"]
    assert codes["suspicious_model_company_conflict"] == 1
    assert codes["missing_source_link"] >= 1
    assert codes["non_chinese_residue"] == 1
    assert codes["internal_artifact"] == 1


def test_scan_layer2_quality_flags_bad_points_and_missing_sources():
    report = scan_layer2_quality(
        [
            {
                "screen_name": "badkol",
                "core_view": "OpenAI计划发布Claude新模型",
                "bullets": [
                    {
                        "point": "$000660 100조 주주환원 추진 단독보도",
                        "tickers": ["000660"],
                        "tweet_url": "https://x.com/badkol/status/1",
                    },
                    {"point": "作者认为 $NVDA 需求强", "tickers": ["NVDA"]},
                ],
            }
        ]
    )

    assert report["status"] == "fail"
    codes = report["issue_counts_by_code"]
    assert codes["layer2_core_suspicious_model_company_conflict"] == 1
    assert codes["layer2_point_non_chinese_residue"] == 1
    assert codes["layer2_missing_source"] == 1


def test_write_quality_draft_writes_cleaned_and_report(tmp_db, tmp_path):
    layer2 = [
        {
            "screen_name": "badkol",
            "tweet_count": 2,
            "core_view": "OpenAI计划发布Claude新模型",
            "bullets": [
                {
                    "point": "OpenAI计划发布claude-sonnet-4-6",
                    "tickers": ["AI"],
                    "tweet_url": "https://x.com/badkol/status/1",
                },
                {
                    "point": "$000660 100조 주주환원 추진 단독보도",
                    "tickers": ["000660"],
                    "tweet_url": "https://x.com/badkol/status/2",
                },
                {
                    "point": "作者称 $NVDA 需求仍强",
                    "tickers": ["NVDA"],
                    "tweet_url": "https://x.com/badkol/status/3",
                },
            ],
            "sentiment": "neutral",
        }
    ]
    db.save_digest(
        date="2026-06-16",
        summary_md=(
            "## 特朗普相关\n\n"
            "- 暂无高质量信号。\n\n"
            "## 今日关键词\n\n"
            "- AI\n\n"
            "## 重要新闻\n\n"
            "- OpenAI计划发布claude-sonnet-4-6。"
            "[@badkol](https://x.com/badkol/status/1)\n\n"
            "## 宏观判断\n\n"
            "- 作者认为收益率影响科技股。[@badkol](https://x.com/badkol/status/3)\n\n"
            "## 产业/个股焦点\n\n"
            "- 作者称 $NVDA 需求仍强。[@badkol](https://x.com/badkol/status/3)\n\n"
            "## 交易信号\n\n"
            "| 标的 | 线索 | 来源 |\n"
            "|---|---|---|\n"
            "| $NVDA | 需求仍强 | [@badkol](https://x.com/badkol/status/3) |\n\n"
            "## 投资理念\n\n"
            "- 作者称只保留有来源信号。[@badkol](https://x.com/badkol/status/3)\n"
        ),
        layer2_json=json.dumps(layer2, ensure_ascii=False),
        kol_count=1,
        tweet_count=2,
        model="test",
    )

    result = write_quality_draft("2026-06-16", output_dir=tmp_path)

    out_dir = Path(result["output_dir"])
    draft = (out_dir / "draft.md").read_text(encoding="utf-8")
    cleaned = (out_dir / "cleaned_existing.md").read_text(encoding="utf-8")
    repaired = (out_dir / "repaired_fallback.md").read_text(encoding="utf-8")
    normalized = json.loads((out_dir / "layer2_normalized.json").read_text(encoding="utf-8"))
    report = json.loads((out_dir / "quality_report.json").read_text(encoding="utf-8"))

    assert "OpenAI计划" not in cleaned
    assert "claude-sonnet-4-6" not in cleaned
    assert "OpenAI计划" not in repaired
    assert "주주환원" not in repaired
    assert normalized[0]["core_view"] == "作者称 $NVDA 需求仍强"
    assert len(normalized[0]["bullets"]) == 1
    assert draft == cleaned
    assert report["date"] == "2026-06-16"
    assert report["selected_draft"] == "cleaned_existing"
    assert report["metrics"]["input_layer2_bullets"] == 3
    assert report["metrics"]["normalized_layer2_bullets"] == 1


def test_scan_flags_json_residue_and_broken_links():
    # Reproduces the 2026-06-17 leak: a malformed tweet_url swallowed trailing JSON,
    # corrupting the [原推] link and leaving raw claim_type/confidence fields in the body.
    md = """## 重要新闻

- 作者转述：某事件 [原推](https://x.com/blazingbees/status/2067202446859145715",
      "claim_type": "news",
      "confidence": "medium)
"""
    report = scan_summary_quality(md)
    codes = report["issue_counts_by_code"]
    assert codes.get("json_residue", 0) >= 1
    assert codes.get("broken_source_link", 0) >= 1
    assert report["status"] == "fail"


def test_scan_clean_digest_has_no_json_or_link_errors():
    md = """## 重要新闻

- 作者认为 $NVDA 强势 [@foo](https://x.com/foo/status/123)
"""
    report = scan_summary_quality(md)
    codes = report["issue_counts_by_code"]
    assert codes.get("json_residue", 0) == 0
    assert codes.get("broken_source_link", 0) == 0


def test_scan_summary_quality_warns_on_long_plain_paragraph():
    md = """## 特朗普相关

[@realDonaldTrump 原文](https://x.com/realDonaldTrump/status/truth_1) 称美股继续上涨，市场情绪改善。[@kol](https://x.com/kol/status/2) 认为半导体和军工板块会继续受益，同时指出如果关税谈判反复，供应链波动也会重新加剧，因此需要继续观察后续表态和执行层面的变化，并且这类影响可能同时传导到大型科技股、工业股和防务相关板块。

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
    report = scan_summary_quality(md)
    assert report["issue_counts_by_code"].get("long_plain_paragraph", 0) >= 1


def test_scan_spacex_ticker_conflation_warns_but_spares_disambiguation():
    bad = "## 重要新闻\n\n- 木头姐买入 $SPCE，SpaceX 流通量少导致暴涨 [@k](https://x.com/k/status/1)\n"
    legit = "## 重要新闻\n\n- 部分投资者误将 $SPCE 当作 $SPCX 交易后卖出 [@k](https://x.com/k/status/1)\n"
    assert scan_summary_quality(bad)["issue_counts_by_code"].get("spacex_ticker_conflation", 0) >= 1
    assert scan_summary_quality(legit)["issue_counts_by_code"].get("spacex_ticker_conflation", 0) == 0


def test_scan_summary_quality_flags_anonymous_kol_reference():
    md = """## 宏观判断

- 某KOL认为流动性仍支撑科技股 [@foo](https://x.com/foo/status/123)
"""

    report = scan_summary_quality(md)

    assert report["status"] == "fail"
    assert report["issue_counts_by_code"]["anonymous_kol_reference"] == 1


def test_prepare_layer1_replaces_anonymous_kol_when_source_is_present():
    md = """## 宏观判断

- 某KOL认为流动性仍支撑科技股 [@foo](https://x.com/foo/status/123)
"""

    cleaned = _prepare_layer1_markdown(md)

    assert "某KOL" not in cleaned
    assert "@foo认为流动性仍支撑科技股" in cleaned
    report = scan_summary_quality(cleaned)
    assert report["issue_counts_by_code"].get("anonymous_kol_reference", 0) == 0
