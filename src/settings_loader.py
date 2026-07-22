"""Load ``config/settings.yaml`` with optional environment overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SETTINGS_PATH = _PROJECT_ROOT / "config" / "settings.yaml"


def project_root() -> Path:
    return _PROJECT_ROOT


def _coerce_env_value(raw: str) -> Any:
    lowered = raw.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        pass
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("'\"") for item in inner.split(",")]
    return raw


def _apply_env_overrides(settings: dict[str, Any]) -> dict[str, Any]:
    prefix = "SETTINGS__"
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix) :].lower().split("__")
        node: Any = settings
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = _coerce_env_value(value)
    return settings


def load_settings(path: Path | None = None) -> dict[str, Any]:
    settings_path = path or _DEFAULT_SETTINGS_PATH
    with settings_path.open(encoding="utf-8") as fh:
        settings: dict[str, Any] = yaml.safe_load(fh) or {}
    settings = _apply_env_overrides(settings)
    if os.environ.get("NVIDIA_API_BASE"):
        settings["base_url"] = os.environ["NVIDIA_API_BASE"]
    return settings


# Writable state that should live under $DATA_DIR when set (cloud persistence).
_DATA_DIR_KEYS = {"output_dir", "tracker_xlsx", "jobs_db"}


def resolve_path(relative: str, settings: dict[str, Any] | None = None) -> Path:
    """Resolve a path from settings ``paths`` or a relative project path.

    If the ``DATA_DIR`` environment variable is set, writable state (outputs, the
    tracker spreadsheet, and the jobs database) is placed under it so it survives
    restarts on a mounted disk in the cloud.
    """
    root = project_root()
    rel = relative
    if settings:
        rel = settings.get("paths", {}).get(relative, relative)

    data_dir = os.environ.get("DATA_DIR", "").strip()
    if data_dir and relative in _DATA_DIR_KEYS:
        return Path(data_dir).expanduser() / Path(rel).name
    return root / rel


def app_mode(settings: dict[str, Any] | None = None) -> str:
    """Return the deployment mode: ``local`` (default) or ``cloud``."""
    settings = settings or {}
    return str(settings.get("mode", "local")).strip().lower() or "local"


def feature_enabled(
    settings: dict[str, Any] | None, name: str, default: bool = True
) -> bool:
    """Whether a feature flag is on. ``apply_autofill`` is forced off in cloud mode."""
    settings = settings or {}
    features = settings.get("features", {}) or {}
    value = bool(features.get(name, default))
    if name == "apply_autofill" and app_mode(settings) != "local":
        return False
    return value
