"""Integritas kalender event high-impact USD (D-050)."""

import csv
from datetime import date
from pathlib import Path

CALENDAR = Path(__file__).resolve().parent.parent / "data" / "calendar" / "usd_high_impact.csv"
EVENTS = {"FOMC", "NFP", "CPI", "PPI", "RETAIL_SALES", "PCE", "GDP", "ISM_MANUFACTURING", "ISM_SERVICES"}
TIMES = {"08:30", "10:00", "14:00"}


def rows():
    with open(CALENDAR, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_columns_and_closed_event_list():
    data = rows()
    assert data and set(data[0]) == {"date_et", "time_et", "event", "source"}
    assert {r["event"] for r in data} == EVENTS


def test_every_row_is_valid_and_sourced():
    for r in rows():
        date.fromisoformat(r["date_et"])
        assert r["time_et"] in TIMES
        assert r["source"].strip()


def test_sorted_without_duplicates_and_covers_period():
    data = [(r["date_et"], r["time_et"], r["event"]) for r in rows()]
    assert data == sorted(data)
    assert len(data) == len(set(data))
    assert data[0][0] <= "2023-11-01" and data[-1][0] >= "2026-12-01"


def test_fomc_releases_at_1400_and_data_at_0830_or_1000():
    for r in rows():
        if r["event"] == "FOMC":
            assert r["time_et"] == "14:00"
        elif r["event"].startswith("ISM"):
            assert r["time_et"] == "10:00"
        else:
            assert r["time_et"] == "08:30"
