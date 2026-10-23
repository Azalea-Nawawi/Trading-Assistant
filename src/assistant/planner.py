"""Multi-timeframe recommendation planner for Telegram output.

This module combines H1, M30, M15, and M5 analysis results with News,
Geopolitics, and Macro filter results according to Spesifikasi Final v1.0.
The mandatory decision order is: validate data, News, Geopolitics, aligned
M15/M30 bias, valid M5 rejection and location, then structural-risk validation
between 0.8x and 2.0x ATR. Only when every gate passes is the final status
VALID; otherwise the result is STANDBY, except incomplete or invalid module
results which produce DATA_INVALID.

The planner is pure: it receives already-computed mappings, performs no MT5
access and makes no network calls. The Macro result is accepted as a
placeholder mapping; any status other than CLEAR is handled fail-closed as
STANDBY. Every Telegram summary includes the warning that the final
transaction decision remains with the trader.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Final, Literal, Sequence, TypedDict


MIN_RISK_ATR_MULTIPLIER: Final[float] = 0.80
MAX_RISK_ATR_MULTIPLIER: Final[float] = 2.00
VALID_H1_STATUS: Final[str] = "OK"
VALID_MACRO_STATUS: Final[str] = "CLEAR"
TRADER_WARNING: Final[str] = "Keputusan transaksi tetap di tangan trader."

PlanDirection = Literal["BULLISH", "BEARISH"]
PlannerStatus = Literal["VALID", "STANDBY", "DATA_INVALID"]
Snapshot = dict[str, object]


class EntryZone(TypedDict):
    """Validated entry-zone interval."""

    low: float
    high: float


class TradePlan(TypedDict):
    """Executable price plan copied from a validated M5 result."""

    entry_zone: EntryZone
    sl_suggested: float
    sl_structure: float
    sl_atr: float
    tp1: float
    tp2: float
    direction: PlanDirection


class PlannerResult(TypedDict):
    """Typed result returned by build_trade_plan."""

    status: PlannerStatus
    reason: str
    h1: Snapshot
    m30: Snapshot
    m15: Snapshot
    m5: Snapshot
    filters: dict[str, Snapshot]
    plan: TradePlan | None
    summary_text: str


def _snapshot(value: object) -> Snapshot:
    """Copy a mapping for safe inclusion in the planner output."""

    return dict(value) if isinstance(value, Mapping) else {}


def _validate_result(
    name: str,
    value: object,
    allowed_statuses: set[str] | None = None,
) -> str | None:
    """Return a clear validation error for one upstream module result."""

    if not isinstance(value, Mapping):
        return f"{name} result is missing or is not a mapping."

    status = value.get("status")
    if not isinstance(status, str):
        return f"{name} result does not contain a valid status."

    if status == "DATA_INVALID":
        return f"{name} reported DATA_INVALID."

    if allowed_statuses is not None and status not in allowed_statuses:
        return f"{name} has unsupported status '{status}'."

    return None


def _as_float(value: object) -> float | None:
    """Return a finite float or None for a non-numeric value."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    number = float(value)
    return number if isfinite(number) else None


def _entry_zone(value: object) -> EntryZone | None:
    """Validate and normalize an entry-zone mapping."""

    if not isinstance(value, Mapping):
        return None

    low = _as_float(value.get("low"))
    high = _as_float(value.get("high"))
    if low is None or high is None or low > high:
        return None

    return {"low": low, "high": high}


def _base_result(
    status: PlannerStatus,
    reason: str,
    h1: object,
    m30: object,
    m15: object,
    m5: object,
    news: object,
    geopolitics: object,
    macro: object,
    plan: TradePlan | None = None,
) -> PlannerResult:
    """Build the common planner result and Telegram summary."""

    analysis_snapshots = {
        "h1": _snapshot(h1),
        "m30": _snapshot(m30),
        "m15": _snapshot(m15),
        "m5": _snapshot(m5),
    }
    filter_snapshots = {
        "news": _snapshot(news),
        "geopolitics": _snapshot(geopolitics),
        "macro": _snapshot(macro),
    }
    return {
        "status": status,
        "reason": reason,
        **analysis_snapshots,
        "filters": filter_snapshots,
        "plan": plan,
        "summary_text": _summary_text(
            status=status,
            reason=reason,
            plan=plan,
            filters=filter_snapshots,
        ),
    }


def _summary_text(
    status: PlannerStatus,
    reason: str,
    plan: TradePlan | None,
    filters: Mapping[str, Snapshot],
) -> str:
    """Render a concise Telegram-ready summary."""

    lines = [
        "📊 Trading Assistant",
        f"Status: {status}",
    ]

    if plan is not None:
        zone = plan["entry_zone"]
        lines.extend(
            [
                f"Arah: {plan['direction']}",
                f"Entry Zone: {zone['low']:.2f} - {zone['high']:.2f}",
                f"SL: {plan['sl_suggested']:.2f}",
                f"TP1: {plan['tp1']:.2f}",
                f"TP2: {plan['tp2']:.2f}",
            ]
        )
    else:
        lines.append("Plan: tidak tersedia.")

    filter_statuses = " | ".join(
        f"{name}: {snapshot.get('status', 'UNKNOWN')}"
        for name, snapshot in filters.items()
    )
    lines.extend(
        [
            f"Filter: {filter_statuses}",
            f"Alasan: {reason}",
            TRADER_WARNING,
        ]
    )
    return "\n".join(lines)


def _extract_trade_plan(m5: Mapping[str, object]) -> tuple[TradePlan | None, str | None]:
    """Validate the complete plan fields supplied by the M5 module."""

    if m5.get("rejection_valid") is not True:
        return None, "M5 rejection is not valid."
    if m5.get("location_valid") is not True:
        return None, "M5 rejection location is not valid."

    direction = m5.get("direction")
    if direction not in ("BULLISH", "BEARISH"):
        return None, "M5 direction is missing or invalid."

    entry_zone = _entry_zone(m5.get("entry_zone"))
    if entry_zone is None:
        return None, "M5 Entry Zone is missing or invalid."

    numeric_fields = (
        "sl_suggested",
        "sl_structure",
        "sl_atr",
        "tp1",
        "tp2",
        "risk_struct",
        "risk_atr",
    )
    numeric_values: dict[str, float] = {}
    for field in numeric_fields:
        number = _as_float(m5.get(field))
        if number is None:
            return None, f"M5 field '{field}' is missing or invalid."
        numeric_values[field] = number

    if numeric_values["risk_atr"] <= 0:
        return None, "M5 risk_atr must be positive."

    return (
        {
            "entry_zone": entry_zone,
            "sl_suggested": numeric_values["sl_suggested"],
            "sl_structure": numeric_values["sl_structure"],
            "sl_atr": numeric_values["sl_atr"],
            "tp1": numeric_values["tp1"],
            "tp2": numeric_values["tp2"],
            "direction": direction,
        },
        None,
    )


def build_trade_plan(
    h1: Mapping[str, object],
    m30: Mapping[str, object],
    m15: Mapping[str, object],
    m5: Mapping[str, object],
    news: Mapping[str, object],
    geopolitics: Mapping[str, object],
    macro: Mapping[str, object],
) -> PlannerResult:
    """Combine analysis and filters into one final trading recommendation.

    Args:
        h1: Result from the H1 support/resistance analysis.
        m30: Result from the M30 market-structure analysis.
        m15: Result from the M15 EMA-bias analysis.
        m5: Result from the M5 rejection and trade-plan analysis.
        news: Result from the economic high-impact news filter.
        geopolitics: Result from the geopolitical keyword filter.
        macro: Placeholder macro-filter result with at least a status field.

    Returns:
        A nested mapping containing the original analysis/filter snapshots, a
        final VALID, STANDBY, or DATA_INVALID status, an optional trade plan,
        the decision reason, and Telegram-ready summary text.

    Raises:
        None. Missing or malformed upstream results are represented as
        status="DATA_INVALID".
    """

    input_specs: Sequence[tuple[str, object, set[str] | None]] = (
        ("H1", h1, {VALID_H1_STATUS}),
        ("M30", m30, {"UPTREND", "DOWNTREND", "SIDEWAYS", "TRANSITION"}),
        ("M15", m15, {"BULLISH", "BEARISH", "NEUTRAL"}),
        ("M5", m5, {"VALID", "STANDBY"}),
        ("News", news, {"CLEAR", "STANDBY", "NEWS_UNKNOWN"}),
        ("Geopolitics", geopolitics, {"CLEAR", "RISK_OFF", "GEO_UNKNOWN"}),
        ("Macro", macro, None),
    )
    for name, value, allowed_statuses in input_specs:
        validation_error = _validate_result(name, value, allowed_statuses)
        if validation_error is not None:
            return _base_result(
                "DATA_INVALID",
                validation_error,
                h1,
                m30,
                m15,
                m5,
                news,
                geopolitics,
                macro,
            )

    news_status = str(news["status"])
    if news_status != "CLEAR":
        return _base_result(
            "STANDBY",
            f"News filter blocks entry with status {news_status}.",
            h1,
            m30,
            m15,
            m5,
            news,
            geopolitics,
            macro,
        )

    geopolitics_status = str(geopolitics["status"])
    if geopolitics_status != "CLEAR":
        return _base_result(
            "STANDBY",
            f"Geopolitical filter blocks entry with status {geopolitics_status}.",
            h1,
            m30,
            m15,
            m5,
            news,
            geopolitics,
            macro,
        )

    macro_status = str(macro["status"])
    if macro_status != VALID_MACRO_STATUS:
        return _base_result(
            "STANDBY",
            f"Macro filter is not CLEAR (status {macro_status}).",
            h1,
            m30,
            m15,
            m5,
            news,
            geopolitics,
            macro,
        )

    m15_status = str(m15["status"])
    m30_status = str(m30["status"])
    aligned_direction: PlanDirection | None = None
    if m15_status == "BULLISH" and m30_status == "UPTREND":
        aligned_direction = "BULLISH"
    elif m15_status == "BEARISH" and m30_status == "DOWNTREND":
        aligned_direction = "BEARISH"

    # M15/M30 alignment is a mandatory gate before evaluating the M5 setup.
    if aligned_direction is None:
        return _base_result(
            "STANDBY",
            "M15 bias and M30 structure are not aligned.",
            h1,
            m30,
            m15,
            m5,
            news,
            geopolitics,
            macro,
        )

    if not isinstance(m5, Mapping):
        return _base_result(
            "DATA_INVALID",
            "M5 result is not a mapping.",
            h1,
            m30,
            m15,
            m5,
            news,
            geopolitics,
            macro,
        )

    plan, plan_error = _extract_trade_plan(m5)
    if plan_error is not None or plan is None:
        status = "DATA_INVALID" if m5.get("status") == "VALID" else "STANDBY"
        return _base_result(
            status,
            plan_error or "M5 trade plan is incomplete.",
            h1,
            m30,
            m15,
            m5,
            news,
            geopolitics,
            macro,
        )

    if plan["direction"] != aligned_direction:
        return _base_result(
            "STANDBY",
            "M5 rejection direction does not match aligned M15/M30 direction.",
            h1,
            m30,
            m15,
            m5,
            news,
            geopolitics,
            macro,
        )

    risk_struct = _as_float(m5.get("risk_struct"))
    risk_atr = _as_float(m5.get("risk_atr"))
    if risk_struct is None or risk_atr is None or risk_atr <= 0:
        return _base_result(
            "DATA_INVALID",
            "M5 structural-risk data is incomplete.",
            h1,
            m30,
            m15,
            m5,
            news,
            geopolitics,
            macro,
        )

    minimum_risk = MIN_RISK_ATR_MULTIPLIER * risk_atr
    maximum_risk = MAX_RISK_ATR_MULTIPLIER * risk_atr

    # Re-check the final ATR risk gate before allowing VALID status.
    if not minimum_risk <= risk_struct <= maximum_risk:
        return _base_result(
            "STANDBY",
            "M5 structural risk is outside the 0.8x-2.0x ATR range.",
            h1,
            m30,
            m15,
            m5,
            news,
            geopolitics,
            macro,
        )

    return _base_result(
        "VALID",
        "All data, news, geopolitical, alignment, rejection, location, and ATR-risk gates passed.",
        h1,
        m30,
        m15,
        m5,
        news,
        geopolitics,
        macro,
        plan=plan,
    )


__all__ = [
    "EntryZone",
    "PlannerResult",
    "TradePlan",
    "build_trade_plan",
]
