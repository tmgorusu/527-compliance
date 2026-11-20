"""Unit + golden tests for deleted_records.txt format (PIPELINE.md)."""

from __future__ import annotations

from pathlib import Path

from contract.models import DeletedRecord
from src.cli.deleted_report import (
    NO_RECORDS_LINE,
    format_deleted_records_txt,
    summarize_deletions,
    write_deleted_records,
)


def test_no_records_golden(fixtures_dir: Path) -> None:
    golden = (fixtures_dir / "golden" / "deleted_records_none.txt").read_text(
        encoding="utf-8"
    )
    assert format_deleted_records_txt([]) == golden
    assert format_deleted_records_txt([]).startswith(NO_RECORDS_LINE)


def test_with_deletes_golden(
    fixtures_dir: Path, sample_deleted_records: list[DeletedRecord]
) -> None:
    golden = (
        fixtures_dir / "golden" / "deleted_records_with_deletes.txt"
    ).read_text(encoding="utf-8")
    assert format_deleted_records_txt(sample_deleted_records) == golden


def test_line_pipe_fields(sample_deleted_records: list[DeletedRecord]) -> None:
    text = format_deleted_records_txt(sample_deleted_records)
    data_lines = [ln for ln in text.splitlines() if ln.startswith("DELETED |")]
    assert len(data_lines) == 3
    for line in data_lines:
        parts = [p.strip() for p in line.split("|")]
        assert parts[0] == "DELETED"
        assert parts[1] in {"A", "B", "LEDGER", "OTHER"}
        assert parts[2].isdigit()
        assert parts[5] == "1.00"


def test_summary_totals(sample_deleted_records: list[DeletedRecord]) -> None:
    summary = summarize_deletions(sample_deleted_records)
    assert summary["count"] == 3
    assert summary["total"] == "3.00"
    assert summary["by_schedule"]["A"]["count"] == 1
    assert summary["by_schedule"]["B"]["total"] == "1.00"


def test_write_deleted_records_roundtrip(
    tmp_path: Path, sample_deleted_records: list[DeletedRecord]
) -> None:
    path = write_deleted_records(tmp_path / "deleted_records.txt", sample_deleted_records)
    assert path.is_file()
    assert path.read_text(encoding="utf-8") == format_deleted_records_txt(
        sample_deleted_records
    )


def test_always_trailing_newline() -> None:
    assert format_deleted_records_txt([]).endswith("\n")
    rec = DeletedRecord(
        schedule="A",
        source_row=1,
        date="2026-01-01",
        name="X",
        amount="1.00",
        reason="test",
    )
    assert format_deleted_records_txt([rec]).endswith("\n")
