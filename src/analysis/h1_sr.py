"""H1 support and resistance calculation from confirmed swing points.

This module implements the H1 Support & Resistance rules from Spesifikasi
Final v1.0: two-candle swing confirmation, a 60-candle lookback, the three
latest confirmed swing highs and lows, and USD 1.50 proximity clustering.

All input candles must already be closed and ordered from oldest to newest.
The latest candle close is used as the current price. Swing candidates are
limited to candles with two candles on both sides, so a swing is never used
before its two right-hand candles have closed (anti look-ahead).
"""

from __future__ import annotations

from statistics import fmean
from typing import Final, Literal, Sequence, TypedDict

from src.models import Candle, Timeframe


LOOKBACK_CANDLES: Final[int] = 60
SWING_RADIUS: Final[int] = 2
MAX_SWINGS_PER_SIDE: Final[int] = 3
ZONE_DISTANCE_USD: Final[float] = 1.50
MAX_ZONES_PER_SIDE: Final[int] = 3

Status = Literal["OK", "DATA_INVALID"]


class H1SRResult(TypedDict):
    """Typed result returned by calculate_h1_sr."""

    supports: list[float]
    resistances: list[float]
    nearest_support: float | None
    nearest_resistance: float | None
    distance_to_support: float | None
    distance_to_resistance: float | None
    status: Status


def _invalid_result() -> H1SRResult:
    """Build the standard result for invalid or insufficient candle data."""

    return {
        "supports": [],
        "resistances": [],
        "nearest_support": None,
        "nearest_resistance": None,
        "distance_to_support": None,
        "distance_to_resistance": None,
        "status": "DATA_INVALID",
    }


def _has_valid_input(candles: Sequence[Candle]) -> bool:
    """Return whether the input is a chronological, H1-only candle sequence."""

    if len(candles) < LOOKBACK_CANDLES:
        return False

    if not all(isinstance(candle, Candle) for candle in candles):
        return False

    if not all(candle.timeframe is Timeframe.H1 for candle in candles):
        return False

    return all(
        previous.open_time < current.open_time
        for previous, current in zip(candles, candles[1:])
    )


def _confirmed_swings(
    candles: Sequence[Candle],
) -> tuple[list[float], list[float]]:
    """Return the latest confirmed swing highs and lows from the lookback."""

    lookback = candles[-LOOKBACK_CANDLES:]
    swing_highs: list[float] = []
    swing_lows: list[float] = []

    # The two right-hand candles required by the definition make each point
    # anti-look-ahead safe.
    first_candidate = SWING_RADIUS
    last_candidate = len(lookback) - SWING_RADIUS
    for index in range(last_candidate - 1, first_candidate - 1, -1):
        candle = lookback[index]
        left = lookback[index - SWING_RADIUS : index]
        right = lookback[index + 1 : index + SWING_RADIUS + 1]

        if len(swing_highs) < MAX_SWINGS_PER_SIDE and all(
            candle.high > neighbour.high for neighbour in (*left, *right)
        ):
            swing_highs.append(candle.high)

        if len(swing_lows) < MAX_SWINGS_PER_SIDE and all(
            candle.low < neighbour.low for neighbour in (*left, *right)
        ):
            swing_lows.append(candle.low)

        if (
            len(swing_highs) == MAX_SWINGS_PER_SIDE
            and len(swing_lows) == MAX_SWINGS_PER_SIDE
        ):
            break

    return swing_highs, swing_lows


def _cluster_levels(levels: Sequence[float]) -> list[float]:
    """Group nearby levels and return the mean price of each zone."""

    if not levels:
        return []

    sorted_levels = sorted(levels)
    clusters: list[list[float]] = [[sorted_levels[0]]]

    # Adjacent sorted levels define a cluster; each resulting zone is its mean.
    for level in sorted_levels[1:]:
        current_cluster = clusters[-1]
        if level - current_cluster[-1] <= ZONE_DISTANCE_USD:
            current_cluster.append(level)
        else:
            clusters.append([level])

    return [fmean(cluster) for cluster in clusters]


def _nearest_zones(
    swing_highs: Sequence[float],
    swing_lows: Sequence[float],
    current_price: float,
) -> tuple[list[float], list[float]]:
    """Return up to three closest support and resistance zones."""

    support_levels = [level for level in swing_lows if level < current_price]
    resistance_levels = [level for level in swing_highs if level > current_price]

    supports = _cluster_levels(support_levels)
    resistances = _cluster_levels(resistance_levels)

    # Supports are closest from the high end; resistances are closest from the low end.
    return supports[-MAX_ZONES_PER_SIDE:], resistances[:MAX_ZONES_PER_SIDE]


def calculate_h1_sr(candles: Sequence[Candle]) -> H1SRResult:
    """Calculate H1 support and resistance from confirmed swing levels.

    Args:
        candles: At least 60 closed H1 Candle objects, ordered from oldest to
            newest. The close of the newest candle is treated as current price.

    Returns:
        A mapping containing up to three ascending support zones, up to three
        ascending resistance zones, the nearest zone and its non-negative
        distance on each side, plus an OK or DATA_INVALID status.

    Raises:
        None. Insufficient, non-H1, non-chronological, or otherwise invalid
        candle input returns status="DATA_INVALID".
    """

    if not _has_valid_input(candles):
        return _invalid_result()

    current_price = candles[-1].close
    swing_highs, swing_lows = _confirmed_swings(candles)
    supports, resistances = _nearest_zones(
        swing_highs=swing_highs,
        swing_lows=swing_lows,
        current_price=current_price,
    )

    nearest_support = supports[-1] if supports else None
    nearest_resistance = resistances[0] if resistances else None

    return {
        "supports": supports,
        "resistances": resistances,
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
        "distance_to_support": (
            current_price - nearest_support if nearest_support is not None else None
        ),
        "distance_to_resistance": (
            nearest_resistance - current_price
            if nearest_resistance is not None
            else None
        ),
        "status": "OK",
    }


__all__ = [
    "H1SRResult",
    "LOOKBACK_CANDLES",
    "MAX_SWINGS_PER_SIDE",
    "MAX_ZONES_PER_SIDE",
    "SWING_RADIUS",
    "ZONE_DISTANCE_USD",
    "calculate_h1_sr",
]
