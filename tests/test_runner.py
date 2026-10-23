"""Runner evaluation chain (DEC-002: geopolitics and macro are not in v1.0)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.assistant import runner
from src.models import Timeframe

from tests._candles import flat_series
from tests.test_planner import H1, M15_BULL, M30_UP, NEWS_CLEAR, m5_valid


def test_runner_fetches_enough_m5_candles_for_analysis():
    from src.analysis.m5_rejection import MIN_CANDLES

    assert runner.CANDLE_COUNTS[Timeframe.M5] >= MIN_CANDLES


def test_runner_does_not_import_inactive_filters():
    assert not hasattr(runner, "check_geopolitical_risk")
    assert not hasattr(runner, "check_macro_filter")


def test_analysis_cycle_reaches_valid_with_only_news_filter(monkeypatch):
    m30 = {
        **M30_UP,
        "last_swing_high": None,
        "prev_swing_high": None,
        "last_swing_low": None,
        "prev_swing_low": None,
    }
    h1_prices = []
    monkeypatch.setattr(
        runner,
        "calculate_h1_sr",
        lambda candles, current_price: h1_prices.append(current_price) or H1,
    )
    monkeypatch.setattr(runner, "calculate_m30_structure", lambda candles: m30)
    monkeypatch.setattr(runner, "calculate_m15_bias", lambda candles: M15_BULL)
    monkeypatch.setattr(runner, "calculate_m5_rejection", lambda candles, **kw: m5_valid())
    monkeypatch.setattr(runner, "check_news_filter", lambda now, path: NEWS_CLEAR)

    candles = {timeframe: [] for timeframe in Timeframe}
    now = datetime(2026, 10, 23, tzinfo=timezone.utc)

    assert runner._analyse_and_filter(candles, now, 2000.0)["status"] == "VALID"
    # The live price is passed through to the Entry Zone expiry check (DEC-006).
    assert runner._analyse_and_filter(candles, now, 2010.0)["status"] == "STANDBY"
    # H1 zones are split around the live price, not the last H1 close (BUG-011).
    assert h1_prices == [2000.0, 2010.0]


# --- Step 1 data validation: stale candles (DEC-009) ---------------------------------

def fresh_candles(now):
    """Per timeframe, a series whose newest candle closed within the last slot."""

    result = {}
    for timeframe in (Timeframe.H1, Timeframe.M30, Timeframe.M15, Timeframe.M5):
        series = flat_series(3, timeframe)
        shift = now - (series[-1].open_time + timedelta(seconds=timeframe.seconds))
        result[timeframe] = flat_series(3, timeframe, start_shift=shift)
    return result


def test_fresh_candles_pass_staleness_check():
    now = datetime(2026, 10, 23, 10, 3, tzinfo=timezone.utc)
    assert runner._stale_data_reason(fresh_candles(now), now) is None


def test_stale_candles_are_reported():
    now = datetime(2026, 10, 23, 10, 3, tzinfo=timezone.utc)
    candles = fresh_candles(now - timedelta(hours=60))  # e.g. weekend, feed frozen
    reason = runner._stale_data_reason(candles, now)
    assert reason is not None and "stale" in reason


def test_missing_candles_are_reported():
    now = datetime(2026, 10, 23, 10, 3, tzinfo=timezone.utc)
    candles = fresh_candles(now)
    candles[Timeframe.M5] = []
    assert runner._stale_data_reason(candles, now) is not None


def test_run_once_returns_data_invalid_on_stale_candles(monkeypatch):
    stale = fresh_candles(datetime(2026, 10, 1, tzinfo=timezone.utc))

    class StaleBroker:
        def connect(self):
            pass

        def disconnect(self):
            pass

        def candles(self, timeframe, count):
            return stale[timeframe]

        def tick(self):
            return SimpleNamespace(bid=2000.0)

    monkeypatch.setattr(runner, "_load_broker", lambda symbol: StaleBroker())
    result = runner.run_once("XAUUSDm", emit=False)
    assert result["status"] == "DATA_INVALID"
    assert "stale" in result["reason"]


def test_runner_fetches_enough_m15_candles_for_converged_ema():
    from src.analysis.m15_bias import MIN_CANDLES

    assert runner.CANDLE_COUNTS[Timeframe.M15] >= MIN_CANDLES
