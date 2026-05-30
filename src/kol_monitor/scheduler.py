from __future__ import annotations

import asyncio
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from kol_monitor.config import settings

logger = logging.getLogger(__name__)


def daily_job_sync_wrapper() -> None:
    from kol_monitor.cli import _run_once

    logger.info("starting scheduled KOL monitor job")
    asyncio.run(_run_once(_today(), publish=True))


def run_daemon() -> None:
    scheduler = BlockingScheduler(timezone=ZoneInfo(settings.schedule.timezone))
    scheduler.add_job(
        daily_job_sync_wrapper,
        CronTrigger(hour=settings.schedule.hour, minute=settings.schedule.minute),
        misfire_grace_time=settings.schedule.misfire_grace_seconds,
        coalesce=True,
    )
    scheduler.start()


def _today() -> str:
    from datetime import datetime

    return datetime.now(ZoneInfo(settings.schedule.timezone)).date().isoformat()
