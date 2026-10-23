"""M30 structure classification (CLAUDE.md: UPTREND/DOWNTREND/TRANSITION/SIDEWAYS/UNCLEAR)."""

from src.analysis.m30_structure import calculate_m30_structure
from src.models import Timeframe

from tests._candles import flat_series


def test_too_few_confirmed_swings_is_unclear_not_data_invalid():
    # One swing high and one swing low only: valid data, unreadable structure.
    candles = flat_series(50, Timeframe.M30, highs={20: 2010.0}, lows={30: 1990.0})
    result = calculate_m30_structure(candles)
    assert result["status"] == "UNCLEAR"


def test_insufficient_candles_is_still_data_invalid():
    candles = flat_series(49, Timeframe.M30)
    assert calculate_m30_structure(candles)["status"] == "DATA_INVALID"
