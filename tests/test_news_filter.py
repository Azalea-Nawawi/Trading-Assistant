"""News filter decisions (DEC-003: NEWS_UNKNOWN is never NEWS_CLEAR)."""

from datetime import datetime, timezone

import pytest

from src.filters.news import check_news_filter

HEADER = "date_et,time_et,event,source\n"


@pytest.fixture
def calendar(tmp_path):
    def write(rows):
        path = tmp_path / "calendar.csv"
        path.write_text(HEADER + "".join(f"{row},src\n" for row in rows), encoding="utf-8")
        return path

    return write


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_event_inside_45_minute_window_is_standby(calendar):
    # 08:30 ET on 2026-10-23 = 12:30 UTC (EDT).
    path = calendar(["2026-10-23,08:30,CPI", "2026-11-06,08:30,NFP"])
    assert check_news_filter(utc(2026, 10, 23, 12, 0), path)["status"] == "STANDBY"


def test_no_event_nearby_with_future_coverage_is_clear(calendar):
    path = calendar(["2026-10-23,08:30,CPI", "2026-11-06,08:30,NFP"])
    assert check_news_filter(utc(2026, 10, 23, 15, 0), path)["status"] == "CLEAR"


def test_time_beyond_calendar_coverage_is_news_unknown(calendar):
    path = calendar(["2026-10-23,08:30,CPI"])
    result = check_news_filter(utc(2026, 10, 24, 12, 0), path)
    assert result["status"] == "NEWS_UNKNOWN"


def test_missing_calendar_is_news_unknown(tmp_path):
    result = check_news_filter(utc(2026, 10, 23, 12, 0), tmp_path / "missing.csv")
    assert result["status"] == "NEWS_UNKNOWN"


def test_naive_time_is_news_unknown(calendar):
    path = calendar(["2026-11-06,08:30,NFP"])
    assert check_news_filter(datetime(2026, 10, 23, 12, 0), path)["status"] == "NEWS_UNKNOWN"
