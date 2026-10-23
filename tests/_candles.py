"""Candle builders shared by analysis tests."""

from datetime import datetime, timedelta, timezone

from src.models import Candle, Timeframe

START = datetime(2026, 10, 23, 8, 0, tzinfo=timezone.utc)


def candle(index, open_, high, low, close, timeframe=Timeframe.M5):
    return Candle(
        symbol="XAUUSDm",
        timeframe=timeframe,
        open_time=START + timedelta(seconds=timeframe.seconds * index),
        open=open_,
        high=high,
        low=low,
        close=close,
    )


def flat_series(count, timeframe, price=2000.0, half_range=0.5, lows=None, highs=None):
    """Flat candles around ``price``; ``lows``/``highs`` map index -> spike level."""

    lows, highs = lows or {}, highs or {}
    return [
        candle(
            index,
            price,
            highs.get(index, price + half_range),
            lows.get(index, price - half_range),
            price,
            timeframe,
        )
        for index in range(count)
    ]
