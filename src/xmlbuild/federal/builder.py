"""Build IRS Form 8872 XML from a NormalizedBundle."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import yaml
from lxml import etree

from contract.models import (
    Address,
    CoverRecord,
    NormalizedBundle,
    ScheduleARecord,
    ScheduleBRecord,
)
from src.xmlbuild.federal.errors import FederalXmlValidationError
from src.xmlbuild.federal.money import money_to_xml_int
from src.xmlbuild.federal.validate import validate_form_8872

NS = "http://forms.irs.gov/pofd/schema"
NSMAP = {None: NS}

# StreetAddressType / CityType first-char exclusions + allowed continuation
# (spec/8871and8872Common.xsd). Fail early with a clear message.
_STREET_LINE1 = re.compile(
    r"^[^\s_@$^&()+=|\\\[\]{}*><'\":;?!][A-Za-z0-9.\-#%/,\s]+$"
)
_STREET_LINE2 = re.compile(
    r"^[^\s_@$^&()+=|\\\[\]{}*><'\":;?!][A-Za-z0-9.\-#%/,\s]*$"
)
_CITY = re.compile(
    r"^[^\s_@$^&()+=|\\\[\]{}*><'\":;?!][A-Za-z0-9.\-#%/,\s]*$"
)

_FILING_TYPE_ELEMENT = {
    "initial": "InitialReport",
    "change_of_address": "ChangeOfAddress",
    "amended": "AmendedReport",
    "final": "FinalReport",
}

_REPORT_TYPE_CHECKBOX = {
    "first_quarterly": "FirstQuarterlyReport",
    "second_quarterly": "SecondQuarterlyReport",
    "third_quarterly": "ThirdQuarterlyReport",
    "year_end": "YearEndReport",
    "mid_year": "MidYearReport",
}

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "defaults.yaml"


def build_form_8872(
    bundle: NormalizedBundle,
    config: dict[str, Any] | None = None,
) -> bytes:
    """Serialize ``bundle`` to Form 8872 XML bytes and validate against the XSD.

    Amount encoding is read from ``config["MONEY"]["federal_xml_amount_encoding"]``
    (Phase 2 default: ``integer_cents``). When ``config`` is ``None``, loads
    ``config/defaults.yaml``.
    """
    cfg = _resolve_config(config)
    encoding = _amount_encoding(cfg)
    errors: list[str] = []

    root = etree.Element(f"{{{NS}}}FORM8872", nsmap=NSMAP)
    if bundle.cover.ein:
        root.set("ein", bundle.cover.ein)
    if bundle.cover.pac_id:
        root.set("pacId", bundle.cover.pac_id)

    _append_address(root, "MailingAddress", bundle.cover.mailing, "cover.mailing", errors)
    _append_filing_type(root, bundle.cover)
    _sub(root, "DateEstablished", bundle.cover.date_established)
    _sub(root, "eMail", bundle.cover.email)
    _sub(root, "CustodianName", bundle.cover.custodian_name)
    _append_address(
        root, "CustodianAddress", bundle.cover.custodian, "cover.custodian", errors
    )
    _sub(root, "ContactPerson", bundle.cover.contact_name)
    _append_address(root, "ContactAddress", bundle.cover.contact, "cover.contact", errors)
    _append_address(
        root, "BusinessAddress", bundle.cover.business, "cover.business", errors
    )
    _sub(root, "PeriodBeginDate", bundle.cover.period_begin)
    _sub(root, "PeriodEndDate", bundle.cover.period_end)
    _append_report_type(root, bundle.cover, errors)
    _append_schedule_a(root, bundle.schedule_a, encoding, errors)
    _append_schedule_b(root, bundle.schedule_b, encoding, errors)

    if errors:
        raise FederalXmlValidationError(errors)

    xml_bytes = etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )
    # lxml pretty_print uses 2-space indent; normalize to ensure trailing newline
    if not xml_bytes.endswith(b"\n"):
        xml_bytes += b"\n"

    validate_form_8872(xml_bytes)
    return xml_bytes


def _resolve_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if config is not None:
        return config
    if not _DEFAULT_CONFIG_PATH.is_file():
        raise FederalXmlValidationError(
            f"config is None and defaults not found at {_DEFAULT_CONFIG_PATH}"
        )
    with _DEFAULT_CONFIG_PATH.open(encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh)
    if not isinstance(loaded, dict):
        raise FederalXmlValidationError("config/defaults.yaml did not parse as a mapping")
    return loaded


def _amount_encoding(config: dict[str, Any]) -> str:
    money = config.get("MONEY")
    if not isinstance(money, dict) or "federal_xml_amount_encoding" not in money:
        raise FederalXmlValidationError(
            "MONEY.federal_xml_amount_encoding is unset; "
            "refuse amount encode (ambiguity A1)"
        )
    encoding = money["federal_xml_amount_encoding"]
    if not isinstance(encoding, str) or not encoding.strip():
        raise FederalXmlValidationError(
            "MONEY.federal_xml_amount_encoding is empty; refuse amount encode"
        )
    return encoding


def _sub(parent: etree._Element, tag: str, text: str) -> etree._Element:
    el = etree.SubElement(parent, f"{{{NS}}}{tag}")
    el.text = text
    return el


def _check_street(value: str, field: str, line: int, errors: list[str]) -> None:
    pattern = _STREET_LINE1 if line == 1 else _STREET_LINE2
    max_len = 35
    if len(value) > max_len:
        errors.append(
            f"{field}: street address exceeds {max_len} characters ({value!r})"
        )
        return
    if not pattern.match(value):
        errors.append(
            f"{field}: street address fails XSD StreetAddressType pattern "
            f"(no leading space; forbidden chars _@$^&()+=|\\[]{{}}*><'\":;?!): {value!r}"
        )


def _check_city(value: str, field: str, errors: list[str]) -> None:
    if len(value) > 22:
        errors.append(f"{field}: city exceeds 22 characters ({value!r})")
        return
    if not _CITY.match(value):
        errors.append(
            f"{field}: city fails XSD CityType pattern "
            f"(no leading space; forbidden chars): {value!r}"
        )


def _append_address(
    parent: etree._Element,
    tag: str,
    address: Address,
    label: str,
    errors: list[str],
) -> None:
    _check_street(address.address_line1, f"{label}.address_line1", 1, errors)
    if address.address_line2 is not None and address.address_line2 != "":
        _check_street(address.address_line2, f"{label}.address_line2", 2, errors)
    _check_city(address.city, f"{label}.city", errors)

    addr_el = etree.SubElement(parent, f"{{{NS}}}{tag}")
    _sub(addr_el, "AddressLine1", address.address_line1)
    if address.address_line2:
        _sub(addr_el, "AddressLine2", address.address_line2)
    _sub(addr_el, "City", address.city)
    _sub(addr_el, "State", address.state)
    _sub(addr_el, "ZIP5", address.zip5)
    if address.zip4:
        _sub(addr_el, "ZIP4", address.zip4)


def _append_filing_type(parent: etree._Element, cover: CoverRecord) -> None:
    filing = etree.SubElement(parent, f"{{{NS}}}FilingType")
    element_name = _FILING_TYPE_ELEMENT[cover.filing_type]
    _sub(filing, element_name, "1")


def _append_report_type(
    parent: etree._Element,
    cover: CoverRecord,
    errors: list[str],
) -> None:
    report = etree.SubElement(parent, f"{{{NS}}}ReportType")
    rt = cover.report_type

    if rt in _REPORT_TYPE_CHECKBOX:
        _sub(report, _REPORT_TYPE_CHECKBOX[rt], "1")
        return

    if rt == "monthly":
        if not cover.monthly_month:
            errors.append("cover.monthly_month required when report_type=monthly")
            return
        _sub(report, "MonthlyReport", cover.monthly_month)
        return

    if rt == "pre_election":
        if not cover.election_type or not cover.election_date or not cover.election_state:
            errors.append(
                "cover.election_type, election_date, and election_state required "
                "for report_type=pre_election"
            )
            return
        pre = etree.SubElement(report, f"{{{NS}}}PreElectionReport")
        _sub(pre, "ElectionType", cover.election_type)
        _sub(pre, "ElectionDate", cover.election_date)
        _sub(pre, "State", cover.election_state)
        return

    if rt == "post_general_election":
        if not cover.election_date or not cover.election_state:
            errors.append(
                "cover.election_date and election_state required "
                "for report_type=post_general_election"
            )
            return
        post = etree.SubElement(report, f"{{{NS}}}PostGeneralElectionReport")
        _sub(post, "ElectionDate", cover.election_date)
        _sub(post, "State", cover.election_state)
        return

    errors.append(f"unsupported cover.report_type {rt!r}")


def _is_deletion_marker_row(rec: ScheduleARecord | ScheduleBRecord) -> bool:
    """Agent D emits $0 non-rollup rows when deletions flip threshold status.

    Those markers are for findings only — never emit them in filing XML.
    """
    if rec.is_rollup:
        return False
    if not getattr(rec, "threshold_status_changed_by_deletion", False):
        return False
    try:
        return money_to_xml_int(rec.amount, "integer_cents") == 0
    except ValueError:
        return rec.amount in {"0.00", "0", "0.0"}


def _emit_schedule_a_records(
    records: Iterable[ScheduleARecord],
) -> list[ScheduleARecord]:
    """Drop $0 deletion-marker rows before sort/emit."""
    return [r for r in records if not _is_deletion_marker_row(r)]


def _emit_schedule_b_records(
    records: Iterable[ScheduleBRecord],
) -> list[ScheduleBRecord]:
    return [r for r in records if not _is_deletion_marker_row(r)]


def _sort_schedule_a(records: Iterable[ScheduleARecord]) -> list[ScheduleARecord]:
    items = _emit_schedule_a_records(records)
    regular = [r for r in items if not r.is_rollup]
    rollups = [r for r in items if r.is_rollup]
    key = lambda r: (r.date, r.name, r.address.address_line1, r.amount, r.source_row)
    return sorted(regular, key=key) + sorted(rollups, key=key)


def _sort_schedule_b(records: Iterable[ScheduleBRecord]) -> list[ScheduleBRecord]:
    items = _emit_schedule_b_records(records)
    regular = [r for r in items if not r.is_rollup]
    rollups = [r for r in items if r.is_rollup]
    key = lambda r: (r.date, r.name, r.purpose, r.amount, r.source_row)
    return sorted(regular, key=key) + sorted(rollups, key=key)


def _append_schedule_a(
    parent: etree._Element,
    records: list[ScheduleARecord],
    encoding: str,
    errors: list[str],
) -> None:
    ordered = _sort_schedule_a(records)
    if not ordered:
        _sub(parent, "NoScheduleA", "1")
        return
    for idx, rec in enumerate(ordered):
        label = f"schedule_a[{idx}]"
        try:
            amount_int = money_to_xml_int(rec.amount, encoding)
            ytd_int = money_to_xml_int(rec.aggregate_ytd, encoding)
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
            continue
        el = etree.SubElement(parent, f"{{{NS}}}SCHEDULEA")
        _sub(el, "ContributorName", rec.name)
        _append_address(el, "ContributorAddress", rec.address, f"{label}.address", errors)
        _sub(el, "ContributorEmployer", rec.employer)
        _sub(el, "ContributorOccupation", rec.occupation)
        _sub(el, "ContributionDate", rec.date)
        _sub(el, "ContributionAmount", str(amount_int))
        _sub(el, "AggregateContributionsYTD", str(ytd_int))


def _append_schedule_b(
    parent: etree._Element,
    records: list[ScheduleBRecord],
    encoding: str,
    errors: list[str],
) -> None:
    ordered = _sort_schedule_b(records)
    if not ordered:
        _sub(parent, "NoScheduleB", "1")
        return
    for idx, rec in enumerate(ordered):
        label = f"schedule_b[{idx}]"
        try:
            amount_int = money_to_xml_int(rec.amount, encoding)
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
            continue
        el = etree.SubElement(parent, f"{{{NS}}}SCHEDULEB")
        _sub(el, "RecipientName", rec.name)
        _append_address(el, "RecipientAddress", rec.address, f"{label}.address", errors)
        _sub(el, "RecipientEmployer", rec.employer)
        _sub(el, "RecipientOccupation", rec.occupation)
        _sub(el, "ExpenditureDate", rec.date)
        _sub(el, "ExpenditureAmount", str(amount_int))
        _sub(el, "ExpenditurePurpose", rec.purpose)
