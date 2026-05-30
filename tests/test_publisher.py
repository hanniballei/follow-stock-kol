from __future__ import annotations

from kol_monitor.publisher import render_digest_md, render_readme


def test_render_readme_contains_required_sections():
    md = render_readme(
        date="2026-05-29",
        layer1_md="### 今日关键词\n通胀降温",
        layer2_kols=[
            {
                "screen_name": "qinbafrank",
                "tweet_count": 3,
                "core_view": "科技股估值进入消化期",
                "bullets": [
                    {
                        "point": "看好半导体设备",
                        "tickers": ["AMAT"],
                        "tweet_url": "https://x.com/qinbafrank/status/1",
                    }
                ],
                "sentiment": "bullish",
            }
        ],
        kol_list=["qinbafrank", "NickTimiraos"],
        recent_digests=[("2026-05-29", "digests/2026/05/29.md")],
        history_dirs=[("2026-05", "digests/2026/05/"), ("2026-04", "digests/2026/04/")],
    )

    assert "## 监控的 KOL" in md
    assert "[阅读今日完整报告](digests/2026/05/29.md)" in md
    assert "## 最近 7 天" in md
    assert md.index("### 今日关键词") < md.index("## 监控的 KOL")
    assert "[@qinbafrank](https://x.com/qinbafrank)" in md
    assert "<details>" in md
    assert "## 历史归档" in md
    assert "https://x.com/qinbafrank/status/1" in md
    assert "2026-05-29" in md


def test_digest_md_no_collapse():
    md = render_digest_md(
        date="2026-05-29",
        layer1_md="### 今日关键词\n...",
        layer2_kols=[],
    )

    assert "<details>" not in md
    assert "2026-05-29" in md
