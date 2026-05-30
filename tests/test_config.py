from __future__ import annotations

from kol_monitor.config import load_settings


def test_load_settings_reads_existing_yaml():
    settings = load_settings()

    assert len(settings.kols) == 54
    assert settings.schedule.hour == 20
    assert settings.schedule.timezone == "Asia/Shanghai"


def test_env_overrides_paths(monkeypatch, tmp_path):
    db_path = tmp_path / "custom.db"
    media_dir = tmp_path / "custom_media"
    monkeypatch.setenv("KOL_MONITOR_DB", str(db_path))
    monkeypatch.setenv("KOL_MONITOR_MEDIA_DIR", str(media_dir))

    settings = load_settings()

    assert settings.db_path == db_path
    assert settings.media_dir == media_dir
