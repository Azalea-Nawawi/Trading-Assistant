"""M5 rejection shape, SL and plan rules (DEC-005, DEC-007)."""

from src.analysis.m5_rejection import _detect_rejection_shape

from tests._candles import candle


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
