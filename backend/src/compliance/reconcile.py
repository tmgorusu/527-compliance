"""P&L tie-out reconciliation and report writer (Agent D)."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from contract.models import Finding, NormalizedBundle, PLLineRecord, Severity

from ._money import load_money_config, money_str, sum_money, to_money


def _finding(
    *,
    id: str,
    severity: Severity,
    rule: str,
    message: str,
    source: str,
    sheet: str | None = None,
    row: int | None = None,
    field: str | None = None,
    context: dict[str, Any] | None = None,
) -> Finding:
    return Finding(
        id=id,
        severity=severity,
        rule=rule,
        sheet=sheet,
        row=row,
        field=field,
        message=message,
        source=source,
        context=context,
    )


def _label_key(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip().upper())


def _pick_pl_amount(lines: list[PLLineRecord], *exact_labels: str) -> Decimal | None:
    wanted = {_label_key(x) for x in exact_labels}
    for line in lines:
        if _label_key(line.line_label) in wanted:
            return to_money(line.amount)
    return None


def _pl_revenue_target(lines: list[PLLineRecord], quantize: Decimal, rounding: str) -> tuple[Decimal, str]:
    """Derive P&L revenue figure that should tie to Schedule A.

    Prefer Total for Revenue + Total for Other Revenue when both exist
    (UPF: donations + transfers). Else Total for Revenue alone.
    """
    rev = _pick_pl_amount(lines, "Total for Revenue")
    other = _pick_pl_amount(lines, "Total for Other Revenue")
    if rev is not None and other is not None:
        total = to_money(rev + other, quantize, rounding)
        return total, "Total for Revenue + Total for Other Revenue"
    if rev is not None:
        return to_money(rev, quantize, rounding), "Total for Revenue"
    # Fallback: first line whose label contains SCHEDULE A hint via section/label
    for line in lines:
        if "SCHEDULE A" in _label_key(line.line_label):
            return to_money(line.amount, quantize, rounding), line.line_label
    raise ValueError("P&L has no identifiable revenue total (expected 'Total for Revenue')")


def _pl_expense_target(lines: list[PLLineRecord], quantize: Decimal, rounding: str) -> tuple[Decimal, str]:
    """Derive P&L expense figure that should tie to Schedule B.

    Prefer Total for Expenditures + Total for Other Expenditures.
    """
    exp = _pick_pl_amount(lines, "Total for Expenditures")
    other = _pick_pl_amount(lines, "Total for Other Expenditures")
    # UPF uses "Total for Contribution" under Other Expenditures path — also
    # accept that label when Other Expenditures total is absent.
    if exp is not None and other is not None:
        total = to_money(exp + other, quantize, rounding)
        return total, "Total for Expenditures + Total for Other Expenditures"
    if exp is not None:
        contrib = _pick_pl_amount(lines, "Total for Contribution")
        if contrib is not None:
            total = to_money(exp + contrib, quantize, rounding)
            return total, "Total for Expenditures + Total for Contribution"
        return to_money(exp, quantize, rounding), "Total for Expenditures"
    raise ValueError(
        "P&L has no identifiable expense total (expected 'Total for Expenditures')"
    )


def _deleted_totals(
    bundle: NormalizedBundle, quantize: Decimal, rounding: str
) -> tuple[Decimal, Decimal, Decimal]:
    a = sum_money(
        [d.amount for d in bundle.deleted if d.schedule == "A"], quantize, rounding
    )
    b = sum_money(
        [d.amount for d in bundle.deleted if d.schedule == "B"], quantize, rounding
    )
    other = sum_money(
        [d.amount for d in bundle.deleted if d.schedule not in ("A", "B")],
        quantize,
        rounding,
    )
    return a, b, other


def reconcile(
    bundle: NormalizedBundle, config: Mapping[str, Any]
) -> tuple[str, list[Finding], bool]:
    """Tie Schedule A/B sums to P&L; treat deletions as labeled reconciling lines.

    Returns ``(report_text, findings, ok)``. ``ok`` is False when any unexplained
    difference remains (also emitted as ERROR findings). Callers may treat
    ``ok is False`` as a hard fail.
    """
    quantize, rounding = load_money_config(config)
    findings: list[Finding] = []
    lines_out: list[str] = []

    sum_a = sum_money([r.amount for r in bundle.schedule_a], quantize, rounding)
    sum_b = sum_money([r.amount for r in bundle.schedule_b], quantize, rounding)
    del_a, del_b, del_other = _deleted_totals(bundle, quantize, rounding)
    del_all = to_money(del_a + del_b + del_other, quantize, rounding)

    lines_out.append("527 COMPLIANCE — P&L RECONCILIATION REPORT")
    lines_out.append("=" * 60)
    org = bundle.cover.organization_name or bundle.cover.ein
    lines_out.append(f"Organization: {org}")
    lines_out.append(f"EIN: {bundle.cover.ein}")
    lines_out.append(f"Period: {bundle.cover.period_begin} → {bundle.cover.period_end}")
    lines_out.append("")

    lines_out.append("SCHEDULE TOTALS (post-deletion, post-roll-up)")
    lines_out.append("-" * 60)
    lines_out.append(f"  Schedule A sum:  {money_str(sum_a, quantize, rounding)}")
    lines_out.append(f"  Schedule B sum:  {money_str(sum_b, quantize, rounding)}")
    lines_out.append("")

    lines_out.append("DELETED DOLLARS (labeled reconciling lines)")
    lines_out.append("-" * 60)
    lines_out.append(f"  Deleted Schedule A:     {money_str(del_a, quantize, rounding)}")
    lines_out.append(f"  Deleted Schedule B:     {money_str(del_b, quantize, rounding)}")
    lines_out.append(f"  Deleted LEDGER/OTHER:   {money_str(del_other, quantize, rounding)}")
    lines_out.append(f"  Deleted total:          {money_str(del_all, quantize, rounding)}")
    if bundle.deleted:
        for d in sorted(bundle.deleted, key=lambda x: (x.schedule, x.source_row)):
            lines_out.append(
                f"    DELETED | {d.schedule} | row {d.source_row} | "
                f"{d.date or ''} | {d.name or ''} | {d.amount} | {d.reason}"
            )
    else:
        lines_out.append("    NO RECORDS DELETED")
    lines_out.append("")

    ok = True
    try:
        pl_rev, rev_label = _pl_revenue_target(bundle.pl_lines, quantize, rounding)
        pl_exp, exp_label = _pl_expense_target(bundle.pl_lines, quantize, rounding)
    except ValueError as exc:
        findings.append(
            _finding(
                id="PL-CFG-001",
                severity=Severity.ERROR,
                rule="pl_tieout",
                sheet="pl",
                message=str(exc),
                source="client_style_guide; SPEC §6 P&L",
            )
        )
        report = "\n".join(lines_out) + f"\nERROR: {exc}\n"
        findings.sort(key=lambda f: (f.id, f.message))
        return report, findings, False

    lines_out.append("P&L TARGETS")
    lines_out.append("-" * 60)
    lines_out.append(f"  Revenue ({rev_label}): {money_str(pl_rev, quantize, rounding)}")
    lines_out.append(f"  Expenses ({exp_label}): {money_str(pl_exp, quantize, rounding)}")
    lines_out.append("")

    # Bridge: P&L − Schedule = difference; deletions explain part of that gap
    # when P&L still includes deleted dollars.
    diff_a = to_money(pl_rev - sum_a, quantize, rounding)
    explained_a = del_a
    unexplained_a = to_money(diff_a - explained_a, quantize, rounding)

    diff_b = to_money(pl_exp - sum_b, quantize, rounding)
    explained_b = del_b
    unexplained_b = to_money(diff_b - explained_b, quantize, rounding)

    lines_out.append("TIE-OUT — SCHEDULE A vs P&L REVENUE")
    lines_out.append("-" * 60)
    lines_out.append(f"  P&L revenue:                    {money_str(pl_rev, quantize, rounding)}")
    lines_out.append(f"  Less: Schedule A sum:           {money_str(sum_a, quantize, rounding)}")
    lines_out.append(f"  Difference:                     {money_str(diff_a, quantize, rounding)}")
    lines_out.append(
        f"  Reconciling: Deleted Schedule A: {money_str(explained_a, quantize, rounding)}"
    )
    lines_out.append(
        f"  Unexplained:                     {money_str(unexplained_a, quantize, rounding)}"
    )
    lines_out.append("")

    lines_out.append("TIE-OUT — SCHEDULE B vs P&L EXPENSES")
    lines_out.append("-" * 60)
    lines_out.append(f"  P&L expenses:                   {money_str(pl_exp, quantize, rounding)}")
    lines_out.append(f"  Less: Schedule B sum:           {money_str(sum_b, quantize, rounding)}")
    lines_out.append(f"  Difference:                     {money_str(diff_b, quantize, rounding)}")
    lines_out.append(
        f"  Reconciling: Deleted Schedule B: {money_str(explained_b, quantize, rounding)}"
    )
    lines_out.append(
        f"  Unexplained:                     {money_str(unexplained_b, quantize, rounding)}"
    )
    lines_out.append("")

    zero = to_money(Decimal("0.00"), quantize, rounding)

    if unexplained_a != zero:
        ok = False
        findings.append(
            _finding(
                id="PL-A-001",
                severity=Severity.ERROR,
                rule="pl_tieout",
                sheet="pl",
                field="revenue",
                message=(
                    f"Unexplained Schedule A vs P&L revenue difference of "
                    f"{money_str(unexplained_a, quantize, rounding)} "
                    f"(P&L {pl_rev} − Schedule A {sum_a} − deleted A {del_a})."
                ),
                source="client_style_guide; SPEC §6 P&L",
                context={
                    "pl_revenue": money_str(pl_rev, quantize, rounding),
                    "schedule_a_sum": money_str(sum_a, quantize, rounding),
                    "deleted_a": money_str(del_a, quantize, rounding),
                    "unexplained": money_str(unexplained_a, quantize, rounding),
                },
            )
        )

    if unexplained_b != zero:
        ok = False
        findings.append(
            _finding(
                id="PL-B-001",
                severity=Severity.ERROR,
                rule="pl_tieout",
                sheet="pl",
                field="expenses",
                message=(
                    f"Unexplained Schedule B vs P&L expense difference of "
                    f"{money_str(unexplained_b, quantize, rounding)} "
                    f"(P&L {pl_exp} − Schedule B {sum_b} − deleted B {del_b})."
                ),
                source="client_style_guide; SPEC §6 P&L",
                context={
                    "pl_expenses": money_str(pl_exp, quantize, rounding),
                    "schedule_b_sum": money_str(sum_b, quantize, rounding),
                    "deleted_b": money_str(del_b, quantize, rounding),
                    "unexplained": money_str(unexplained_b, quantize, rounding),
                },
            )
        )

    lines_out.append("RESULT")
    lines_out.append("-" * 60)
    if ok:
        lines_out.append("  OK — Schedule A/B tie to P&L with only explained reconciling items.")
    else:
        lines_out.append("  FAIL — unexplained difference(s); see ERROR findings.")
    lines_out.append("")

    findings.sort(key=lambda f: (f.id, f.message))
    return "\n".join(lines_out), findings, ok


def write_reconciliation_report(path: str | Path, report_text: str) -> None:
    """Write reconciliation report text to ``path`` (UTF-8, parent dirs created)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(report_text if report_text.endswith("\n") else report_text + "\n", encoding="utf-8")
