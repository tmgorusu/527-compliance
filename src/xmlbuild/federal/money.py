"""Amount encoding for IRS Form 8872 USAmountType (xsd:integer)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

ENCODING_INTEGER_CENTS = "integer_cents"
ENCODING_WHOLE_DOLLARS = "whole_dollars"
_ALLOWED = frozenset({ENCODING_INTEGER_CENTS, ENCODING_WHOLE_DOLLARS})


def money_to_xml_int(amount_str: str, encoding: str) -> int:
    """Convert a normalized dollar string (``"250.00"``) to an XML integer.

    Phase 2 default (A1): ``integer_cents`` → ``$250.00`` becomes ``25000``.
    ``whole_dollars`` rounds half-up to the nearest dollar.
    """
    if encoding not in _ALLOWED:
        raise ValueError(
            f"unknown federal_xml_amount_encoding {encoding!r}; "
            f"expected one of {sorted(_ALLOWED)}"
        )
    try:
        amount = Decimal(amount_str)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"invalid amount string {amount_str!r}") from exc

    quantized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if encoding == ENCODING_INTEGER_CENTS:
        cents = (quantized * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return int(cents)

    dollars = quantized.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(dollars)
