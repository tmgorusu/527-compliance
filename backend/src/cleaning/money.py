"""Money parsing/quantization from config MONEY settings."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_DOWN, ROUND_UP
from typing import Any

_ROUNDING_MAP = {
    "ROUND_HALF_UP": ROUND_HALF_UP,
    "ROUND_DOWN": ROUND_DOWN,
    "ROUND_UP": ROUND_UP,
}


def parse_money(raw: str) -> Decimal:
    """Parse a money-like string into Decimal. Strips $, commas, whitespace."""
    text = str(raw).strip()
    if text == "":
        raise ValueError("empty money value")
    text = text.replace("$", "").replace(",", "").replace(" ", "")
    # parentheses negative accounting
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    return Decimal(text)


def quantize_money(value: Decimal, config: dict[str, Any] | None = None) -> Decimal:
    money_cfg = (config or {}).get("MONEY") or {}
    quant = Decimal(str(money_cfg.get("quantize", "0.01")))
    rounding_name = str(money_cfg.get("rounding", "ROUND_HALF_UP"))
    rounding = _ROUNDING_MAP.get(rounding_name, ROUND_HALF_UP)
    return value.quantize(quant, rounding=rounding)


def money_str(value: Decimal, config: dict[str, Any] | None = None) -> str:
    return f"{quantize_money(value, config):.2f}"


def parse_money_str(raw: str, config: dict[str, Any] | None = None) -> str:
    return money_str(parse_money(raw), config)
