"""Logical-field → TEC element mapping stubs.

Do NOT invent TEC element names, form numbers, thresholds, or deadlines.
Every ``tec_element`` stays TBD until an official TEC spec is dropped under
``spec/texas/`` (see REQUIRED_SPEC.md).
"""

from __future__ import annotations

from typing import TypedDict

TBD = "TBD — awaiting official TEC spec"


class MappingRow(TypedDict):
    logical_field: str
    tec_element: str
    notes: str


# Columns: logical_field, tec_element, notes
MAPPING_TABLE: list[MappingRow] = [
    {
        "logical_field": "cover.ein",
        "tec_element": TBD,
        "notes": "Filer identity; TEC element name unknown until official spec.",
    },
    {
        "logical_field": "cover.organization_name",
        "tec_element": TBD,
        "notes": "Filer identity; may not map 1:1 to a TEC field.",
    },
    {
        "logical_field": "cover.period_begin",
        "tec_element": TBD,
        "notes": "Reporting period start; date format TBD (SPEC §5 item 4).",
    },
    {
        "logical_field": "cover.period_end",
        "tec_element": TBD,
        "notes": "Reporting period end; date format TBD (SPEC §5 item 4).",
    },
    {
        "logical_field": "cover.filing_type",
        "tec_element": TBD,
        "notes": "Filing / report type; TEC form identifier TBD (SPEC §5 item 2).",
    },
    {
        "logical_field": "cover.report_type",
        "tec_element": TBD,
        "notes": "Report period kind; do not assume IRS 8872 report-type names.",
    },
    {
        "logical_field": "address.address_line1",
        "tec_element": TBD,
        "notes": "Address line 1 for filer / contributor / recipient as applicable.",
    },
    {
        "logical_field": "address.address_line2",
        "tec_element": TBD,
        "notes": "Address line 2; optional on federal — TEC rules unknown.",
    },
    {
        "logical_field": "address.city",
        "tec_element": TBD,
        "notes": "City.",
    },
    {
        "logical_field": "address.state",
        "tec_element": TBD,
        "notes": "State; encoding/case rules TBD (SPEC §5 item 7).",
    },
    {
        "logical_field": "address.zip5",
        "tec_element": TBD,
        "notes": "ZIP5; TEC postal rules unknown.",
    },
    {
        "logical_field": "address.zip4",
        "tec_element": TBD,
        "notes": "ZIP+4; may be optional or absent in TEC format.",
    },
    {
        "logical_field": "schedule_a.name",
        "tec_element": TBD,
        "notes": "Contribution schedule — contributor name.",
    },
    {
        "logical_field": "schedule_a.employer",
        "tec_element": TBD,
        "notes": "Contribution schedule — employer.",
    },
    {
        "logical_field": "schedule_a.occupation",
        "tec_element": TBD,
        "notes": "Contribution schedule — occupation.",
    },
    {
        "logical_field": "schedule_a.date",
        "tec_element": TBD,
        "notes": "Contribution date; format TBD (SPEC §5 item 4).",
    },
    {
        "logical_field": "schedule_a.amount",
        "tec_element": TBD,
        "notes": "Contribution amount; amount format TBD (SPEC §5 item 5).",
    },
    {
        "logical_field": "schedule_a.aggregate_ytd",
        "tec_element": TBD,
        "notes": "YTD aggregate; thresholds must come from TEC (SPEC §5 item 6).",
    },
    {
        "logical_field": "schedule_b.name",
        "tec_element": TBD,
        "notes": "Expenditure schedule — recipient name.",
    },
    {
        "logical_field": "schedule_b.employer",
        "tec_element": TBD,
        "notes": "Expenditure schedule — employer.",
    },
    {
        "logical_field": "schedule_b.occupation",
        "tec_element": TBD,
        "notes": "Expenditure schedule — occupation.",
    },
    {
        "logical_field": "schedule_b.date",
        "tec_element": TBD,
        "notes": "Expenditure date; format TBD (SPEC §5 item 4).",
    },
    {
        "logical_field": "schedule_b.amount",
        "tec_element": TBD,
        "notes": "Expenditure amount; amount format TBD (SPEC §5 item 5).",
    },
    {
        "logical_field": "schedule_b.purpose",
        "tec_element": TBD,
        "notes": "Expenditure purpose; TEC length/charset unknown.",
    },
]


def mapping_rows() -> list[MappingRow]:
    """Return a copy of the stub mapping table."""
    return [dict(row) for row in MAPPING_TABLE]
