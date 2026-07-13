from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from collections import Counter
from pathlib import Path

import markdown as md_lib

from kol_monitor import db
from kol_monitor.config import settings
from kol_monitor.summarizer import (
    _fallback_layer1_markdown,
    _normalize_layer2_result,
    _prepare_layer1_markdown,
    sanitize_tweet_url,
)

logger = logging.getLogger(__name__)

# Unambiguously-invented SpaceX ticker forms -> the project's canonical $SPCX. These map
# entries are SAFE to auto-rewrite because no real listed company trades under them.
# $SPCE is deliberately NOT here: it is Virgin Galactic's real ticker, and KOLs sometimes
# reference it legitimately (incl. warning others not to confuse it with $SPCX).
_INVENTED_TICKER_FIXES = {"SPACEX": "SPCX", "SPACE": "SPCX"}


def _normalize_ticker_code(ticker: object) -> str:
    code = str(ticker).strip().lstrip("$").upper()
    return _INVENTED_TICKER_FIXES.get(code, code)



def render_readme(
    date: str,
    layer1_md: str,
    layer2_kols: list[dict],
    kol_list: list[str],
    history_dirs: list[tuple[str, str]],
    recent_digests: list[tuple[str, str]] | None = None,
) -> str:
    today_digest_path = _digest_rel_path(date)
    kol_count = len(kol_list)
    top_highlights = _render_top_highlights(layer2_kols)
    parts = [
        "# 美股KOL每日摘要",
        "",
        f"最后更新：{date}",
        "",
        f"这个仓库每天北京时间 {settings.schedule.hour:02d}:{settings.schedule.minute:02d} 自动抓取 X 上 {kol_count} 位美股相关 KOL 的发言，整理成一页过去 24 小时市场摘要。你可以先看今日完整报告，再看下面的当日总结和各 KOL 细节。",
        "",
        f"[阅读今日完整报告]({today_digest_path})",
        "",
        "## 你会看到什么",
        "",
        "- **当日总结**：上次运行至本次运行之间最重要的市场共识、分歧和特朗普相关影响",
        "- **最近 7 天**：快速回看过去一周的变化",
        "- **KOL 明细**：每位账号当天具体说了什么",
        "- **历史归档**：按月查看以前的日报",
        "",
        "## 自己运行",
        "",
        "- 默认不会执行远端 `git push`；只有 `publish.git_push=true` 且 `KOL_MONITOR_ALLOW_PUSH=true` 同时满足时才会推送。",
        "- 如果你从 GitHub clone 后直接运行，它不会自动推送到原仓库；要发布到自己的仓库，请先把 `origin` 改成自己的 fork。",
        "- 只想本地验证流程，可以运行 `kol-monitor run-once --no-publish`。",
        "",
        f"## {date} 当日总结",
        "",
        top_highlights,
        "",
        layer1_md.strip(),
        "",
        "## 最近 7 天",
        "",
        _render_recent_digests(recent_digests or []),
        "",
        "## 监控的 KOL",
        "",
        _render_kol_list(kol_list),
        "",
        "<details>",
        "<summary>各 KOL 详细总结（点击展开）</summary>",
        "",
        _render_layer2(layer2_kols),
        "",
        "</details>",
        "",
        "## 历史归档",
        "",
        _render_history(history_dirs),
        "",
    ]
    return "\n".join(parts)


def render_digest_md(date: str, layer1_md: str, layer2_kols: list[dict]) -> str:
    top_highlights = _render_top_highlights(layer2_kols)
    parts = [
        f"# {date} 美股 KOL 每日总结",
        "",
        top_highlights,
        "",
        layer1_md.strip(),
        "",
        "## 各 KOL 详细总结",
        "",
        _render_layer2(layer2_kols),
        "",
    ]
    return "\n".join(parts)


def _render_top_highlights(layer2_kols: list[dict], limit: int = 5) -> str:
    rows = _top_highlight_rows(layer2_kols, limit=limit)
    if not rows:
        return "## 今日最重要 5 条\n\n- 暂无有来源的高质量要点。"
    lines = ["## 今日最重要 5 条", ""]
    for row in rows:
        ticker_text = (
            f"**{', '.join(row['tickers'])}**："
            if row["tickers"]
            else ""
        )
        lines.append(
            f"- {ticker_text}{row['point']} "
            f"[@{row['handle']}]({row['tweet_url']})"
        )
    return "\n".join(lines)


def _top_highlight_rows(layer2_kols: list[dict], limit: int = 5) -> list[dict]:
    candidates: list[tuple[int, int, dict]] = []
    seen_urls: set[str] = set()
    seen_points: set[str] = set()
    handle_counts: Counter = Counter()
    order = 0
    for item in layer2_kols:
        handle = str(item.get("screen_name") or "").strip()
        if not handle:
            continue
        for bullet in item.get("bullets") or []:
            if not isinstance(bullet, dict):
                continue
            point = " ".join(str(bullet.get("point") or "").split())
            url = sanitize_tweet_url(bullet.get("tweet_url"))
            if not point or not url:
                continue
            claim_type = str(bullet.get("claim_type") or "opinion").strip().lower()
            if claim_type in {"personal", "irrelevant"}:
                continue
            point_key = re.sub(r"\s+", "", point)[:80]
            if url in seen_urls or point_key in seen_points:
                continue
            seen_urls.add(url)
            seen_points.add(point_key)
            tickers = []
            for ticker in bullet.get("tickers") or []:
                formatted = _format_ticker(ticker)
                if formatted:
                    tickers.append(formatted)
            row = {
                "handle": handle,
                "point": point,
                "tickers": tickers[:5],
                "tweet_url": url,
                "claim_type": claim_type,
                "confidence": str(bullet.get("confidence") or "medium").strip().lower(),
            }
            candidates.append((_highlight_score(row), order, row))
            order += 1
    candidates.sort(key=lambda item: (-item[0], item[1]))
    selected: list[dict] = []
    for _score, _order, row in candidates:
        handle = row["handle"]
        if handle_counts[handle] >= 2:
            continue
        selected.append(row)
        handle_counts[handle] += 1
        if len(selected) >= limit:
            break
    return selected


def _highlight_score(row: dict) -> int:
    claim_scores = {
        "news": 80,
        "policy": 76,
        "earnings": 72,
        "market_data": 68,
        "trade_signal": 64,
        "opinion": 52,
        "personal": 10,
        "irrelevant": 0,
    }
    confidence_scores = {"high": 8, "medium": 4, "low": 0}
    return (
        claim_scores.get(str(row.get("claim_type") or "opinion"), 52)
        + confidence_scores.get(str(row.get("confidence") or "medium"), 4)
        + min(len(row.get("tickers") or []), 3) * 3
    )


def render_monthly_index(year: int, month: int) -> str:
    month_dir = settings.project_root / "digests" / f"{year:04d}" / f"{month:02d}"
    days = sorted(month_dir.glob("*.md")) if month_dir.exists() else []
    lines = [f"# {year:04d}-{month:02d} 月度归档", ""]
    for path in days:
        if path.name == "README.md":
            continue
        lines.append(f"- [{path.stem}]({path.name})")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML daily report
# ---------------------------------------------------------------------------


def render_daily_html(
    date: str,
    layer1_md: str,
    layer2_kols: list[dict],
    kol_list: list[str],
) -> str:
    """Render the daily digest as a self-contained HTML page."""
    ticker_counts = _count_tickers(layer2_kols)
    sentiment_counts = _count_sentiments(layer2_kols)
    total_kols = len(kol_list)
    active_kols = len(layer2_kols)
    total_tweets = sum(item.get("tweet_count", 0) for item in layer2_kols)

    parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        _html_head(date),
        "<body>",
        '<div class="container">',
        _html_header(date, total_kols, active_kols, total_tweets),
        _html_sentiment_overview(sentiment_counts, ticker_counts),
        _html_layer1_sections(layer1_md),
        _html_trade_signals(layer2_kols),
        _html_kol_cards(layer2_kols),
        _html_footer(date),
        "</div>",
        "</body>",
        "</html>",
    ]
    return "\n".join(parts) + "\n"


def _html_head(date: str) -> str:
    return f"""<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>美股KOL日报 · {date}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --ink: #0f172a;
    --ink-muted: #475569;
    --paper: #fafafa;
    --paper-white: #ffffff;
    --border: #e2e8f0;
    --border-strong: #94a3b8;
    --bullish: #059669;
    --bearish: #dc2626;
    --neutral: #64748b;
    --unclear: #d97706;
    --accent: #0f172a;
    --font: "Inter", -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    --mono: "JetBrains Mono", "SF Mono", "Cascadia Code", monospace;
    --section-gap: 56px;
    --block-gap: 32px;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: var(--font);
    background: var(--paper);
    color: var(--ink);
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }}
  .container {{ max-width: 720px; margin: 0 auto; padding: 64px 28px 80px; }}

  /* ── hero ── */
  .page-hero {{
    margin-bottom: var(--section-gap);
    padding-bottom: 40px;
    border-bottom: 1px solid var(--ink);
  }}
  .page-hero h1 {{
    font-family: var(--font);
    font-size: clamp(36px, 6vw, 56px);
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1.05;
    color: var(--ink);
    margin-bottom: 8px;
  }}
  .page-hero .hero-date {{
    font-size: 16px;
    font-weight: 400;
    color: var(--ink-muted);
    margin-bottom: 28px;
    letter-spacing: 0.01em;
  }}
  .hero-stats {{
    display: flex;
    flex-wrap: wrap;
    gap: 24px;
    font-size: 13px;
    font-weight: 500;
    color: var(--ink-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }}
  .hero-stats span {{ white-space: nowrap; }}
  .hero-stats strong {{
    font-family: var(--mono);
    font-weight: 600;
    font-size: 20px;
    color: var(--ink);
    display: block;
    letter-spacing: -0.02em;
  }}

  /* ── overview ── */
  .overview {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 40px;
    margin-bottom: var(--section-gap);
    padding-bottom: 40px;
    border-bottom: 1px solid var(--border);
  }}
  @media (max-width: 600px) {{ .overview {{ grid-template-columns: 1fr; gap: 28px; }} }}
  .overview-block {{ }}
  .overview-block .block-label {{
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink-muted);
    margin-bottom: 18px;
  }}

  /* sentiment bars — flat */
  .sent-bars {{ display: flex; flex-direction: column; gap: 12px; }}
  .sent-row {{ display: grid; grid-template-columns: 44px 1fr 36px; align-items: center; gap: 10px; }}
  .sent-row .sent-label {{
    font-size: 13px;
    font-weight: 600;
    text-align: right;
  }}
  .sent-row .sent-label.bullish {{ color: var(--bullish); }}
  .sent-row .sent-label.bearish {{ color: var(--bearish); }}
  .sent-row .sent-label.neutral {{ color: var(--neutral); }}
  .sent-row .sent-label.unclear {{ color: var(--unclear); }}
  .sent-bar-wrap {{ height: 8px; background: var(--border); }}
  .sent-bar {{ height: 100%; transition: width .3s; }}
  .sent-bar.bullish {{ background: var(--bullish); }}
  .sent-bar.bearish {{ background: var(--bearish); }}
  .sent-bar.neutral {{ background: var(--neutral); }}
  .sent-bar.unclear {{ background: var(--unclear); }}
  .sent-row .sent-count {{
    font-family: var(--mono);
    font-size: 12px;
    font-weight: 600;
    color: var(--ink-muted);
  }}

  /* ticker list — flat mono tags */
  .ticker-list {{ display: flex; flex-wrap: wrap; gap: 6px 14px; }}
  .ticker-tag {{
    font-family: var(--mono);
    font-size: 14px;
    font-weight: 600;
    color: var(--ink);
    white-space: nowrap;
    padding-bottom: 1px;
    border-bottom: 2px solid transparent;
    text-decoration: none;
  }}
  .ticker-tag.hot {{
    color: var(--bearish);
    border-bottom-color: var(--bearish);
  }}
  .ticker-tag .count {{
    font-size: 10px;
    font-weight: 500;
    color: var(--ink-muted);
    margin-left: 1px;
  }}

  /* ── layer 1 sections ── */
  .layer1 {{ margin-bottom: var(--section-gap); }}
  .layer1 .section-block {{
    margin-bottom: var(--block-gap);
    padding-left: 0;
  }}
  .layer1 .section-block .section-head {{
    font-family: var(--font);
    font-size: 18px;
    font-weight: 700;
    color: var(--ink);
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
    letter-spacing: -0.01em;
  }}
  .layer1 .section-block .section-body {{
    font-size: 14.5px;
    color: #334155;
    line-height: 1.7;
  }}
  .layer1 .section-block .section-body ul,
  .layer1 .section-block .section-body ol {{
    padding-left: 18px;
    margin: 4px 0;
  }}
  .layer1 .section-block .section-body li {{
    margin-bottom: 5px;
  }}
  .layer1 .section-block .section-body li:last-child {{ margin-bottom: 0; }}
  .layer1 .section-block .section-body a {{
    color: var(--ink);
    text-decoration: none;
    border-bottom: 1px solid var(--border-strong);
    font-weight: 500;
    font-size: 13px;
    transition: border-color .15s;
  }}
  .layer1 .section-block .section-body a:hover {{
    border-bottom-color: var(--ink);
  }}
  .layer1 .section-block .section-body strong {{
    color: var(--ink);
    font-weight: 600;
  }}
  .layer1 .section-block .section-body table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13.5px;
  }}
  .layer1 .section-block .section-body th {{
    font-weight: 600;
    text-align: left;
    padding: 8px 10px;
    border-bottom: 2px solid var(--ink);
    color: var(--ink);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .layer1 .section-block .section-body td {{
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }}
  .layer1 .section-block .section-body code {{
    font-family: var(--mono);
    background: transparent;
    padding: 0;
    font-size: 13px;
    font-weight: 600;
  }}

  /* ── trade signals ── */
  .trade-signals {{
    margin-bottom: var(--section-gap);
    padding-bottom: 40px;
    border-bottom: 1px solid var(--border);
  }}
  .trade-signals .section-head {{
    font-family: var(--font);
    font-size: 18px;
    font-weight: 700;
    color: var(--ink);
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--ink);
    letter-spacing: -0.01em;
  }}
  .trade-signals table {{
    width: 100%;
    border-collapse: collapse;
  }}
  .trade-signals th {{
    font-weight: 600;
    text-align: left;
    padding: 8px 10px;
    border-bottom: 2px solid var(--ink);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--ink-muted);
  }}
  .trade-signals td {{
    padding: 10px 10px;
    border-bottom: 1px solid var(--border);
    font-size: 14px;
    vertical-align: top;
  }}
  .trade-signals tr:last-child td {{ border-bottom: none; }}
  .trade-signals .sig-ticker {{
    font-family: var(--mono);
    font-weight: 600;
    font-size: 13px;
    color: var(--ink);
    white-space: nowrap;
  }}
  .trade-signals a {{
    color: var(--ink);
    text-decoration: none;
    border-bottom: 1px solid var(--border-strong);
    font-size: 13px;
    font-weight: 500;
    transition: border-color .15s;
  }}
  .trade-signals a:hover {{ border-bottom-color: var(--ink); }}

  /* ── KOL cards ── */
  .kol-details {{ margin-bottom: var(--section-gap); }}
  .kol-details > h2 {{
    font-family: var(--font);
    font-size: 18px;
    font-weight: 700;
    margin-bottom: 24px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--ink);
    letter-spacing: -0.01em;
  }}
  .kol-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2px 1px;
    background: var(--border);
  }}
  @media (max-width: 600px) {{ .kol-grid {{ grid-template-columns: 1fr; }} }}
  .kol-card {{
    background: var(--paper-white);
    padding: 22px 24px 20px;
    border-left: 3px solid var(--border);
    transition: border-left-color .15s;
  }}
  .kol-card:hover {{ border-left-color: var(--ink); }}
  .kol-card.bullish {{ border-left-color: var(--bullish); }}
  .kol-card.bearish {{ border-left-color: var(--bearish); }}
  .kol-card.neutral {{ border-left-color: var(--neutral); }}
  .kol-card.unclear {{ border-left-color: var(--unclear); }}
  .kol-card .kol-head {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 10px;
  }}
  .kol-card .kol-name {{
    font-family: var(--mono);
    font-size: 13px;
    font-weight: 700;
    color: var(--ink);
    text-decoration: none;
    letter-spacing: -0.01em;
  }}
  .kol-card .kol-name:hover {{ opacity: 0.6; }}
  .kol-card .sent-tag {{
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 0;
    background: none;
  }}
  .sent-tag.bullish {{ color: var(--bullish); }}
  .sent-tag.bearish {{ color: var(--bearish); }}
  .sent-tag.neutral {{ color: var(--neutral); }}
  .sent-tag.unclear {{ color: var(--unclear); }}
  .kol-card .kol-core {{
    font-size: 14px;
    font-weight: 500;
    color: var(--ink);
    margin-bottom: 12px;
    line-height: 1.5;
    font-style: italic;
  }}
  .kol-card .kol-bullets {{
    list-style: none;
    padding: 0;
  }}
  .kol-card .kol-bullets li {{
    font-size: 13px;
    color: #475569;
    margin-bottom: 4px;
    padding-left: 14px;
    position: relative;
    line-height: 1.55;
  }}
  .kol-card .kol-bullets li::before {{
    content: "—";
    position: absolute;
    left: 0;
    color: var(--border-strong);
    font-size: 10px;
  }}
  .kol-card .kol-bullets .ticker-inline {{
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 600;
    color: var(--ink);
  }}
  .kol-card .kol-bullets a {{
    color: var(--ink-muted);
    font-size: 11px;
    text-decoration: none;
    border-bottom: 1px solid var(--border);
    margin-left: 2px;
    transition: border-color .15s;
  }}
  .kol-card .kol-bullets a:hover {{ border-bottom-color: var(--ink); }}
  .kol-card .kol-meta {{
    margin-top: 14px;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--ink-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}

  /* ── footer ── */
  .page-footer {{
    padding-top: 28px;
    border-top: 1px solid var(--border);
    font-size: 11px;
    color: var(--ink-muted);
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }}
  .page-footer a {{
    color: var(--ink);
    text-decoration: none;
    border-bottom: 1px solid var(--border-strong);
  }}
</style>
</head>"""


def _html_header(
    date: str, total_kols: int, active_kols: int, total_tweets: int
) -> str:
    return f"""<header class="page-hero">
<h1>美股 KOL 日报</h1>
<div class="hero-date">{date}</div>
<div class="hero-stats">
  <span><strong>{total_kols}</strong> 位 KOL</span>
  <span><strong>{active_kols}</strong> 位有发言</span>
  <span><strong>{total_tweets}</strong> 条推文</span>
</div>
</header>"""


def _count_sentiments(layer2_kols: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {"bullish": 0, "bearish": 0, "neutral": 0, "unclear": 0}
    for item in layer2_kols:
        sentiment = str(item.get("sentiment", "unclear") or "unclear").strip().lower()
        if sentiment in counts:
            counts[sentiment] += 1
        else:
            counts["unclear"] += 1
    return counts


_SENTIMENT_NAMES = {
    "bullish": "看多",
    "bearish": "看空",
    "neutral": "中性",
    "unclear": "不明",
}


def _html_sentiment_overview(
    sentiment_counts: dict[str, int], ticker_counts: list[tuple[str, int]]
) -> str:
    total = sum(sentiment_counts.values()) or 1

    bar_rows = ""
    for key, label in _SENTIMENT_NAMES.items():
        count = sentiment_counts[key]
        pct = round(count / total * 100)
        bar_rows += (
            f'<div class="sent-row">'
            f'<span class="sent-label {key}">{label}</span>'
            f'<div class="sent-bar-wrap"><div class="sent-bar {key}" style="width:{pct}%"></div></div>'
            f'<span class="sent-count">{count}</span>'
            f"</div>\n"
        )

    ticker_tags = ""
    for ticker, count in ticker_counts[:18]:
        hot = " hot" if count >= max(3, ticker_counts[0][1] * 0.5 if ticker_counts else 1) else ""
        ticker_tags += (
            f'<span class="ticker-tag{hot}">${ticker}'
            f'<span class="count">{count}</span></span>\n'
        )
    if not ticker_tags:
        ticker_tags = '<span style="color:var(--ink-muted);font-size:13px">暂无股票代码</span>'

    return f"""<div class="overview">
<div class="overview-block">
  <div class="block-label">市场情绪</div>
  <div class="sent-bars">
{bar_rows}
  </div>
</div>
<div class="overview-block">
  <div class="block-label">热议标的</div>
  <div class="ticker-list">
{ticker_tags}
  </div>
</div>
</div>"""


def _count_tickers(layer2_kols: list[dict]) -> list[tuple[str, int]]:
    counter: Counter = Counter()
    for item in layer2_kols:
        for bullet in item.get("bullets") or []:
            for ticker in bullet.get("tickers") or []:
                code = _normalize_ticker_code(ticker)
                if code and len(code) <= 6:
                    counter[code] += 1
    return counter.most_common()


def _html_layer1_sections(summary_md: str) -> str:
    """Split Layer 1 markdown by ## headings, render each section flat."""
    md = summary_md.strip()
    if not md:
        return ""

    sections = re.split(r"(?=^## )", md, flags=re.MULTILINE)
    rendered = []

    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        lines = sec.splitlines()
        heading_line = lines[0].strip()
        heading_text = re.sub(r"^#{2,4}\s*", "", heading_line)

        if len(lines) > 1:
            body_text = "\n".join(lines[1:]).strip()
        else:
            body_text = ""

        if not body_text or body_text in ("暂无高质量信号。", "暂无明确判断。", ""):
            body_text = "_暂无高质量信号。_"

        body_html = md_lib.markdown(
            body_text,
            extensions=["extra", "codehilite"],
            output_format="html",
        )

        rendered.append(
            f'<div class="section-block">'
            f'<div class="section-head">{heading_text}</div>'
            f'<div class="section-body">{body_html}</div>'
            f"</div>"
        )

    return f'<div class="layer1">\n{"".join(rendered)}\n</div>'


def _html_trade_signals(layer2_kols: list[dict]) -> str:
    """Build a flat trade signals table from layer2 bullets that contain tickers."""
    rows: list[dict] = []
    for item in layer2_kols:
        handle = str(item.get("screen_name") or "")
        sentiment = str(item.get("sentiment", "unclear")).strip().lower()
        for bullet in item.get("bullets") or []:
            tickers = [
                f"${_normalize_ticker_code(t)}"
                for t in bullet.get("tickers") or []
            ]
            if not tickers:
                continue
            point = str(bullet.get("point", "")).strip()
            url = sanitize_tweet_url(bullet.get("tweet_url", ""))
            if point:
                rows.append(
                    {
                        "tickers": tickers,
                        "point": point,
                        "url": url,
                        "handle": handle,
                        "sentiment": sentiment,
                    }
                )

    if not rows:
        return ""

    table_rows = ""
    for r in rows:
        ticker_cells = ", ".join(
            f'<span class="sig-ticker">{t}</span>' for t in r["tickers"]
        )
        source = (
            f'<a href="{r["url"]}" target="_blank" rel="noopener">@{r["handle"]}</a>'
            if r["url"]
            else f"@{r['handle']}"
        )
        table_rows += (
            f"<tr>"
            f'<td style="white-space:nowrap">{ticker_cells}</td>'
            f"<td>{r['point']}</td>"
            f'<td style="white-space:nowrap">{source}</td>'
            f"</tr>\n"
        )

    return f"""<div class="trade-signals">
<div class="section-head">交易信号</div>
<table>
<thead><tr><th>标的</th><th>线索</th><th>来源</th></tr></thead>
<tbody>
{table_rows}
</tbody>
</table>
</div>"""


def _html_kol_cards(layer2_kols: list[dict]) -> str:
    """Render KOL detail cards in a 2-column grid with left-border sentiment."""
    sorted_kols = sorted(
        [item for item in layer2_kols if _should_render_kol_detail(item)],
        key=lambda item: item.get("tweet_count", 0),
        reverse=True,
    )
    cards = ""
    for item in sorted_kols:
        handle = str(item.get("screen_name") or "")
        core_view = str(item.get("core_view") or "").strip()
        if core_view == "summary_failed":
            core_view = "总结失败，请查看原始推文"
        sentiment = str(item.get("sentiment", "unclear")).strip().lower()
        if sentiment not in ("bullish", "bearish", "neutral", "unclear"):
            sentiment = "unclear"
        tweet_count = item.get("tweet_count", 0)

        bullets_html = ""
        for b in item.get("bullets") or []:
            point = str(b.get("point", "")).strip()
            if not point:
                continue
            tickers_html = ""
            tickers = b.get("tickers") or []
            if tickers:
                codes = [f"${_normalize_ticker_code(t)}" for t in tickers]
                tickers_html = (
                    " "
                    + " ".join(
                        f'<span class="ticker-inline">{c}</span>' for c in codes
                    )
                )
            url = sanitize_tweet_url(b.get("tweet_url", ""))
            link_html = (
                f' <a href="{url}" target="_blank" rel="noopener">↗</a>'
                if url
                else ""
            )
            bullets_html += f"<li>{point}{tickers_html}{link_html}</li>\n"

        cards += (
            f'<div class="kol-card {sentiment}">'
            f'<div class="kol-head">'
            f'<a class="kol-name" href="https://x.com/{handle}" target="_blank" rel="noopener">@{handle}</a>'
            f'<span class="sent-tag {sentiment}">{_SENTIMENT_NAMES.get(sentiment, sentiment)}</span>'
            f"</div>"
            f'<div class="kol-core">{core_view or "暂无核心观点"}</div>'
            f'<ul class="kol-bullets">{bullets_html}</ul>'
            f'<div class="kol-meta">{tweet_count} 条推文</div>'
            f"</div>\n"
        )
    if not cards:
        cards = '<p class="empty-state">暂无 KOL 明细。</p>'

    return f"""<div class="kol-details">
<h2>KOL 详细观点</h2>
<div class="kol-grid">
{cards}
</div>
</div>"""


def _html_footer(date: str) -> str:
    from datetime import datetime, timezone, timedelta

    cst = timezone(timedelta(hours=8))
    now = datetime.now(cst).strftime("%Y-%m-%d %H:%M CST")
    return f"""<footer class="page-footer">
KOL Daily &middot; Generated at {now}
</footer>"""


def write_outputs(date: str) -> list[Path]:
    digest = db.get_digest(date)
    if digest is None:
        raise RuntimeError(f"missing digest for {date}")
    raw_layer2 = json.loads(digest["layer2_json"] or "[]")
    # Normalize before rendering so the published per-KOL detail goes through the same
    # language/residue/model-conflict filters as the layer1 fallback. Without this, the
    # raw layer2 (e.g. an untranslated Korean @blazingbees block, or a leaked tweet_url)
    # would render verbatim into the .md even though the DB-level scan flagged it.
    layer2 = [
        _normalize_layer2_result(dict(item))
        for item in raw_layer2
        if isinstance(item, dict)
    ]
    # Clean the layer1 summary before it reaches any renderer, and fall back to the local
    # sourced template if older DB summaries do not satisfy the current publishability gate.
    layer1_md = _select_publishable_layer1(date, digest["summary_md"] or "", layer2)
    readme = render_readme(
        date=date,
        layer1_md=layer1_md,
        layer2_kols=layer2,
        kol_list=settings.kols,
        history_dirs=history_dirs(),
        recent_digests=recent_digest_links(),
    )
    digest_md = render_digest_md(date, layer1_md, layer2)
    readme_path = settings.project_root / "README.md"
    year, month, day = date.split("-")
    digest_dir = settings.project_root / "digests" / year / month
    digest_dir.mkdir(parents=True, exist_ok=True)
    md_path = digest_dir / f"{day}.md"
    readme_path.write_text(readme, encoding="utf-8")
    md_path.write_text(digest_md, encoding="utf-8")
    _scan_rendered_digest(date, digest_md)
    # HTML output was retired 2026-06-18 (per-day .html no longer generated; the Markdown
    # digest + README are the published artifacts). render_daily_html() is kept as a
    # standalone renderer in case HTML is reinstated, but is intentionally not called here.
    return [readme_path, md_path]


def _select_publishable_layer1(date: str, raw_layer1: str, layer2: list[dict]) -> str:
    cleaned = _prepare_layer1_markdown(raw_layer1)
    if not _layer1_has_quality_errors(cleaned):
        return cleaned

    trump_summary = next(
        (
            item
            for item in layer2
            if str(item.get("screen_name") or "").lower() == "realdonaldtrump"
        ),
        None,
    )
    fallback = _prepare_layer1_markdown(
        _fallback_layer1_markdown(layer2, trump_summary=trump_summary)
    )
    if not _layer1_has_quality_errors(fallback):
        logger.warning("layer1 %s failed publish scan; using local fallback summary", date)
        return fallback

    logger.error("layer1 %s and local fallback both failed publish scan; using cleaned layer1", date)
    return cleaned


def _layer1_has_quality_errors(markdown: str) -> bool:
    try:
        from kol_monitor.quality import scan_summary_quality

        report = scan_summary_quality(markdown)
    except Exception:
        logger.exception("layer1 quality scan failed")
        return False
    return bool(report.get("error_count"))


def premarket_path(date: str) -> Path:
    year, month, day = date.split("-")
    return settings.project_root / "premarket" / year / month / f"{day}.md"


def write_premarket(date: str, tweet_text: str) -> Path:
    """Legacy helper for writing a Layer 3 pre-market tweet draft.

    Daily run/regen no longer call this function; keep it available for manual experiments
    or a future reinstatement. The file holds only the tweet body (no front matter)."""
    path = premarket_path(date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tweet_text.strip() + "\n", encoding="utf-8")
    return path


def _scan_rendered_digest(date: str, digest_md: str) -> None:
    """Scan the final rendered markdown (what readers actually see) and log any defects.

    The DB-level layer1/layer2 gates run earlier, but rendering can still introduce
    reader-visible defects (broken source links, leaked JSON, residue). Surfacing them
    here closes the gap where a passing DB scan diverged from the published .md. Logged,
    not raised, to honor the publish-must-not-fail rule.
    """
    try:
        from kol_monitor.quality import scan_summary_quality

        report = scan_summary_quality(digest_md)
    except Exception:  # never let the gate break publishing
        logger.exception("rendered digest scan failed for %s", date)
        return
    if report.get("error_count"):
        codes = report.get("issue_counts_by_code", {})
        logger.error(
            "rendered digest %s has %d quality errors after render: %s",
            date,
            report["error_count"],
            codes,
        )
    elif report.get("warning_count"):
        logger.warning(
            "rendered digest %s has %d warnings: %s",
            date,
            report["warning_count"],
            report.get("issue_counts_by_code", {}),
        )


def git_publish(date: str, files: list[Path]) -> bool:
    rel_files = [str(path.relative_to(settings.project_root)) for path in files]
    env = _git_env()
    subprocess.run(["git", "add", *rel_files], cwd=settings.project_root, env=env, check=True)
    message = f"digest: {date}"
    subprocess.run(["git", "commit", "-m", message], cwd=settings.project_root, env=env, check=True)
    if settings.publish.git_push and getattr(settings, "allow_git_push", False):
        _git_push_with_retry(env)
    db.mark_digest_published(date)
    return True


def _git_push_with_retry(env: dict[str, str] | None) -> None:
    attempts = max(1, int(getattr(settings.publish, "push_retry", 1) or 1))
    delay = 5
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(1, attempts + 1):
        try:
            subprocess.run(["git", "push", "origin", "main"], cwd=settings.project_root, env=env, check=True)
            return
        except subprocess.CalledProcessError as exc:
            last_error = exc
            if attempt >= attempts:
                break
            logger.warning("git push failed on attempt %s/%s; retrying in %ss", attempt, attempts, delay)
            time.sleep(delay)
            delay *= 2
    logger.error("git push failed after %s attempts", attempts)
    if last_error is not None:
        raise last_error


def _git_env() -> dict[str, str] | None:
    alt_git_dir = settings.project_root / ".git-data"
    if not alt_git_dir.exists():
        return None
    env = os.environ.copy()
    env.setdefault("HOME", str(Path.home()))
    env["GIT_DIR"] = str(alt_git_dir)
    env["GIT_WORK_TREE"] = str(settings.project_root)
    return env


def history_dirs() -> list[tuple[str, str]]:
    base = settings.project_root / "digests"
    if not base.exists():
        return []
    entries: list[tuple[str, str]] = []
    for year_dir in sorted(base.iterdir(), reverse=True):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        for month_dir in sorted(year_dir.iterdir(), reverse=True):
            if month_dir.is_dir() and month_dir.name.isdigit():
                label = f"{year_dir.name}-{month_dir.name}"
                entries.append((label, f"digests/{year_dir.name}/{month_dir.name}/"))
    return entries[: settings.publish.history_index_months]


def recent_digest_links(limit: int = 7) -> list[tuple[str, str]]:
    base = settings.project_root / "digests"
    if not base.exists():
        return []
    files = sorted(base.glob("*/*/*.md"), reverse=True)
    entries = []
    for path in files:
        if path.name == "README.md":
            continue
        try:
            year = path.parent.parent.name
            month = path.parent.name
            day = path.stem
            label = f"{year}-{month}-{day}"
        except Exception:
            continue
        entries.append((label, str(path.relative_to(settings.project_root))))
        if len(entries) >= limit:
            break
    return entries


def _render_kol_list(kol_list: list[str]) -> str:
    return "\n".join(f"- [@{handle}](https://x.com/{handle})" for handle in kol_list)


def _render_history(history: list[tuple[str, str]]) -> str:
    if not history:
        return "暂无历史归档。"
    return "\n".join(f"- [{label}]({path})" for label, path in history)


def _render_recent_digests(recent: list[tuple[str, str]]) -> str:
    if not recent:
        return "暂无最近日报。"
    return "\n".join(f"- [{label}]({path})" for label, path in recent)


def _digest_rel_path(date: str) -> str:
    year, month, day = date.split("-")
    return f"digests/{year}/{month}/{day}.md"


def _render_layer2(layer2_kols: list[dict]) -> str:
    renderable = [item for item in layer2_kols if _should_render_kol_detail(item)]
    if not renderable:
        return "暂无 KOL 明细。"
    sections = []
    for item in sorted(renderable, key=lambda row: row.get("tweet_count", 0), reverse=True):
        sections.append(
            f"### @{item.get('screen_name')} · {item.get('tweet_count', 0)} 条\n\n"
            f"**核心观点**：{item.get('core_view', '')}\n\n"
            f"**情绪**：{item.get('sentiment', 'unclear')}\n\n"
            f"{_render_bullets(item.get('bullets') or [])}"
        )
    return "\n\n".join(sections)


def _should_render_kol_detail(item: dict) -> bool:
    core_view = str(item.get("core_view") or "").strip().lower()
    if core_view == "summary_failed":
        return True
    if core_view in {"无市场相关内容", "暂无要点", "no market relevant content"}:
        return False
    return bool(item.get("bullets"))


def _render_bullets(bullets: list[dict]) -> str:
    if not bullets:
        return "- 暂无要点。"
    lines = []
    for bullet in bullets:
        tickers = bullet.get("tickers") or []
        formatted_tickers = [_format_ticker(ticker) for ticker in tickers]
        formatted_tickers = [ticker for ticker in formatted_tickers if ticker]
        ticker_text = f" ({', '.join(formatted_tickers)})" if formatted_tickers else ""
        link = sanitize_tweet_url(bullet.get("tweet_url"))
        link_text = f" [原推]({link})" if link else ""
        lines.append(f"- {bullet.get('point', '')}{ticker_text}{link_text}")
    return "\n".join(lines)


def _format_ticker(ticker: object) -> str:
    code = _normalize_ticker_code(ticker)
    return f"${code}" if code else ""
