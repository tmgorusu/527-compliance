"""Unapplied cash identification and zero-balance drop (config UNAPPLIED_CASH)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Sequence

from src.cleaning.money import parse_money, quantize_money
from src.cleaning.rejects import RejectCollector


def _cfg(config: dict[str, Any]) -> dict[str, Any]:
    return dict(config.get("UNAPPLIED_CASH") or {})


def is_unapplied_cash_row(row: dict[str, str], config: dict[str, Any]) -> bool:
    """
    True if marker column is truthy and/or name/purpose contains configured substrings.
    """
    uc = _cfg(config)
    marker_col = str(uc.get("marker_column") or "is_unapplied_cash")
    marker_val = str(row.get(marker_col, "")).strip().lower()
    if marker_val in {"1", "true", "yes", "y", "t"}:
        return True

    substrings: Sequence[str] = list(uc.get("name_or_purpose_substrings") or [])
    haystacks = [
        str(row.get("recipient_name") or row.get("name") or ""),
        str(row.get("expenditure_purpose") or row.get("purpose") or ""),
        str(row.get("description") or ""),
        str(row.get("account_name") or ""),
    ]
    joined = " ".join(haystacks).upper()
    for sub in substrings:
        if str(sub).upper() in joined:
            return True
    return False


def filter_unapplied_cash(
    rows: list[dict[str, str]],
    *,
    sheet: str,
    amount_keys: Sequence[str],
    config: dict[str, Any],
    rejects: RejectCollector,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """
    Drop zero-balance unapplied rows (reject with reason).
    Keep nonzero unapplied rows and set ``is_unapplied_cash=true`` on them.

    Returns (kept_rows, dropped_zero_rows).
    """
    kept: list[dict[str, str]] = []
    dropped: list[dict[str, str]] = []
    for row in rows:
        if not is_unapplied_cash_row(row, config):
            kept.append(row)
            continue
        amount_text = ""
        for k in amount_keys:
            if str(row.get(k, "")).strip():
                amount_text = str(row[k]).strip()
                break
        try:
            amount = quantize_money(parse_money(amount_text), config) if amount_text else Decimal("0.00")
        except Exception:
            # Leave for later clean reject
            row = dict(row)
            row["is_unapplied_cash"] = "true"
            kept.append(row)
            continue

        if amount == Decimal("0.00"):
            src_row = None
            try:
                src_row = int(row.get("_source_row") or 0) or None
            except ValueError:
                src_row = None
            rejects.add(
                sheet=sheet,
                source_file=row.get("_source_file"),
                source_row=src_row,
                field="amount",
                reason="zero-balance unapplied cash dropped per UNAPPLIED_CASH / style guide",
                raw=row,
            )
            dropped.append(row)
            continue

        row = dict(row)
        row["is_unapplied_cash"] = "true"
        kept.append(row)

    return kept, dropped
