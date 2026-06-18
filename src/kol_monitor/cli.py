from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from kol_monitor import db
from kol_monitor.config import settings
from kol_monitor.fetcher import backfill_incomplete, daily_fetch
from kol_monitor.client import OpenTwitterClient
from kol_monitor.logging_setup import setup
from kol_monitor.media import download_pending_media
from kol_monitor.publisher import git_publish, write_outputs, write_premarket
from kol_monitor.quality import DEFAULT_QUALITY_DRAFT_DIR, write_quality_draft
from kol_monitor.scheduler import run_daemon
from kol_monitor.summarizer import generate_layer3_tweet, summarize_day


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kol-monitor")
    sub = parser.add_subparsers(dest="command", required=True)

    run_once = sub.add_parser("run-once", help="run fetch, media, summarize, and publish once")
    run_once.add_argument("--date", help="digest date, default is today in Asia/Shanghai")
    run_once.add_argument("--dry-run", action="store_true", help="validate command wiring without API calls")
    run_once.add_argument("--no-publish", action="store_true", help="write markdown but skip git commit/push")

    fetch_only = sub.add_parser("fetch-only", help="fetch tweets only")
    fetch_only.add_argument("--dry-run", action="store_true")

    backfill = sub.add_parser("backfill", help="run incomplete search backfill")
    backfill.add_argument("--dry-run", action="store_true")

    regen = sub.add_parser("regen-digest", help="regenerate digest markdown for a date")
    regen.add_argument("--date", required=True)
    regen.add_argument("--no-publish", action="store_true")

    premarket = sub.add_parser(
        "premarket",
        help="(re)generate the Layer 3 pre-market tweet draft for a date (no publish)",
    )
    premarket.add_argument("--date", required=True)

    quality_draft = sub.add_parser(
        "quality-draft",
        help="write no-publish digest repair drafts and quality reports for a date",
    )
    quality_draft.add_argument("--date", required=True)
    quality_draft.add_argument(
        "--output-dir",
        default=str(DEFAULT_QUALITY_DRAFT_DIR),
        help=f"draft root directory, default: {DEFAULT_QUALITY_DRAFT_DIR}",
    )
    quality_draft.add_argument("--dry-run", action="store_true")

    sub.add_parser("daemon", help="start scheduler daemon")
    sub.add_parser("list-kols", help="print configured KOL handles")
    sub.add_parser("validate-handles", help="validate all configured handles with 6551")

    add_kol = sub.add_parser("add-kol", help="append one KOL handle to config/kols.yaml")
    add_kol.add_argument("handle")
    add_kol.add_argument("--validate", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup(settings.logging.level, settings.logging.file, settings.logging.rich_console)

    if args.command == "list-kols":
        print(f"{len(settings.kols)} KOL handles")
        for handle in settings.kols:
            print(handle)
        return

    if getattr(args, "dry_run", False):
        print(f"dry run: {args.command} command is wired")
        raise SystemExit(0)

    if args.command == "run-once":
        asyncio.run(_run_once(args.date or _today_shanghai(), publish=not args.no_publish))
        return
    if args.command == "fetch-only":
        asyncio.run(daily_fetch(trigger="manual"))
        return
    if args.command == "backfill":
        asyncio.run(_backfill())
        return
    if args.command == "regen-digest":
        asyncio.run(_regen_digest(args.date, publish=not args.no_publish))
        return
    if args.command == "premarket":
        path = asyncio.run(_premarket_only(args.date))
        print(f"premarket draft: {path}")
        return
    if args.command == "quality-draft":
        result = write_quality_draft(args.date, output_dir=args.output_dir)
        report = result["report"]
        print(f"quality draft: {report['status']}")
        print(f"output: {result['output_dir']}")
        for name, path in result["files"].items():
            print(f"{name}: {path}")
        return
    if args.command == "daemon":
        run_daemon()
        return
    if args.command == "validate-handles":
        asyncio.run(_validate_all())
        return
    if args.command == "add-kol":
        asyncio.run(_add_kol(args.handle, validate=args.validate))
        return


async def _run_once(date: str, publish: bool) -> None:
    await daily_fetch(trigger="manual")
    await download_pending_media(date)
    await summarize_day(date)
    files = write_outputs(date)
    await _append_premarket(date, files)
    if publish:
        git_publish(date, list(files))


async def _regen_digest(date: str, publish: bool) -> None:
    await summarize_day(date)
    files = write_outputs(date)
    await _append_premarket(date, files)
    if publish:
        git_publish(date, list(files))


async def _append_premarket(date: str, files: list[Path]) -> None:
    """Generate the Layer 3 pre-market tweet draft and append its path to the publish set.

    Best-effort: a failure here is logged and skipped so it never blocks the digest
    (Layer 1 / Layer 2)."""
    import logging

    try:
        tweet = await generate_layer3_tweet(date)
        files.append(write_premarket(date, tweet))
    except Exception as exc:  # Layer 3 is supplementary, never break the digest
        logging.getLogger(__name__).warning("layer3 premarket generation failed for %s: %s", date, exc)


async def _premarket_only(date: str) -> Path:
    tweet = await generate_layer3_tweet(date)
    return write_premarket(date, tweet)


async def _backfill() -> None:
    if not settings.opentwitter_token:
        raise RuntimeError("OPENTWITTER_TOKEN is required")
    client = OpenTwitterClient(settings.opentwitter_token, settings.opentwitter_base_url)
    try:
        await backfill_incomplete(client)
    finally:
        await client.close()


async def _validate_all() -> None:
    if not settings.opentwitter_token:
        raise RuntimeError("OPENTWITTER_TOKEN is required")
    client = OpenTwitterClient(settings.opentwitter_token, settings.opentwitter_base_url)
    try:
        db.init_db(settings.db_path)
        for handle in settings.kols:
            info = await client.user_info(handle)
            if info is None:
                db.mark_kol_inactive(handle, "user_info returned empty")
                print(f"{handle}: invalid")
            else:
                db.upsert_kol(handle, info.get("display_name"), info.get("twitter_user_id"))
                print(f"{handle}: ok")
    finally:
        await client.close()


async def _add_kol(handle: str, validate: bool) -> None:
    normalized = handle.lstrip("@")
    if normalized in settings.kols:
        print(f"{normalized} already exists")
        return
    if validate:
        if not settings.opentwitter_token:
            raise RuntimeError("OPENTWITTER_TOKEN is required")
        client = OpenTwitterClient(settings.opentwitter_token, settings.opentwitter_base_url)
        try:
            info = await client.user_info(normalized)
        finally:
            await client.close()
        if info is None:
            raise RuntimeError(f"handle validation failed: {normalized}")
    _append_kol_to_config(normalized)
    print(f"added {normalized}")


def _append_kol_to_config(handle: str) -> None:
    path = settings.project_root / "config" / "kols.yaml"
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + f"  - {handle}\n", encoding="utf-8")


def _today_shanghai() -> str:
    return datetime.now(ZoneInfo(settings.schedule.timezone)).date().isoformat()


if __name__ == "__main__":
    main()
