"""Errors for the Texas TEC jurisdiction plugin."""

from __future__ import annotations


class SpecMissingError(Exception):
    """Raised when official TEC filing materials under ``spec/texas/`` are incomplete.

    ``missing`` enumerates the SPEC.md §5 checklist items that are still absent.
    """

    def __init__(self, missing: list[str]) -> None:
        self.missing: list[str] = list(missing)
        message = self.format_refusal(self.missing)
        super().__init__(message)

    @staticmethod
    def format_refusal(missing: list[str]) -> str:
        """Build a clear refusal message listing every missing checklist item."""
        if not missing:
            return "Texas TEC build refused: no missing items recorded."
        lines = [
            "Texas TEC filing generation is blocked until official TEC materials "
            "are present under spec/texas/.",
            "Missing items (SPEC.md §5):",
        ]
        for i, item in enumerate(missing, start=1):
            lines.append(f"  {i}. {item}")
        lines.append(
            "See spec/texas/REQUIRED_SPEC.md for exact filenames the human must drop."
        )
        return "\n".join(lines)
