"""Export client workbook Final tabs to pipeline CSVs. Never touches Filing Access."""

from __future__ import annotations

import csv
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

FORBIDDEN = re.compile(r"password|username|secret|credential|login", re.I)

COVER_MAP = [
    ("A) For the period beginning", "period_begin"),
    ("A) and ending", "period_end"),
    ('B) Report "Check applicable box"', "filing_type_raw"),
    ("1) Name of Organization", "organization_name"),
    ("EIN", "ein"),
    ("2) Mailing Address Line 1", "mailing_address_line1"),
    ("2) Mailing Address Line 2", "mailing_address_line2"),
    ("2) Mailing Address City", "mailing_city"),
    ("2) Mailing Address State", "mailing_state"),
    ("2) Mailing Address Zip", "mailing_zip5"),
    ("2) Mailing Address Zip4", "mailing_zip4"),
    ("3) Email Address of organization", "email"),
    ("4) Organization Date", "date_established"),
    ("5a) Custodian of Records", "custodian_name"),
    ("5b) Custodian's Address Line 1", "custodian_address_line1"),
    ("5b) Custodian's Address Line 2", "custodian_address_line2"),
    ("5b) Custodian's Address City", "custodian_city"),
    ("5b) Custodian's Address State", "custodian_state"),
    ("5b) Custodian's Address Zip", "custodian_zip5"),
    ("5b) Custodian's Address Zip4", "custodian_zip4"),
    ("6a) Contact Person", "contact_name"),
    ("6b) Contact's Address Line 1", "contact_address_line1"),
    ("6b) Contact's Address Line 2", "contact_address_line2"),
    ("6b) Contact's Address City", "contact_city"),
    ("6b) Contact's Address State", "contact_state"),
    ("6b) Contact's Address Zip", "contact_zip5"),
    ("6b) Contact's Address Zip4", "contact_zip4"),
    ("7) Business Address Line 1", "business_address_line1"),
    ("7) Business Address Line 2", "business_address_line2"),
    ("7) Business Address City", "business_city"),
    ("7) Business Address State", "business_state"),
    ("7) Business Address Zip", "business_zip5"),
    ("7) Business Address Zip4", "business_zip4"),
    ("8) Type of Report", "report_type_raw"),
    ("8f) Monthly report for the month of:", "monthly_month"),
    ("8g) Pre-election report, Type of election:", "election_type"),
    ("8g) Pre-election report, Date of election:", "election_date"),
    ("8g) Pre-election report, For the state of:", "election_state"),
    ("8h) Post-election report, Date of election:", "post_election_date"),
    ("8h) Post-election report, For the state of:", "post_election_state"),
    ("9) Total of Schedule A", "schedule_a_total"),
    ("10) Total of Schedule B", "schedule_b_total"),
]

FILING_MAP = {
    "Initial report": "initial",
    "Change of address": "change_of_address",
    "Amended report": "amended",
    "Final report": "final",
}
REPORT_MAP = {
    "First quarterly": "first_quarterly",
    "Second quarterly": "second_quarterly",
    "Third quarterly": "third_quarterly",
    "Year-end": "year_end",
    "Mid-year": "mid_year",
    "Monthly": "monthly",
    "Pre-election": "pre_election",
    "Post-general election": "post_general_election",
}

COVER_FIELDS = [
    "ein",
    "organization_name",
    "period_begin",
    "period_end",
    "filing_type",
    "report_type",
    "date_established",
    "email",
    "custodian_name",
    "contact_name",
    "mailing_address_line1",
    "mailing_address_line2",
    "mailing_city",
    "mailing_state",
    "mailing_zip5",
    "mailing_zip4",
    "custodian_address_line1",
    "custodian_address_line2",
    "custodian_city",
    "custodian_state",
    "custodian_zip5",
    "custodian_zip4",
    "contact_address_line1",
    "contact_address_line2",
    "contact_city",
    "contact_state",
    "contact_zip5",
    "contact_zip4",
    "business_address_line1",
    "business_address_line2",
    "business_city",
    "business_state",
    "business_zip5",
    "business_zip4",
    "monthly_month",
    "election_type",
    "election_date",
    "election_state",
    "post_election_date",
    "post_election_state",
    "schedule_a_total",
    "schedule_b_total",
]

# Logical sheet name → output CSV. Filing Access is intentionally omitted.
SHEET_EXPORTS: list[tuple[str, str]] = [
    ("Schedule A Final", "schedule_a.csv"),
    ("Schedule B Final", "schedule_b.csv"),
    ("Vendor List", "vendor_list.csv"),
    ("Vendor Expenditures YTD Totals", "vendor_ytd_totals.csv"),
]

RAW_LEDGER_SHEETS = ("Raw QBO Data ", "Raw Vendor Data QBO", "Raw QBO Data")


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        if value == int(value) and abs(value) >= 1000:
            return str(int(value))
        return str(value)
    return str(value).strip()


def _write_table(path: Path, rows: list[list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    headers = [
        h
        for h in rows[0]
        if h is not None and not FORBIDDEN.search(str(h))
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=[str(h) for h in headers], extrasaction="ignore"
        )
        writer.writeheader()
        for row in rows[1:]:
            if all(v is None or str(v).strip() == "" for v in row[: len(headers)]):
                continue
            record = {
                str(h): _cell(row[i]) if i < len(row) else ""
                for i, h in enumerate(headers)
            }
            if any(FORBIDDEN.search(k) for k in record):
                continue
            writer.writerow(record)


def _export_cover(ws: Any, path: Path) -> None:
    kv: dict[str, str] = {}
    for row in ws.iter_rows(max_row=50, values_only=True):
        if not row or row[0] is None:
            continue
        key = str(row[0]).strip()
        val = row[1] if len(row) > 1 else None
        for label, field in COVER_MAP:
            if key == label:
                kv[field] = _cell(val)
    if "filing_type_raw" in kv:
        kv["filing_type"] = FILING_MAP.get(kv["filing_type_raw"], kv["filing_type_raw"])
    if "report_type_raw" in kv:
        kv["report_type"] = REPORT_MAP.get(kv["report_type_raw"], kv["report_type_raw"])
    if "ein" in kv:
        kv["ein"] = re.sub(r"\D", "", kv["ein"])[:9]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COVER_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerow({k: kv.get(k, "") for k in COVER_FIELDS})


def _export_pl(ws: Any, path: Path) -> None:
    rows: list[list[str]] = [["line_label", "amount", "section", "note"]]
    section = ""
    for row in ws.iter_rows(min_row=1, values_only=True):
        label = row[0] if row else None
        if label is None or str(label).strip() == "":
            continue
        label_s = str(label).strip()
        amt = row[1] if len(row) > 1 else None
        note = ""
        if len(row) > 3 and row[3]:
            note = _cell(row[3])
        elif len(row) > 2 and isinstance(row[2], str):
            note = _cell(row[2])
        if amt is None or amt == "":
            section = label_s
            continue
        try:
            Decimal(str(amt))
        except Exception:
            section = label_s
            continue
        rows.append(
            [label_s, f"{Decimal(str(amt)):.2f}", section, note]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)


def _sheet_rows(ws: Any) -> list[list[Any]]:
    return [list(r) for r in ws.iter_rows(values_only=True)]


def workbook_to_inputs(workbook_path: Path, output_dir: Path) -> list[str]:
    """Export Final tabs from an .xlsx into ``output_dir`` as pipeline CSVs.

    Returns the list of CSV filenames written. Raises ValueError on bad input.
    """
    if workbook_path.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise ValueError(f"Unsupported workbook type: {workbook_path.name}")

    wb = load_workbook(workbook_path, data_only=True, read_only=True)
    try:
        # Hard skip credentials sheet even if present
        written: list[str] = []
        names = set(wb.sheetnames)

        if "Cover Page" in names:
            _export_cover(wb["Cover Page"], output_dir / "cover.csv")
            written.append("cover.csv")
        if "PL" in names:
            _export_pl(wb["PL"], output_dir / "pl.csv")
            written.append("pl.csv")

        for sheet_name, csv_name in SHEET_EXPORTS:
            if sheet_name in names:
                _write_table(output_dir / csv_name, _sheet_rows(wb[sheet_name]))
                written.append(csv_name)

        for sheet_name in RAW_LEDGER_SHEETS:
            if sheet_name in names:
                _write_table(output_dir / "raw_ledger.csv", _sheet_rows(wb[sheet_name]))
                written.append("raw_ledger.csv")
                break

        if not written:
            raise ValueError(
                f"No recognized sheets in {workbook_path.name}. "
                "Expected Cover Page / Schedule A Final / Schedule B Final / PL."
            )
        return written
    finally:
        wb.close()
