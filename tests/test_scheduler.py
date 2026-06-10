from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from kol_monitor.scheduler import _daily_trigger


def test_daily_trigger_uses_configured_timezone():
    trigger = _daily_trigger()
    shanghai = ZoneInfo("Asia/Shanghai")

    next_fire = trigger.get_next_fire_time(
        None,
        datetime(2026, 5, 30, 21, 17, tzinfo=shanghai),
    )

    assert str(trigger.timezone) == "Asia/Shanghai"
    assert next_fire is not None
    assert next_fire.astimezone(shanghai).strftime("%Y-%m-%d %H:%M") == "2026-05-31 21:00"
