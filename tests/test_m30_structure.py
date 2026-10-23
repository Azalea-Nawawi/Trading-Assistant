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


def structure(highs, lows):
    return calculate_m30_structure(flat_series(50, Timeframe.M30, highs=highs, lows=lows))


def test_higher_high_and_higher_low_is_uptrend():
    assert structure({15: 2005.0, 35: 2008.0}, {10: 1990.0, 30: 1995.0})["status"] == "UPTREND"


def test_lower_high_and_lower_low_is_downtrend():
    assert structure({15: 2008.0, 35: 2005.0}, {10: 1995.0, 30: 1990.0})["status"] == "DOWNTREND"


def test_mixed_swings_within_one_atr_is_sideways():
    # Higher high but lower low, both differences tiny versus ATR.
    result = structure({15: 2005.0, 35: 2005.2}, {10: 1995.0, 30: 1994.8})
    assert result["status"] == "SIDEWAYS"


def test_mixed_swings_beyond_one_atr_is_transition():
    result = structure({15: 2005.0, 35: 2030.0}, {10: 1995.0, 30: 1970.0})
    assert result["status"] == "TRANSITION"


def test_latest_swings_are_reported_newest_first():
    result = structure({15: 2005.0, 35: 2008.0}, {10: 1990.0, 30: 1995.0})
    assert (result["last_swing_high"], result["prev_swing_high"]) == (2008.0, 2005.0)
    assert (result["last_swing_low"], result["prev_swing_low"]) == (1995.0, 1990.0)
