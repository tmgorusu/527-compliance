"""Fixture inventory and structural checks (no sibling agents required)."""

from __future__ import annotations

from pathlib import Path

import pytest

REQUIRED_EDGE_CASES = (
    "dollar_one",
    "unapplied_cash_zero",
    "below_threshold",
    "bad_rows",
    "state_zip",
)

REQUIRED_CSV = ("cover.csv", "schedule_a.csv", "schedule_b.csv", "pl.csv")


def test_edge_case_dirs_exist(fixtures_dir: Path) -> None:
    root = fixtures_dir / "edge_cases"
    for name in REQUIRED_EDGE_CASES:
        case_dir = root / name
        assert case_dir.is_dir(), f"missing fixture dir: {case_dir}"
        for csv_name in REQUIRED_CSV:
            assert (case_dir / csv_name).is_file(), f"missing {csv_name} in {name}"


def test_dollar_one_contains_exact_one_dollar(fixtures_dir: Path) -> None:
    text_a = (fixtures_dir / "edge_cases" / "dollar_one" / "schedule_a.csv").read_text(
        encoding="utf-8"
    )
    text_b = (fixtures_dir / "edge_cases" / "dollar_one" / "schedule_b.csv").read_text(
        encoding="utf-8"
    )
    assert ",1.00," in text_a or text_a.endswith("1.00\n") or "1.00" in text_a
    assert "1.00" in text_b
    assert "ONE DOLLAR" in text_a
    assert (fixtures_dir / "edge_cases" / "dollar_one" / "raw_ledger.csv").is_file()


def test_unapplied_cash_zero_marker(fixtures_dir: Path) -> None:
    text = (
        fixtures_dir / "edge_cases" / "unapplied_cash_zero" / "schedule_b.csv"
    ).read_text(encoding="utf-8")
    assert "is_unapplied_cash" in text
    assert "0.00" in text
    assert "UNAPPLIED CASH" in text


def test_state_zip_quirks(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "edge_cases" / "state_zip" / "schedule_a.csv").read_text(
        encoding="utf-8"
    )
    assert "VA (Virginia)" in text
    assert "23237.0" in text or "22701" in text


def test_bad_rows_present(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "edge_cases" / "bad_rows" / "schedule_a.csv").read_text(
        encoding="utf-8"
    )
    assert "not-a-date" in text
    assert "abc" in text


def test_golden_deleted_snippets_exist(fixtures_dir: Path) -> None:
    assert (fixtures_dir / "golden" / "deleted_records_none.txt").is_file()
    assert (fixtures_dir / "golden" / "deleted_records_with_deletes.txt").is_file()
    none = (fixtures_dir / "golden" / "deleted_records_none.txt").read_text(
        encoding="utf-8"
    )
    assert none.startswith("NO RECORDS DELETED")
