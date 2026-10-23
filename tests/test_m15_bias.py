"""M15 EMA bias (BULLISH: price > EMA21 > EMA50, BEARISH: price < EMA21 < EMA50)."""

from src.analysis.m15_bias import calculate_m15_bias
from src.models import Timeframe

from tests._candles import candle


def series(closes):
    return [
        candle(index, close, close + 0.5, close - 0.5, close, Timeframe.M15)
        for index, close in enumerate(closes)
    ]


def test_rising_market_is_bullish():
    assert calculate_m15_bias(series([2000.0 + i for i in range(300)]))["status"] == "BULLISH"


def test_falling_market_is_bearish():
    assert calculate_m15_bias(series([2300.0 - i for i in range(300)]))["status"] == "BEARISH"


def test_flat_market_is_neutral():
    assert calculate_m15_bias(series([2000.0] * 300))["status"] == "NEUTRAL"


def test_price_back_below_ema21_in_uptrend_is_neutral():
    closes = [2000.0 + i for i in range(299)] + [2280.0]  # drop under EMA21, above EMA50
    result = calculate_m15_bias(series(closes))
    assert result["ema50"] < result["close"] < result["ema21"]
    assert result["status"] == "NEUTRAL"
