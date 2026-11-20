"""Load pipeline config from YAML (defaults + optional override)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "defaults.yaml"


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load defaults.yaml, then deep-merge an optional override file."""
    base = _read_yaml(DEFAULT_CONFIG_PATH)
    if path is None:
        return base
    override_path = Path(path)
    if not override_path.is_file():
        raise FileNotFoundError(f"Config file not found: {override_path}")
    override = _read_yaml(override_path)
    return _deep_merge(base, override)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a mapping: {path}")
    return data


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(value, dict)
        ):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out
