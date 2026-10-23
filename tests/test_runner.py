"""Runner evaluation chain (DEC-002: geopolitics and macro are not in v1.0)."""

from datetime import datetime, timezone

from src.assistant import runner
from src.models import Timeframe

from tests.test_planner import H1, M15_BULL, M30_UP, NEWS_CLEAR, m5_valid


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
    monkeypatch.setattr(runner, "calculate_h1_sr", lambda candles: H1)
    monkeypatch.setattr(runner, "calculate_m30_structure", lambda candles: m30)
    monkeypatch.setattr(runner, "calculate_m15_bias", lambda candles: M15_BULL)
    monkeypatch.setattr(runner, "calculate_m5_rejection", lambda candles, **kw: m5_valid())
    monkeypatch.setattr(runner, "check_news_filter", lambda now, path: NEWS_CLEAR)

    candles = {timeframe: [] for timeframe in Timeframe}
    now = datetime(2026, 10, 23, tzinfo=timezone.utc)

    assert runner._analyse_and_filter(candles, now, 2000.0)["status"] == "VALID"
    # The live price is passed through to the Entry Zone expiry check (DEC-006).
    assert runner._analyse_and_filter(candles, now, 2010.0)["status"] == "STANDBY"
