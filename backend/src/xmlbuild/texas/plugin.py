"""Texas Ethics Commission (``texas_tec``) jurisdiction plugin skeleton.

Refuses to emit or validate filing payloads until official TEC materials are
present under ``spec/texas/``. Never invents element names, form numbers,
thresholds, or deadlines.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from src.xmlbuild.texas.errors import SpecMissingError

# Repo root: src/xmlbuild/texas/plugin.py → parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_SPEC_DIR = _REPO_ROOT / "spec" / "texas"

# ---------------------------------------------------------------------------
# SPEC.md §5 — exact 10-item checklist (mirrored for refusal messages).
# ---------------------------------------------------------------------------

SPEC_SECTION5_ITEMS: list[str] = [
    "Official TEC filing format for the applicable report "
    "(PDF + machine schema if any: XSD, JSON Schema, CSV template, or EDI).",
    "Root document / form identifier and version (form number, revision date).",
    "Element or field names for: filer identity, period, contribution schedule, "
    "expenditure schedule, address, amounts, dates.",
    "Date format required by TEC.",
    "Amount format (decimals allowed? cents? whole dollars?).",
    "Thresholds and aggregation rules TEC requires "
    "(do not reuse IRS $200/$500 without TEC source).",
    "Character set / case / encoding rules.",
    "Sample accepted filing file (redacted) if available.",
    "Filing deadline / period rules only if the tool must validate them "
    "(otherwise leave to human).",
    "Confirmation whether Texas uses the same CSV inputs or a different extract.",
]

# Preferred concrete filenames under spec/texas/ (see REQUIRED_SPEC.md).
# Flexible items accept alternate extensions or a ``.NONE`` marker.
_MACHINE_SCHEMA_CANDIDATES = (
    "tec_machine_schema.xsd",
    "tec_machine_schema.json",
    "tec_machine_schema.csv",
    "tec_machine_schema.edi",
    "tec_machine_schema.NONE",
)

_SAMPLE_CANDIDATES = (
    "sample_accepted_filing.xml",
    "sample_accepted_filing.json",
    "sample_accepted_filing.csv",
    "sample_accepted_filing.txt",
    "sample_accepted_filing.bin",
    "sample_accepted_filing.NONE",
)

_DEADLINE_CANDIDATES = (
    "filing_deadlines.txt",
    "filing_deadlines.NONE",
)

def _is_file(spec_dir: Path, name: str) -> bool:
    return (spec_dir / name).is_file()


def _any_file(spec_dir: Path, names: tuple[str, ...]) -> bool:
    return any(_is_file(spec_dir, name) for name in names)


def _item1_present(spec_dir: Path) -> bool:
    """Item 1: official PDF plus machine schema file or ``.NONE`` marker."""
    return _is_file(spec_dir, "tec_filing_format.pdf") and _any_file(
        spec_dir, _MACHINE_SCHEMA_CANDIDATES
    )


def _item_present(spec_dir: Path, index: int) -> bool:
    """Return True if SPEC §5 item ``index`` (0-based) is satisfied on disk."""
    checks = [
        lambda: _item1_present(spec_dir),
        lambda: _is_file(spec_dir, "form_identifier.txt"),
        lambda: _is_file(spec_dir, "field_names.md"),
        lambda: _is_file(spec_dir, "date_format.txt"),
        lambda: _is_file(spec_dir, "amount_format.txt"),
        lambda: _is_file(spec_dir, "thresholds.txt"),
        lambda: _is_file(spec_dir, "charset_encoding.txt"),
        lambda: _any_file(spec_dir, _SAMPLE_CANDIDATES),
        lambda: _any_file(spec_dir, _DEADLINE_CANDIDATES),
        lambda: _is_file(spec_dir, "input_csv_confirmation.txt"),
    ]
    return checks[index]()


def missing_spec_items(spec_dir: Path | None = None) -> list[str]:
    """Return SPEC.md §5 checklist strings still unsatisfied under ``spec_dir``."""
    directory = Path(spec_dir) if spec_dir is not None else _DEFAULT_SPEC_DIR
    return [
        text
        for index, text in enumerate(SPEC_SECTION5_ITEMS)
        if not _item_present(directory, index)
    ]


def required_spec_file_paths(spec_dir: Path | None = None) -> list[str]:
    """Missing preferred paths under ``spec/texas/``; empty list when ready.

    Flexible drops (machine schema / sample / deadlines) report the preferred
    concrete filename when no candidate (including ``.NONE``) is present.
    """
    directory = Path(spec_dir) if spec_dir is not None else _DEFAULT_SPEC_DIR
    missing: list[str] = []

    if not _is_file(directory, "tec_filing_format.pdf"):
        missing.append("spec/texas/tec_filing_format.pdf")
    if not _any_file(directory, _MACHINE_SCHEMA_CANDIDATES):
        missing.append("spec/texas/tec_machine_schema.xsd")
    for name in (
        "form_identifier.txt",
        "field_names.md",
        "date_format.txt",
        "amount_format.txt",
        "thresholds.txt",
        "charset_encoding.txt",
    ):
        if not _is_file(directory, name):
            missing.append(f"spec/texas/{name}")
    if not _any_file(directory, _SAMPLE_CANDIDATES):
        missing.append("spec/texas/sample_accepted_filing.xml")
    if not _any_file(directory, _DEADLINE_CANDIDATES):
        missing.append("spec/texas/filing_deadlines.txt")
    if not _is_file(directory, "input_csv_confirmation.txt"):
        missing.append("spec/texas/input_csv_confirmation.txt")
    return missing


class JurisdictionPlugin(Protocol):
    """Conceptual plugin interface from SPEC.md §10."""

    id: str

    def required_spec_files(self) -> list[str]: ...

    def build(self, normalized_bundle: Any) -> bytes: ...

    def validate(self, payload: bytes) -> list[Any]: ...


class TexasTecPlugin:
    """Texas TEC plugin — skeleton that refuses until ``spec/texas/`` is complete."""

    id: str = "texas_tec"

    def __init__(self, spec_dir: Path | str | None = None) -> None:
        self.spec_dir = Path(spec_dir) if spec_dir is not None else _DEFAULT_SPEC_DIR

    def required_spec_files(self) -> list[str]:
        """Return missing required paths under ``spec/texas/``; empty if ready."""
        return required_spec_file_paths(self.spec_dir)

    def _raise_if_incomplete(self) -> None:
        missing = missing_spec_items(self.spec_dir)
        if missing:
            raise SpecMissingError(missing=missing)

    def build(self, normalized_bundle: Any) -> bytes:
        """Refuse to emit Texas filing bytes until SPEC §5 materials are present."""
        del normalized_bundle  # unused while blocked
        self._raise_if_incomplete()
        raise NotImplementedError(
            "Texas TEC build is unlocked by spec drops but emitter is not "
            "implemented until official field mapping is filled in mapping.py."
        )

    def validate(self, payload: bytes) -> list[Any]:
        """Refuse validation until SPEC §5 materials are present."""
        del payload  # unused while blocked
        self._raise_if_incomplete()
        raise NotImplementedError(
            "Texas TEC validate is unlocked by spec drops but validators are not "
            "implemented until official TEC schema is available."
        )


# Default singleton for CLI / Agent E imports
plugin = TexasTecPlugin()
