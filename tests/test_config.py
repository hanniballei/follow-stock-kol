from __future__ import annotations

from kol_monitor.config import load_settings


def test_load_settings_reads_existing_yaml():
    settings = load_settings()

    assert len(settings.kols) == 53
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


def test_anthropic_fallback_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "primary")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://primary.example")
    monkeypatch.setenv("ANTHROPIC_FALLBACK_API_KEY", "fallback")
    monkeypatch.setenv("ANTHROPIC_FALLBACK_BASE_URL", "https://fallback.example")
    monkeypatch.setenv("ANTHROPIC_THIRD_API_KEY", "third")
    monkeypatch.setenv("ANTHROPIC_THIRD_BASE_URL", "https://third.example")
    monkeypatch.setenv("ANTHROPIC_THIRD_MODEL", "anthropic/claude-sonnet-4.6")

    settings = load_settings()

    assert settings.anthropic_api_key == "primary"
    assert settings.anthropic_base_url == "https://primary.example"
    assert settings.anthropic_fallback_api_key == "fallback"
    assert settings.anthropic_fallback_base_url == "https://fallback.example"
    assert settings.anthropic_third_api_key == "third"
    assert settings.anthropic_third_base_url == "https://third.example"
    assert settings.anthropic_third_model == "anthropic/claude-sonnet-4.6"
