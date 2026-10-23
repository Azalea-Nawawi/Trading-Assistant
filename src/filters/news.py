"""Fail-closed USD high-impact news filter.

This module checks data/calendar/usd_high_impact.csv against the
Spesifikasi Final v1.0 news rule: a high-impact USD event within plus or minus
45 minutes of the supplied current time produces STANDBY; otherwise the result
is CLEAR. Unreadable, missing, malformed, or unusable calendar data produces
NEWS_UNKNOWN and is never treated as CLEAR.

The source CSV stores date_et and time_et in America/New_York. Event timestamps
are converted to UTC, and every comparison and returned timestamp uses UTC.
The function accepts the current time explicitly so the calculation remains
deterministic and does not use hidden global state.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final, Literal, Sequence, TypedDict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_CALENDAR_PATH: Final[Path] = Path("data") / "calendar" / "usd_high_impact.csv"
NEWS_WINDOW_MINUTES: Final[float] = 45.0
UTC = timezone.utc
SOURCE_TIMEZONE_NAME: Final[str] = "America/New_York"
REQUIRED_COLUMNS: Final[frozenset[str]] = frozenset(
    {"date_et", "time_et", "event", "source"}
)

NewsStatus = Literal["CLEAR", "STANDBY", "NEWS_UNKNOWN"]


class NextEvent(TypedDict):
    """Upcoming or currently blocking calendar event."""

    name: str
    time_utc: str
    minutes_until: float | None


class NewsFilterResult(TypedDict):
    """Typed result returned by check_news_filter."""

    status: NewsStatus
    next_event: NextEvent | None
    reason: str


@dataclass(frozen=True)
class _CalendarEvent:
    """One validated calendar event normalized to UTC."""

    name: str
    time_utc: datetime


def _unknown_result(reason: str) -> NewsFilterResult:
    """Build a fail-closed NEWS_UNKNOWN result."""

    return {
        "status": "NEWS_UNKNOWN",
        "next_event": None,
        "reason": reason,
    }


def _parse_event_time(date_et: str, time_et: str, source_timezone: ZoneInfo) -> datetime:
    """Parse a source ET date/time and normalize it to UTC."""

    # The CSV's ET wall-clock time must be localized before conversion to UTC.
    local_time = datetime.strptime(
        f"{date_et.strip()} {time_et.strip()}",
        "%Y-%m-%d %H:%M",
    ).replace(tzinfo=source_timezone)
    return local_time.astimezone(UTC)


def _load_calendar(path: Path) -> list[_CalendarEvent]:
    """Read, validate, parse, and sort calendar events from a CSV file."""

    source_timezone = ZoneInfo(SOURCE_TIMEZONE_NAME)
    events: list[_CalendarEvent] = []

    # DictReader makes the required CSV fields explicit and preserves source rows.
    with path.open("r", encoding="utf-8", newline="") as calendar_file:
        reader = csv.DictReader(calendar_file)
        fieldnames = set(reader.fieldnames or ())
        if not REQUIRED_COLUMNS.issubset(fieldnames):
            raise ValueError("Calendar CSV is missing one or more required columns.")

        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"Calendar CSV row {row_number} has extra columns.")

            values = {key: (value or "").strip() for key, value in row.items()}
            if not any(values.values()):
                continue

            event_name = values["event"]
            if not event_name or not values["date_et"] or not values["time_et"]:
                raise ValueError(f"Calendar CSV row {row_number} has empty event data.")

            events.append(
                _CalendarEvent(
                    name=event_name,
                    time_utc=_parse_event_time(
                        date_et=values["date_et"],
                        time_et=values["time_et"],
                        source_timezone=source_timezone,
                    ),
                )
            )

    if not events:
        raise ValueError("Calendar CSV contains no usable events.")

    return sorted(events, key=lambda event: event.time_utc)


def _event_output(event: _CalendarEvent, now_utc: datetime) -> NextEvent:
    """Convert an internal event to the public output shape."""

    minutes_until = (event.time_utc - now_utc).total_seconds() / 60.0
    return {
        "name": event.name,
        "time_utc": event.time_utc.isoformat(),
        "minutes_until": minutes_until,
    }


def _next_future_event(
    events: Sequence[_CalendarEvent],
    now_utc: datetime,
) -> _CalendarEvent | None:
    """Return the first event at or after the current UTC time."""

    return next((event for event in events if event.time_utc >= now_utc), None)


def check_news_filter(
    now_utc: datetime,
    calendar_path: str | Path = DEFAULT_CALENDAR_PATH,
) -> NewsFilterResult:
    """Determine whether high-impact USD news permits an entry suggestion.

    Args:
        now_utc: Current timezone-aware time. It is normalized to UTC before
            comparing it with calendar events.
        calendar_path: Path to the USD high-impact CSV calendar. It defaults to
            data/calendar/usd_high_impact.csv.

    Returns:
        A mapping with CLEAR when no event is within plus or minus 45 minutes,
        STANDBY when an event is within that window, or NEWS_UNKNOWN when the
        calendar/time data cannot be safely read. The result includes the
        nearest blocking event or next future event when available.

    Raises:
        None. File, parsing, timezone, and invalid-time errors are converted
        into status="NEWS_UNKNOWN".
    """

    if now_utc.tzinfo is None or now_utc.utcoffset() is None:
        return _unknown_result("Current time must be timezone-aware UTC.")

    now_utc = now_utc.astimezone(UTC)

    try:
        events = _load_calendar(Path(calendar_path))
    except (
        OSError,
        TypeError,
        ValueError,
        csv.Error,
        ZoneInfoNotFoundError,
    ) as error:
        return _unknown_result(f"Unable to read or parse the news calendar: {error}")

    window = timedelta(minutes=NEWS_WINDOW_MINUTES)
    nearby_events = [
        event for event in events if abs(event.time_utc - now_utc) <= window
    ]

    # The closest event in the symmetric window is the event responsible for STANDBY.
    if nearby_events:
        blocking_event = min(
            nearby_events,
            key=lambda event: abs(event.time_utc - now_utc),
        )
        minutes_until = (
            blocking_event.time_utc - now_utc
        ).total_seconds() / 60.0
        return {
            "status": "STANDBY",
            "next_event": _event_output(blocking_event, now_utc),
            "reason": (
                f"High-impact USD event '{blocking_event.name}' is "
                f"{minutes_until:.1f} minutes from now, inside the plus or minus "
                f"{NEWS_WINDOW_MINUTES:.0f}-minute news window."
            ),
        }

    next_event = _next_future_event(events, now_utc)

    # Past the last listed event the calendar no longer covers now (DEC-003).
    if next_event is None:
        return _unknown_result(
            "News calendar has no future events; coverage has ended and must be updated."
        )

    return {
        "status": "CLEAR",
        "next_event": _event_output(next_event, now_utc) if next_event else None,
        "reason": (
            f"No high-impact USD event is within the plus or minus "
            f"{NEWS_WINDOW_MINUTES:.0f}-minute window in UTC."
        ),
    }


__all__ = [
    "DEFAULT_CALENDAR_PATH",
    "NEWS_WINDOW_MINUTES",
    "NewsFilterResult",
    "NewsStatus",
    "NextEvent",
    "check_news_filter",
]
