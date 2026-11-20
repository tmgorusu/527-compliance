"""Sub-$1 expense cleanup + exact DELETE_AMOUNTS (Kyle upload rules)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from src.ingest.deletion import apply_delete_amounts


def _cfg(**overrides):
    base = {
        "DELETE_AMOUNTS": ["1.00"],
        "DELETE_STRICTLY_UNDER": "1.00",
        "DELETE_STRICTLY_UNDER_SCHEDULES": ["B", "LEDGER"],
    }
    base.update(overrides)
    return base


def test_sub_dollar_expenses_removed_from_b_and_ledger(tmp_path: Path) -> None:
    result = apply_delete_amounts(
        schedule_a=[
            {
                "_source_row": "2",
                "contributor_name": "Keep A",
                "contribution_amount": "0.50",
                "contribution_date": "2026-01-02",
            }
        ],
        schedule_b=[
            {
                "_source_row": "2",
                "recipient_name": "Penny Vendor",
                "expenditure_amount": "0.01",
                "expenditure_date": "2026-01-03",
            },
            {
                "_source_row": "3",
                "recipient_name": "Keep B",
                "expenditure_amount": "1.01",
                "expenditure_date": "2026-01-04",
            },
            {
                "_source_row": "4",
                "recipient_name": "Exact Dollar",
                "expenditure_amount": "1.00",
                "expenditure_date": "2026-01-05",
            },
        ],
        raw_ledger=[
            {
                "_source_row": "2",
                "name": "Ledger Penny",
                "amount": "0.99",
                "transaction_date": "2026-01-06",
            },
            {
                "_source_row": "3",
                "name": "Ledger Keep",
                "amount": "25.00",
                "transaction_date": "2026-01-07",
            },
        ],
        config=_cfg(),
        output_path=tmp_path / "deleted_records.txt",
    )

    assert len(result.schedule_a) == 1
    assert result.schedule_a[0]["contributor_name"] == "Keep A"
    assert [r["recipient_name"] for r in result.schedule_b] == ["Keep B"]
    assert [r["name"] for r in result.raw_ledger] == ["Ledger Keep"]

    amounts = sorted(Decimal(d.amount) for d in result.deleted)
    assert amounts == [Decimal("0.01"), Decimal("0.99"), Decimal("1.00")]
    under = [d for d in result.deleted if "sub-$1" in d.reason]
    exact = [d for d in result.deleted if "exact match" in d.reason]
    assert len(under) == 2
    assert len(exact) == 1
    assert (tmp_path / "deleted_records.txt").is_file()


def test_exact_one_dollar_still_deleted_on_schedule_a(tmp_path: Path) -> None:
    result = apply_delete_amounts(
        schedule_a=[
            {
                "_source_row": "2",
                "contributor_name": "Dollar Donor",
                "contribution_amount": "1.00",
                "contribution_date": "2026-02-01",
            },
            {
                "_source_row": "3",
                "contributor_name": "Keep",
                "contribution_amount": "50.00",
                "contribution_date": "2026-02-02",
            },
        ],
        schedule_b=[],
        raw_ledger=[],
        config=_cfg(),
        output_path=tmp_path / "deleted_records.txt",
    )
    assert len(result.schedule_a) == 1
    assert result.deleted[0].amount == "1.00"
    assert "exact match" in result.deleted[0].reason


def test_sub_dollar_disabled_when_under_unset(tmp_path: Path) -> None:
    result = apply_delete_amounts(
        schedule_a=[],
        schedule_b=[
            {
                "_source_row": "2",
                "recipient_name": "Penny",
                "expenditure_amount": "0.25",
                "expenditure_date": "2026-03-01",
            }
        ],
        raw_ledger=[],
        config=_cfg(DELETE_STRICTLY_UNDER=None),
        output_path=tmp_path / "deleted_records.txt",
    )
    assert len(result.schedule_b) == 1
    assert result.deleted == []
