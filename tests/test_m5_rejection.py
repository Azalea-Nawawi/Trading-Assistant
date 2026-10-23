"""M5 rejection shape, SL and plan rules (DEC-005, DEC-007)."""

import pytest

from src.analysis.m5_rejection import _detect_rejection_shape, calculate_m5_rejection
from src.models import Timeframe

from tests._candles import candle, flat_series


def bullish_pin_setup(m5_swing_low):
    """20 M5 candles: one confirmed swing low at index 10, bullish Pin Bar last.

    The Pin Bar low (1997.0) sits on the H1 support 1997.5, which becomes the
    centre of the Entry Zone.
    """

    candles = flat_series(19, Timeframe.M5, half_range=1.0, lows={10: m5_swing_low})
    candles.append(candle(19, 2000.6, 2001.0, 1997.0, 2000.8))
    return calculate_m5_rejection(candles, bias="BULLISH", h1_supports=[1997.5])


def test_identical_bodies_are_not_engulfing():
    previous = candle(0, 2001.0, 2001.1, 1999.9, 2000.0)
    current = candle(1, 2000.0, 2001.1, 1999.9, 2001.0)
    assert _detect_rejection_shape(previous, current)[0] is None


def test_shared_body_edge_is_not_engulfing():
    previous = candle(0, 2001.0, 2001.1, 1999.9, 2000.0)
    current = candle(1, 2000.0, 2002.1, 1999.9, 2002.0)
    assert _detect_rejection_shape(previous, current)[0] is None


def test_strictly_larger_body_is_engulfing():
    previous = candle(0, 2001.0, 2001.1, 1999.9, 2000.0)
    current = candle(1, 1999.5, 2002.1, 1999.4, 2002.0)
    assert _detect_rejection_shape(previous, current)[:2] == ("ENGULFING", "BULLISH")


def test_sl_structure_lies_beyond_entry_zone_not_on_entry_level():
    result = bullish_pin_setup(m5_swing_low=1995.0)
    assert result["status"] == "VALID", result["reason"]
    assert result["entry_zone"]["low"] > 1995.0
    # M5 swing 1995.0 minus the 0.40 buffer, not H1 entry level 1997.5 minus buffer.
    assert result["sl_structure"] == pytest.approx(1994.6)


def test_structural_risk_above_1_5x_risk_atr_is_standby():
    # Swing 1993.0 -> risk 4.9 vs Risk_ATR ~3.09: 1.59x, inside the old 2.0x limit.
    result = bullish_pin_setup(m5_swing_low=1993.0)
    assert result["risk_struct"] > 1.5 * result["risk_atr"]
    assert result["status"] == "STANDBY"
    assert "1.5" in result["reason"]


def test_result_exposes_m5_atr_for_entry_zone_expiry():
    result = bullish_pin_setup(m5_swing_low=1995.0)
    # ATR(14) of the 14 candles before the Pin Bar: twelve TRs of 2.0, swing TRs 6.0 and 2.0.
    assert result["atr"] == pytest.approx(32.0 / 14.0)


def test_signal_candle_does_not_inflate_its_own_atr():
    candles = flat_series(19, Timeframe.M5, half_range=0.5)
    candles.append(candle(19, 2004.5, 2005.0, 1995.0, 2004.8))  # range 10.0 Pin Bar
    result = calculate_m5_rejection(candles, bias="BULLISH", h1_supports=[1995.0])
    assert result["atr"] == pytest.approx(1.0)
