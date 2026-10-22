"""Trading models: Signal, OrderRequest, OrderResult, Position, RiskDecision (D-039).

Only data and field validation; sizing (risk) and broker-code
classification (execution) live in their own packages.
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
from .enums import DealEntry, Direction, ExecutionEventKind, OrderOutcome, OrderStatus, OrderType


def _require_reason_codes(codes: tuple[str, ...]) -> None:
    if not isinstance(codes, tuple):
        raise ValueError("reason_codes must be a tuple")
    for code in codes:
        require_text("reason code", code)


@dataclass(frozen=True)
class Signal:
    """Strategy output (Strategy Spec bagian 4: Signal{waktu, arah, entry, sl,
    tp, setup_id, kode_alasan[]}). Never carries a lot size (PRD 4, 5.2).

    ``time`` is the signal candle time in UTC. ``tp`` may be None for an exit
    without a fixed target.
    """

    time: datetime
    symbol: str
    direction: Direction
    entry: float
    sl: float
    tp: float | None
    setup_id: str
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        require_utc("time", self.time)
        require_text("symbol", self.symbol)
        require_enum("direction", self.direction, Direction)
        require_positive("entry", self.entry)
        require_protective_sides(self.direction, self.entry, self.sl, self.tp)
        require_text("setup_id", self.setup_id)
        _require_reason_codes(self.reason_codes)


@dataclass(frozen=True)
class OrderRequest:
    """Order sent to the broker; SL is mandatory and sent with the order (PRD 6.1).

    ``price`` is the requested price (reference price for MARKET).
    ``magic`` and ``comment`` identify bot orders (PRD 6.1 idempotensi).
    """

    setup_id: str
    symbol: str
    direction: Direction
    order_type: OrderType
    volume: float
    price: float
    sl: float | None
    tp: float | None = None
    magic: int = 0
    comment: str = ""

    def __post_init__(self) -> None:
        require_text("setup_id", self.setup_id)
        require_text("symbol", self.symbol)
        require_enum("direction", self.direction, Direction)
        require_enum("order_type", self.order_type, OrderType)
        require_positive("volume", self.volume)
        require_positive("price", self.price)
        if self.sl is None:
            raise ValueError("OrderRequest requires an SL (PRD 6.1, D-011)")
        require_protective_sides(self.direction, self.price, self.sl, self.tp)
        if not isinstance(self.magic, int) or isinstance(self.magic, bool):
            raise ValueError("magic must be an int")
        if not isinstance(self.comment, str):
            raise ValueError("comment must be a string")


@dataclass(frozen=True)
class OrderResult:
    """Classified broker reply to an OrderRequest (D-012 item 1).

    ``outcome`` is set by ``execution``. UNCERTAIN (TIDAK_PASTI) keeps the
    order SENT (DIKIRIM) until reconciliation (PRD 6.1).
    """

    setup_id: str
    outcome: OrderOutcome
    time: datetime
    retcode: int | None = None
    broker_order_id: int | None = None
    message: str = ""

    def __post_init__(self) -> None:
        require_text("setup_id", self.setup_id)
        require_enum("outcome", self.outcome, OrderOutcome)
        require_utc("time", self.time)


@dataclass(frozen=True)
class Position:
    """Open position as read from the broker (D-011, PRD 6).

    ``sl`` None means no server-side SL was read (D-011 condition 2).
    """

    ticket: int
    symbol: str
    direction: Direction
    volume: float
    open_price: float
    open_time: datetime
    sl: float | None
    tp: float | None = None
    magic: int = 0
    comment: str = ""
    profit: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.ticket, int) or isinstance(self.ticket, bool) or self.ticket <= 0:
            raise ValueError("ticket must be a positive int")
        require_text("symbol", self.symbol)
        require_enum("direction", self.direction, Direction)
        require_positive("volume", self.volume)
        require_positive("open_price", self.open_price)
        require_utc("open_time", self.open_time)
        if self.sl is not None:
            require_positive("sl", self.sl)
        if self.tp is not None:
            require_positive("tp", self.tp)
        require_finite("profit", self.profit)


@dataclass(frozen=True)
class RiskDecision:
    """Result of the risk check for one Signal (PRD 5.2, D-016).

    Approved: ``volume`` > 0 is the lot to send. Rejected: no volume and at
    least one reason code (e.g. lot minimum above budget).
    """

    setup_id: str
    approved: bool
    volume: float | None = None
    planned_risk: float | None = None
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        require_text("setup_id", self.setup_id)
        if not isinstance(self.approved, bool):
            raise ValueError("approved must be a bool")
        _require_reason_codes(self.reason_codes)
        if self.approved:
            if self.volume is None:
                raise ValueError("approved RiskDecision requires a volume")
            require_positive("volume", self.volume)
        else:
            if self.volume is not None:
                raise ValueError("rejected RiskDecision must not carry a volume")
            if not self.reason_codes:
                raise ValueError("rejected RiskDecision requires a reason code")
        if self.planned_risk is not None:
            require_finite("planned_risk", self.planned_risk)


@dataclass(frozen=True)
class PendingOrder:
    """Pending (LIMIT/STOP) order as read from the broker (D-041, PRD 6.1).

    ``sl``/``tp`` None means not set at the broker.
    """

    ticket: int
    symbol: str
    direction: Direction
    order_type: OrderType
    volume: float
    price: float
    time_setup: datetime
    sl: float | None
    tp: float | None = None
    magic: int = 0
    comment: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.ticket, int) or isinstance(self.ticket, bool) or self.ticket <= 0:
            raise ValueError("ticket must be a positive int")
        require_text("symbol", self.symbol)
        require_enum("direction", self.direction, Direction)
        require_enum("order_type", self.order_type, OrderType)
        if self.order_type is OrderType.MARKET:
            raise ValueError("a pending order cannot be MARKET")
        require_positive("volume", self.volume)
        require_positive("price", self.price)
        require_utc("time_setup", self.time_setup)
        if self.sl is not None:
            require_positive("sl", self.sl)
        if self.tp is not None:
            require_positive("tp", self.tp)


@dataclass(frozen=True)
class BrokerReply:
    """Raw broker answer to one order action, uninterpreted (D-044).

    ``retcode`` None means order_send returned None or raised; ``error``
    then holds the last_error code or exception type. Classification into
    OrderOutcome is done by ``execution`` (D-012 item 5, D-043). ``request``
    is the request sent to the broker; it never holds credentials.
    """

    action: str
    time: datetime
    request: dict
    retcode: int | None
    order: int | None = None
    deal: int | None = None
    comment: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        require_text("action", self.action)
        require_utc("time", self.time)
        if not isinstance(self.request, dict):
            raise ValueError("request must be a dict")
        for name in ("retcode", "order", "deal"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
                raise ValueError(f"{name} must be an int or None")
        if not isinstance(self.comment, str) or not isinstance(self.error, str):
            raise ValueError("comment and error must be strings")


@dataclass(frozen=True)
class Deal:
    """One deal from the broker history (D-044); prices as executed."""

    ticket: int
    order: int
    position_id: int
    symbol: str
    direction: Direction
    entry: DealEntry
    volume: float
    price: float
    time: datetime
    magic: int = 0
    comment: str = ""
    profit: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.ticket, int) or isinstance(self.ticket, bool) or self.ticket <= 0:
            raise ValueError("ticket must be a positive int")
        require_text("symbol", self.symbol)
        require_enum("direction", self.direction, Direction)
        require_enum("entry", self.entry, DealEntry)
        require_positive("volume", self.volume)
        require_positive("price", self.price)
        require_utc("time", self.time)
        require_finite("profit", self.profit)


@dataclass(frozen=True)
class HistoryOrder:
    """One order from the broker history (D-044). ``state`` is the raw MT5
    ORDER_STATE_* value, not interpreted here."""

    ticket: int
    position_id: int
    symbol: str
    direction: Direction
    order_type: OrderType
    volume: float
    price: float
    state: int
    time_setup: datetime
    time_done: datetime | None
    sl: float | None = None
    tp: float | None = None
    magic: int = 0
    comment: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.ticket, int) or isinstance(self.ticket, bool) or self.ticket <= 0:
            raise ValueError("ticket must be a positive int")
        require_text("symbol", self.symbol)
        require_enum("direction", self.direction, Direction)
        require_enum("order_type", self.order_type, OrderType)
        require_positive("volume", self.volume)
        require_non_negative("price", self.price)
        require_utc("time_setup", self.time_setup)
        if self.time_done is not None:
            require_utc("time_done", self.time_done)


@dataclass(frozen=True)
class ExecutionEvent:
    """One step reported by execution to core (D-044).

    ``critical`` marks D-012 critical incidents (manual reset); core decides
    the lock, execution never holds it (D-011, D-012). ``outcome`` is the
    classified broker reply when one was involved; ``status`` the lifecycle
    status read from broker data (PRD 6.1).
    """

    setup_id: str
    time: datetime
    kind: ExecutionEventKind
    critical: bool = False
    outcome: OrderOutcome | None = None
    status: OrderStatus | None = None
    ticket: int | None = None
    retcode: int | None = None
    message: str = ""

    def __post_init__(self) -> None:
        require_text("setup_id", self.setup_id)
        require_utc("time", self.time)
        require_enum("kind", self.kind, ExecutionEventKind)
        if not isinstance(self.critical, bool):
            raise ValueError("critical must be a bool")
        if self.outcome is not None:
            require_enum("outcome", self.outcome, OrderOutcome)
        if self.status is not None:
            require_enum("status", self.status, OrderStatus)
        for name in ("ticket", "retcode"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
                raise ValueError(f"{name} must be an int or None")


SETUP_ID_MAX_LENGTH = 24  # broker comment limit (D-043)


def make_setup_id(direction: Direction, strategy_code: str, signal_time: datetime) -> str:
    """Deterministic setup_id (D-044): ``<B|S><strategy code>-<YYMMDDHHMM UTC>``.

    ``signal_time`` is the UTC time of the signal candle, e.g. BUY, "S2",
    2026-10-21 07:35 UTC -> "BS2-2610210735". The result must fit the
    24-character broker comment (D-043); a longer one raises ValueError.
    """
    require_enum("direction", direction, Direction)
    require_utc("signal_time", signal_time)
    if not isinstance(strategy_code, str) or not strategy_code.isalnum() or not strategy_code.isascii():
        raise ValueError("strategy_code must be ASCII letters and digits")
    prefix = "B" if direction is Direction.BUY else "S"
    setup_id = f"{prefix}{strategy_code}-{signal_time:%y%m%d%H%M}"
    if len(setup_id) > SETUP_ID_MAX_LENGTH:
        raise ValueError(f"setup_id {setup_id!r} longer than {SETUP_ID_MAX_LENGTH} characters")
    return setup_id
