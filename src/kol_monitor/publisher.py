from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from kol_monitor import db
from kol_monitor.config import settings


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
    parts = [
        "# 美股 KOL 每日监控",
        "",
        f"最后更新：{date}",
        "",
        f"每天自动抓取 {kol_count} 位美股相关 X/KOL，提炼当日市场共识、分歧和特朗普相关影响。",
        "",
        f"[阅读今日完整报告]({today_digest_path})",
        "",
        f"## {date} 当日总结",
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
    parts = [
        f"# {date} 美股 KOL 每日总结",
        "",
        layer1_md.strip(),
        "",
        "## 各 KOL 详细总结",
        "",
        _render_layer2(layer2_kols),
        "",
    ]
    return "\n".join(parts)


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


def write_outputs(date: str) -> tuple[Path, Path]:
    digest = db.get_digest(date)
    if digest is None:
        raise RuntimeError(f"missing digest for {date}")
    layer2 = json.loads(digest["layer2_json"] or "[]")
    readme = render_readme(
        date=date,
        layer1_md=digest["summary_md"],
        layer2_kols=layer2,
        kol_list=settings.kols,
        history_dirs=history_dirs(),
        recent_digests=recent_digest_links(),
    )
    digest_md = render_digest_md(date, digest["summary_md"], layer2)
    readme_path = settings.project_root / "README.md"
    year, month, day = date.split("-")
    digest_path = settings.project_root / "digests" / year / month / f"{day}.md"
    digest_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text(readme, encoding="utf-8")
    digest_path.write_text(digest_md, encoding="utf-8")
    return readme_path, digest_path


def git_publish(date: str, files: list[Path]) -> bool:
    rel_files = [str(path.relative_to(settings.project_root)) for path in files]
    env = _git_env()
    subprocess.run(["git", "add", *rel_files], cwd=settings.project_root, env=env, check=True)
    message = f"digest: {date}"
    subprocess.run(["git", "commit", "-m", message], cwd=settings.project_root, env=env, check=True)
    if settings.publish.git_push:
        subprocess.run(["git", "push", "origin", "main"], cwd=settings.project_root, env=env, check=True)
    db.mark_digest_published(date)
    return True


def _git_env() -> dict[str, str] | None:
    alt_git_dir = settings.project_root / ".git-data"
    if not alt_git_dir.exists():
        return None
    env = os.environ.copy()
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
    if not layer2_kols:
        return "暂无 KOL 明细。"
    sections = []
    for item in sorted(layer2_kols, key=lambda row: row.get("tweet_count", 0), reverse=True):
        sections.append(
            f"### @{item.get('screen_name')} · {item.get('tweet_count', 0)} 条\n\n"
            f"**核心观点**：{item.get('core_view', '')}\n\n"
            f"**情绪**：{item.get('sentiment', 'unclear')}\n\n"
            f"{_render_bullets(item.get('bullets') or [])}"
        )
    return "\n\n".join(sections)


def _render_bullets(bullets: list[dict]) -> str:
    if not bullets:
        return "- 暂无要点。"
    lines = []
    for bullet in bullets:
        tickers = bullet.get("tickers") or []
        ticker_text = f" ({', '.join(tickers)})" if tickers else ""
        link = bullet.get("tweet_url")
        link_text = f" [原推]({link})" if link else ""
        lines.append(f"- {bullet.get('point', '')}{ticker_text}{link_text}")
    return "\n".join(lines)
