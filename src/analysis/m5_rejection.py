"""M5 rejection detection and trade-plan calculation.

This module implements the Rejection, location, Entry Zone, Stop Loss, and
Take Profit rules from Spesifikasi Final v1.0. It detects bullish or bearish
Pin Bars and Engulfing candles, filters candle size with ATR(14), validates
location near H1 zones or M30 swings, and checks structural risk against
1.2 times ATR before producing TP1 at 1.5R and TP2 at 2.5R.

Only closed M5 candles ordered from oldest to newest are accepted. The latest
candle is the rejection candidate and the prior candle is used for engulfing.
Confirmed M5 swings require two candles on the right, so the calculation is
anti look-ahead. No Entry Zone, Stop Loss, or Take Profit is forced when the
rejection, location, bias, or structural-risk requirements are not satisfied.
"""

from __future__ import annotations

from math import isfinite
from statistics import fmean
from typing import Final, Literal, Mapping, Sequence, TypedDict

from src.models import Candle, Timeframe


ATR_PERIOD: Final[int] = 14
SWING_RADIUS: Final[int] = 2
MIN_CANDLES: Final[int] = ATR_PERIOD + 1

PIN_BAR_WICK_RATIO: Final[float] = 0.60
MIN_REJECTION_RANGE_ATR: Final[float] = 0.80
LOCATION_TOLERANCE_ATR: Final[float] = 0.50
SL_ATR_MULTIPLIER: Final[float] = 1.20
SL_BUFFER_USD: Final[float] = 0.40
MIN_RISK_ATR_MULTIPLIER: Final[float] = 0.80
MAX_RISK_ATR_MULTIPLIER: Final[float] = 2.00
TP1_R_MULTIPLIER: Final[float] = 1.50
TP2_R_MULTIPLIER: Final[float] = 2.50

Bias = Literal["BULLISH", "BEARISH", "NEUTRAL"]
Direction = Literal["BULLISH", "BEARISH"]
RejectionType = Literal["PIN_BAR", "ENGULFING"]
PlanStatus = Literal["VALID", "STANDBY", "DATA_INVALID"]


class EntryZone(TypedDict):
    """Price interval proposed around a validated structural level."""

    low: float
    high: float


class M5RejectionResult(TypedDict):
    """Typed result returned by calculate_m5_rejection."""

    rejection_valid: bool
    rejection_type: RejectionType | None
    direction: Direction | None
    location_valid: bool
    entry_zone: EntryZone | None
    sl_structure: float | None
    sl_atr: float | None
    sl_suggested: float | None
    tp1: float | None
    tp2: float | None
    risk_struct: float | None
    risk_atr: float | None
    status: PlanStatus
    reason: str


def _empty_result(
    status: PlanStatus,
    reason: str,
    *,
    rejection_valid: bool = False,
    rejection_type: RejectionType | None = None,
    direction: Direction | None = None,
    location_valid: bool = False,
    entry_zone: EntryZone | None = None,
    risk_struct: float | None = None,
    risk_atr: float | None = None,
) -> M5RejectionResult:
    """Build a result while keeping incomplete plans free of forced prices."""

    return {
        "rejection_valid": rejection_valid,
        "rejection_type": rejection_type,
        "direction": direction,
        "location_valid": location_valid,
        "entry_zone": entry_zone,
        "sl_structure": None,
        "sl_atr": None,
        "sl_suggested": None,
        "tp1": None,
        "tp2": None,
        "risk_struct": risk_struct,
        "risk_atr": risk_atr,
        "status": status,
        "reason": reason,
    }


def _has_valid_input(candles: Sequence[Candle]) -> bool:
    """Return whether the input has enough chronological M5 candles."""

    if len(candles) < MIN_CANDLES:
        return False

    if not all(isinstance(candle, Candle) for candle in candles):
        return False

    if not all(candle.timeframe is Timeframe.M5 for candle in candles):
        return False

    return all(
        previous.open_time < current.open_time
        for previous, current in zip(candles, candles[1:])
    )


def _true_range(previous: Candle, current: Candle) -> float:
    """Calculate one True Range value from two closed candles."""

    return max(
        current.high - current.low,
        abs(current.high - previous.close),
        abs(current.low - previous.close),
    )


def _atr_sma(candles: Sequence[Candle]) -> float | None:
    """Calculate ATR(14) as the SMA of the latest True Range values."""

    if len(candles) < MIN_CANDLES:
        return None

    true_ranges = [
        _true_range(previous, current)
        for previous, current in zip(candles, candles[1:])
    ]
    return fmean(true_ranges[-ATR_PERIOD:])


def _detect_rejection_shape(
    previous: Candle,
    current: Candle,
) -> tuple[RejectionType | None, Direction | None, str]:
    """Detect the Pin Bar or Engulfing shape of the latest candle."""

    candle_range = current.high - current.low
    if candle_range <= 0:
        return None, None, "The latest candle has no measurable range."

    body_low = min(current.open, current.close)
    body_high = max(current.open, current.close)
    lower_wick = body_low - current.low
    upper_wick = current.high - body_high
    midpoint = current.low + (candle_range * 0.5)

    # Wick ratios and close-half checks define the two Pin Bar directions.
    bullish_pin = (
        lower_wick / candle_range >= PIN_BAR_WICK_RATIO
        and current.close >= midpoint
    )
    bearish_pin = (
        upper_wick / candle_range >= PIN_BAR_WICK_RATIO
        and current.close <= midpoint
    )

    previous_body_low = min(previous.open, previous.close)
    previous_body_high = max(previous.open, previous.close)
    current_body_engulfs = (
        body_low <= previous_body_low and body_high >= previous_body_high
    )

    # The current body must fully contain the previous body and close in its direction.
    bullish_engulfing = current_body_engulfs and current.close > current.open
    bearish_engulfing = current_body_engulfs and current.close < current.open

    if bullish_pin:
        return "PIN_BAR", "BULLISH", "Bullish Pin Bar shape detected."
    if bearish_pin:
        return "PIN_BAR", "BEARISH", "Bearish Pin Bar shape detected."
    if bullish_engulfing:
        return "ENGULFING", "BULLISH", "Bullish Engulfing shape detected."
    if bearish_engulfing:
        return "ENGULFING", "BEARISH", "Bearish Engulfing shape detected."

    return None, None, "The latest candle is neither a valid Pin Bar nor Engulfing."


def _confirmed_m5_swing(candles: Sequence[Candle], direction: Direction) -> float | None:
    """Return the latest confirmed M5 swing level for the trade direction."""

    if len(candles) < (SWING_RADIUS * 2) + 1:
        return None

    first_candidate = SWING_RADIUS
    last_candidate = len(candles) - SWING_RADIUS
    for index in range(last_candidate - 1, first_candidate - 1, -1):
        candle = candles[index]
        left = candles[index - SWING_RADIUS : index]
        right = candles[index + 1 : index + SWING_RADIUS + 1]

        if direction == "BULLISH" and all(
            candle.low < neighbour.low for neighbour in (*left, *right)
        ):
            return candle.low

        if direction == "BEARISH" and all(
            candle.high > neighbour.high for neighbour in (*left, *right)
        ):
            return candle.high

    return None


def _finite_levels(levels: Sequence[float]) -> list[float]:
    """Return finite structural levels only."""

    return [level for level in levels if isfinite(level)]


def _m30_location_levels(
    direction: Direction,
    last_swing_high: float | None,
    prev_swing_high: float | None,
    last_swing_low: float | None,
    prev_swing_low: float | None,
) -> list[float]:
    """Return M30 swing levels relevant for location validation."""

    if direction == "BULLISH":
        return _finite_levels(
            [level for level in (last_swing_low, prev_swing_low) if level is not None]
        )

    return _finite_levels(
        [level for level in (last_swing_high, prev_swing_high) if level is not None]
    )


def _entry_levels(
    bias: Bias,
    h1_supports: Sequence[float],
    h1_resistances: Sequence[float],
    last_swing_high: float | None,
    prev_swing_high: float | None,
    last_swing_low: float | None,
    prev_swing_low: float | None,
) -> list[float]:
    """Return H1 and M30 higher-low/lower-high candidates for the Entry Zone."""

    if bias == "BULLISH":
        levels = list(_finite_levels(h1_supports))
        if (
            last_swing_low is not None
            and prev_swing_low is not None
            and last_swing_low > prev_swing_low
        ):
            levels.append(last_swing_low)
        return levels

    if bias == "BEARISH":
        levels = list(_finite_levels(h1_resistances))
        if (
            last_swing_high is not None
            and prev_swing_high is not None
            and last_swing_high < prev_swing_high
        ):
            levels.append(last_swing_high)
        return levels

    return []


def _nearest_level(levels: Sequence[float], anchor: float) -> float | None:
    """Return the structural level nearest to an anchor price."""

    return min(levels, key=lambda level: abs(level - anchor)) if levels else None


def _level_near_anchor(
    levels: Sequence[float],
    anchor: float,
    tolerance: float,
) -> bool:
    """Return whether any structural level is within the location tolerance."""

    return any(abs(level - anchor) <= tolerance for level in levels)


def _structural_stop_level(
    direction: Direction,
    entry: float,
    entry_level: float,
    h1_levels: Sequence[float],
    m5_swing: float | None,
) -> float | None:
    """Select the closest valid structural level on the protective side."""

    candidates = list(h1_levels)
    if m5_swing is not None:
        candidates.append(m5_swing)
    candidates.append(entry_level)

    if direction == "BULLISH":
        valid_levels = [level for level in candidates if level <= entry]
        return max(valid_levels) if valid_levels else None

    valid_levels = [level for level in candidates if level >= entry]
    return min(valid_levels) if valid_levels else None


def _build_valid_plan(
    direction: Direction,
    entry_zone: EntryZone,
    structure_level: float,
    atr: float,
) -> tuple[float, float, float, float, float, float, str] | None:
    """Build SL, risk, and TP values when structural risk passes the ATR filter."""

    entry = (entry_zone["low"] + entry_zone["high"]) / 2.0
    if direction == "BULLISH":
        sl_structure = structure_level - SL_BUFFER_USD
    else:
        sl_structure = structure_level + SL_BUFFER_USD

    risk_struct = abs(entry - sl_structure)
    risk_atr = SL_ATR_MULTIPLIER * atr
    minimum_risk = MIN_RISK_ATR_MULTIPLIER * risk_atr
    maximum_risk = MAX_RISK_ATR_MULTIPLIER * risk_atr

    # Structural risk must stay between 0.8R_ATR and 2.0R_ATR.
    if not minimum_risk <= risk_struct <= maximum_risk:
        return None

    if direction == "BULLISH":
        sl_atr = entry - risk_atr
        tp1 = entry + (TP1_R_MULTIPLIER * risk_struct)
        tp2 = entry + (TP2_R_MULTIPLIER * risk_struct)
    else:
        sl_atr = entry + risk_atr
        tp1 = entry - (TP1_R_MULTIPLIER * risk_struct)
        tp2 = entry - (TP2_R_MULTIPLIER * risk_struct)

    return (
        sl_structure,
        sl_atr,
        sl_structure,
        tp1,
        tp2,
        risk_struct,
        risk_atr,
    )


def calculate_m5_rejection(
    candles: Sequence[Candle],
    *,
    bias: Bias,
    h1_supports: Sequence[float] = (),
    h1_resistances: Sequence[float] = (),
    m30_last_swing_high: float | None = None,
    m30_prev_swing_high: float | None = None,
    m30_last_swing_low: float | None = None,
    m30_prev_swing_low: float | None = None,
) -> M5RejectionResult:
    """Build an M5 rejection plan using H1/M30 structural context.

    Args:
        candles: At least 15 closed M5 Candle objects ordered from oldest to
            newest. The latest candle is tested for Pin Bar or Engulfing.
        bias: Directional bias, normally from the M15 EMA module.
        h1_supports: H1 support-zone prices.
        h1_resistances: H1 resistance-zone prices.
        m30_last_swing_high: Most recent confirmed M30 swing high.
        m30_prev_swing_high: Previous confirmed M30 swing high.
        m30_last_swing_low: Most recent confirmed M30 swing low.
        m30_prev_swing_low: Previous confirmed M30 swing low.

    Returns:
        A mapping with rejection classification, location validation, an Entry
        Zone, structural and ATR risk diagnostics, optional SL/TP prices, a
        VALID, STANDBY, or DATA_INVALID status, and a reason.

    Raises:
        None. Invalid candle or context data is represented by
        status="DATA_INVALID".
    """

    if bias not in ("BULLISH", "BEARISH", "NEUTRAL"):
        return _empty_result("DATA_INVALID", "Bias must be BULLISH, BEARISH, or NEUTRAL.")

    if not _has_valid_input(candles):
        return _empty_result(
            "DATA_INVALID",
            "At least 15 chronological closed M5 candles are required.",
        )

    atr = _atr_sma(candles)
    if atr is None or atr <= 0:
        return _empty_result("DATA_INVALID", "A positive ATR(14) is required.")

    previous, current = candles[-2], candles[-1]
    rejection_type, direction, shape_reason = _detect_rejection_shape(previous, current)

    if rejection_type is None or direction is None:
        return _empty_result("STANDBY", shape_reason)

    candle_range = current.high - current.low
    minimum_range = MIN_REJECTION_RANGE_ATR * atr
    if candle_range < minimum_range:
        return _empty_result(
            "STANDBY",
            f"{shape_reason} Candle range is below {MIN_REJECTION_RANGE_ATR:.2f} ATR.",
            rejection_type=rejection_type,
            direction=direction,
        )

    rejection_valid = True
    location_tolerance = LOCATION_TOLERANCE_ATR * atr
    location_anchor = current.low if direction == "BULLISH" else current.high
    h1_levels = (
        _finite_levels(h1_supports)
        if direction == "BULLISH"
        else _finite_levels(h1_resistances)
    )
    m30_levels = _m30_location_levels(
        direction=direction,
        last_swing_high=m30_last_swing_high,
        prev_swing_high=m30_prev_swing_high,
        last_swing_low=m30_last_swing_low,
        prev_swing_low=m30_prev_swing_low,
    )
    location_levels = [*h1_levels, *m30_levels]
    location_valid = _level_near_anchor(
        levels=location_levels,
        anchor=location_anchor,
        tolerance=location_tolerance,
    )

    entry_levels = _entry_levels(
        bias=bias,
        h1_supports=h1_supports,
        h1_resistances=h1_resistances,
        last_swing_high=m30_last_swing_high,
        prev_swing_high=m30_prev_swing_high,
        last_swing_low=m30_last_swing_low,
        prev_swing_low=m30_prev_swing_low,
    )
    entry_level = _nearest_level(entry_levels, location_anchor)
    entry_zone = (
        {
            "low": entry_level - location_tolerance,
            "high": entry_level + location_tolerance,
        }
        if entry_level is not None and location_valid and direction == bias
        else None
    )

    if not location_valid:
        return _empty_result(
            "STANDBY",
            f"{shape_reason} Rejection location is not near a relevant H1 or M30 level.",
            rejection_valid=rejection_valid,
            rejection_type=rejection_type,
            direction=direction,
            location_valid=False,
        )

    if direction != bias or entry_zone is None:
        return _empty_result(
            "STANDBY",
            f"{shape_reason} Rejection direction does not match the supplied bias or has no valid Entry Zone.",
            rejection_valid=rejection_valid,
            rejection_type=rejection_type,
            direction=direction,
            location_valid=True,
        )

    entry = (entry_zone["low"] + entry_zone["high"]) / 2.0
    m5_swing = _confirmed_m5_swing(candles, direction)
    h1_entry_levels = (
        _finite_levels(h1_supports)
        if direction == "BULLISH"
        else _finite_levels(h1_resistances)
    )
    structure_level = _structural_stop_level(
        direction=direction,
        entry=entry,
        entry_level=entry_level,
        h1_levels=h1_entry_levels,
        m5_swing=m5_swing,
    )

    if structure_level is None:
        return _empty_result(
            "STANDBY",
            f"{shape_reason} No clear M5 swing or H1 structural level exists for SL.",
            rejection_valid=rejection_valid,
            rejection_type=rejection_type,
            direction=direction,
            location_valid=True,
            entry_zone=entry_zone,
            risk_atr=SL_ATR_MULTIPLIER * atr,
        )

    plan = _build_valid_plan(
        direction=direction,
        entry_zone=entry_zone,
        structure_level=structure_level,
        atr=atr,
    )
    if plan is None:
        entry_price = (entry_zone["low"] + entry_zone["high"]) / 2.0
        risk_atr = SL_ATR_MULTIPLIER * atr
        if direction == "BULLISH":
            sl_structure = structure_level - SL_BUFFER_USD
        else:
            sl_structure = structure_level + SL_BUFFER_USD
        risk_struct = abs(entry_price - sl_structure)
        return _empty_result(
            "STANDBY",
            f"{shape_reason} Structural risk is outside the {MIN_RISK_ATR_MULTIPLIER:.2f}-{MAX_RISK_ATR_MULTIPLIER:.2f} ATR risk range.",
            rejection_valid=rejection_valid,
            rejection_type=rejection_type,
            direction=direction,
            location_valid=True,
            entry_zone=entry_zone,
            risk_struct=risk_struct,
            risk_atr=risk_atr,
        )

    (
        sl_structure,
        sl_atr,
        sl_suggested,
        tp1,
        tp2,
        risk_struct,
        risk_atr,
    ) = plan
    return {
        "rejection_valid": rejection_valid,
        "rejection_type": rejection_type,
        "direction": direction,
        "location_valid": True,
        "entry_zone": entry_zone,
        "sl_structure": sl_structure,
        "sl_atr": sl_atr,
        "sl_suggested": sl_suggested,
        "tp1": tp1,
        "tp2": tp2,
        "risk_struct": risk_struct,
        "risk_atr": risk_atr,
        "status": "VALID",
        "reason": f"{shape_reason} Location and structural-risk filters passed.",
    }


__all__ = [
    "ATR_PERIOD",
    "Bias",
    "Direction",
    "EntryZone",
    "LOCATION_TOLERANCE_ATR",
    "M5RejectionResult",
    "MIN_REJECTION_RANGE_ATR",
    "PlanStatus",
    "RejectionType",
    "SL_ATR_MULTIPLIER",
    "SL_BUFFER_USD",
    "TP1_R_MULTIPLIER",
    "TP2_R_MULTIPLIER",
    "calculate_m5_rejection",
]
