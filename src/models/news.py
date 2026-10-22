"""News filter result (Semi-Auto Spec #1 F1, D-050, D-069).

Shared model: ``data`` produces it, ``core`` decides on it and the notifier
can show it, so it lives in ``models`` like ``Advice``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ._validation import require_enum, require_finite, require_text, require_utc


class NewsState(str, Enum):
    """CLEAR = no listed event within the window; NEWS = at least one (STANDBY);
    NO_CALENDAR = the date is outside the calendar coverage (fail-closed, STANDBY)."""

    CLEAR = "CLEAR"
    NEWS = "NEWS"
    NO_CALENDAR = "NO_CALENDAR"


@dataclass(frozen=True)
class NewsStatus:
    """F1 result for one candle close. ``events`` are the names of the nearest
    event time (several events can share one release time), ``event_time`` that
    time in UTC and ``minutes`` its signed distance (positive = still to come).
    All three are empty when the calendar has no event to report."""

    state: NewsState
    events: tuple[str, ...] = field(default_factory=tuple)
    event_time: datetime | None = None
    minutes: float | None = None

    def __post_init__(self) -> None:
        require_enum("state", self.state, NewsState)
        if not isinstance(self.events, tuple):
            raise ValueError("events must be a tuple")
        for name in self.events:
            require_text("event", name)
        nearest = (bool(self.events), self.event_time is not None, self.minutes is not None)
        if any(nearest) and not all(nearest):
            raise ValueError("events, event_time and minutes are set together")
        if self.event_time is not None:
            require_utc("event_time", self.event_time)
            require_finite("minutes", self.minutes)
        if self.state is NewsState.NEWS and not self.events:
            raise ValueError("NEWS needs the event that blocks")


@dataclass(frozen=True)
class ScheduledEvent:
    """One release of the news calendar (several events can share it), for the
    RENCANA message (section 5); ``time`` in UTC."""

    time: datetime
    events: tuple[str, ...]

    def __post_init__(self) -> None:
        require_utc("time", self.time)
        if not isinstance(self.events, tuple) or not self.events:
            raise ValueError("events must be a non-empty tuple")
        for name in self.events:
            require_text("event", name)
