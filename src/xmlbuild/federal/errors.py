"""Errors raised by the federal IRS 8872 XML builder / validator."""

from __future__ import annotations


class FederalXmlValidationError(Exception):
    """Raised when Form 8872 XML fails XSD validation or pre-emit checks."""

    def __init__(self, messages: list[str] | str) -> None:
        if isinstance(messages, str):
            messages = [messages]
        self.messages = list(messages)
        joined = "; ".join(self.messages) if self.messages else "validation failed"
        super().__init__(joined)
