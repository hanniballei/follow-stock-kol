from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from kol_monitor.scheduler import _daily_trigger, daily_job_sync_wrapper


def test_daily_trigger_uses_configured_timezone():
    trigger = _daily_trigger()
    shanghai = ZoneInfo("Asia/Shanghai")

    next_fire = trigger.get_next_fire_time(
        None,
        datetime(2026, 5, 30, 21, 17, tzinfo=shanghai),
    )

    assert str(trigger.timezone) == "Asia/Shanghai"
    assert next_fire is not None
    # Daily run is 20:30 Beijing; from 21:17 on the 30th the next fire is the 31st 20:30.
    assert next_fire.astimezone(shanghai).strftime("%Y-%m-%d %H:%M") == "2026-05-31 20:30"


def test_daily_job_marks_fetch_run_as_scheduled(monkeypatch):
    calls = []

    async def fake_run_once(date, publish, trigger):
        calls.append((date, publish, trigger))

    monkeypatch.setattr("kol_monitor.cli._run_once", fake_run_once)
    monkeypatch.setattr("kol_monitor.scheduler._today", lambda: "2026-05-31")

    daily_job_sync_wrapper()

    assert calls == [("2026-05-31", True, "scheduled")]
