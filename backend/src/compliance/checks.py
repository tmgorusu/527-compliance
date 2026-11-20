"""Advisory compliance checks → Finding list (Agent D)."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Mapping

from contract.models import Finding, NormalizedBundle, Severity

from ._money import load_money_config, sum_money, to_money


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


def _date_in_period(date: str, begin: str, end: str) -> bool:
    return begin <= date <= end


def _norm_name(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", name.upper())


def _near_duplicate_pairs(names: list[str], ratio_threshold: float = 0.88) -> list[tuple[str, str, float]]:
    """Return pairs of distinct display names that look like near-duplicates."""
    unique = sorted({n for n in names if n})
    pairs: list[tuple[str, str, float]] = []
    seen_norm: dict[str, str] = {}
    for name in unique:
        nk = _norm_name(name)
        if not nk:
            continue
        if nk in seen_norm and seen_norm[nk] != name:
            pairs.append((seen_norm[nk], name, 1.0))
        else:
            seen_norm.setdefault(nk, name)

    for i, a in enumerate(unique):
        na = _norm_name(a)
        if len(na) < 4:
            continue
        for b in unique[i + 1 :]:
            nb = _norm_name(b)
            if na == nb:
                continue  # already caught via seen_norm
            ratio = SequenceMatcher(None, na, nb).ratio()
            if ratio >= ratio_threshold:
                pairs.append((a, b, ratio))
    # Deterministic
    pairs.sort(key=lambda t: (t[0], t[1]))
    return pairs


def run_compliance(bundle: NormalizedBundle, config: Mapping[str, Any]) -> list[Finding]:
    """Run advisory compliance checks; return deterministic Finding list.

    Checks:
      1. threshold_status_changed_by_deletion flags → WARN findings
      2. Date-in-period for non-rollup schedule rows
      3. Cover schedule_a_total / schedule_b_total vs schedule sums
      4. Near-duplicate names → WARN
      5. Amended filing → WARN restatement reminder
      6. Client WITHHELD vs IRS Aggregate below Threshold vocabulary (A5)
      7. Non-empty deletions → WARN human sign-off for $1 deletions
    """
    quantize, rounding = load_money_config(config)
    findings: list[Finding] = []
    begin = bundle.cover.period_begin
    end = bundle.cover.period_end

    # --- 1. Threshold status flipped by deletion ---
    thr_a_rows = [
        r for r in bundle.schedule_a if r.threshold_status_changed_by_deletion and not r.is_rollup
    ]
    thr_b_rows = [
        r for r in bundle.schedule_b if r.threshold_status_changed_by_deletion and not r.is_rollup
    ]
    # One finding per person (first row)
    seen_a: set[str] = set()
    for r in thr_a_rows:
        key = r.name.upper()
        if key in seen_a:
            continue
        seen_a.add(key)
        findings.append(
            _finding(
                id=f"THR-A-{len(seen_a):03d}",
                severity=Severity.WARN,
                rule="threshold_status_changed_by_deletion",
                sheet="schedule_a",
                row=r.source_row,
                field="aggregate_ytd",
                message=(
                    f"Contributor {r.name!r} crossed the Schedule A itemization "
                    f"threshold because of deletions; human review required."
                ),
                source="client_style_guide; IRS Instructions for Form 8872 (Oct 2020) Schedule A",
                context={
                    "name": r.name,
                    "aggregate_ytd": r.aggregate_ytd,
                    "threshold_status_changed_by_deletion": True,
                },
            )
        )

    seen_b: set[str] = set()
    for r in thr_b_rows:
        key = r.name.upper()
        if key in seen_b:
            continue
        seen_b.add(key)
        findings.append(
            _finding(
                id=f"THR-B-{len(seen_b):03d}",
                severity=Severity.WARN,
                rule="threshold_status_changed_by_deletion",
                sheet="schedule_b",
                row=r.source_row,
                field="amount",
                message=(
                    f"Vendor/recipient {r.name!r} crossed the Schedule B itemization "
                    f"threshold because of deletions; human review required."
                ),
                source="client_style_guide; IRS Instructions for Form 8872 (Oct 2020) Schedule B",
                context={
                    "name": r.name,
                    "threshold_status_changed_by_deletion": True,
                },
            )
        )

    # --- 2. Date-in-period (itemize rows must fall in reporting period) ---
    # IRS Instructions for Form 8872 (Oct 2020): report contributions/expenditures
    # accepted/made during the reporting period on the applicable schedule.
    date_n = 0
    for r in bundle.schedule_a:
        if r.is_rollup:
            continue
        # Skip $0 deletion-threshold marker rows (see thresholds.apply_*).
        if to_money(r.amount, quantize, rounding) == 0 and r.threshold_status_changed_by_deletion:
            continue
        if not _date_in_period(r.date, begin, end):
            date_n += 1
            findings.append(
                _finding(
                    id=f"DATE-A-{date_n:03d}",
                    severity=Severity.ERROR,
                    rule="date_in_period",
                    sheet="schedule_a",
                    row=r.source_row,
                    field="date",
                    message=(
                        f"Contribution date {r.date} is outside reporting period "
                        f"{begin}–{end}."
                    ),
                    source="IRS Instructions for Form 8872 (Oct 2020) Schedule A",
                    context={"date": r.date, "period_begin": begin, "period_end": end},
                )
            )

    for r in bundle.schedule_b:
        if r.is_rollup:
            continue
        if to_money(r.amount, quantize, rounding) == 0 and r.threshold_status_changed_by_deletion:
            continue
        if not _date_in_period(r.date, begin, end):
            date_n += 1
            findings.append(
                _finding(
                    id=f"DATE-B-{date_n:03d}",
                    severity=Severity.ERROR,
                    rule="date_in_period",
                    sheet="schedule_b",
                    row=r.source_row,
                    field="date",
                    message=(
                        f"Expenditure date {r.date} is outside reporting period "
                        f"{begin}–{end}."
                    ),
                    source="IRS Instructions for Form 8872 (Oct 2020) Schedule B",
                    context={"date": r.date, "period_begin": begin, "period_end": end},
                )
            )

    # --- 3. Cover totals vs schedule sums ---
    # IRS Instructions for Form 8872 (Oct 2020) Lines 9–10: enter total of all
    # Schedule A / Schedule B subtotals.
    sum_a = sum_money([r.amount for r in bundle.schedule_a], quantize, rounding)
    sum_b = sum_money([r.amount for r in bundle.schedule_b], quantize, rounding)

    if bundle.cover.schedule_a_total is not None:
        cover_a = to_money(bundle.cover.schedule_a_total, quantize, rounding)
        if cover_a != sum_a:
            findings.append(
                _finding(
                    id="COVER-A-001",
                    severity=Severity.ERROR,
                    rule="cover_schedule_a_total",
                    sheet="cover",
                    row=bundle.cover.source_row,
                    field="schedule_a_total",
                    message=(
                        f"Cover schedule_a_total {cover_a} does not equal "
                        f"Schedule A sum {sum_a}."
                    ),
                    source="IRS Instructions for Form 8872 (Oct 2020) Line 9",
                    context={
                        "cover_total": str(cover_a),
                        "schedule_sum": str(sum_a),
                        "difference": str(cover_a - sum_a),
                    },
                )
            )

    if bundle.cover.schedule_b_total is not None:
        cover_b = to_money(bundle.cover.schedule_b_total, quantize, rounding)
        if cover_b != sum_b:
            findings.append(
                _finding(
                    id="COVER-B-001",
                    severity=Severity.ERROR,
                    rule="cover_schedule_b_total",
                    sheet="cover",
                    row=bundle.cover.source_row,
                    field="schedule_b_total",
                    message=(
                        f"Cover schedule_b_total {cover_b} does not equal "
                        f"Schedule B sum {sum_b}."
                    ),
                    source="IRS Instructions for Form 8872 (Oct 2020) Line 10",
                    context={
                        "cover_total": str(cover_b),
                        "schedule_sum": str(sum_b),
                        "difference": str(cover_b - sum_b),
                    },
                )
            )

    # --- 4. Near-duplicate names ---
    names_a = [
        r.name
        for r in bundle.schedule_a
        if not r.is_rollup
        and not (
            to_money(r.amount, quantize, rounding) == 0
            and r.threshold_status_changed_by_deletion
        )
    ]
    names_b = [
        r.name
        for r in bundle.schedule_b
        if not r.is_rollup
        and not (
            to_money(r.amount, quantize, rounding) == 0
            and r.threshold_status_changed_by_deletion
        )
    ]
    dup_n = 0
    for a, b, ratio in _near_duplicate_pairs(names_a):
        dup_n += 1
        findings.append(
            _finding(
                id=f"DUP-A-{dup_n:03d}",
                severity=Severity.WARN,
                rule="near_duplicate_name",
                sheet="schedule_a",
                field="name",
                message=f"Near-duplicate contributor names: {a!r} ~ {b!r}.",
                source="client_style_guide",
                context={"name_a": a, "name_b": b, "similarity": round(ratio, 4)},
            )
        )
    for a, b, ratio in _near_duplicate_pairs(names_b):
        dup_n += 1
        findings.append(
            _finding(
                id=f"DUP-B-{dup_n:03d}",
                severity=Severity.WARN,
                rule="near_duplicate_name",
                sheet="schedule_b",
                field="name",
                message=f"Near-duplicate recipient names: {a!r} ~ {b!r}.",
                source="client_style_guide",
                context={"name_a": a, "name_b": b, "similarity": round(ratio, 4)},
            )
        )

    # --- 5. Amended report restatement reminder ---
    if bundle.cover.filing_type == "amended":
        findings.append(
            _finding(
                id="AMD-001",
                severity=Severity.WARN,
                rule="amended_restatement_reminder",
                sheet="cover",
                row=bundle.cover.source_row,
                field="filing_type",
                message=(
                    "Amended report: confirm this filing fully restates the period "
                    "and that prior-period figures needing correction are addressed."
                ),
                source="IRS Instructions for Form 8872 (Oct 2020) FilingType/AmendedReport",
            )
        )

    # --- 6. A5: WITHHELD vs IRS Aggregate below Threshold ---
    roll_cfg = config.get("ROLLUP") or {}
    client_b_name = str(roll_cfg.get("schedule_b_name", "WITHHELD")).upper()
    has_withheld_rollup = any(
        r.is_rollup and r.rollup_kind in ("withheld", "aggregate_below_threshold")
        for r in bundle.schedule_b
    ) or any(r.schedule == "B" and r.kind == "withheld" for r in bundle.rollups)

    if has_withheld_rollup and client_b_name == "WITHHELD":
        # Ambiguity A5 / IRS Instructions for Form 8872 (Oct 2020) Schedule B:
        # below-threshold label is "Aggregate below Threshold"; "Withheld" is the
        # non-disclosure (penalty) vocabulary.
        findings.append(
            _finding(
                id="A5-001",
                severity=Severity.WARN,
                rule="withheld_vs_irs_vocabulary",
                sheet="schedule_b",
                field="name",
                message=(
                    "Client Schedule B below-threshold label is WITHHELD; IRS "
                    "Instructions for Form 8872 (Oct 2020) Schedule B use "
                    "'Aggregate below Threshold' for below-$500 aggregates and "
                    "'Withheld' for non-disclosed amounts subject to penalty. "
                    "Human review of vocabulary choice required."
                ),
                source="IRS Instructions for Form 8872 (Oct 2020) Schedule B; ambiguity A5",
                context={"client_label": client_b_name, "irs_below_threshold": "Aggregate below Threshold"},
            )
        )

    # --- 7. Deletion human sign-off ---
    if bundle.deleted:
        del_total = sum_money([d.amount for d in bundle.deleted], quantize, rounding)
        findings.append(
            _finding(
                id="DEL-SIGN-001",
                severity=Severity.WARN,
                rule="deletion_human_signoff",
                sheet="deleted_records",
                field="amount",
                message=(
                    f"{len(bundle.deleted)} deleted record(s) totaling {del_total} "
                    f"require human sign-off before filing."
                ),
                source="client_style_guide; SPEC §6 $1 deletion rule",
                context={
                    "deleted_count": len(bundle.deleted),
                    "deleted_total": str(del_total),
                },
            )
        )

    # Deterministic order
    findings.sort(key=lambda f: (f.id, f.sheet or "", f.row or 0, f.message))
    return findings
