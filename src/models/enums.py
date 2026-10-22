"""Enumerations shared by every package (D-039)."""

from __future__ import annotations

from enum import Enum, IntEnum


class Direction(str, Enum):
    """Trade direction (Strategy Spec: arah)."""

    BUY = "BUY"
    SELL = "SELL"


class Timeframe(str, Enum):
    """Candle timeframe; ``seconds`` is the candle length."""

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"

    @property
    def seconds(self) -> int:
        return _TIMEFRAME_SECONDS[self]


_TIMEFRAME_SECONDS = {
    Timeframe.M1: 60,
    Timeframe.M5: 5 * 60,
    Timeframe.M15: 15 * 60,
    Timeframe.M30: 30 * 60,
    Timeframe.H1: 60 * 60,
    Timeframe.H4: 4 * 60 * 60,
    Timeframe.D1: 24 * 60 * 60,
}


class OrderType(str, Enum):
    """How an order is placed at the broker."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class OrderOutcome(str, Enum):
    """Class of a broker reply to an order (D-012 item 1, PRD 6.1).

    REJECTED_CONFIRMED = DITOLAK_TERKONFIRMASI, SUCCESS = BERHASIL,
    UNCERTAIN = TIDAK_PASTI (every other result, fail-closed). The mapping
    from broker codes is done in ``execution``, not here.
    """

    REJECTED_CONFIRMED = "REJECTED_CONFIRMED"
    SUCCESS = "SUCCESS"
    UNCERTAIN = "UNCERTAIN"


class OrderStatus(str, Enum):
    """Order lifecycle status read from broker data (PRD 6.1).

    SENT = DIKIRIM, PENDING = PENDING, FILLED = TERISI, REJECTED = DITOLAK,
    CANCELLED = dibatalkan.
    """

    SENT = "SENT"
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class LockStatus(str, Enum):
    """Safety lock status (D-012 item 2).

    OPEN = TERBUKA, LOCKED_AUTO = TERKUNCI_OTOMATIS,
    LOCKED_MANUAL = TERKUNCI_MANUAL.
    """

    OPEN = "OPEN"
    LOCKED_AUTO = "LOCKED_AUTO"
    LOCKED_MANUAL = "LOCKED_MANUAL"


class KillSwitchLevel(IntEnum):
    """Kill switch level (PRD 5.4); 0 = not active."""

    NONE = 0
    LEVEL_1 = 1  # stop new entries, cancel pending orders
    LEVEL_2 = 2  # level 1 + close all positions
    LEVEL_3 = 3  # stop the bot process


class DealEntry(str, Enum):
    """Deal direction relative to a position (MT5 DEAL_ENTRY_*): IN opens, OUT closes."""

    IN = "IN"
    OUT = "OUT"
    INOUT = "INOUT"
    OUT_BY = "OUT_BY"


class ExecutionEventKind(str, Enum):
    """What execution reports to core for one setup (D-044)."""

    NOT_SENT = "NOT_SENT"  # broker refused to build/send (precondition)
    DUPLICATE_SKIPPED = "DUPLICATE_SKIPPED"  # setup_id already has an order/position
    READ_FAILED = "READ_FAILED"  # broker read failed; nothing sent
    REJECTED = "REJECTED"  # DITOLAK_TERKONFIRMASI, no retry
    FILLED = "FILLED"  # position found for the setup
    PENDING_PLACED = "PENDING_PLACED"  # pending order found for the setup
    CLOSED_IN_HISTORY = "CLOSED_IN_HISTORY"  # order only in history (filled and closed, or cancelled)
    UNKNOWN_HISTORY_STATE = "UNKNOWN_HISTORY_STATE"  # history order in a state not in config (critical)
    SL_VERIFIED = "SL_VERIFIED"  # server-side SL within tolerance
    SL_REPAIRED = "SL_REPAIRED"  # SL set again and verified
    POSITION_CLOSED_SL_FAILED = "POSITION_CLOSED_SL_FAILED"  # D-012 critical incident 2
    SL_AND_CLOSE_FAILED = "SL_AND_CLOSE_FAILED"  # D-012 critical incident 1
    UNCERTAIN_UNRESOLVED = "UNCERTAIN_UNRESOLVED"  # D-012 critical incident 3


# --- Semi-Auto advice (Semi-Auto Spec #1, D-069) ------------------------------------


class Bias(str, Enum):
    """H1 (A2) and M15 (A4) bias."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class Trend(str, Enum):
    """M30 structure (A3)."""

    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    SIDEWAYS = "SIDEWAYS"


class Session(str, Enum):
    """F3 window in which the advice candle closed."""

    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"


class AdviceDecision(str, Enum):
    """What the user did with an advice (section 6): followed it or not."""

    TAKEN = "TAKEN"
    SKIPPED = "SKIPPED"


class AdviceOutcome(str, Enum):
    """Hypothetical result of an advice (section 6): SL, TP1, TP2, forced exit
    at 16:55 New York, or EXPIRED (closed without a result, e.g. data gap)."""

    SL = "SL"
    TP1 = "TP1"
    TP2 = "TP2"
    FORCED_EXIT = "FORCED_EXIT"
    EXPIRED = "EXPIRED"
