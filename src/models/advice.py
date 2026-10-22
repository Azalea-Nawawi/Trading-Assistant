"""Semi-Auto advice model (Semi-Auto Spec #1, D-069).

An Advice is a suggestion, never an order: it carries no lot size and is
not passed to ``execution``. ``Signal`` (one TP) stays unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ._validation import (
    require_enum,
    require_finite,
    require_non_negative,
    require_positive,
    require_protective_sides,
    require_text,
    require_utc,
)
from .enums import Bias, Direction, Session, Trend
from .news import NewsState, NewsStatus, ScheduledEvent


@dataclass(frozen=True)
class Advice:
    """One SINYAL of section 5: A6-A11 values for a closed M5 rejection candle.

    ``time`` is the open time (UTC) of the rejection candle; ``entry_ref`` is
    its close (E, A8). ``risk`` = min(``risk_struct``, ``risk_atr``) (A9);
    ``tp1``/``tp2`` = E +/- 1,5R / 2,5R (A10). ``opposite_level`` is the next
    H1 level against the trade (None when there is none) and
    ``opposite_distance_r`` its distance from E in R; ``low_room`` flags a
    level closer than the configured R (K12). ``cost_r`` = (spread + slippage)
    / risk (K14); every ``rr_net_*`` = target in R minus ``cost_r``.
    """

    time: datetime
    symbol: str
    direction: Direction
    entry_ref: float
    zone_low: float
    zone_high: float
    zone_level: float
    sl: float
    tp1: float
    tp2: float
    risk: float
    risk_struct: float
    risk_atr: float
    opposite_level: float | None
    opposite_distance_r: float | None
    low_room: bool
    cost_r: float
    rr_net_tp1: float
    rr_net_tp2: float
    rr_net_opposite: float | None
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        require_utc("time", self.time)
        require_text("symbol", self.symbol)
        require_enum("direction", self.direction, Direction)
        for name in ("entry_ref", "zone_low", "zone_high", "zone_level", "risk"):
            require_positive(name, getattr(self, name))
        for name in ("risk_struct", "risk_atr", "cost_r", "rr_net_tp1", "rr_net_tp2"):
            require_finite(name, getattr(self, name))
        require_non_negative("cost_r", self.cost_r)
        if not self.zone_low <= self.zone_level <= self.zone_high:
            raise ValueError(f"zone_level {self.zone_level} must lie in [{self.zone_low}, {self.zone_high}]")
        require_protective_sides(self.direction, self.entry_ref, self.sl, self.tp1)
        require_protective_sides(self.direction, self.entry_ref, self.sl, self.tp2)
        beyond = self.tp2 > self.tp1 if self.direction is Direction.BUY else self.tp2 < self.tp1
        if not beyond:
            raise ValueError(f"tp2 {self.tp2} must be beyond tp1 {self.tp1}")
        opposite = (self.opposite_level, self.opposite_distance_r, self.rr_net_opposite)
        if any(value is None for value in opposite) and any(value is not None for value in opposite):
            raise ValueError("opposite_level, opposite_distance_r and rr_net_opposite are set together")
        if self.opposite_level is not None:
            require_positive("opposite_level", self.opposite_level)
            require_non_negative("opposite_distance_r", self.opposite_distance_r)
            require_finite("rr_net_opposite", self.rr_net_opposite)
        if not isinstance(self.low_room, bool):
            raise ValueError("low_room must be a bool")
        if self.low_room and self.opposite_level is None:
            raise ValueError("low_room needs an opposite_level")
        if not isinstance(self.reason_codes, tuple):
            raise ValueError("reason_codes must be a tuple")
        for code in self.reason_codes:
            require_text("reason code", code)


@dataclass(frozen=True)
class AdviceContext:
    """Market context stored with an Advice (journal v3): the three biases (A2,
    A3, A4), the F3 session, the F1 news state and the spread in points at the
    time (None when not read). No account data."""

    bias_h1: Bias
    bias_m30: Trend
    bias_m15: Bias
    session: Session
    news_state: NewsState
    spread_points: float | None = None

    def __post_init__(self) -> None:
        require_enum("bias_h1", self.bias_h1, Bias)
        require_enum("bias_m30", self.bias_m30, Trend)
        require_enum("bias_m15", self.bias_m15, Bias)
        require_enum("session", self.session, Session)
        require_enum("news_state", self.news_state, NewsState)
        if self.spread_points is not None:
            require_non_negative("spread_points", self.spread_points)


@dataclass(frozen=True)
class AdvicePlan:
    """RENCANA (section 5): sent once when a session window opens. ``overall``
    NEUTRAL means the biases are not aligned (A5 STANDBY). ``supports`` and
    ``resistances`` are the merged H1 display levels, nearest first (A1).
    ``news`` lists today's calendar releases; ``news_state`` NO_CALENDAR means
    the day is outside the calendar coverage."""

    time: datetime
    symbol: str
    session: Session
    bias_h1: Bias
    bias_m30: Trend
    bias_m15: Bias
    overall: Bias
    supports: tuple[float, ...]
    resistances: tuple[float, ...]
    news: tuple[ScheduledEvent, ...]
    news_state: NewsState
    spread_points: float | None = None

    def __post_init__(self) -> None:
        require_utc("time", self.time)
        require_text("symbol", self.symbol)
        require_enum("session", self.session, Session)
        require_enum("bias_h1", self.bias_h1, Bias)
        require_enum("bias_m30", self.bias_m30, Trend)
        require_enum("bias_m15", self.bias_m15, Bias)
        require_enum("overall", self.overall, Bias)
        require_enum("news_state", self.news_state, NewsState)
        for name in ("supports", "resistances", "news"):
            if not isinstance(getattr(self, name), tuple):
                raise ValueError(f"{name} must be a tuple")
        for level in self.supports + self.resistances:
            require_positive("level", level)
        for event in self.news:
            require_enum("news item", event, ScheduledEvent)
        if self.spread_points is not None:
            require_non_negative("spread_points", self.spread_points)


@dataclass(frozen=True)
class AdviceStandby:
    """STANDBY (section 5): sent only when the status changes. ``reason`` is the
    code of the first failing filter or rule, ``detail`` an optional plain
    explanation, ``news`` the F1 status when the news filter is the reason."""

    time: datetime
    symbol: str
    reason: str
    detail: str = ""
    news: NewsStatus | None = None

    def __post_init__(self) -> None:
        require_utc("time", self.time)
        require_text("symbol", self.symbol)
        require_text("reason", self.reason)
        if not isinstance(self.detail, str):
            raise ValueError("detail must be a string")
        if self.news is not None:
            require_enum("news", self.news, NewsStatus)
