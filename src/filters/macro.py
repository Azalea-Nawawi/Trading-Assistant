"""Fail-closed placeholder for the macroeconomic filter.

The final macro rules are not implemented yet. This placeholder exists so the
semi-auto runner can keep a stable filter contract required by Spesifikasi
Final v1.0. It returns MACRO_UNKNOWN rather than CLEAR, so the planner keeps
the recommendation at STANDBY until a real macro data source and rules are
implemented.
"""

from __future__ import annotations

from typing import Final, Literal, TypedDict


MACRO_UNKNOWN_STATUS: Final[str] = "MACRO_UNKNOWN"
MacroStatus = Literal["MACRO_UNKNOWN"]


class MacroFilterResult(TypedDict):
    """Typed result returned by check_macro_filter."""

    status: MacroStatus
    reason: str


def check_macro_filter() -> MacroFilterResult:
    """Return the fail-closed placeholder macro-filter result.

    Returns:
        A MACRO_UNKNOWN result indicating that macro filtering is not
        implemented yet. The planner must treat this as STANDBY.

    Raises:
        None.
    """

    return {
        "status": MACRO_UNKNOWN_STATUS,
        "reason": "Macro filter is not implemented yet; recommendation is fail-closed.",
    }


__all__ = [
    "MACRO_UNKNOWN_STATUS",
    "MacroFilterResult",
    "MacroStatus",
    "check_macro_filter",
]
