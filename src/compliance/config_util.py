"""Load compliance config dict from YAML path or pass-through mapping."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, MutableMapping

import yaml


def load_config(config: Mapping[str, Any] | str | Path | None = None) -> dict[str, Any]:
    """Return a config dict.

    ``config`` may be an already-loaded mapping, a path to YAML, or None
    (loads ``config/defaults.yaml`` relative to the repo root).
    """
    if config is None:
        root = Path(__file__).resolve().parents[2]
        path = root / "config" / "defaults.yaml"
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise TypeError(f"config root must be a mapping: {path}")
        return data
    if isinstance(config, (str, Path)):
        path = Path(config)
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise TypeError(f"config root must be a mapping: {path}")
        return data
    return dict(config)


def merge_config(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Shallow-merge top-level keys; nested dicts are replaced, not deep-merged."""
    out: MutableMapping[str, Any] = dict(base)
    out.update(override)
    return dict(out)
