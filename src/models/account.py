"""Account snapshot and risk state models (D-039, D-040)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ._validation import require_finite, require_non_negative, require_positive, require_text, require_utc


@dataclass(frozen=True)
class AccountState:
    """Account snapshot passed from core to risk (PRD 5.1, 5.2).

    Deliberately has no account number or login (CLAUDE.md, D-028).
    Equity = balance + floating P/L.
    """

    time: datetime
    currency: str
    balance: float
    equity: float
    margin_free: float
    is_demo: bool

    def __post_init__(self) -> None:
        require_utc("time", self.time)
        require_text("currency", self.currency)
        for name in ("balance", "equity", "margin_free"):
            require_finite(name, getattr(self, name))
        if not isinstance(self.is_demo, bool):
            raise ValueError("is_demo must be a bool")


@dataclass(frozen=True)
class RiskState:
    """Risk counters kept by core and passed to the stateless risk package (D-040).

    ``equity_day_start`` = equity at the trading-day change (PRD 5.1);
    ``hwm`` = highest equity observed (PRD 5.1); ``trades_filled_today``
    counts FILLED orders today; ``open_positions`` counts open positions.
    """

    equity_day_start: float
    hwm: float
    trades_filled_today: int
    open_positions: int

    def __post_init__(self) -> None:
        require_positive("equity_day_start", self.equity_day_start)
        require_positive("hwm", self.hwm)
        for name in ("trades_filled_today", "open_positions"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{name} must be an int")
            require_non_negative(name, value)
