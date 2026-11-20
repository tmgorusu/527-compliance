"""XSD validation for IRS Form 8872 XML."""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from src.xmlbuild.federal.errors import FederalXmlValidationError

_NS = "http://forms.irs.gov/pofd/schema"
_DEFAULT_XSD_DIR = Path(__file__).resolve().parents[3] / "spec"
_SCHEMA_NAME = "8872Schema.xsd"


def _resolve_xsd_path(xsd_dir: Path | None) -> Path:
    directory = Path(xsd_dir) if xsd_dir is not None else _DEFAULT_XSD_DIR
    path = directory / _SCHEMA_NAME
    if not path.is_file():
        raise FederalXmlValidationError(
            f"XSD not found at {path}; expected {_SCHEMA_NAME} under {directory}"
        )
    return path


def validate_form_8872(xml_bytes: bytes, xsd_dir: Path | None = None) -> None:
    """Validate Form 8872 XML against the official IRS XSD.

    Raises:
        FederalXmlValidationError: on parse or schema validation failure.
    """
    xsd_path = _resolve_xsd_path(xsd_dir)
    try:
        schema_doc = etree.parse(str(xsd_path))
        schema = etree.XMLSchema(schema_doc)
    except etree.XMLSchemaParseError as exc:
        raise FederalXmlValidationError(f"failed to load XSD {xsd_path}: {exc}") from exc

    try:
        doc = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        raise FederalXmlValidationError(f"XML parse error: {exc}") from exc

    if not schema.validate(doc):
        messages: list[str] = []
        for error in schema.error_log:
            messages.append(
                f"line {error.line}: {error.message} "
                f"(domain={_NS})"
            )
        if not messages:
            messages.append("XSD validation failed with no error details")
        raise FederalXmlValidationError(messages)
