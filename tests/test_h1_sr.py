"""H1 S/R zone algorithm (DEC-004): collect all swings -> merge <= 1.50 -> nearest 3."""

from src.analysis.h1_sr import calculate_h1_sr
from src.models import Timeframe

from tests._candles import flat_series


def test_older_swing_nearest_to_price_is_kept():
    # Oldest swing low (index 10) is closest to price; three newer ones are deeper.
    candles = flat_series(
        60, Timeframe.H1, lows={10: 1995.0, 20: 1980.0, 30: 1970.0, 40: 1960.0}
    )
    result = calculate_h1_sr(candles)
    assert result["supports"] == [1970.0, 1980.0, 1995.0]
    assert result["nearest_support"] == 1995.0


def test_levels_within_1_50_merge_before_nearest_selection():
    candles = flat_series(
        60,
        Timeframe.H1,
        highs={10: 2005.0, 20: 2006.0, 30: 2020.0, 40: 2030.0, 50: 2040.0},
    )
    result = calculate_h1_sr(candles)
    assert result["resistances"] == [2005.5, 2020.0, 2030.0]


def test_live_price_is_used_instead_of_last_h1_close():
    # Last H1 close is 2000.0; the live price has already moved to 2003.0.
    candles = flat_series(60, Timeframe.H1, highs={20: 2005.0}, lows={30: 1995.0})
    result = calculate_h1_sr(candles, current_price=2003.0)
    assert result["distance_to_resistance"] == 2.0
    assert result["distance_to_support"] == 8.0
