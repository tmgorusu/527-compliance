"""Pydantic models mirroring contract/*.schema.json — shared by all agents."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"


class Address(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address_line1: str = Field(min_length=1, max_length=35)
    address_line2: Optional[str] = Field(default=None, max_length=35)
    city: str = Field(min_length=1, max_length=22)
    state: str = Field(pattern=r"^[A-Z]{2}$")
    zip5: str = Field(pattern=r"^[0-9]{5}$")
    zip4: Optional[str] = Field(default=None, pattern=r"^[0-9]{4}$")


class CoverRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ein: str = Field(pattern=r"^[0-9]{9}$")
    organization_name: Optional[str] = None
    pac_id: Optional[str] = Field(default=None, pattern=r"^[0-9]+$")
    period_begin: str
    period_end: str
    filing_type: Literal["initial", "change_of_address", "amended", "final"]
    report_type: Literal[
        "first_quarterly",
        "second_quarterly",
        "third_quarterly",
        "year_end",
        "mid_year",
        "monthly",
        "pre_election",
        "post_general_election",
    ]
    monthly_month: Optional[str] = Field(default=None, pattern=r"^(0[1-9]|1[0-2])$")
    election_type: Optional[
        Literal["primary", "general", "convention", "special", "run-off"]
    ] = None
    election_date: Optional[str] = None
    election_state: Optional[str] = Field(default=None, pattern=r"^[A-Z]{2}$")
    date_established: str
    email: str = Field(min_length=7, max_length=150)
    custodian_name: str = Field(min_length=1, max_length=50)
    contact_name: str = Field(min_length=1, max_length=50)
    mailing: Address
    custodian: Address
    contact: Address
    business: Address
    schedule_a_total: Optional[str] = Field(default=None, pattern=r"^-?[0-9]+\.[0-9]{2}$")
    schedule_b_total: Optional[str] = Field(default=None, pattern=r"^-?[0-9]+\.[0-9]{2}$")
    source_file: Optional[str] = None
    source_row: Optional[int] = Field(default=None, ge=1)


class ScheduleARecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=50)
    address: Address
    employer: str = Field(min_length=1, max_length=70)
    occupation: str = Field(min_length=1, max_length=70)
    date: str
    amount: str = Field(pattern=r"^-?[0-9]+\.[0-9]{2}$")
    aggregate_ytd: str = Field(pattern=r"^-?[0-9]+\.[0-9]{2}$")
    is_rollup: bool
    rollup_kind: Optional[
        Literal["aggregate_below_threshold", "withheld"]
    ] = None
    threshold_status_changed_by_deletion: bool = False
    source_file: Optional[str] = None
    source_row: int = Field(ge=1)
    raw_name: Optional[str] = None


class ScheduleBRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=50)
    address: Address
    employer: str = Field(min_length=1, max_length=70)
    occupation: str = Field(min_length=1, max_length=70)
    date: str
    amount: str = Field(pattern=r"^-?[0-9]+\.[0-9]{2}$")
    purpose: str = Field(min_length=1, max_length=512)
    is_rollup: bool
    rollup_kind: Optional[
        Literal["withheld", "aggregate_below_threshold", "unapplied_cash_fold"]
    ] = None
    is_unapplied_cash: bool = False
    threshold_status_changed_by_deletion: bool = False
    source_file: Optional[str] = None
    source_row: int = Field(ge=1)
    raw_name: Optional[str] = None


class DeletedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedule: Literal["A", "B", "LEDGER", "OTHER"]
    source_file: Optional[str] = None
    source_row: int = Field(ge=1)
    date: Optional[str] = None
    name: Optional[str] = None
    amount: str = Field(pattern=r"^-?[0-9]+\.[0-9]{2}$")
    reason: str
    matched_delete_amount: Optional[str] = Field(
        default=None, pattern=r"^-?[0-9]+\.[0-9]{2}$"
    )


class RollupRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedule: Literal["A", "B"]
    kind: Literal["aggregate_below_threshold", "withheld", "unapplied_cash_fold"]
    name: str
    amount: str = Field(pattern=r"^-?[0-9]+\.[0-9]{2}$")
    component_count: int = Field(ge=0)
    component_source_rows: list[int]
    address: Address
    date: Optional[str] = None
    employer: str = "N/A"
    occupation: str = "N/A"
    purpose: Optional[str] = None


class PLLineRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_label: str
    amount: str = Field(pattern=r"^-?[0-9]+\.[0-9]{2}$")
    section: Optional[str] = None
    source_row: Optional[int] = None


class NormalizedBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cover: CoverRecord
    schedule_a: list[ScheduleARecord]
    schedule_b: list[ScheduleBRecord]
    deleted: list[DeletedRecord]
    rollups: list[RollupRecord]
    pl_lines: list[PLLineRecord]


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    severity: Severity
    rule: str
    sheet: Optional[str] = None
    row: Optional[int] = Field(default=None, ge=1)
    field: Optional[str] = None
    message: str = Field(min_length=1)
    source: str
    context: Optional[dict[str, Any]] = None


class FindingsDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[Finding]
