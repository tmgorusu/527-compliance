"""Aggregate YTD, threshold status, and Schedule A/B roll-ups.

Federal threshold rules are cited from IRS Instructions for Form 8872
(Rev. October 2020). Client roll-up labels come from config / style guide.
"""

from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal
from typing import Any, Mapping

from contract.models import (
    Address,
    DeletedRecord,
    NormalizedBundle,
    RollupRecord,
    ScheduleARecord,
    ScheduleBRecord,
)

from ._money import load_money_config, money_str, sum_money, to_money

# Roll-up names that indicate a synthetic line already present in inputs.
_DEFAULT_ROLLUP_A = "AGGREGATE BELOW THRESHOLD"
_DEFAULT_ROLLUP_B = "WITHHELD"


def _name_key(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"\s+", " ", name.strip().upper())


def _meets_threshold(ytd: Decimal, threshold: Decimal, comparison: str) -> bool:
    # IRS Instructions for Form 8872 (Oct 2020) Schedule A: itemize when
    # aggregate contributions during the calendar year as of period end were
    # "at least $200". Schedule B: "at least $500". Contract default comparison
    # is gte (ambiguity A2).
    if comparison == "gt":
        return ytd > threshold
    return ytd >= threshold


def _strip_schedule_a_rollups(
    rows: list[ScheduleARecord],
    rollup_names: set[str],
    quantize: Decimal,
    rounding: str,
) -> tuple[list[ScheduleARecord], Decimal, Decimal, Address | None, list[int]]:
    """Remove existing roll-up lines so rebuilt totals are not double-counted.

    Returns
    ``(detail_rows, seed_amount, seed_ytd, seed_address, seed_source_rows)``.

    Final-tab exports often include only the aggregate roll-up line (no
    underlying below-threshold detail). Preserve that line's period amount,
    calendar-year YTD (``aggregate_ytd``), and address (e.g. ``STE 300``) so
    the rebuilt AGGREGATE BELOW THRESHOLD row matches the filed Final sheet.
    """
    out: list[ScheduleARecord] = []
    seed = Decimal("0.00")
    seed_ytd = Decimal("0.00")
    seed_address: Address | None = None
    seed_rows: list[int] = []
    for r in rows:
        if r.is_rollup or _name_key(r.name) in rollup_names:
            seed = to_money(seed + to_money(r.amount, quantize, rounding), quantize, rounding)
            # Prefer the largest YTD seen on seed roll-up lines (normally one).
            ytd = to_money(r.aggregate_ytd, quantize, rounding)
            if ytd > seed_ytd:
                seed_ytd = ytd
            if seed_address is None:
                seed_address = r.address
            seed_rows.append(r.source_row)
            continue
        out.append(r)
    return out, seed, seed_ytd, seed_address, seed_rows


def _strip_schedule_b_rollups(
    rows: list[ScheduleBRecord],
    rollup_names: set[str],
    quantize: Decimal,
    rounding: str,
) -> tuple[list[ScheduleBRecord], Decimal, list[int]]:
    """Remove existing roll-up lines; return detail + seed (see Schedule A)."""
    out: list[ScheduleBRecord] = []
    seed = Decimal("0.00")
    seed_rows: list[int] = []
    for r in rows:
        if r.is_rollup or _name_key(r.name) in rollup_names:
            seed = to_money(seed + to_money(r.amount, quantize, rounding), quantize, rounding)
            seed_rows.append(r.source_row)
            continue
        out.append(r)
    return out, seed, seed_rows


def _is_unapplied_cash(row: ScheduleBRecord, config: Mapping[str, Any]) -> bool:
    if row.is_unapplied_cash:
        return True
    cfg = config.get("UNAPPLIED_CASH") or {}
    substrings = [str(s).upper() for s in (cfg.get("name_or_purpose_substrings") or [])]
    if not substrings:
        return False
    hay = f"{row.name} {row.purpose}".upper()
    return any(s in hay for s in substrings if s)


def _deleted_by_name(
    deleted: list[DeletedRecord], schedule: str
) -> dict[str, list[DeletedRecord]]:
    by_name: dict[str, list[DeletedRecord]] = defaultdict(list)
    for d in deleted:
        if d.schedule != schedule:
            continue
        by_name[_name_key(d.name)].append(d)
    return by_name


def _recompute_ytd_a(
    rows: list[ScheduleARecord],
    deleted_for_name: list[DeletedRecord],
    quantize: Decimal,
    rounding: str,
) -> Decimal:
    """Recompute contributor YTD after deletions (Schedule A).

    Assumption (pipeline order delete → aggregate): surviving rows still carry
    pre-deletion aggregate_ytd from ingest/clean. Subtract deleted dollars for
    that person. If no aggregate is usable, fall back to period sum.

    IRS Instructions for Form 8872 (Oct 2020) Schedule A — Aggregate Year-to-Date
    Contributions: total accepted from the contributor during this calendar year
    as of the end of this reporting period.
    """
    deleted_sum = sum_money([d.amount for d in deleted_for_name], quantize, rounding)
    period_sum = sum_money([r.amount for r in rows], quantize, rounding)
    if not rows:
        return to_money(Decimal("0.00"), quantize, rounding)
    max_ytd = max(to_money(r.aggregate_ytd, quantize, rounding) for r in rows)
    adjusted = to_money(max_ytd - deleted_sum, quantize, rounding)
    if adjusted < period_sum:
        return period_sum
    return adjusted


def _recompute_ytd_b(
    rows: list[ScheduleBRecord],
    deleted_for_name: list[DeletedRecord],
    quantize: Decimal,
    rounding: str,
) -> Decimal:
    """Recompute vendor YTD after deletions (Schedule B).

    ScheduleBRecord has no aggregate_ytd field. Without a prior-period vendor YTD
    feed in the bundle, YTD is approximated as period sum of surviving rows
    (post-deletion). Threshold-change detection compares period+deleted vs period.
    """
    period_sum = sum_money([r.amount for r in rows], quantize, rounding)
    return period_sum


def _sort_schedule_a(rows: list[ScheduleARecord]) -> list[ScheduleARecord]:
    # SPEC §8: (date, name, address_line1, amount, source_row); roll-ups last.
    def key(r: ScheduleARecord) -> tuple:
        return (
            1 if r.is_rollup else 0,
            r.date,
            r.name,
            r.address.address_line1,
            to_money(r.amount),
            r.source_row,
        )

    return sorted(rows, key=key)


def _sort_schedule_b(rows: list[ScheduleBRecord]) -> list[ScheduleBRecord]:
    # SPEC §8: (date, name, purpose, amount, source_row); roll-ups last.
    def key(r: ScheduleBRecord) -> tuple:
        return (
            1 if r.is_rollup else 0,
            r.date,
            r.name,
            r.purpose,
            to_money(r.amount),
            r.source_row,
        )

    return sorted(rows, key=key)


def _next_source_row(*row_lists: list) -> int:
    mx = 0
    for rows in row_lists:
        for r in rows:
            mx = max(mx, int(getattr(r, "source_row", 0) or 0))
    return mx + 1


def apply_thresholds_and_rollups(
    bundle: NormalizedBundle, config: Mapping[str, Any]
) -> NormalizedBundle:
    """Recompute YTD after deletions, apply thresholds, rebuild roll-up lines.

    Behavior if inputs already contain roll-up lines
    ------------------------------------------------
    Any schedule row with ``is_rollup=True`` or whose name matches the configured
    roll-up labels (Schedule A ``AGGREGATE BELOW THRESHOLD``, Schedule B
    ``WITHHELD`` / IRS ``Aggregate below Threshold``) is **stripped** before
    aggregation. If below-threshold *detail* rows are present, the roll-up is
    rebuilt solely from those (seed discarded — no double-count). If only a
    prior aggregate line existed (typical Final-tab export), its amount is
    preserved as a seed and re-emitted. Nonzero unapplied-cash rows are folded
    into the Schedule B WITHHELD total.

    IRS Instructions for Form 8872 (Rev. October 2020):
      - Schedule A: itemize contributors with aggregate YTD at least $200 who
        gave during the period; below-threshold → one "Aggregate below Threshold"
        line (client label from config, typically AGGREGATE BELOW THRESHOLD) using
        organization address, last day of period, employer/occupation N/A.
      - Schedule B: itemize recipients with aggregate YTD at least $500; IRS
        below-threshold label is "Aggregate below Threshold"; client process uses
        WITHHELD (see compliance WARN A5).
    """
    quantize, rounding = load_money_config(config)
    thr_cfg = config.get("THRESHOLDS") or {}
    roll_cfg = config.get("ROLLUP") or {}

    thr_a = to_money(thr_cfg.get("schedule_a_itemize_ytd", "200.00"), quantize, rounding)
    thr_b = to_money(thr_cfg.get("schedule_b_itemize_ytd", "500.00"), quantize, rounding)
    comparison = str(thr_cfg.get("comparison", "gte")).lower()

    name_a = str(roll_cfg.get("schedule_a_name", _DEFAULT_ROLLUP_A))
    name_b = str(roll_cfg.get("schedule_b_name", _DEFAULT_ROLLUP_B))
    purpose_b = str(roll_cfg.get("schedule_b_purpose", "WITHHELD"))

    rollup_name_keys = {
        _name_key(name_a),
        _name_key(name_b),
        _name_key("AGGREGATE BELOW THRESHOLD"),
        _name_key("Aggregate below Threshold"),
        _name_key("WITHHELD"),
        _name_key("Withheld"),
    }

    business: Address = bundle.cover.business
    period_end = bundle.cover.period_end

    # --- Schedule A ---
    raw_a, seed_a, seed_ytd_a, seed_address_a, seed_rows_a = _strip_schedule_a_rollups(
        list(bundle.schedule_a), rollup_name_keys, quantize, rounding
    )
    deleted_a = _deleted_by_name(bundle.deleted, "A")

    by_name_a: dict[str, list[ScheduleARecord]] = defaultdict(list)
    for r in raw_a:
        by_name_a[_name_key(r.name)].append(r)

    itemized_a: list[ScheduleARecord] = []
    rollup_components_a: list[ScheduleARecord] = []
    rollup_ytd_parts: list[Decimal] = []
    # Demoted-by-deletion markers: $0 rows so XML builders can skip zero amounts
    # while compliance still sees threshold_status_changed_by_deletion=True.
    # Demoted-by-deletion markers: amount 0.00 so schedule sums / P&L are
    # unchanged; compliance reads threshold_status_changed_by_deletion.
    # XML builders should omit non-rollup rows with amount 0.00.
    deletion_markers_a: list[ScheduleARecord] = []

    for key, rows in sorted(by_name_a.items(), key=lambda kv: kv[0]):
        deleted_rows = deleted_a.get(key, [])
        ytd_after = _recompute_ytd_a(rows, deleted_rows, quantize, rounding)
        deleted_sum = sum_money([d.amount for d in deleted_rows], quantize, rounding)
        ytd_before = to_money(ytd_after + deleted_sum, quantize, rounding)

        after_ok = _meets_threshold(ytd_after, thr_a, comparison)
        before_ok = _meets_threshold(ytd_before, thr_a, comparison)
        changed = bool(deleted_rows) and (before_ok != after_ok)

        updated: list[ScheduleARecord] = []
        for r in rows:
            updated.append(
                r.model_copy(
                    update={
                        "aggregate_ytd": money_str(ytd_after, quantize, rounding),
                        "threshold_status_changed_by_deletion": changed,
                        "is_rollup": False,
                        "rollup_kind": None,
                    }
                )
            )

        if after_ok:
            itemized_a.extend(updated)
        else:
            rollup_components_a.extend(updated)
            rollup_ytd_parts.append(ytd_after)
            if changed and updated:
                deletion_markers_a.append(
                    updated[0].model_copy(
                        update={
                            "amount": money_str(Decimal("0.00"), quantize, rounding),
                            "threshold_status_changed_by_deletion": True,
                        }
                    )
                )

    rollups: list[RollupRecord] = []
    schedule_a: list[ScheduleARecord] = list(itemized_a) + list(deletion_markers_a)

    # Seed (stripped Final roll-up) + demoted itemized rows (disjoint sets for
    # Final exports). Period amount on the roll-up line; YTD comes from the
    # Final seed's Aggregate Contributions YTD (not the period amount).
    demoted_amt_a = sum_money([r.amount for r in rollup_components_a], quantize, rounding)
    amt = to_money(seed_a + demoted_amt_a, quantize, rounding)
    demoted_ytd = sum_money(rollup_ytd_parts, quantize, rounding)
    if seed_ytd_a > 0:
        ytd_roll = to_money(seed_ytd_a + demoted_ytd, quantize, rounding)
    else:
        # No Final seed YTD — fall back to period seed amount + demoted YTDs.
        ytd_roll = to_money(seed_a + demoted_ytd, quantize, rounding)
    # Prefer Final aggregate-row address (STE 300) over cover business (SUITE 300).
    rollup_address_a = seed_address_a or business
    src_rows = sorted(set(seed_rows_a) | {r.source_row for r in rollup_components_a})
    component_count = len(rollup_components_a)

    if rollup_components_a or seed_a != 0:
        # IRS Instructions for Form 8872 (Oct 2020) Schedule A — Aggregate below
        # Threshold: org address, last day of reporting period, N/A employer/occupation.
        rollups.append(
            RollupRecord(
                schedule="A",
                kind="aggregate_below_threshold",
                name=name_a,
                amount=money_str(amt, quantize, rounding),
                component_count=component_count,
                component_source_rows=src_rows,
                address=rollup_address_a,
                date=period_end,
                employer="N/A",
                occupation="N/A",
                purpose=None,
            )
        )
        schedule_a.append(
            ScheduleARecord(
                name=name_a,
                address=rollup_address_a,
                employer="N/A",
                occupation="N/A",
                date=period_end,
                amount=money_str(amt, quantize, rounding),
                aggregate_ytd=money_str(ytd_roll, quantize, rounding),
                is_rollup=True,
                rollup_kind="aggregate_below_threshold",
                threshold_status_changed_by_deletion=False,
                source_file=None,
                source_row=_next_source_row(raw_a, bundle.deleted),
                raw_name=None,
            )
        )

    # --- Schedule B ---
    raw_b, seed_b, seed_rows_b = _strip_schedule_b_rollups(
        list(bundle.schedule_b), rollup_name_keys, quantize, rounding
    )
    deleted_b = _deleted_by_name(bundle.deleted, "B")

    unapplied_fold: list[ScheduleBRecord] = []
    candidates_b: list[ScheduleBRecord] = []
    for r in raw_b:
        if _is_unapplied_cash(r, config):
            amt = to_money(r.amount, quantize, rounding)
            if amt == 0:
                # Style guide: drop zero-balance unapplied cash.
                continue
            # Nonzero unapplied cash is folded into WITHHELD (not itemized).
            unapplied_fold.append(r)
        else:
            candidates_b.append(r)

    by_name_b: dict[str, list[ScheduleBRecord]] = defaultdict(list)
    for r in candidates_b:
        by_name_b[_name_key(r.name)].append(r)

    itemized_b: list[ScheduleBRecord] = []
    rollup_components_b: list[ScheduleBRecord] = []
    deletion_markers_b: list[ScheduleBRecord] = []

    for key, rows in sorted(by_name_b.items(), key=lambda kv: kv[0]):
        deleted_rows = deleted_b.get(key, [])
        ytd_after = _recompute_ytd_b(rows, deleted_rows, quantize, rounding)
        deleted_sum = sum_money([d.amount for d in deleted_rows], quantize, rounding)
        ytd_before = to_money(ytd_after + deleted_sum, quantize, rounding)

        # IRS Instructions for Form 8872 (Oct 2020) Schedule B: itemize when
        # aggregate expenditures to that person during the calendar year as of
        # period end were at least $500.
        #
        # ScheduleBRecord has no aggregate_ytd. Period-sum is a lower bound.
        # Without prior-period vendor YTD in the bundle, trust Final-tab
        # itemization unless deletions flip the period-sum threshold proxy.
        after_period = _meets_threshold(ytd_after, thr_b, comparison)
        before_period = _meets_threshold(ytd_before, thr_b, comparison)
        if deleted_rows and before_period != after_period:
            after_ok = after_period
            changed = True
        else:
            after_ok = True
            changed = False

        updated_b: list[ScheduleBRecord] = []
        for r in rows:
            updated_b.append(
                r.model_copy(
                    update={
                        "threshold_status_changed_by_deletion": changed,
                        "is_rollup": False,
                        "rollup_kind": None,
                    }
                )
            )

        if after_ok:
            itemized_b.extend(updated_b)
        else:
            rollup_components_b.extend(updated_b)
            if changed and updated_b:
                deletion_markers_b.append(
                    updated_b[0].model_copy(
                        update={
                            "amount": money_str(Decimal("0.00"), quantize, rounding),
                            "threshold_status_changed_by_deletion": True,
                        }
                    )
                )

    schedule_b: list[ScheduleBRecord] = list(itemized_b) + list(deletion_markers_b)

    fold_amt = sum_money([r.amount for r in unapplied_fold], quantize, rounding)
    # Seed (stripped Final roll-up) + newly demoted itemized rows are treated as
    # disjoint; Final exports do not list below-threshold vendors individually.
    demoted_amt = sum_money([r.amount for r in rollup_components_b], quantize, rounding)
    below_amt = to_money(seed_b + demoted_amt, quantize, rounding)
    below_src = set(seed_rows_b) | {r.source_row for r in rollup_components_b}
    below_count = len(rollup_components_b)

    # Fold nonzero unapplied cash into WITHHELD (client style guide).
    withheld_amt = to_money(below_amt + fold_amt, quantize, rounding)

    if rollup_components_b or seed_b != 0 or unapplied_fold:
        # Client process: below-threshold Schedule B → WITHHELD (config).
        # IRS Instructions for Form 8872 (Oct 2020) Schedule B uses
        # "Aggregate below Threshold" for below-$500; "Withheld" is the
        # non-disclosure/penalty line. Client label wins; compliance emits WARN.
        src_rows = sorted(below_src | {r.source_row for r in unapplied_fold})
        rollups.append(
            RollupRecord(
                schedule="B",
                kind="withheld",
                name=name_b,
                amount=money_str(withheld_amt, quantize, rounding),
                component_count=below_count + len(unapplied_fold),
                component_source_rows=src_rows,
                address=business,
                date=period_end,
                employer="N/A",
                occupation="N/A",
                purpose=purpose_b,
            )
        )
        if fold_amt != 0:
            rollups.append(
                RollupRecord(
                    schedule="B",
                    kind="unapplied_cash_fold",
                    name=name_b,
                    amount=money_str(fold_amt, quantize, rounding),
                    component_count=len(unapplied_fold),
                    component_source_rows=sorted({r.source_row for r in unapplied_fold}),
                    address=business,
                    date=period_end,
                    employer="N/A",
                    occupation="N/A",
                    purpose=purpose_b,
                )
            )
        schedule_b.append(
            ScheduleBRecord(
                name=name_b,
                address=business,
                employer="N/A",
                occupation="N/A",
                date=period_end,
                amount=money_str(withheld_amt, quantize, rounding),
                purpose=purpose_b,
                is_rollup=True,
                rollup_kind="withheld",
                is_unapplied_cash=False,
                threshold_status_changed_by_deletion=False,
                source_file=None,
                source_row=_next_source_row(raw_b, bundle.deleted),
                raw_name=None,
            )
        )

    schedule_a = _sort_schedule_a(schedule_a)
    schedule_b = _sort_schedule_b(schedule_b)

    # Stable rollup list: A then B, by kind then name.
    rollups = sorted(rollups, key=lambda r: (r.schedule, r.kind, r.name, r.amount))

    return NormalizedBundle(
        cover=bundle.cover,
        schedule_a=schedule_a,
        schedule_b=schedule_b,
        deleted=list(bundle.deleted),
        rollups=rollups,
        pl_lines=list(bundle.pl_lines),
    )
