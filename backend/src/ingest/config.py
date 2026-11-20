"""Load pipeline defaults from config/defaults.yaml (never hardcode delete amounts)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG = _REPO_ROOT / "config" / "defaults.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load YAML config. Defaults to repo ``config/defaults.yaml``."""
    cfg_path = Path(path) if path is not None else _DEFAULT_CONFIG
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Config not found: {cfg_path}")
    with cfg_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a mapping: {cfg_path}")
    return data


def repo_root() -> Path:
    return _REPO_ROOT
