"""Texas plugin must refuse with a clear missing-spec message (Agent C)."""

from __future__ import annotations

import pytest

from contract.models import NormalizedBundle
from src.cli.siblings import resolve_siblings


@pytest.mark.requires_c
def test_texas_build_refuses_with_missing_spec(
    minimal_bundle: NormalizedBundle,
    require_agent_c: None,
) -> None:
    apis = resolve_siblings()
    assert apis.texas_build is not None
    assert apis.SpecMissingError is not None

    with pytest.raises(apis.SpecMissingError) as exc_info:
        apis.texas_build(minimal_bundle)

    message = str(exc_info.value)
    assert "missing" in message.lower() or "blocked" in message.lower()
    # SPEC.md §5 checklist themes should appear in the refusal
    lowered = message.lower()
    assert "tec" in lowered
    # Enumerated list expected
    assert "1." in message or "1)" in message or "- " in message

    missing = getattr(exc_info.value, "missing", None)
    if missing is not None:
        assert isinstance(missing, list)
        assert len(missing) >= 1


@pytest.mark.requires_c
def test_texas_required_spec_files_nonempty(require_agent_c: None) -> None:
    apis = resolve_siblings()
    if apis.texas_required_spec_files is None:
        pytest.skip("required_spec_files() not exported yet")
    files = apis.texas_required_spec_files()
    assert isinstance(files, (list, tuple))
    assert len(files) >= 1


def test_spec_missing_error_importable_or_skip() -> None:
    """SpecMissingError may exist even before build() is wired."""
    apis = resolve_siblings()
    if apis.SpecMissingError is None:
        pytest.skip("Agent C SpecMissingError not importable yet")
    err = apis.SpecMissingError(["Official TEC filing format"])
    assert "Official TEC filing format" in str(err)
