from __future__ import annotations

import json
from pathlib import Path

from kol_monitor import db
from kol_monitor.quality import scan_layer2_quality, scan_summary_quality, write_quality_draft


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
