"""Market data models: Candle and SymbolSpec (D-039)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ._validation import require_enum, require_non_negative, require_positive, require_text, require_utc
from .enums import Timeframe


@dataclass(frozen=True)
class Candle:
    """One closed OHLC candle; prices are bid (Strategy Spec bagian 2).

    ``open_time`` is the candle open in UTC. ``spread_points`` is the
    broker's spread field in points.
    """

    symbol: str
    timeframe: Timeframe
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    spread_points: float = 0.0
    tick_volume: int = 0

    def __post_init__(self) -> None:
        require_text("symbol", self.symbol)
        require_enum("timeframe", self.timeframe, Timeframe)
        require_utc("open_time", self.open_time)
        for name in ("open", "high", "low", "close"):
            require_positive(name, getattr(self, name))
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError(
                f"invalid OHLC: open={self.open} high={self.high} low={self.low} close={self.close}"
            )
        require_non_negative("spread_points", self.spread_points)
        require_non_negative("tick_volume", self.tick_volume)


@dataclass(frozen=True)
class SymbolSpec:
    """Symbol specification read from the broker at runtime (D-026, D-027).

    ``stops_level`` and ``freeze_level`` are in points.
    """

    name: str
    digits: int
    point: float
    tick_size: float
    tick_value: float
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    stops_level: int = 0
    freeze_level: int = 0

    def __post_init__(self) -> None:
        require_text("name", self.name)
        require_non_negative("digits", self.digits)
        for name in ("point", "tick_size", "tick_value", "contract_size", "volume_min", "volume_max", "volume_step"):
            require_positive(name, getattr(self, name))
        if self.volume_min > self.volume_max:
            raise ValueError(f"volume_min {self.volume_min} must be <= volume_max {self.volume_max}")
        require_non_negative("stops_level", self.stops_level)
        require_non_negative("freeze_level", self.freeze_level)


@dataclass(frozen=True)
class Tick:
    """Latest bid/ask quote (D-041); ``time`` in UTC. Spread = ask - bid."""

    symbol: str
    time: datetime
    bid: float
    ask: float

    def __post_init__(self) -> None:
        require_text("symbol", self.symbol)
        require_utc("time", self.time)
        require_positive("bid", self.bid)
        require_positive("ask", self.ask)
        if self.ask < self.bid:
            raise ValueError(f"ask {self.ask} must be >= bid {self.bid}")

    @property
    def spread(self) -> float:
        return self.ask - self.bid
