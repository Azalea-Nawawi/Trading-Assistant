"""M15 short-term bias from standard EMA(21) and EMA(50).

This module implements the bias rules from Spesifikasi Final v1.0:
BULLISH requires the latest close above both EMAs with EMA(21) above EMA(50),
BEARISH requires the latest close below both EMAs with EMA(21) below EMA(50),
and all other valid combinations are NEUTRAL.

Only closed M15 candles ordered from oldest to newest are accepted. EMA is a
lagging indicator and is used here only as a directional filter, not as a
standalone trading signal. EMA values use the standard alpha formula and an
SMA seed for the initial period.
"""

from __future__ import annotations

from statistics import fmean
from typing import Final, Literal, Sequence, TypedDict

from src.models import Candle, Timeframe


EMA_FAST_PERIOD: Final[int] = 21
EMA_SLOW_PERIOD: Final[int] = 50
MIN_CANDLES: Final[int] = 60

BiasStatus = Literal["BULLISH", "BEARISH", "NEUTRAL", "DATA_INVALID"]


class M15BiasResult(TypedDict):
    """Typed result returned by calculate_m15_bias."""

    status: BiasStatus
    close: float | None
    ema21: float | None
    ema50: float | None
    reason: str


def _invalid_result(reason: str) -> M15BiasResult:
    """Build a DATA_INVALID result with a specific validation reason."""

    return {
        "status": "DATA_INVALID",
        "close": None,
        "ema21": None,
        "ema50": None,
        "reason": reason,
    }


def _has_valid_input(candles: Sequence[Candle]) -> bool:
    """Return whether the input has enough chronological M15 candles."""

    if len(candles) < MIN_CANDLES:
        return False

    if not all(isinstance(candle, Candle) for candle in candles):
        return False

    if not all(candle.timeframe is Timeframe.M15 for candle in candles):
        return False

    return all(
        previous.open_time < current.open_time
        for previous, current in zip(candles, candles[1:])
    )


def _calculate_ema(closes: Sequence[float], period: int) -> float | None:
    """Calculate an EMA with an SMA seed and the standard alpha formula."""

    if len(closes) < period:
        return None

    alpha = 2.0 / (period + 1.0)

    # Seeding with the first-period SMA avoids depending on a global initial value.
    ema = fmean(closes[:period])
    for close in closes[period:]:
        ema = (close * alpha) + (ema * (1.0 - alpha))

    return ema


def calculate_m15_bias(candles: Sequence[Candle]) -> M15BiasResult:
    """Determine short-term M15 directional bias from EMA(21) and EMA(50).

    Args:
        candles: At least 60 closed M15 Candle objects ordered from oldest to
            newest. The latest candle close is used as the evaluated close.

    Returns:
        A mapping containing BULLISH, BEARISH, or NEUTRAL for valid data, the
        latest close, both EMA values, and a reason. Insufficient or invalid
        data returns status="DATA_INVALID".

    Raises:
        None. Invalid candle input is represented by status="DATA_INVALID".
    """

    if not _has_valid_input(candles):
        return _invalid_result(
            "At least 60 chronological closed M15 candles are required."
        )

    closes = [candle.close for candle in candles]
    close = closes[-1]
    ema21 = _calculate_ema(closes, EMA_FAST_PERIOD)
    ema50 = _calculate_ema(closes, EMA_SLOW_PERIOD)

    if ema21 is None or ema50 is None:
        return _invalid_result(
            "Enough candles are required to calculate both EMA(21) and EMA(50)."
        )

    if close > ema21 and close > ema50 and ema21 > ema50:
        status: BiasStatus = "BULLISH"
        reason = "The latest close is above both EMAs and EMA(21) is above EMA(50)."
    elif close < ema21 and close < ema50 and ema21 < ema50:
        status = "BEARISH"
        reason = "The latest close is below both EMAs and EMA(21) is below EMA(50)."
    else:
        status = "NEUTRAL"
        reason = "The close and EMA alignment do not satisfy bullish or bearish rules."

    return {
        "status": status,
        "close": close,
        "ema21": ema21,
        "ema50": ema50,
        "reason": reason,
    }


__all__ = [
    "BiasStatus",
    "EMA_FAST_PERIOD",
    "EMA_SLOW_PERIOD",
    "M15BiasResult",
    "MIN_CANDLES",
    "calculate_m15_bias",
]
