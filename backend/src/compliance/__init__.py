"""Compliance: thresholds, roll-ups, advisory checks, and P&L reconciliation.

Public API (Agent D):
  apply_thresholds_and_rollups(bundle, config) -> NormalizedBundle
  run_compliance(bundle, config) -> list[Finding]
  reconcile(bundle, config) -> tuple[str, list[Finding], bool]
  write_reconciliation_report(path, report_text) -> None
"""

from __future__ import annotations

from .checks import run_compliance
from .reconcile import reconcile, write_reconciliation_report
from .thresholds import apply_thresholds_and_rollups

__all__ = [
    "apply_thresholds_and_rollups",
    "run_compliance",
    "reconcile",
    "write_reconciliation_report",
]
