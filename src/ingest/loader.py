"""CSV ingest: load required/optional inputs; reject credential-like columns."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

REQUIRED_FILES = (
    "cover.csv",
    "schedule_a.csv",
    "schedule_b.csv",
    "pl.csv",
)

OPTIONAL_NAMED_FILES = (
    "raw_ledger.csv",
    "exceptions.csv",
)

VENDOR_GLOB = "vendor_*.csv"


class CredentialColumnError(ValueError):
    """Raised when an input CSV contains a credential-like column name."""


class MissingInputError(FileNotFoundError):
    """Raised when a required input CSV is missing."""


def _normalize_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def header_has_credential(headers: Sequence[str], forbidden_substrings: Sequence[str]) -> list[str]:
    """Return forbidden column names that match config substrings (case-insensitive)."""
    hits: list[str] = []
    lowered = [s.lower() for s in forbidden_substrings]
    for h in headers:
        norm = _normalize_header(h)
        raw_l = h.lower()
        for sub in lowered:
            if sub in norm or sub in raw_l:
                hits.append(h)
                break
    return hits


def read_csv_rows(
    path: Path,
    *,
    forbidden_substrings: Sequence[str],
) -> tuple[list[str], list[dict[str, str]]]:
    """
    Read a CSV into row dicts keyed by original headers.

    Adds ``_source_file`` and ``_source_row`` (1-based data row; header is row 0).
    Never logs cell values for credential columns — rejection happens before row use.
    """
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header row: {path}")
        headers = list(reader.fieldnames)
        bad = header_has_credential(headers, forbidden_substrings)
        if bad:
            raise CredentialColumnError(
                f"Credential-like column(s) in {path.name}: {bad}. "
                "Portal credentials must never be ingested, logged, or stored."
            )
        rows: list[dict[str, str]] = []
        for i, raw in enumerate(reader, start=1):
            # Skip fully empty trailing rows
            if all((v is None or str(v).strip() == "") for v in raw.values()):
                continue
            row = {k: ("" if v is None else str(v)) for k, v in raw.items() if k is not None}
            row["_source_file"] = path.name
            row["_source_row"] = str(i)
            rows.append(row)
    return headers, rows


def _snake_keys(row: dict[str, str]) -> dict[str, str]:
    """Copy row with normalized snake_case keys; keep provenance keys."""
    out: dict[str, str] = {}
    for k, v in row.items():
        if k.startswith("_"):
            out[k] = v
        else:
            out[_normalize_header(k)] = v
    return out


@dataclass
class RawIngest:
    """Jurisdiction-independent raw CSV payload (pre-deletion, pre-clean)."""

    inputs_dir: Path
    cover: list[dict[str, str]] = field(default_factory=list)
    schedule_a: list[dict[str, str]] = field(default_factory=list)
    schedule_b: list[dict[str, str]] = field(default_factory=list)
    pl: list[dict[str, str]] = field(default_factory=list)
    raw_ledger: list[dict[str, str]] = field(default_factory=list)
    exceptions: list[dict[str, str]] = field(default_factory=list)
    vendors: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    # original headers per file (for diagnostics)
    headers: dict[str, list[str]] = field(default_factory=dict)


def ingest_directory(
    inputs_dir: str | Path,
    config: dict[str, Any],
) -> RawIngest:
    """
    Load CSVs from ``inputs_dir``.

    Required: cover, schedule_a, schedule_b, pl.
    Optional: vendor_*.csv, raw_ledger.csv, exceptions.csv.
    Rejects credential-like columns per ``CREDENTIALS.forbidden_column_substrings``.
    """
    root = Path(inputs_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"Inputs directory not found: {root}")

    creds = config.get("CREDENTIALS") or {}
    forbidden: list[str] = list(creds.get("forbidden_column_substrings") or [])

    missing = [name for name in REQUIRED_FILES if not (root / name).is_file()]
    if missing:
        raise MissingInputError(
            f"Missing required input file(s) in {root}: {', '.join(missing)}"
        )

    result = RawIngest(inputs_dir=root)

    def _load(name: str) -> list[dict[str, str]]:
        path = root / name
        headers, rows = read_csv_rows(path, forbidden_substrings=forbidden)
        result.headers[name] = headers
        return [_snake_keys(r) for r in rows]

    result.cover = _load("cover.csv")
    result.schedule_a = _load("schedule_a.csv")
    result.schedule_b = _load("schedule_b.csv")
    result.pl = _load("pl.csv")

    for name in OPTIONAL_NAMED_FILES:
        path = root / name
        if path.is_file():
            if name == "raw_ledger.csv":
                result.raw_ledger = _load(name)
            elif name == "exceptions.csv":
                result.exceptions = _load(name)

    for path in sorted(root.glob(VENDOR_GLOB)):
        headers, rows = read_csv_rows(path, forbidden_substrings=forbidden)
        result.headers[path.name] = headers
        result.vendors[path.name] = [_snake_keys(r) for r in rows]

    return result


def iter_amount_candidates(row: dict[str, str], keys: Iterable[str]) -> Iterator[str]:
    for key in keys:
        if key in row and str(row[key]).strip() != "":
            yield row[key]
