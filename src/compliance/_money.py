"""Money helpers — Decimal dollars quantized per config MONEY section."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Mapping


_ROUNDING = {
    "ROUND_HALF_UP": ROUND_HALF_UP,
}


def load_money_config(config: Mapping[str, Any]) -> tuple[Decimal, str]:
    money = config.get("MONEY") or {}
    quant = Decimal(str(money.get("quantize", "0.01")))
    rounding_name = str(money.get("rounding", "ROUND_HALF_UP"))
    return quant, rounding_name


def to_money(value: Any, quantize: Decimal = Decimal("0.01"), rounding: str = "ROUND_HALF_UP") -> Decimal:
    """Parse to Decimal dollars; quantize with configured rounding (default HALF_UP)."""
    if isinstance(value, Decimal):
        d = value
    else:
        try:
            d = Decimal(str(value).strip().replace(",", ""))
        except (InvalidOperation, AttributeError) as exc:
            raise ValueError(f"invalid money value: {value!r}") from exc
    mode = _ROUNDING.get(rounding, ROUND_HALF_UP)
    return d.quantize(quantize, rounding=mode)


def money_str(value: Decimal | str | Any, quantize: Decimal = Decimal("0.01"), rounding: str = "ROUND_HALF_UP") -> str:
    return format(to_money(value, quantize, rounding), "f")


def sum_money(values: list[Any], quantize: Decimal = Decimal("0.01"), rounding: str = "ROUND_HALF_UP") -> Decimal:
    total = sum((to_money(v, quantize, rounding) for v in values), Decimal("0.00"))
    return to_money(total, quantize, rounding)
