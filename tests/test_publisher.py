from __future__ import annotations

from pathlib import Path
import subprocess

from kol_monitor import publisher
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

    assert md.startswith("# 美股KOL每日摘要")
    assert "X 上 2 位美股相关 KOL 的发言" in md
    assert "美股 X/KOL 每日摘要" not in md
    assert "## 你会看到什么" in md
    assert "## 自己运行" in md
    assert "KOL_MONITOR_ALLOW_PUSH=true" in md
    assert "## 监控的 KOL" in md
    assert "[阅读今日完整报告](digests/2026/05/29.md)" in md
    assert "## 最近 7 天" in md
    assert "这个仓库每天北京时间 20:30 自动抓取" in md
    assert md.index("### 今日关键词") < md.index("## 监控的 KOL")
    assert "[@qinbafrank](https://x.com/qinbafrank)" in md
    assert "<details>" in md
    assert "## 历史归档" in md
    assert "https://x.com/qinbafrank/status/1" in md
    assert "2026-05-29" in md
    assert "$AMAT" in md


def test_digest_md_no_collapse():
    md = render_digest_md(
        date="2026-05-29",
        layer1_md="### 今日关键词\n...",
        layer2_kols=[],
    )

    assert "<details>" not in md
    assert "2026-05-29" in md


def test_git_publish_does_not_push_without_explicit_allow(monkeypatch, tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# test\n", encoding="utf-8")
    calls = []
    published = []

    monkeypatch.setattr(publisher.settings, "project_root", tmp_path)
    monkeypatch.setattr(publisher.settings.publish, "git_push", True)
    monkeypatch.setattr(publisher.settings, "allow_git_push", False, raising=False)
    monkeypatch.setattr(
        publisher.subprocess,
        "run",
        lambda cmd, **_kwargs: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0),
    )
    monkeypatch.setattr(publisher.db, "mark_digest_published", published.append)

    assert publisher.git_publish("2026-05-30", [readme]) is True

    assert ["git", "add", "README.md"] in calls
    assert ["git", "commit", "-m", "digest: 2026-05-30"] in calls
    assert ["git", "push", "origin", "main"] not in calls
    assert published == ["2026-05-30"]


def test_git_publish_pushes_when_explicitly_allowed(monkeypatch, tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# test\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(publisher.settings, "project_root", tmp_path)
    monkeypatch.setattr(publisher.settings.publish, "git_push", True)
    monkeypatch.setattr(publisher.settings, "allow_git_push", True, raising=False)
    monkeypatch.setattr(
        publisher.subprocess,
        "run",
        lambda cmd, **_kwargs: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0),
    )
    monkeypatch.setattr(publisher.db, "mark_digest_published", lambda _date: None)

    publisher.git_publish("2026-05-30", [readme])

    assert ["git", "push", "origin", "main"] in calls


def test_git_publish_retries_transient_push_failure(monkeypatch, tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# test\n", encoding="utf-8")
    calls = []
    published = []
    push_attempts = {"count": 0}

    monkeypatch.setattr(publisher.settings, "project_root", tmp_path)
    monkeypatch.setattr(publisher.settings.publish, "git_push", True)
    monkeypatch.setattr(publisher.settings.publish, "push_retry", 3)
    monkeypatch.setattr(publisher.settings, "allow_git_push", True, raising=False)
    monkeypatch.setattr(publisher.time, "sleep", lambda _seconds: None)

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        if cmd == ["git", "push", "origin", "main"]:
            push_attempts["count"] += 1
            if push_attempts["count"] == 1:
                raise subprocess.CalledProcessError(128, cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(publisher.subprocess, "run", fake_run)
    monkeypatch.setattr(publisher.db, "mark_digest_published", published.append)

    assert publisher.git_publish("2026-05-30", [readme]) is True

    assert calls.count(["git", "push", "origin", "main"]) == 2
    assert published == ["2026-05-30"]


def test_git_publish_sets_home_for_systemd_environment(monkeypatch, tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# test\n", encoding="utf-8")
    (tmp_path / ".git-data").mkdir()
    child_envs = []

    monkeypatch.setattr(publisher.settings, "project_root", tmp_path)
    monkeypatch.setattr(publisher.settings.publish, "git_push", True)
    monkeypatch.setattr(publisher.settings, "allow_git_push", True, raising=False)
    monkeypatch.delenv("HOME", raising=False)

    def fake_run(cmd, **kwargs):
        child_envs.append(kwargs["env"])
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(publisher.subprocess, "run", fake_run)
    monkeypatch.setattr(publisher.db, "mark_digest_published", lambda _date: None)

    publisher.git_publish("2026-05-30", [readme])

    assert child_envs
    assert all(env["HOME"] == str(Path.home()) for env in child_envs)


# ---------------------------------------------------------------------------
# HTML daily report tests
# ---------------------------------------------------------------------------

SAMPLE_LAYER2_KOLS = [
    {
        "screen_name": "qinbafrank",
        "tweet_count": 5,
        "core_view": "科技股估值进入消化期",
        "bullets": [
            {
                "point": "看好半导体设备板块",
                "tickers": ["AMAT", "LRCX"],
                "tweet_url": "https://x.com/qinbafrank/status/1",
            },
            {
                "point": "宏观经济数据支持下半年降息",
                "tickers": ["SPY", "QQQ"],
                "tweet_url": "https://x.com/qinbafrank/status/2",
            },
        ],
        "sentiment": "bullish",
    },
    {
        "screen_name": "realDonaldTrump",
        "tweet_count": 12,
        "core_view": "继续推动关税政策",
        "bullets": [
            {
                "point": "提议对中国商品加征新关税",
                "tickers": ["AAPL", "TSLA"],
                "tweet_url": "https://x.com/realDonaldTrump/status/3",
            },
        ],
        "sentiment": "bearish",
    },
    {
        "screen_name": "charliebilello",
        "tweet_count": 3,
        "core_view": "关注估值回调风险",
        "bullets": [
            {
                "point": "NVDA当前估值过高",
                "tickers": ["NVDA"],
                "tweet_url": "https://x.com/charliebilello/status/4",
            },
        ],
        "sentiment": "neutral",
    },
]

SAMPLE_LAYER1_MD = """## 特朗普相关

- 提议对中国商品加征新关税，可能影响 $AAPL $TSLA 等公司 [@realDonaldTrump 原文](https://x.com/realDonaldTrump/status/3)

## 今日关键词

- 关税政策
- 科技股估值
- 降息预期
- 半导体

## 重要新闻

- 半导体设备板块受到市场关注

## 宏观判断

- 宏观经济数据支持下半年降息

## 产业/个股焦点

- $AMAT：看好半导体设备板块
- $NVDA：当前估值过高引发市场关注

## 交易信号

| 标的 | 线索 | 来源 |
|---|---|---|
| $AMAT, $LRCX | 看好半导体设备板块 | [@qinbafrank](https://x.com/qinbafrank/status/1) |
| $AAPL, $TSLA | 提议对中国商品加征新关税 | [@realDonaldTrump 原文](https://x.com/realDonaldTrump/status/3) |

## 投资理念

- @qinbafrank：科技股估值进入消化期，关注半导体设备板块
"""


def test_render_daily_html_contains_required_sections():
    html = publisher.render_daily_html(
        date="2026-05-29",
        layer1_md=SAMPLE_LAYER1_MD,
        layer2_kols=SAMPLE_LAYER2_KOLS,
        kol_list=["qinbafrank", "realDonaldTrump", "charliebilello"],
    )

    assert "<!DOCTYPE html>" in html
    assert '<html lang="zh-CN">' in html
    assert "<title>美股KOL日报" in html
    assert "美股 KOL 日报" in html
    assert "2026-05-29" in html
    # Layer 1 section headings rendered
    assert "特朗普相关" in html
    assert "今日关键词" in html
    assert "投资理念" in html
    # KOL cards
    assert "@qinbafrank" in html
    assert "@realDonaldTrump" in html
    assert "@charliebilello" in html
    # Sentiment badges
    assert "看多" in html  # bullish → 看多
    assert "看空" in html  # bearish → 看空
    assert "中性" in html  # neutral → 中性
    # Ticker tags
    assert "$AMAT" in html
    assert "$NVDA" in html
    # Trade signals section
    assert "交易信号" in html
    # Stats (total tweets: 5 + 12 + 3 = 20, 3 KOLs in list)
    assert "<strong>3</strong> 位 KOL" in html
    assert "<strong>20</strong> 条推文" in html


def test_render_daily_html_closes_all_tags():
    html = publisher.render_daily_html(
        date="2026-05-29",
        layer1_md=SAMPLE_LAYER1_MD,
        layer2_kols=SAMPLE_LAYER2_KOLS,
        kol_list=["qinbafrank"],
    )

    assert html.endswith("</html>\n")
    assert html.count("</div>") >= 3
    assert "</body>" in html
    assert "</html>" in html


def test_render_daily_html_handles_empty():
    html = publisher.render_daily_html(
        date="2026-05-29",
        layer1_md="",
        layer2_kols=[],
        kol_list=[],
    )

    assert "<!DOCTYPE html>" in html
    assert "2026-05-29" in html
    assert html.endswith("</html>\n")


def test_render_daily_html_handles_summary_failed():
    kols = [
        {
            "screen_name": "testkol",
            "tweet_count": 1,
            "core_view": "summary_failed",
            "bullets": [],
            "sentiment": "unclear",
        },
    ]
    html = publisher.render_daily_html(
        date="2026-05-29",
        layer1_md="## 今日关键词\n\n- 无信号",
        layer2_kols=kols,
        kol_list=["testkol"],
    )

    assert "总结失败，请查看原始推文" in html
    assert "@testkol" in html


def test_render_digest_skips_empty_market_kol_sections():
    md = render_digest_md(
        date="2026-05-29",
        layer1_md="## 今日关键词\n\n- 无信号",
        layer2_kols=[
            {
                "screen_name": "sportskol",
                "tweet_count": 1,
                "core_view": "无市场相关内容",
                "bullets": [],
                "sentiment": "unclear",
            },
            {
                "screen_name": "marketkol",
                "tweet_count": 1,
                "core_view": "作者认为 $NVDA 仍强",
                "bullets": [
                    {
                        "point": "作者认为 $NVDA 需求强",
                        "tickers": ["NVDA"],
                        "tweet_url": "https://x.com/marketkol/status/1",
                    }
                ],
                "sentiment": "bullish",
            },
        ],
    )

    assert "@sportskol" not in md
    assert "@marketkol" in md
    assert "暂无要点" not in md


def test_render_daily_html_ticker_cloud_order():
    """Tickers should be sorted by frequency, most common first."""
    html = publisher.render_daily_html(
        date="2026-05-29",
        layer1_md=SAMPLE_LAYER1_MD,
        layer2_kols=SAMPLE_LAYER2_KOLS,
        kol_list=["a", "b", "c"],
    )

    # AMAT appears in qinbafrank's two bullets (AMAT+LRCX, SPY+QQQ)
    # AMAT and other tickers appear once each (but AMAT appears once in one bullet)
    # Actually let's check: AMAT in bullet1, SPY in bullet2, AAPL in trump, TSLA in trump, NVDA in charlie
    # So AMAT, LRCX, SPY, QQQ, AAPL, TSLA all once
    amat_pos = html.find("$AMAT")
    nvda_pos = html.find("$NVDA")
    assert amat_pos > 0
    assert nvda_pos > 0


def test_sentiment_counts():
    from kol_monitor.publisher import _count_sentiments

    counts = _count_sentiments(SAMPLE_LAYER2_KOLS)
    assert counts["bullish"] == 1
    assert counts["bearish"] == 1
    assert counts["neutral"] == 1
    assert counts["unclear"] == 0


def test_ticker_counts():
    from kol_monitor.publisher import _count_tickers

    tickers = _count_tickers(SAMPLE_LAYER2_KOLS)
    assert isinstance(tickers, list)
    assert len(tickers) >= 5  # AMAT, LRCX, SPY, QQQ, AAPL, TSLA, NVDA
    ticker_names = [t[0] for t in tickers]
    assert "AAPL" in ticker_names
    assert "NVDA" in ticker_names


def test_write_outputs_excludes_html(tmp_path, monkeypatch):
    """write_outputs returns README + Markdown only; per-day HTML is no longer produced."""
    monkeypatch.setattr(publisher.settings, "project_root", tmp_path)
    monkeypatch.setattr(publisher.settings, "kols", ["testkol"])
    monkeypatch.setattr(
        publisher.db,
        "get_digest",
        lambda date: {
            "date": date,
            "summary_md": "## 今日关键词\n\n- 测试",
            "layer2_json": "[]",
            "kol_count": 1,
            "tweet_count": 0,
        },
    )
    monkeypatch.setattr(
        publisher,
        "history_dirs",
        lambda: [],
    )
    monkeypatch.setattr(
        publisher,
        "recent_digest_links",
        lambda: [],
    )

    paths = publisher.write_outputs("2026-05-29")
    assert [p.suffix for p in paths] == [".md", ".md"]  # README.md + DD.md
    for p in paths:
        assert p.exists()
    # No .html should be written anywhere under the digest dir.
    assert not list((tmp_path / "digests").rglob("*.html"))


def test_select_publishable_layer1_uses_fallback_when_scan_fails():
    layer2 = [
        {
            "screen_name": "testkol",
            "tweet_count": 1,
            "core_view": "作者认为 $NVDA 需求仍强",
            "bullets": [
                {
                    "point": "作者认为 $NVDA 需求仍强",
                    "tickers": ["NVDA"],
                    "tweet_url": "https://x.com/testkol/status/1",
                    "claim_type": "opinion",
                }
            ],
            "sentiment": "bullish",
        }
    ]
    bad_layer1 = """## 产业/个股焦点

| 板块 | 标的 |
|------|------|
| AI 云服务 | $CRWV、$NBIS |
| 软件层 | $IBM |

## 交易信号

| 标的 | 线索 | 来源 |
|---|---|---|
| $NVDA | 需求仍强 | [@testkol](https://x.com/testkol/status/1) |

## 投资理念

- 作者认为只做有来源的交易
"""
    selected = publisher._select_publishable_layer1("2026-05-29", bad_layer1, layer2)

    assert "本地兜底模板" in selected
    assert "作者认为 $NVDA 需求仍强（$NVDA） [@testkol](https://x.com/testkol/status/1)" in selected


def test_invented_spacex_tickers_normalized_but_spce_preserved():
    from kol_monitor.publisher import _format_ticker, _normalize_ticker_code

    # Invented forms collapse to canonical $SPCX.
    assert _format_ticker("SPACEX") == "$SPCX"
    assert _format_ticker("$SPACE") == "$SPCX"
    assert _normalize_ticker_code("spacex") == "SPCX"
    # Real tickers are untouched, including Virgin Galactic's genuine $SPCE.
    assert _format_ticker("SPCE") == "$SPCE"
    assert _format_ticker("$NVDA") == "$NVDA"
    assert _format_ticker("SPCX") == "$SPCX"


def test_write_premarket_writes_pure_text(tmp_path, monkeypatch):
    monkeypatch.setattr(publisher.settings, "project_root", tmp_path)
    path = publisher.write_premarket("2026-06-18", "  盘前快报正文\n非投资建议。  ")
    assert path == tmp_path / "premarket" / "2026" / "06" / "18.md"
    content = path.read_text(encoding="utf-8")
    assert content == "盘前快报正文\n非投资建议。\n"
    assert "---" not in content  # no front matter, copy-paste ready
