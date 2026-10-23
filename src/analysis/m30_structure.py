"""M30 market-structure classification from confirmed swing points.

This module implements the M30 structure rules from Spesifikasi Final v1.0:
strict two-candle-left and two-candle-right swing confirmation, a 50-candle
M30 lookback, UPTREND and DOWNTREND swing-direction checks, SIDEWAYS
comparison against one ATR(14), and TRANSITION for all remaining structures.

All input candles must already be closed and ordered from oldest to newest.
The two right-hand candles are required before a swing can be considered, so
the calculation is anti look-ahead. ATR(14) uses the simple moving average of
the latest 14 True Range values.
"""

from __future__ import annotations

from statistics import fmean
from typing import Final, Literal, Sequence, TypedDict

from src.models import Candle, Timeframe


LOOKBACK_CANDLES: Final[int] = 50
SWING_RADIUS: Final[int] = 2
ATR_PERIOD: Final[int] = 14
ATR_MULTIPLIER: Final[float] = 1.0

StructureStatus = Literal[
    "UPTREND",
    "DOWNTREND",
    "SIDEWAYS",
    "TRANSITION",
    "DATA_INVALID",
]


class M30StructureResult(TypedDict):
    """Typed result returned by calculate_m30_structure."""

    status: StructureStatus
    last_swing_high: float | None
    prev_swing_high: float | None
    last_swing_low: float | None
    prev_swing_low: float | None
    atr: float | None
    reason: str


def _invalid_result(reason: str) -> M30StructureResult:
    """Build a DATA_INVALID result with a specific validation reason."""

    return {
        "status": "DATA_INVALID",
        "last_swing_high": None,
        "prev_swing_high": None,
        "last_swing_low": None,
        "prev_swing_low": None,
        "atr": None,
        "reason": reason,
    }


def _has_valid_input(candles: Sequence[Candle]) -> bool:
    """Return whether the input has enough chronological M30 candles."""

    if len(candles) < LOOKBACK_CANDLES:
        return False

    if not all(isinstance(candle, Candle) for candle in candles):
        return False

    if not all(candle.timeframe is Timeframe.M30 for candle in candles):
        return False

    return all(
        previous.open_time < current.open_time
        for previous, current in zip(candles, candles[1:])
    )


def _confirmed_swings(
    candles: Sequence[Candle],
) -> tuple[list[float], list[float]]:
    """Return latest confirmed swing highs and lows, newest first."""

    lookback = candles[-LOOKBACK_CANDLES:]
    swing_highs: list[float] = []
    swing_lows: list[float] = []

    # The last candidate is two candles before the end, enforcing confirmation.
    first_candidate = SWING_RADIUS
    last_candidate = len(lookback) - SWING_RADIUS
    for index in range(last_candidate - 1, first_candidate - 1, -1):
        candle = lookback[index]
        left = lookback[index - SWING_RADIUS : index]
        right = lookback[index + 1 : index + SWING_RADIUS + 1]

        if len(swing_highs) < 2 and all(
            candle.high > neighbour.high for neighbour in (*left, *right)
        ):
            swing_highs.append(candle.high)

        if len(swing_lows) < 2 and all(
            candle.low < neighbour.low for neighbour in (*left, *right)
        ):
            swing_lows.append(candle.low)

        if len(swing_highs) == 2 and len(swing_lows) == 2:
            break

    return swing_highs, swing_lows


def _true_range(previous: Candle, current: Candle) -> float:
    """Calculate one True Range value using the previous close."""

    # True Range includes gaps through the previous candle close.
    return max(
        current.high - current.low,
        abs(current.high - previous.close),
        abs(current.low - previous.close),
    )


def _atr_sma(candles: Sequence[Candle]) -> float | None:
    """Calculate ATR using the SMA of the latest ATR_PERIOD True Ranges."""

    if len(candles) < ATR_PERIOD + 1:
        return None

    true_ranges = [
        _true_range(previous, current)
        for previous, current in zip(candles, candles[1:])
    ]
    return fmean(true_ranges[-ATR_PERIOD:])


def _classify_structure(
    last_swing_high: float,
    prev_swing_high: float,
    last_swing_low: float,
    prev_swing_low: float,
    atr: float,
) -> tuple[Literal["UPTREND", "DOWNTREND", "SIDEWAYS", "TRANSITION"], str]:
    """Classify structure from the latest two swings and ATR."""

    high_rising = last_swing_high > prev_swing_high
    low_rising = last_swing_low > prev_swing_low
    high_falling = last_swing_high < prev_swing_high
    low_falling = last_swing_low < prev_swing_low

    if high_rising and low_rising:
        return "UPTREND", "The latest two swing highs and lows are both rising."

    if high_falling and low_falling:
        return "DOWNTREND", "The latest two swing highs and lows are both falling."

    high_difference = abs(last_swing_high - prev_swing_high)
    low_difference = abs(last_swing_low - prev_swing_low)
    sideways_limit = ATR_MULTIPLIER * atr

    # Sideways requires both swing differences to remain within one ATR.
    if high_difference <= sideways_limit and low_difference <= sideways_limit:
        return (
            "SIDEWAYS",
            "The latest swing-high and swing-low differences are within one ATR.",
        )

    return "TRANSITION", "Swing directions do not satisfy trend or sideways rules."


def calculate_m30_structure(candles: Sequence[Candle]) -> M30StructureResult:
    """Classify M30 market structure from confirmed swing points.

    Args:
        candles: At least 50 closed M30 Candle objects ordered from oldest to
            newest. Two right-hand candles are required before a swing is used.

    Returns:
        A mapping containing the structure status, the latest and previous
        swing levels, SMA-based ATR(14), and a human-readable reason.
        Insufficient or invalid data returns status="DATA_INVALID".

    Raises:
        None. Invalid candle input is represented by status="DATA_INVALID".
    """

    if not _has_valid_input(candles):
        return _invalid_result(
            "At least 50 chronological closed M30 candles are required."
        )

    lookback = candles[-LOOKBACK_CANDLES:]
    swing_highs, swing_lows = _confirmed_swings(lookback)
    atr = _atr_sma(lookback)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return _invalid_result(
            "At least two confirmed swing highs and two confirmed swing lows are required."
        )

    if atr is None:
        return _invalid_result("At least 15 candles are required to calculate ATR(14).")

    last_swing_high, prev_swing_high = swing_highs[0], swing_highs[1]
    last_swing_low, prev_swing_low = swing_lows[0], swing_lows[1]
    status, reason = _classify_structure(
        last_swing_high=last_swing_high,
        prev_swing_high=prev_swing_high,
        last_swing_low=last_swing_low,
        prev_swing_low=prev_swing_low,
        atr=atr,
    )

    return {
        "status": status,
        "last_swing_high": last_swing_high,
        "prev_swing_high": prev_swing_high,
        "last_swing_low": last_swing_low,
        "prev_swing_low": prev_swing_low,
        "atr": atr,
        "reason": reason,
    }


__all__ = [
    "ATR_MULTIPLIER",
    "ATR_PERIOD",
    "LOOKBACK_CANDLES",
    "M30StructureResult",
    "StructureStatus",
    "SWING_RADIUS",
    "calculate_m30_structure",
]
