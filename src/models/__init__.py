"""Domain data models shared by every package (D-009, D-039).

Frozen dataclasses with field validation only; standard library only; this
package imports no other ``src`` package (D-010).
"""

from .account import AccountState, RiskState
from .advice import Advice, AdviceContext, AdvicePlan, AdviceStandby
from .enums import (
    AdviceDecision,
    AdviceOutcome,
    Bias,
    DealEntry,
    Direction,
    ExecutionEventKind,
    KillSwitchLevel,
    LockStatus,
    OrderOutcome,
    OrderStatus,
    OrderType,
    Session,
    Timeframe,
    Trend,
)
from .market import Candle, SymbolSpec, Tick
from .news import NewsState, NewsStatus, ScheduledEvent
from .trading import (
    BrokerReply,
    Deal,
    ExecutionEvent,
    HistoryOrder,
    OrderRequest,
    OrderResult,
    PendingOrder,
    Position,
    RiskDecision,
    Signal,
    make_setup_id,
)

__all__ = [
    "AccountState",
    "Advice",
    "AdviceContext",
    "AdviceDecision",
    "AdviceOutcome",
    "AdvicePlan",
    "AdviceStandby",
    "Bias",
    "BrokerReply",
    "Candle",
    "Deal",
    "DealEntry",
    "Direction",
    "ExecutionEvent",
    "ExecutionEventKind",
    "HistoryOrder",
    "KillSwitchLevel",
    "LockStatus",
    "NewsState",
    "NewsStatus",
    "OrderOutcome",
    "OrderRequest",
    "OrderResult",
    "OrderStatus",
    "OrderType",
    "PendingOrder",
    "Position",
    "RiskDecision",
    "RiskState",
    "ScheduledEvent",
    "Session",
    "Signal",
    "SymbolSpec",
    "Tick",
    "Timeframe",
    "Trend",
    "make_setup_id",
]
