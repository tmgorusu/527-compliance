"""Unit tests for the Texas TEC plugin skeleton.

Runnable via:
  pytest src/xmlbuild/texas/test_texas_plugin.py
Agent E may relocate or collect these under tests/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.xmlbuild.texas import (
    MAPPING_TABLE,
    SPEC_SECTION5_ITEMS,
    SpecMissingError,
    TBD,
    TexasTecPlugin,
    mapping_rows,
    missing_spec_items,
)


def test_plugin_id() -> None:
    assert TexasTecPlugin().id == "texas_tec"


def test_spec_section5_has_exactly_ten_items() -> None:
    assert len(SPEC_SECTION5_ITEMS) == 10


def test_mapping_table_is_tbd_stub() -> None:
    assert MAPPING_TABLE
    for row in mapping_rows():
        assert set(row.keys()) == {"logical_field", "tec_element", "notes"}
        assert row["tec_element"] == TBD
        assert row["tec_element"] == "TBD — awaiting official TEC spec"
        assert row["logical_field"]
        assert row["notes"]


def test_required_spec_files_lists_paths_when_empty(tmp_path: Path) -> None:
    plugin = TexasTecPlugin(spec_dir=tmp_path)
    missing_paths = plugin.required_spec_files()
    assert missing_paths
    assert all(p.startswith("spec/texas/") for p in missing_paths)
    assert "spec/texas/tec_filing_format.pdf" in missing_paths
    assert "spec/texas/form_identifier.txt" in missing_paths
    assert "spec/texas/field_names.md" in missing_paths
    assert "spec/texas/date_format.txt" in missing_paths
    assert "spec/texas/amount_format.txt" in missing_paths
    assert "spec/texas/thresholds.txt" in missing_paths
    assert "spec/texas/charset_encoding.txt" in missing_paths
    assert "spec/texas/input_csv_confirmation.txt" in missing_paths


def test_missing_spec_items_mirrors_all_ten(tmp_path: Path) -> None:
    assert missing_spec_items(tmp_path) == list(SPEC_SECTION5_ITEMS)


def test_build_raises_spec_missing_with_ten_items(tmp_path: Path) -> None:
    plugin = TexasTecPlugin(spec_dir=tmp_path)
    with pytest.raises(SpecMissingError) as exc_info:
        plugin.build(normalized_bundle=None)
    err = exc_info.value
    assert err.missing == list(SPEC_SECTION5_ITEMS)
    message = str(err)
    assert "blocked" in message.lower() or "Missing items" in message
    for item in SPEC_SECTION5_ITEMS:
        assert item in message
    for i in range(1, 11):
        assert f"  {i}. " in message


def test_validate_raises_spec_missing_with_ten_items(tmp_path: Path) -> None:
    plugin = TexasTecPlugin(spec_dir=tmp_path)
    with pytest.raises(SpecMissingError) as exc_info:
        plugin.validate(payload=b"")
    assert exc_info.value.missing == list(SPEC_SECTION5_ITEMS)


def test_partial_drops_enumerate_only_remaining(tmp_path: Path) -> None:
    (tmp_path / "tec_filing_format.pdf").write_bytes(b"%PDF-placeholder")
    (tmp_path / "tec_machine_schema.NONE").write_text(
        "No machine schema published.\n", encoding="utf-8"
    )
    (tmp_path / "form_identifier.txt").write_text("TBD from human\n", encoding="utf-8")
    plugin = TexasTecPlugin(spec_dir=tmp_path)
    missing = plugin.required_spec_files()
    assert "spec/texas/tec_filing_format.pdf" not in missing
    assert "spec/texas/tec_machine_schema.xsd" not in missing
    assert "spec/texas/form_identifier.txt" not in missing
    assert "spec/texas/field_names.md" in missing

    with pytest.raises(SpecMissingError) as exc_info:
        plugin.build(normalized_bundle=None)
    # Items 1–2 satisfied → missing starts at item 3
    assert SPEC_SECTION5_ITEMS[0] not in exc_info.value.missing
    assert SPEC_SECTION5_ITEMS[1] not in exc_info.value.missing
    assert SPEC_SECTION5_ITEMS[2] in exc_info.value.missing
    assert len(exc_info.value.missing) == 8


def _drop_all_required(spec_dir: Path) -> None:
    (spec_dir / "tec_filing_format.pdf").write_bytes(b"%PDF-placeholder")
    (spec_dir / "tec_machine_schema.NONE").write_text("none\n", encoding="utf-8")
    for name in (
        "form_identifier.txt",
        "field_names.md",
        "date_format.txt",
        "amount_format.txt",
        "thresholds.txt",
        "charset_encoding.txt",
        "input_csv_confirmation.txt",
    ):
        (spec_dir / name).write_text("human drop\n", encoding="utf-8")
    (spec_dir / "sample_accepted_filing.NONE").write_text("unavailable\n", encoding="utf-8")
    (spec_dir / "filing_deadlines.NONE").write_text("human validates\n", encoding="utf-8")


def test_required_spec_files_empty_when_complete(tmp_path: Path) -> None:
    _drop_all_required(tmp_path)
    plugin = TexasTecPlugin(spec_dir=tmp_path)
    assert plugin.required_spec_files() == []
    assert missing_spec_items(tmp_path) == []


def test_build_not_implemented_after_unlock(tmp_path: Path) -> None:
    """Skeleton still does not emit TEC XML even when checklist files exist."""
    _drop_all_required(tmp_path)
    plugin = TexasTecPlugin(spec_dir=tmp_path)
    with pytest.raises(NotImplementedError):
        plugin.build(normalized_bundle=None)
