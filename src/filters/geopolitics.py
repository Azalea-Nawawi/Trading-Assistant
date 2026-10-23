"""Simple keyword-based geopolitical risk filter.

This module implements the Version 1 geopolitical filter from Spesifikasi
Final v1.0 and the associated design decision: matching a fixed list of
high-risk keywords against supplied recent headlines. A match produces
RISK_OFF, no match produces CLEAR, and unavailable or malformed headline data
produces GEO_UNKNOWN, which must never be treated as CLEAR.

This is intentionally a lightweight complement to the economic news filter.
It performs no sentiment analysis and makes no network calls; the keyword list
can be expanded later as part of a documented logic change.
"""

from __future__ import annotations

from typing import Final, Literal, Sequence, TypedDict


RISK_KEYWORDS: Final[tuple[str, ...]] = (
    "war",
    "invasion",
    "attack",
    "missile",
    "strike",
    "sanctions",
    "conflict",
    "escalation",
    "middle east",
    "iran",
    "israel",
    "hezbollah",
    "hamas",
    "russia",
    "ukraine",
    "taiwan",
    "china military",
    "nuclear",
)

GeoStatus = Literal["CLEAR", "RISK_OFF", "GEO_UNKNOWN"]


class GeopoliticsResult(TypedDict):
    """Typed result returned by check_geopolitical_risk."""

    status: GeoStatus
    matched_keywords: list[str]
    reason: str


def _unknown_result(reason: str) -> GeopoliticsResult:
    """Build a GEO_UNKNOWN result without treating uncertainty as CLEAR."""

    return {
        "status": "GEO_UNKNOWN",
        "matched_keywords": [],
        "reason": reason,
    }


def check_geopolitical_risk(
    headlines: Sequence[str] | None,
) -> GeopoliticsResult:
    """Classify recent headlines with the Version 1 risk keyword filter.

    Args:
        headlines: Recent headline strings. None means the source is
            unavailable; an empty sequence is treated as available with no
            matching headlines.

    Returns:
        A mapping with RISK_OFF and the matched keywords when any keyword is
        found, CLEAR when none match, or GEO_UNKNOWN when the input is
        unavailable or malformed.

    Raises:
        None. Invalid headline data is represented by status="GEO_UNKNOWN".
    """

    if headlines is None:
        return _unknown_result("Geopolitical headline data is unavailable.")

    if not all(isinstance(headline, str) for headline in headlines):
        return _unknown_result("Geopolitical headline data contains non-text values.")

    normalized_headlines = [headline.casefold() for headline in headlines]

    # Matching is deliberately simple substring matching for the Version 1 filter.
    matched_keywords = [
        keyword
        for keyword in RISK_KEYWORDS
        if any(keyword.casefold() in headline for headline in normalized_headlines)
    ]

    if matched_keywords:
        return {
            "status": "RISK_OFF",
            "matched_keywords": matched_keywords,
            "reason": (
                "High-risk geopolitical keyword(s) detected: "
                + ", ".join(matched_keywords)
                + "."
            ),
        }

    return {
        "status": "CLEAR",
        "matched_keywords": [],
        "reason": "No configured high-risk geopolitical keyword was detected.",
    }


__all__ = [
    "GeoStatus",
    "GeopoliticsResult",
    "RISK_KEYWORDS",
    "check_geopolitical_risk",
]
