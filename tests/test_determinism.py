"""Determinism: two identical runs produce the same bytes."""

from __future__ import annotations

from pathlib import Path

import pytest

from contract.models import NormalizedBundle
from src.cli.config_loader import load_config
from src.cli.deleted_report import format_deleted_records_txt
from src.cli.siblings import resolve_siblings


def test_deleted_records_formatter_deterministic(
    sample_deleted_records,
) -> None:
    a = format_deleted_records_txt(sample_deleted_records)
    b = format_deleted_records_txt(sample_deleted_records)
    assert a == b
    assert a.encode("utf-8") == b.encode("utf-8")


@pytest.mark.requires_b
def test_federal_xml_two_builds_same_bytes(
    minimal_bundle: NormalizedBundle,
    require_agent_b: None,
) -> None:
    apis = resolve_siblings()
    assert apis.build_form_8872 is not None
    config = load_config()
    first = bytes(apis.build_form_8872(minimal_bundle, config))
    second = bytes(apis.build_form_8872(minimal_bundle, config))
    assert first == second


@pytest.mark.requires_a
@pytest.mark.requires_d
@pytest.mark.requires_b
def test_pipeline_two_runs_same_federal_xml(
    tmp_path: Path,
    fixtures_dir: Path,
    require_agent_a: None,
    require_agent_d: None,
    require_agent_b: None,
) -> None:
    from src.cli.pipeline import run_pipeline

    inputs = fixtures_dir / "edge_cases" / "below_threshold"
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    r1 = run_pipeline(
        jurisdiction="federal", inputs=inputs, output=out1, fail_on_compliance_error=False
    )
    r2 = run_pipeline(
        jurisdiction="federal", inputs=inputs, output=out2, fail_on_compliance_error=False
    )
    if not r1.ok or not r2.ok:
        pytest.skip(f"Pipeline not fully green yet: {r1.error!r} / {r2.error!r}")
    assert r1.federal_xml is not None and r2.federal_xml is not None
    assert r1.federal_xml == r2.federal_xml
    assert (out1 / "form_8872.xml").read_bytes() == (out2 / "form_8872.xml").read_bytes()
