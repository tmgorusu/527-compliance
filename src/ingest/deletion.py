"""Exact-match DELETE_AMOUNTS filtering — runs BEFORE clean/aggregate.

Amounts come only from config ``DELETE_AMOUNTS`` (never hardcoded).
Applies to Schedule A, Schedule B, and raw ledger rows.
Always writes ``deleted_records.txt`` (or ``NO RECORDS DELETED``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Sequence

from contract.models import DeletedRecord, Finding, Severity

from src.cleaning.money import parse_money, quantize_money


SCHEDULE_A_AMOUNT_KEYS = ("contribution_amount", "amount")
SCHEDULE_B_AMOUNT_KEYS = ("expenditure_amount", "amount")
LEDGER_AMOUNT_KEYS = ("amount",)

SCHEDULE_A_NAME_KEYS = ("contributor_name", "name")
SCHEDULE_B_NAME_KEYS = ("recipient_name", "name")
LEDGER_NAME_KEYS = ("name",)

SCHEDULE_A_DATE_KEYS = ("contribution_date", "date")
SCHEDULE_B_DATE_KEYS = ("expenditure_date", "date", "transaction_date")
LEDGER_DATE_KEYS = ("transaction_date", "date")


def _first(row: dict[str, str], keys: Sequence[str]) -> str:
    for k in keys:
        v = row.get(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return ""


def _source_row(row: dict[str, str]) -> int:
    raw = row.get("_source_row", "1")
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def _source_file(row: dict[str, str]) -> str | None:
    return row.get("_source_file") or None


def delete_amounts_from_config(config: dict[str, Any]) -> list[Decimal]:
    raw = config.get("DELETE_AMOUNTS")
    if raw is None:
        raise KeyError("DELETE_AMOUNTS missing from config — refuse to hardcode")
    amounts: list[Decimal] = []
    for item in raw:
        amounts.append(quantize_money(parse_money(str(item))))
    return amounts


@dataclass
class DeletionResult:
    schedule_a: list[dict[str, str]] = field(default_factory=list)
    schedule_b: list[dict[str, str]] = field(default_factory=list)
    raw_ledger: list[dict[str, str]] = field(default_factory=list)
    deleted: list[DeletedRecord] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    summary_text: str = ""


def _match_delete(
    amount_text: str,
    delete_amounts: Sequence[Decimal],
) -> Decimal | None:
    try:
        value = quantize_money(parse_money(amount_text))
    except (InvalidOperation, ValueError):
        return None
    for target in delete_amounts:
        if value == target:
            return target
    return None


def _apply_to_rows(
    rows: list[dict[str, str]],
    *,
    schedule: str,
    amount_keys: Sequence[str],
    name_keys: Sequence[str],
    date_keys: Sequence[str],
    delete_amounts: Sequence[Decimal],
) -> tuple[list[dict[str, str]], list[DeletedRecord]]:
    kept: list[dict[str, str]] = []
    deleted: list[DeletedRecord] = []
    for row in rows:
        amount_text = _first(row, amount_keys)
        if amount_text == "":
            kept.append(row)
            continue
        matched = _match_delete(amount_text, delete_amounts)
        if matched is None:
            kept.append(row)
            continue
        money = quantize_money(parse_money(amount_text))
        money_str = f"{money:.2f}"
        matched_str = f"{matched:.2f}"
        deleted.append(
            DeletedRecord(
                schedule=schedule,  # type: ignore[arg-type]
                source_file=_source_file(row),
                source_row=_source_row(row),
                date=_first(row, date_keys) or None,
                name=_first(row, name_keys) or None,
                amount=money_str,
                reason=f"exact match DELETE_AMOUNTS={matched_str}",
                matched_delete_amount=matched_str,
            )
        )
    return kept, deleted


def apply_delete_amounts(
    *,
    schedule_a: list[dict[str, str]],
    schedule_b: list[dict[str, str]],
    raw_ledger: list[dict[str, str]],
    config: dict[str, Any],
    output_path: str | Path,
) -> DeletionResult:
    """
    Filter exact DELETE_AMOUNTS matches from A/B/ledger; write deleted_records.txt;
    emit DeletedRecord list + WARN finding for human sign-off.
    """
    delete_amounts = delete_amounts_from_config(config)
    result = DeletionResult()

    a_kept, a_del = _apply_to_rows(
        schedule_a,
        schedule="A",
        amount_keys=SCHEDULE_A_AMOUNT_KEYS,
        name_keys=SCHEDULE_A_NAME_KEYS,
        date_keys=SCHEDULE_A_DATE_KEYS,
        delete_amounts=delete_amounts,
    )
    b_kept, b_del = _apply_to_rows(
        schedule_b,
        schedule="B",
        amount_keys=SCHEDULE_B_AMOUNT_KEYS,
        name_keys=SCHEDULE_B_NAME_KEYS,
        date_keys=SCHEDULE_B_DATE_KEYS,
        delete_amounts=delete_amounts,
    )
    l_kept, l_del = _apply_to_rows(
        raw_ledger,
        schedule="LEDGER",
        amount_keys=LEDGER_AMOUNT_KEYS,
        name_keys=LEDGER_NAME_KEYS,
        date_keys=LEDGER_DATE_KEYS,
        delete_amounts=delete_amounts,
    )

    result.schedule_a = a_kept
    result.schedule_b = b_kept
    result.raw_ledger = l_kept
    result.deleted = a_del + b_del + l_del

    summary = _write_deleted_records_file(result.deleted, Path(output_path))
    result.summary_text = summary
    print(summary)

    if result.deleted:
        by_sched: dict[str, int] = {}
        total = Decimal("0.00")
        for d in result.deleted:
            by_sched[d.schedule] = by_sched.get(d.schedule, 0) + 1
            total += Decimal(d.amount)
        result.findings.append(
            Finding(
                id="DEL-001",
                severity=Severity.WARN,
                rule="delete_amounts",
                sheet=None,
                row=None,
                field="amount",
                message=(
                    f"{len(result.deleted)} row(s) deleted for exact DELETE_AMOUNTS match "
                    f"(total ${total:.2f}). Human sign-off required before filing."
                ),
                source="client_style_guide",
                context={
                    "count": len(result.deleted),
                    "total_dollars": f"{total:.2f}",
                    "per_schedule": by_sched,
                    "delete_amounts": [f"{a:.2f}" for a in delete_amounts],
                },
            )
        )
    else:
        result.findings.append(
            Finding(
                id="DEL-000",
                severity=Severity.INFO,
                rule="delete_amounts",
                sheet=None,
                row=None,
                field="amount",
                message="No rows matched DELETE_AMOUNTS; deleted_records.txt written.",
                source="client_style_guide",
                context={"delete_amounts": [f"{a:.2f}" for a in delete_amounts]},
            )
        )

    return result


def _write_deleted_records_file(deleted: list[DeletedRecord], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if not deleted:
        lines.append("NO RECORDS DELETED")
        summary = (
            "Deletion summary: count=0 total_dollars=0.00 "
            "per_schedule={}"
        )
        lines.append(summary)
    else:
        for d in deleted:
            date = d.date or ""
            name = d.name or ""
            lines.append(
                f"DELETED | {d.schedule} | {d.source_row} | {date} | {name} | "
                f"{d.amount} | {d.reason}"
            )
        total = sum((Decimal(d.amount) for d in deleted), Decimal("0.00"))
        by_sched: dict[str, dict[str, Any]] = {}
        for d in deleted:
            bucket = by_sched.setdefault(d.schedule, {"count": 0, "total": Decimal("0.00")})
            bucket["count"] += 1
            bucket["total"] += Decimal(d.amount)
        per = {
            k: {"count": v["count"], "total": f"{v['total']:.2f}"}
            for k, v in sorted(by_sched.items())
        }
        summary = (
            f"Deletion summary: count={len(deleted)} "
            f"total_dollars={total:.2f} per_schedule={per}"
        )
        lines.append(summary)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary
