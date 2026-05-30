from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml
from dotenv import load_dotenv


class ConfigError(RuntimeError):
    pass


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{key: _namespace(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_namespace(item) for item in value]
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"missing config file: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"config file must contain a mapping: {path}")
    return data


def load_settings(root: str | Path | None = None) -> SimpleNamespace:
    project_root = Path(root).resolve() if root else PROJECT_ROOT
    load_dotenv(project_root / ".env")

    settings_data = _load_yaml(project_root / "config" / "settings.yaml")
    kols_data = _load_yaml(project_root / "config" / "kols.yaml")
    kols = kols_data.get("kols", [])
    if not isinstance(kols, list) or not all(isinstance(item, str) for item in kols):
        raise ConfigError("config/kols.yaml must contain a string list under 'kols'")

    if os.getenv("ANTHROPIC_MODEL"):
        settings_data.setdefault("ai", {})["model"] = os.environ["ANTHROPIC_MODEL"]

    settings = _namespace(settings_data)
    settings.project_root = project_root
    settings.kols = kols
    settings.db_path = Path(os.getenv("KOL_MONITOR_DB") or project_root / "kol_monitor.db")
    settings.media_dir = Path(os.getenv("KOL_MONITOR_MEDIA_DIR") or project_root / "media")
    settings.opentwitter_token = os.getenv("OPENTWITTER_TOKEN")
    settings.opentwitter_base_url = os.getenv("OPENTWITTER_BASE_URL") or "https://ai.6551.io"
    settings.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    settings.anthropic_base_url = os.getenv("ANTHROPIC_BASE_URL") or None
    settings.anthropic_fallback_api_key = os.getenv("ANTHROPIC_FALLBACK_API_KEY")
    settings.anthropic_fallback_base_url = (
        os.getenv("ANTHROPIC_FALLBACK_BASE_URL") or settings.anthropic_base_url
    )
    return settings


settings = load_settings()
