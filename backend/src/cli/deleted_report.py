"""deleted_records.txt formatting — PIPELINE.md contract (Agent E golden owner).

Agent A writes this file during delete_$1; this helper locks the golden format
and can re-emit from ``DeletedRecord`` lists during the report step.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Sequence

from contract.models import DeletedRecord

NO_RECORDS_LINE = "NO RECORDS DELETED"


def _money(amount: str) -> Decimal:
    return Decimal(amount)


def format_deleted_line(rec: DeletedRecord) -> str:
    """Single deleted row line per PIPELINE.md."""
    date = rec.date if rec.date is not None else ""
    name = rec.name if rec.name is not None else ""
    return (
        f"DELETED | {rec.schedule} | {rec.source_row} | {date} | "
        f"{name} | {rec.amount} | {rec.reason}"
    )


def summarize_deletions(records: Sequence[DeletedRecord]) -> dict[str, object]:
    """Return count, total dollars, and per-schedule breakdown."""
    by_schedule: dict[str, dict[str, object]] = {}
    total = Decimal("0.00")
    for rec in records:
        total += _money(rec.amount)
        bucket = by_schedule.setdefault(
            rec.schedule, {"count": 0, "total": Decimal("0.00")}
        )
        bucket["count"] = int(bucket["count"]) + 1
        bucket["total"] = Decimal(str(bucket["total"])) + _money(rec.amount)
    return {
        "count": len(records),
        "total": f"{total.quantize(Decimal('0.01'))}",
        "by_schedule": {
            sched: {
                "count": data["count"],
                "total": f"{Decimal(str(data['total'])).quantize(Decimal('0.01'))}",
            }
            for sched, data in sorted(by_schedule.items())
        },
    }


def format_summary_lines(records: Sequence[DeletedRecord]) -> list[str]:
    summary = summarize_deletions(records)
    lines = [
        f"SUMMARY | count={summary['count']} | total_dollars={summary['total']}",
    ]
    by_schedule = summary["by_schedule"]
    assert isinstance(by_schedule, dict)
    for sched, data in by_schedule.items():
        lines.append(
            f"SUMMARY | schedule={sched} | count={data['count']} | "
            f"total_dollars={data['total']}"
        )
    return lines


def format_deleted_records_txt(records: Iterable[DeletedRecord]) -> str:
    """Full deleted_records.txt body (always ends with a trailing newline)."""
    recs = list(records)
    if not recs:
        return NO_RECORDS_LINE + "\n"
    lines = [format_deleted_line(r) for r in recs]
    lines.extend(format_summary_lines(recs))
    return "\n".join(lines) + "\n"


def write_deleted_records(path: Path, records: Sequence[DeletedRecord]) -> Path:
    """Write deleted_records.txt; parent dirs created as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_deleted_records_txt(records), encoding="utf-8")
    return path


def console_summary(records: Sequence[DeletedRecord]) -> str:
    """Console-printable deletion summary (same summary lines as the file)."""
    if not records:
        return NO_RECORDS_LINE
    return "\n".join(format_summary_lines(records))
