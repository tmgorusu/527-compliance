"""
Agent A — cleaning / normalization after $1 deletion.

Roll-up policy (documented for Agent B/D):
  Input Final-sheet lines named ``AGGREGATE BELOW THRESHOLD`` or ``WITHHELD``
  are cleaned and kept with ``is_rollup=True`` so XML build can proceed against
  real client data. Agent D may strip/rebuild them later. Thresholds are not
  applied here; ``NormalizedBundle.rollups`` is left empty by the pipeline.

Public helpers
--------------
- ``clean_cover`` / ``clean_schedule_a`` / ``clean_schedule_b`` / ``clean_pl``
- ``filter_unapplied_cash``
- ``RejectCollector``
- field helpers in ``src.cleaning.fields`` / ``src.cleaning.money``
"""

from src.cleaning.records import (
    clean_cover,
    clean_pl,
    clean_schedule_a,
    clean_schedule_b,
    detect_rollup,
)
from src.cleaning.rejects import RejectCollector, RejectRow
from src.cleaning.unapplied import filter_unapplied_cash, is_unapplied_cash_row

__all__ = [
    "RejectCollector",
    "RejectRow",
    "clean_cover",
    "clean_pl",
    "clean_schedule_a",
    "clean_schedule_b",
    "detect_rollup",
    "filter_unapplied_cash",
    "is_unapplied_cash_row",
]
