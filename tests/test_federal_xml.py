"""Federal XML build + XSD validation against minimal fixture (Agent B)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contract.models import NormalizedBundle
from src.cli.config_loader import load_config
from src.cli.siblings import resolve_siblings


@pytest.mark.requires_b
def test_minimal_bundle_builds_and_validates_xsd(
    minimal_bundle: NormalizedBundle,
    require_agent_b: None,
) -> None:
    apis = resolve_siblings()
    assert apis.build_form_8872 is not None
    assert apis.validate_form_8872 is not None
    config = load_config()
    xml_bytes = apis.build_form_8872(minimal_bundle, config)
    assert isinstance(xml_bytes, (bytes, bytearray))
    assert b"FORM8872" in xml_bytes or b"Form8872" in xml_bytes or b"8872" in xml_bytes
    apis.validate_form_8872(bytes(xml_bytes))


@pytest.mark.requires_b
def test_federal_build_deterministic(
    minimal_bundle: NormalizedBundle,
    require_agent_b: None,
) -> None:
    apis = resolve_siblings()
    assert apis.build_form_8872 is not None
    config = load_config()
    a = apis.build_form_8872(minimal_bundle, config)
    b = apis.build_form_8872(minimal_bundle, config)
    assert a == b


def test_minimal_bundle_fixture_loads(fixtures_dir: Path) -> None:
    path = fixtures_dir / "federal" / "minimal_bundle.json"
    bundle = NormalizedBundle.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert bundle.cover.ein == "854145928"
    assert bundle.cover.mailing.state == "VA"
    assert len(bundle.schedule_a) >= 1
    assert len(bundle.schedule_b) >= 1
