from __future__ import annotations

from kol_monitor.config import load_settings


def test_load_settings_reads_existing_yaml(monkeypatch):
    monkeypatch.setattr("kol_monitor.config.load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.delenv("KOL_MONITOR_ALLOW_PUSH", raising=False)

    settings = load_settings()

    assert len(settings.kols) == 57
    assert settings.schedule.hour == 20
    assert settings.schedule.minute == 0
    assert settings.schedule.timezone == "Asia/Shanghai"
    assert settings.allow_git_push is False


def test_git_push_requires_explicit_env(monkeypatch):
    monkeypatch.setattr("kol_monitor.config.load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.delenv("KOL_MONITOR_ALLOW_PUSH", raising=False)

    settings = load_settings()

    assert settings.allow_git_push is False


def test_git_push_env_can_enable(monkeypatch):
    monkeypatch.setattr("kol_monitor.config.load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("KOL_MONITOR_ALLOW_PUSH", "true")

    settings = load_settings()

    assert settings.allow_git_push is True


def test_env_local_overrides_env_file(tmp_path):
    project_root = tmp_path
    config_dir = project_root / "config"
    config_dir.mkdir()
    (config_dir / "settings.yaml").write_text(
        "ai:\n  model: claude-sonnet-4-6\nkols:\n  - alice\n",
        encoding="utf-8",
    )
    (config_dir / "kols.yaml").write_text("kols:\n  - alice\n", encoding="utf-8")
    (project_root / ".env").write_text("KOL_MONITOR_ALLOW_PUSH=false\n", encoding="utf-8")
    (project_root / ".env.local").write_text("KOL_MONITOR_ALLOW_PUSH=true\n", encoding="utf-8")

    settings = load_settings(project_root)

    assert settings.allow_git_push is True


def test_env_overrides_paths(monkeypatch, tmp_path):
    db_path = tmp_path / "custom.db"
    media_dir = tmp_path / "custom_media"
    monkeypatch.setenv("KOL_MONITOR_DB", str(db_path))
    monkeypatch.setenv("KOL_MONITOR_MEDIA_DIR", str(media_dir))

    settings = load_settings()

    assert settings.db_path == db_path
    assert settings.media_dir == media_dir


def test_anthropic_fallback_env(monkeypatch):
    monkeypatch.setattr("kol_monitor.config.load_dotenv", lambda *_args, **_kwargs: None)
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
