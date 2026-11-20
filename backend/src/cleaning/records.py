"""
Clean surviving rows into contract models.

Roll-up policy (Agent A choice):
  If Schedule A/B input already contains Final-sheet roll-up lines named
  ``AGGREGATE BELOW THRESHOLD`` or ``WITHHELD``, keep them and set
  ``is_rollup=True`` (with ``rollup_kind``) so Agent B can build against real
  client data. ``NormalizedBundle.rollups`` stays ``[]`` — Agent D owns
  thresholding / rebuilding roll-ups and may replace these lines later.
  We do **not** apply thresholds here.
"""

from __future__ import annotations

from typing import Any, Optional

from contract.models import (
    Address,
    CoverRecord,
    Finding,
    PLLineRecord,
    ScheduleARecord,
    ScheduleBRecord,
    Severity,
)

from src.cleaning.fields import (
    all_caps_text,
    normalize_date,
    normalize_state,
    normalize_whitespace,
    normalize_zip4,
    normalize_zip5,
    suspected_city_typo,
    suspected_name_truncation,
    xml_safe,
)
from src.cleaning.money import parse_money_str
from src.cleaning.rejects import RejectCollector

ROLLUP_A_NAME = "AGGREGATE BELOW THRESHOLD"
ROLLUP_B_NAME = "WITHHELD"


def _src_row(row: dict[str, str]) -> int:
    try:
        return max(1, int(row.get("_source_row") or 1))
    except ValueError:
        return 1


def _src_file(row: dict[str, str]) -> Optional[str]:
    return row.get("_source_file") or None


def _get(row: dict[str, str], *keys: str, default: str = "") -> str:
    for k in keys:
        if k in row and str(row[k]).strip() != "":
            return str(row[k])
    return default


def _build_address(
    row: dict[str, str],
    *,
    prefix: str = "",
    line1_keys: tuple[str, ...] | None = None,
    line2_keys: tuple[str, ...] | None = None,
    city_keys: tuple[str, ...] | None = None,
    state_keys: tuple[str, ...] | None = None,
    zip5_keys: tuple[str, ...] | None = None,
    zip4_keys: tuple[str, ...] | None = None,
) -> Address:
    if prefix:
        line1 = _get(row, f"{prefix}_address_line1", f"{prefix}_address_line_1")
        line2 = _get(row, f"{prefix}_address_line2", f"{prefix}_address_line_2")
        city = _get(row, f"{prefix}_city")
        state = _get(row, f"{prefix}_state")
        zip5 = _get(row, f"{prefix}_zip5", f"{prefix}_zip_5")
        zip4 = _get(row, f"{prefix}_zip4", f"{prefix}_zip_4")
    else:
        line1 = _get(row, *(line1_keys or ("address_line_1", "address_line1")))
        line2 = _get(row, *(line2_keys or ("address_line_2", "address_line2")))
        city = _get(row, *(city_keys or ("city",)))
        state = _get(row, *(state_keys or ("state",)))
        zip5 = _get(row, *(zip5_keys or ("zip_5", "zip5")))
        zip4 = _get(row, *(zip4_keys or ("zip_4", "zip4")))

    line1_n = all_caps_text(line1)
    line2_n = all_caps_text(line2) if line2.strip() else None
    if line2_n == "":
        line2_n = None
    city_n = all_caps_text(city)
    state_n = normalize_state(state)
    zip5_n = normalize_zip5(zip5)
    zip4_n = normalize_zip4(zip4) if zip4.strip() else None

    if not line1_n:
        raise ValueError("address_line1 required")
    if not city_n:
        raise ValueError("city required")

    # Truncate to XSD limits only after flagging? Prefer reject on over-length
    # for line1/city if over — but client data is usually pre-clipped.
    if len(line1_n) > 35:
        line1_n = line1_n[:35]
    if line2_n and len(line2_n) > 35:
        line2_n = line2_n[:35]
    if len(city_n) > 22:
        city_n = city_n[:22]

    return Address(
        address_line1=line1_n,
        address_line2=line2_n,
        city=city_n,
        state=state_n,
        zip5=zip5_n,
        zip4=zip4_n,
    )


def _clip(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len]


def detect_rollup(name: str) -> tuple[bool, Optional[str]]:
    n = all_caps_text(name)
    if n == ROLLUP_A_NAME:
        return True, "aggregate_below_threshold"
    if n == ROLLUP_B_NAME:
        return True, "withheld"
    return False, None


def clean_cover(
    rows: list[dict[str, str]],
    *,
    config: dict[str, Any],
    rejects: RejectCollector,
    findings: list[Finding],
) -> CoverRecord | None:
    if not rows:
        rejects.add(sheet="cover", reason="cover.csv has no data rows", field=None)
        return None
    if len(rows) > 1:
        findings.append(
            Finding(
                id="COV-001",
                severity=Severity.WARN,
                rule="cover_single_row",
                sheet="cover",
                row=None,
                field=None,
                message=f"cover.csv has {len(rows)} rows; using first row only.",
                source="contract/records.schema.json",
            )
        )
    row = rows[0]
    try:
        ein = re_digits(_get(row, "ein"), 9)
        filing_type = _get(row, "filing_type").strip().lower()
        report_type = _get(row, "report_type").strip().lower()
        email = xml_safe(normalize_whitespace(_get(row, "email")))
        # Emails are not ALL CAPS — preserve for delivery validity.
        election_type_raw = _blank_to_none(_get(row, "election_type"))
        election_type = election_type_raw.lower() if election_type_raw else None
        cover = CoverRecord(
            ein=ein,
            organization_name=all_caps_text(_get(row, "organization_name")) or None,
            pac_id=_optional_digits(_get(row, "pac_id")),
            period_begin=normalize_date(_get(row, "period_begin")),
            period_end=normalize_date(_get(row, "period_end")),
            filing_type=filing_type,  # type: ignore[arg-type]
            report_type=report_type,  # type: ignore[arg-type]
            monthly_month=_blank_to_none(_get(row, "monthly_month")),
            election_type=election_type,  # type: ignore[arg-type]
            election_date=(
                normalize_date(_get(row, "election_date"))
                if _get(row, "election_date").strip()
                else None
            ),
            election_state=(
                normalize_state(_get(row, "election_state"))
                if _get(row, "election_state").strip()
                else None
            ),
            date_established=normalize_date(_get(row, "date_established")),
            email=email,
            custodian_name=_clip(all_caps_text(_get(row, "custodian_name")), 50),
            contact_name=_clip(all_caps_text(_get(row, "contact_name")), 50),
            mailing=_build_address(row, prefix="mailing"),
            custodian=_build_address(row, prefix="custodian"),
            contact=_build_address(row, prefix="contact"),
            business=_build_address(row, prefix="business"),
            schedule_a_total=_optional_money(row, "schedule_a_total", config),
            schedule_b_total=_optional_money(row, "schedule_b_total", config),
            source_file=_src_file(row),
            source_row=_src_row(row),
        )
        return cover
    except Exception as exc:
        rejects.add(
            sheet="cover",
            source_file=_src_file(row),
            source_row=_src_row(row),
            field=None,
            reason=f"cover clean failed: {exc}",
            raw=row,
        )
        return None


def clean_schedule_a(
    rows: list[dict[str, str]],
    *,
    config: dict[str, Any],
    rejects: RejectCollector,
    findings: list[Finding],
) -> list[ScheduleARecord]:
    out: list[ScheduleARecord] = []
    for row in rows:
        raw_name = _get(row, "contributor_name", "name")
        try:
            name = _clip(all_caps_text(raw_name), 50)
            if not name:
                raise ValueError("name required")
            is_rollup, rollup_kind = detect_rollup(name)
            employer = _clip(all_caps_text(_get(row, "contributor_employer", "employer")), 70)
            occupation = _clip(
                all_caps_text(_get(row, "contributor_occupation", "occupation")), 70
            )
            if not employer:
                raise ValueError("employer required")
            if not occupation:
                raise ValueError("occupation required")
            # BEST EFFORTS MADE / N/A are valid employer/occupation literals (no special case).

            address = _build_address(row)
            city_flag = suspected_city_typo(address.city)
            if city_flag:
                findings.append(
                    Finding(
                        id=f"TYP-A-{_src_row(row)}",
                        severity=Severity.WARN,
                        rule="suspected_typo",
                        sheet="schedule_a",
                        row=_src_row(row),
                        field="city",
                        message=city_flag,
                        source="client_style_guide",
                        context={"city": address.city, "raw_name": raw_name},
                    )
                )
            name_flag = suspected_name_truncation(raw_name)
            if name_flag:
                findings.append(
                    Finding(
                        id=f"TRN-A-{_src_row(row)}",
                        severity=Severity.INFO,
                        rule="suspected_truncation",
                        sheet="schedule_a",
                        row=_src_row(row),
                        field="name",
                        message=name_flag,
                        source="client_style_guide",
                    )
                )

            amount = parse_money_str(_get(row, "contribution_amount", "amount"), config)
            agg = parse_money_str(
                _get(row, "aggregate_contributions_ytd", "aggregate_ytd"), config
            )
            rec = ScheduleARecord(
                name=name,
                address=address,
                employer=employer,
                occupation=occupation,
                date=normalize_date(_get(row, "contribution_date", "date")),
                amount=amount,
                aggregate_ytd=agg,
                is_rollup=is_rollup,
                rollup_kind=rollup_kind,  # type: ignore[arg-type]
                threshold_status_changed_by_deletion=False,
                source_file=_src_file(row),
                source_row=_src_row(row),
                raw_name=raw_name or None,
            )
            out.append(rec)
        except Exception as exc:
            rejects.add(
                sheet="schedule_a",
                source_file=_src_file(row),
                source_row=_src_row(row),
                field=None,
                reason=f"schedule_a clean failed: {exc}",
                raw=row,
            )
    return out


def clean_schedule_b(
    rows: list[dict[str, str]],
    *,
    config: dict[str, Any],
    rejects: RejectCollector,
    findings: list[Finding],
) -> list[ScheduleBRecord]:
    out: list[ScheduleBRecord] = []
    for row in rows:
        raw_name = _get(row, "recipient_name", "name")
        try:
            name = _clip(all_caps_text(raw_name), 50)
            if not name:
                raise ValueError("name required")
            is_rollup, rollup_kind = detect_rollup(name)
            employer = _clip(all_caps_text(_get(row, "recipient_employer", "employer") or "N/A"), 70)
            occupation = _clip(
                all_caps_text(_get(row, "recipient_occupation", "occupation") or "N/A"), 70
            )
            purpose = _clip(
                all_caps_text(_get(row, "expenditure_purpose", "purpose")), 512
            )
            if not purpose:
                raise ValueError("purpose required")

            address = _build_address(row)
            city_flag = suspected_city_typo(address.city)
            if city_flag:
                findings.append(
                    Finding(
                        id=f"TYP-B-{_src_row(row)}",
                        severity=Severity.WARN,
                        rule="suspected_typo",
                        sheet="schedule_b",
                        row=_src_row(row),
                        field="city",
                        message=city_flag,
                        source="client_style_guide",
                        context={"city": address.city, "raw_name": raw_name},
                    )
                )

            amount = parse_money_str(_get(row, "expenditure_amount", "amount"), config)
            unapplied = str(row.get("is_unapplied_cash", "")).strip().lower() in {
                "1",
                "true",
                "yes",
                "y",
                "t",
            }
            rec = ScheduleBRecord(
                name=name,
                address=address,
                employer=employer,
                occupation=occupation,
                date=normalize_date(_get(row, "expenditure_date", "date")),
                amount=amount,
                purpose=purpose,
                is_rollup=is_rollup,
                rollup_kind=rollup_kind,  # type: ignore[arg-type]
                is_unapplied_cash=unapplied,
                threshold_status_changed_by_deletion=False,
                source_file=_src_file(row),
                source_row=_src_row(row),
                raw_name=raw_name or None,
            )
            out.append(rec)
        except Exception as exc:
            rejects.add(
                sheet="schedule_b",
                source_file=_src_file(row),
                source_row=_src_row(row),
                field=None,
                reason=f"schedule_b clean failed: {exc}",
                raw=row,
            )
    return out


def clean_pl(
    rows: list[dict[str, str]],
    *,
    config: dict[str, Any],
    rejects: RejectCollector,
) -> list[PLLineRecord]:
    out: list[PLLineRecord] = []
    for row in rows:
        try:
            label = normalize_whitespace(_get(row, "line_label", "label"))
            if not label:
                raise ValueError("line_label required")
            amount = parse_money_str(_get(row, "amount"), config)
            section = _blank_to_none(_get(row, "section"))
            out.append(
                PLLineRecord(
                    line_label=label,
                    amount=amount,
                    section=section,
                    source_row=_src_row(row),
                )
            )
        except Exception as exc:
            rejects.add(
                sheet="pl",
                source_file=_src_file(row),
                source_row=_src_row(row),
                field=None,
                reason=f"pl clean failed: {exc}",
                raw=row,
            )
    return out


def re_digits(raw: str, length: int) -> str:
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) != length:
        raise ValueError(f"expected {length} digits, got {raw!r}")
    return digits


def _optional_digits(raw: str) -> Optional[str]:
    text = raw.strip()
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        raise ValueError(f"invalid pac_id: {raw!r}")
    return digits


def _blank_to_none(raw: str) -> Optional[str]:
    text = raw.strip()
    return text if text else None


def _optional_money(
    row: dict[str, str], key: str, config: dict[str, Any]
) -> Optional[str]:
    raw = _get(row, key)
    if not raw.strip():
        return None
    return parse_money_str(raw, config)
