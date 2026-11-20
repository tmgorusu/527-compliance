"""Self-contained smoke test for the federal XML builder.

Run from repo root::

    .venv/bin/python -m src.xmlbuild.federal._smoke
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from contract.models import NormalizedBundle
from src.xmlbuild.federal import build_form_8872, money_to_xml_int, validate_form_8872

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE = _REPO_ROOT / "fixtures" / "federal" / "minimal_bundle.json"
_SPEC = _REPO_ROOT / "spec"


def main() -> int:
    assert money_to_xml_int("250.00", "integer_cents") == 25000
    assert money_to_xml_int("250.40", "whole_dollars") == 250
    assert money_to_xml_int("250.50", "whole_dollars") == 251

    if not _FIXTURE.is_file():
        print(f"FAIL: missing fixture {_FIXTURE}", file=sys.stderr)
        return 1

    bundle = NormalizedBundle.model_validate(json.loads(_FIXTURE.read_text(encoding="utf-8")))
    xml_bytes = build_form_8872(bundle, config=None)
    validate_form_8872(xml_bytes, xsd_dir=_SPEC)

    out = _REPO_ROOT / "output" / "form_8872_smoke.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(xml_bytes)
    print(f"PASS: XSD validation ok ({len(xml_bytes)} bytes) → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
