"""Regression tests for UPF review findings (YTD, STE address, report type)."""

from __future__ import annotations

from pathlib import Path

from contract.models import NormalizedBundle
from src.cleaning.fields import infer_quarterly_report_type
from src.cli.config_loader import load_config
from src.cli.pipeline import run_pipeline
from src.compliance import apply_thresholds_and_rollups


def test_infer_jul_sep_is_third_quarterly():
    assert infer_quarterly_report_type("2026-07-01", "2026-09-30") == "third_quarterly"
    assert infer_quarterly_report_type("2026-04-01", "2026-06-30") == "second_quarterly"


def test_aggregate_seed_preserves_ytd_and_ste_address(tmp_path: Path):
    """Final AGGREGATE row YTD and STE 300 must survive roll-up rebuild."""
    from contract.models import Address, CoverRecord, ScheduleARecord

    ste = Address(
        address_line1="3900 WESTERRE PARKWAY",
        address_line2="STE 300",
        city="RICHMOND",
        state="VA",
        zip5="23233",
        zip4=None,
    )
    suite = Address(
        address_line1="3900 WESTERRE PARKWAY",
        address_line2="SUITE 300",
        city="RICHMOND",
        state="VA",
        zip5="23233",
        zip4=None,
    )
    cover = CoverRecord(
        ein="831616914",
        organization_name="UNITED POLICE FUND",
        period_begin="2026-07-01",
        period_end="2026-09-30",
        filing_type="amended",
        report_type="third_quarterly",
        date_established="2017-07-18",
        email="info@unitedpolicefund.org",
        custodian_name="CHRISTOPHER STROPE",
        contact_name="CHRISTOPHER STROPE",
        mailing=suite,
        custodian=suite,
        contact=suite,
        business=suite,
        schedule_a_total="209514.87",
        schedule_b_total="196887.28",
    )
    itemized = ScheduleARecord(
        name="BIG DONOR",
        address=ste,
        employer="N/A",
        occupation="N/A",
        date="2026-07-08",
        amount="250.00",
        aggregate_ytd="250.00",
        is_rollup=False,
        source_row=2,
    )
    seed = ScheduleARecord(
        name="AGGREGATE BELOW THRESHOLD",
        address=ste,
        employer="N/A",
        occupation="N/A",
        date="2026-09-30",
        amount="186893.87",
        aggregate_ytd="463443.96",
        is_rollup=True,
        rollup_kind="aggregate_below_threshold",
        source_row=107,
    )
    bundle = NormalizedBundle(
        cover=cover,
        schedule_a=[itemized, seed],
        schedule_b=[],
        deleted=[],
        rollups=[],
        pl_lines=[],
    )
    out = apply_thresholds_and_rollups(bundle, load_config())
    agg = [r for r in out.schedule_a if r.is_rollup]
    assert len(agg) == 1
    assert agg[0].amount == "186893.87"
    assert agg[0].aggregate_ytd == "463443.96"
    assert agg[0].address.address_line2 == "STE 300"


def test_upf_inputs_pipeline_fixes(tmp_path: Path):
    inputs = Path("inputs/upf")
    if not inputs.exists():
        return
    result = run_pipeline(
        jurisdiction="federal",
        inputs=inputs,
        output=tmp_path / "out",
    )
    assert result.ok
    assert result.bundle is not None
    assert result.bundle.cover.report_type == "third_quarterly"
    assert any(f.id == "COV-002" for f in result.findings)
    agg = [r for r in result.bundle.schedule_a if r.is_rollup]
    assert len(agg) == 1
    assert agg[0].aggregate_ytd == "463443.96"
    assert agg[0].amount == "186893.87"
    assert agg[0].address.address_line2 == "STE 300"
    # XML must carry integer-cents YTD and STE on the aggregate Schedule A row
    assert result.federal_xml is not None
    xml = result.federal_xml.decode("utf-8")
    assert "46344396" in xml  # $463,443.96 as integer cents
    assert "STE 300" in xml
    # Aggregate SCHEDULEA block should use STE, not the cover SUITE address
    idx = xml.find("AGGREGATE BELOW THRESHOLD")
    assert idx != -1
    chunk = xml[idx : idx + 800]
    assert "STE 300" in chunk
