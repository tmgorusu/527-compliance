"""Threshold / roll-up behavior when Agent D is ready."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from contract.models import NormalizedBundle, ScheduleARecord
from src.cli.config_loader import load_config
from src.cli.siblings import resolve_siblings


def _addr() -> dict:
    return {
        "address_line1": "3900 WESTERRE PARKWAY",
        "address_line2": "STE 300",
        "city": "RICHMOND",
        "state": "VA",
        "zip5": "23233",
        "zip4": None,
    }


@pytest.fixture
def threshold_bundle(minimal_bundle: NormalizedBundle) -> NormalizedBundle:
    """Bundle with clear below- and above-threshold Schedule A rows."""
    data = minimal_bundle.model_dump(mode="json")
    data["schedule_a"] = [
        {
            "name": "SMALL DONOR",
            "address": _addr(),
            "employer": "N/A",
            "occupation": "N/A",
            "date": "2026-07-08",
            "amount": "50.00",
            "aggregate_ytd": "50.00",
            "is_rollup": False,
            "rollup_kind": None,
            "threshold_status_changed_by_deletion": False,
            "source_file": "schedule_a.csv",
            "source_row": 2,
            "raw_name": "SMALL DONOR",
        },
        {
            "name": "BIG DONOR",
            "address": _addr(),
            "employer": "N/A",
            "occupation": "N/A",
            "date": "2026-07-09",
            "amount": "250.00",
            "aggregate_ytd": "250.00",
            "is_rollup": False,
            "rollup_kind": None,
            "threshold_status_changed_by_deletion": False,
            "source_file": "schedule_a.csv",
            "source_row": 3,
            "raw_name": "BIG DONOR",
        },
    ]
    data["schedule_b"] = [
        {
            "name": "SMALL VENDOR",
            "address": _addr(),
            "employer": "N/A",
            "occupation": "N/A",
            "date": "2026-07-14",
            "amount": "100.00",
            "purpose": "ADMIN-MISC",
            "is_rollup": False,
            "rollup_kind": None,
            "is_unapplied_cash": False,
            "threshold_status_changed_by_deletion": False,
            "source_file": "schedule_b.csv",
            "source_row": 2,
            "raw_name": "SMALL VENDOR",
        },
        {
            "name": "BIG VENDOR",
            "address": _addr(),
            "employer": "N/A",
            "occupation": "N/A",
            "date": "2026-07-15",
            "amount": "600.00",
            "purpose": "FUNDRAISING",
            "is_rollup": False,
            "rollup_kind": None,
            "is_unapplied_cash": False,
            "threshold_status_changed_by_deletion": False,
            "source_file": "schedule_b.csv",
            "source_row": 3,
            "raw_name": "BIG VENDOR",
        },
        {
            # Seed Final-tab WITHHELD line — Agent D strips and re-emits.
            "name": "WITHHELD",
            "address": _addr(),
            "employer": "N/A",
            "occupation": "N/A",
            "date": "2026-09-30",
            "amount": "40.00",
            "purpose": "WITHHELD",
            "is_rollup": True,
            "rollup_kind": "withheld",
            "is_unapplied_cash": False,
            "threshold_status_changed_by_deletion": False,
            "source_file": "schedule_b.csv",
            "source_row": 4,
            "raw_name": "WITHHELD",
        },
    ]
    data["rollups"] = []
    data["deleted"] = []
    return NormalizedBundle.model_validate(data)


@pytest.mark.requires_d
def test_below_threshold_produces_rollups(
    threshold_bundle: NormalizedBundle,
    require_agent_d: None,
) -> None:
    apis = resolve_siblings()
    assert apis.apply_thresholds_and_rollups is not None
    config = load_config()
    out = apis.apply_thresholds_and_rollups(threshold_bundle, config)
    if isinstance(out, dict):
        out = NormalizedBundle.model_validate(out)

    a_names = {r.name for r in out.schedule_a}
    b_names = {r.name for r in out.schedule_b}
    rollup_names = {r.name for r in out.rollups}

    assert "AGGREGATE BELOW THRESHOLD" in a_names or "AGGREGATE BELOW THRESHOLD" in rollup_names
    assert "WITHHELD" in b_names or "WITHHELD" in rollup_names
    assert "BIG DONOR" in a_names
    assert "BIG VENDOR" in b_names

    # Below-threshold Schedule A individuals should not remain itemized.
    small_a = [
        r for r in out.schedule_a if r.name == "SMALL DONOR" and not r.is_rollup
    ]
    assert small_a == []


@pytest.mark.requires_d
def test_rollup_amount_sums_below_threshold(
    threshold_bundle: NormalizedBundle,
    require_agent_d: None,
) -> None:
    apis = resolve_siblings()
    assert apis.apply_thresholds_and_rollups is not None
    config = load_config()
    out = apis.apply_thresholds_and_rollups(threshold_bundle, config)
    if isinstance(out, dict):
        out = NormalizedBundle.model_validate(out)

    a_rollups = [
        r
        for r in out.schedule_a
        if isinstance(r, ScheduleARecord)
        and (r.is_rollup or r.name == "AGGREGATE BELOW THRESHOLD")
    ]
    from contract.models import RollupRecord

    a_from_rollups = [
        r for r in out.rollups if isinstance(r, RollupRecord) and r.schedule == "A"
    ]
    if a_rollups:
        total = sum(Decimal(r.amount) for r in a_rollups)
        assert total == Decimal("50.00")
    elif a_from_rollups:
        total = sum(Decimal(r.amount) for r in a_from_rollups)
        assert total == Decimal("50.00")
    else:
        pytest.fail("No Schedule A roll-up found after thresholds")


@pytest.mark.requires_a
@pytest.mark.requires_d
def test_edge_case_below_threshold_inputs(
    fixtures_dir: Path,
    tmp_path: Path,
    require_agent_a: None,
    require_agent_d: None,
) -> None:
    """Edge fixture: small Schedule A donors roll into AGGREGATE BELOW THRESHOLD.

    Note (Agent D current behavior): Schedule B without a prior WITHHELD seed and
    without deletion-flipped YTD keeps period-itemized vendors (Final-tab trust
    proxy). This test locks Schedule A roll-up from the edge CSV inputs.
    """
    apis = resolve_siblings()
    assert apis.run_ingest_pipeline is not None or apis.build_normalized_bundle is not None
    assert apis.apply_thresholds_and_rollups is not None
    config = load_config()
    inputs = fixtures_dir / "edge_cases" / "below_threshold"
    if apis.run_ingest_pipeline is not None:
        a_result = apis.run_ingest_pipeline(inputs, output_dir=tmp_path, config=config)
        bundle = a_result.bundle if hasattr(a_result, "bundle") else a_result
    else:
        assert apis.build_normalized_bundle is not None
        bundle = apis.build_normalized_bundle(inputs, output_dir=tmp_path)
    if isinstance(bundle, dict):
        bundle = NormalizedBundle.model_validate(bundle)
    out = apis.apply_thresholds_and_rollups(bundle, config)
    if isinstance(out, dict):
        out = NormalizedBundle.model_validate(out)
    names_a = {r.name for r in out.schedule_a} | {r.name for r in out.rollups}
    assert "AGGREGATE BELOW THRESHOLD" in names_a
    assert "BIG DONOR" in {r.name for r in out.schedule_a}
    assert not any(r.name == "SMALL DONOR A" and not r.is_rollup for r in out.schedule_a)
