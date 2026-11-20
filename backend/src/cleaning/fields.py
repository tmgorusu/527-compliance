"""Field-level cleaning: state, ZIP, whitespace, XML-safe, ALL CAPS, dates, typos."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

# USPS state codes + common full-name aliases (uppercase keys).
_STATE_NAME_TO_CODE: dict[str, str] = {
    "ALABAMA": "AL",
    "ALASKA": "AK",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "HAWAII": "HI",
    "IDAHO": "ID",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSISSIPPI": "MS",
    "MISSOURI": "MO",
    "MONTANA": "MT",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM",
    "NEW YORK": "NY",
    "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VERMONT": "VT",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI",
    "WYOMING": "WY",
}

_VALID_STATE_CODES = set(_STATE_NAME_TO_CODE.values()) | {"AA", "AE", "AP", "AS", "GU", "MP", "PR", "VI"}

# Invalid XML 1.0 control characters (keep TAB/LF/CR out of text we normalize away anyway).
_XML_ILLEGAL = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

# "VA (Virginia)" / "OK (Oklahoma)" / truncated "WI (Wisconsin"
_STATE_CODE_PAREN = re.compile(
    r"^\s*([A-Za-z]{2})\s*(?:\([^)]*\)?)?\s*$"
)

# Known truncated / typo city forms seen in client extracts — FLAG only, never auto-fix.
_SUSPECT_CITY_EXACT = {
    "FREDERICKSBRG",  # Fredericksburg
    "VIRGINIA BEACJ",  # Virginia Beach
    "VIRGINIA BEAC",
}

_SUSPECT_CITY_SUFFIX = re.compile(
    r"(BRG|BEACJ|BEAC[^H]|VILL$|BUR$|SPRG|HGTS)$"
)


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00a0", " ")).strip()


def xml_safe(value: str) -> str:
    """Strip characters illegal in XML 1.0 text nodes."""
    return _XML_ILLEGAL.sub("", value)


def all_caps_text(value: str) -> str:
    """ALL CAPS for filing text fields (not headers, not emails)."""
    return xml_safe(normalize_whitespace(value)).upper()


def normalize_state(raw: str) -> str:
    """
    Normalize state to 2-letter code.

    Accepts ``VA``, ``VA (Virginia)``, or full name ``Virginia``.
    """
    text = normalize_whitespace(raw)
    if not text:
        raise ValueError("empty state")
    m = _STATE_CODE_PAREN.match(text)
    if m:
        code = m.group(1).upper()
        if code in _VALID_STATE_CODES:
            return code
    upper = text.upper()
    if upper in _VALID_STATE_CODES:
        return upper
    if upper in _STATE_NAME_TO_CODE:
        return _STATE_NAME_TO_CODE[upper]
    # "Virginia" inside bare text without paren form already handled; try stripping.
    raise ValueError(f"unrecognized state: {raw!r}")


def normalize_zip5(raw: str) -> str:
    """Zero-pad numeric ZIP to 5 digits. Reject non-digit payloads after cleaning."""
    text = normalize_whitespace(raw)
    if not text:
        raise ValueError("empty zip5")
    # Excel may emit 23233.0
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    digits = re.sub(r"\D", "", text)
    if not digits:
        raise ValueError(f"invalid zip5: {raw!r}")
    if len(digits) > 5:
        # Sometimes ZIP+4 smashed together — take first 5 for zip5
        digits = digits[:5]
    return digits.zfill(5)


def normalize_zip4(raw: str | None) -> Optional[str]:
    if raw is None:
        return None
    text = normalize_whitespace(str(raw))
    if text == "":
        return None
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    digits = re.sub(r"\D", "", text)
    if not digits:
        raise ValueError(f"invalid zip4: {raw!r}")
    if len(digits) > 4:
        digits = digits[-4:]
    return digits.zfill(4)


_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%Y/%m/%d",
    "%m-%d-%Y",
    "%Y%m%d",
)


def normalize_date(raw: str) -> str:
    """Normalize dates to YYYY-MM-DD."""
    text = normalize_whitespace(raw)
    if not text:
        raise ValueError("empty date")
    # Already ISO with optional time
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        date.fromisoformat(text)  # validate
        return text
    if "T" in text:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date: {raw!r}")


def suspected_city_typo(city: str) -> str | None:
    """
    Return a reason string if the city looks truncated/misspelled.
    Does NOT correct the value — caller should FLAG only.
    """
    c = all_caps_text(city)
    if not c:
        return None
    if c in _SUSPECT_CITY_EXACT:
        return f"suspected city typo/truncation: {c}"
    if _SUSPECT_CITY_SUFFIX.search(c):
        return f"suspected city truncation pattern: {c}"
    # Field max is 22; at-limit cities may be truncated from longer names.
    if len(c) >= 22:
        return f"city at/over max length (possible truncation): {c}"
    return None


def suspected_name_truncation(name: str, max_len: int = 50) -> str | None:
    n = all_caps_text(name)
    if len(n) >= max_len:
        return f"name at max length (possible truncation): {n}"
    # Ends with very short fragment after space (e.g. "... AND SU")
    parts = n.split()
    if len(parts) >= 2 and len(parts[-1]) <= 2 and parts[-1] not in {"JR", "SR", "II", "IV", "PC", "LP", "CO"}:
        return f"suspected truncated name ending: {n}"
    return None


VALID_EMPLOYER_PLACEHOLDERS = frozenset({"BEST EFFORTS MADE", "N/A"})
VALID_OCCUPATION_PLACEHOLDERS = frozenset({"BEST EFFORTS MADE", "N/A"})
