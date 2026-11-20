"""Shared pytest fixtures and sibling-availability helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contract.models import DeletedRecord, NormalizedBundle
from src.cli.siblings import resolve_siblings, sibling_status

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "fixtures"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def minimal_bundle() -> NormalizedBundle:
    path = FIXTURES / "federal" / "minimal_bundle.json"
    return NormalizedBundle.model_validate(json.loads(path.read_text(encoding="utf-8")))


@pytest.fixture
def sample_deleted_records() -> list[DeletedRecord]:
    return [
        DeletedRecord(
            schedule="A",
            source_file="schedule_a.csv",
            source_row=4,
            date="2026-07-15",
            name="ONE DOLLAR DONOR",
            amount="1.00",
            reason="exact DELETE_AMOUNTS match",
            matched_delete_amount="1.00",
        ),
        DeletedRecord(
            schedule="B",
            source_file="schedule_b.csv",
            source_row=7,
            date="2026-08-02",
            name="ONE DOLLAR VENDOR",
            amount="1.00",
            reason="exact DELETE_AMOUNTS match",
            matched_delete_amount="1.00",
        ),
        DeletedRecord(
            schedule="LEDGER",
            source_file="raw_ledger.csv",
            source_row=12,
            date="2026-09-01",
            name="LEDGER ONE DOLLAR",
            amount="1.00",
            reason="exact DELETE_AMOUNTS match",
            matched_delete_amount="1.00",
        ),
    ]


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "requires_a: needs Agent A ingest/cleaning modules"
    )
    config.addinivalue_line(
        "markers", "requires_b: needs Agent B federal XML builder"
    )
    config.addinivalue_line(
        "markers", "requires_c: needs Agent C Texas plugin build()"
    )
    config.addinivalue_line(
        "markers", "requires_d: needs Agent D compliance/threshold modules"
    )


def _skip_unless(flag: str, reason: str) -> None:
    status = sibling_status()
    if not status.get(flag, False):
        pytest.skip(reason)


@pytest.fixture
def require_agent_a() -> None:
    _skip_unless(
        "agent_a_ingest_clean",
        "Agent A ingest/cleaning API not importable yet",
    )


@pytest.fixture
def require_agent_b() -> None:
    apis = resolve_siblings()
    if apis.build_form_8872 is None or apis.validate_form_8872 is None:
        pytest.skip("Agent B federal build/validate API not importable yet")


@pytest.fixture
def require_agent_c() -> None:
    apis = resolve_siblings()
    if apis.texas_build is None or apis.SpecMissingError is None:
        pytest.skip("Agent C Texas build / SpecMissingError not importable yet")


@pytest.fixture
def require_agent_d() -> None:
    apis = resolve_siblings()
    if apis.apply_thresholds_and_rollups is None:
        pytest.skip("Agent D apply_thresholds_and_rollups not importable yet")
