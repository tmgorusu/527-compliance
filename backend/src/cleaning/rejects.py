"""Reject tracking — no silent drops."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RejectRow:
    sheet: str
    source_file: str | None
    source_row: int | None
    field: str | None
    reason: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class RejectCollector:
    rows: list[RejectRow] = field(default_factory=list)

    def add(
        self,
        *,
        sheet: str,
        reason: str,
        source_file: str | None = None,
        source_row: int | None = None,
        field: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        self.rows.append(
            RejectRow(
                sheet=sheet,
                source_file=source_file,
                source_row=source_row,
                field=field,
                reason=reason,
                raw=dict(raw or {}),
            )
        )

    def write_csv(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "sheet",
                    "source_file",
                    "source_row",
                    "field",
                    "reason",
                    "raw_excerpt",
                ],
            )
            writer.writeheader()
            for r in self.rows:
                excerpt_parts = []
                for k, v in r.raw.items():
                    if k.startswith("_"):
                        continue
                    excerpt_parts.append(f"{k}={v}")
                    if len(excerpt_parts) >= 8:
                        break
                writer.writerow(
                    {
                        "sheet": r.sheet,
                        "source_file": r.source_file or "",
                        "source_row": r.source_row if r.source_row is not None else "",
                        "field": r.field or "",
                        "reason": r.reason,
                        "raw_excerpt": " | ".join(excerpt_parts),
                    }
                )
