"""Planner gate order and decision rules (Spesifikasi v1.0, DEC-002/003/006/007)."""

from src.assistant import planner
from src.assistant.planner import build_suggestion


H1 = {"status": "OK", "supports": [2000.0], "resistances": [2010.0]}
M30_UP = {"status": "UPTREND"}
M15_BULL = {"status": "BULLISH"}
NEWS_CLEAR = {"status": "CLEAR"}


def m5_valid(**overrides):
    result = {
        "status": "VALID",
        "rejection_valid": True,
        "location_valid": True,
        "direction": "BULLISH",
        "entry_zone": {"low": 1999.0, "high": 2001.0},
        "sl_structure": 1998.0,
        "sl_atr": 1998.0,
        "sl_suggested": 1998.0,
        "tp1": 2003.0,
        "tp2": 2005.0,
        "risk_struct": 2.0,
        "risk_atr": 2.0,
        "atr": 2.0,
    }
    result.update(overrides)
    return result


def suggest(**overrides):
    kwargs = {
        "h1": H1,
        "m30": M30_UP,
        "m15": M15_BULL,
        "m5": m5_valid(),
        "news": NEWS_CLEAR,
        "current_price": 2000.0,
    }
    kwargs.update(overrides)
    return build_suggestion(**kwargs)


def test_all_gates_pass_without_geopolitics_or_macro():
    result = suggest()
    assert result["status"] == "VALID", result["reason"]


def test_filters_snapshot_contains_only_news():
    assert set(suggest()["filters"]) == {"news"}


def test_news_unknown_returns_standby():
    result = suggest(news={"status": "NEWS_UNKNOWN"})
    assert result["status"] == "STANDBY"
    assert "News" in result["reason"]


def test_planner_has_no_geopolitics_or_macro_gate():
    assert not hasattr(planner, "VALID_MACRO_STATUS")


def test_structural_risk_above_1_5x_risk_atr_is_standby():
    result = suggest(m5=m5_valid(risk_struct=3.5, risk_atr=2.0))
    assert result["status"] == "STANDBY"


def test_structural_risk_exactly_1_5x_risk_atr_passes():
    result = suggest(m5=m5_valid(risk_struct=3.0, risk_atr=2.0))
    assert result["status"] == "VALID", result["reason"]


def test_small_structural_risk_has_no_lower_bound():
    result = suggest(m5=m5_valid(risk_struct=1.0, risk_atr=2.0))
    assert result["status"] == "VALID", result["reason"]


# --- DEC-006: Entry Zone 1999-2001, ATR M5 2.0 -> expiry beyond 1.0 x ATR from the zone edge.


def test_price_more_than_1_atr_above_zone_is_standby():
    result = suggest(current_price=2003.5)
    assert result["status"] == "STANDBY"
    assert "meninggalkan Entry Zone" in result["reason"]
    assert result["plan"] is None


def test_price_more_than_1_atr_below_zone_is_standby():
    result = suggest(current_price=1996.5)
    assert result["status"] == "STANDBY"
    assert "meninggalkan Entry Zone" in result["reason"]


def test_price_exactly_1_atr_from_zone_is_still_valid():
    result = suggest(current_price=2003.0)
    assert result["status"] == "VALID", result["reason"]


def test_missing_current_price_is_data_invalid():
    result = suggest(current_price=None)
    assert result["status"] == "DATA_INVALID"


def test_missing_m5_atr_is_data_invalid():
    m5 = m5_valid()
    del m5["atr"]
    assert suggest(m5=m5)["status"] == "DATA_INVALID"


def test_m30_unclear_is_standby_not_data_invalid():
    result = suggest(m30={"status": "UNCLEAR"})
    assert result["status"] == "STANDBY"
