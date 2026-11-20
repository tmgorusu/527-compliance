"""Federal IRS Form 8872 XML builder (Agent B)."""

from src.xmlbuild.federal.builder import build_form_8872
from src.xmlbuild.federal.errors import FederalXmlValidationError
from src.xmlbuild.federal.money import money_to_xml_int
from src.xmlbuild.federal.validate import validate_form_8872

__all__ = [
    "FederalXmlValidationError",
    "build_form_8872",
    "money_to_xml_int",
    "validate_form_8872",
]
