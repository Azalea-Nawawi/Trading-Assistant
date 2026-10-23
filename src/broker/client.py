"""MetaTrader 5 broker: read-only access (D-041, DEC-001).

The MetaTrader5 module is injected so tests use a fake; this package never
imports it at module level. The broker only reads account, market and history
data: the assistant never opens, modifies, or closes positions (DEC-001).

MT5 times are the server wall clock stored as an epoch; they are read in
``server_timezone`` (IANA, from config) and converted to UTC.
Fail-closed: a None reply, an error, or unmappable data raises BrokerError;
no partial data is returned.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from src.models import (
    AccountState,
    Candle,
    Deal,
    DealEntry,
    Direction,
    HistoryOrder,
    OrderType,
    PendingOrder,
    Position,
    SymbolSpec,
    Tick,
    Timeframe,
)

from .config import BrokerConfig
from .credentials import Credentials
from .errors import BrokerError

log = logging.getLogger(__name__)


def load_mt5_module() -> Any:
    """Import the MetaTrader5 module (Windows only); broker is its only owner (D-010)."""
    import MetaTrader5

    return MetaTrader5


def server_epoch_to_utc(epoch: float, server_timezone: str) -> datetime:
    """Read an MT5 epoch (seconds) as server wall clock in ``server_timezone``, return UTC."""
    wall_clock = datetime.fromtimestamp(epoch, tz=timezone.utc).replace(tzinfo=None)
    return wall_clock.replace(tzinfo=ZoneInfo(server_timezone)).astimezone(timezone.utc)


def _price_or_none(value: float) -> float | None:
    """MT5 reports an unset SL/TP as 0.0."""
    return float(value) if value else None


class MT5Broker:
    """Read-only access to one symbol on an MT5 terminal."""

    def __init__(
        self,
        mt5: Any,
        config: BrokerConfig,
        credentials: Credentials,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._mt5 = mt5
        self._config = config
        self._credentials = credentials
        self._clock = clock
        self._connected = False
        self._is_demo: bool | None = None

    def __repr__(self) -> str:
        return f"MT5Broker(symbol={self._config.symbol!r}, connected={self._connected})"

    # --- helpers -------------------------------------------------------------

    def _fail(self, message: str) -> BrokerError:
        code = None
        try:
            error = self._mt5.last_error()
            code = int(error[0]) if error else None
        except Exception:  # last_error itself failed; keep the message
            code = None
        error = BrokerError(self._credentials.scrub(message), code)
        log.error("broker: %s", error)
        return error

    def _call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Call an MT5 function; None or an exception = BrokerError."""
        try:
            result = getattr(self._mt5, name)(*args, **kwargs)
        except Exception as exc:
            raise self._fail(f"{name} raised {type(exc).__name__}") from None
        if result is None:
            raise self._fail(f"{name} returned None")
        return result

    def _require_connected(self) -> None:
        if not self._connected:
            raise BrokerError("not connected")

    def _utc(self, epoch: float) -> datetime:
        return server_epoch_to_utc(epoch, self._config.server_timezone)

    def _map(self, what: str, build: Callable[[], Any]) -> Any:
        """Turn model validation errors into BrokerError (no partial data)."""
        try:
            return build()
        except (ValueError, TypeError, KeyError, AttributeError, IndexError) as exc:
            raise self._fail(f"unusable {what} data: {type(exc).__name__}") from None

    # --- connection ------------------------------------------------------------

    def connect(self) -> None:
        """Initialize the terminal and log in; refuse non-demo unless allow_live."""
        creds = self._credentials
        ok = self._call("initialize", login=creds.login, password=creds.password, server=creds.server)
        if not ok:
            raise self._fail("initialize failed")
        try:
            account = self._call("account_info")
            if account.server != creds.server:
                raise self._fail("account server does not match MT5_SERVER")
            self._is_demo = account.trade_mode == self._mt5.ACCOUNT_TRADE_MODE_DEMO
            if not self._is_demo and not self._config.allow_live:
                raise self._fail("account is not demo and allow_live is false")
            if not self._call("symbol_select", self._config.symbol, True):
                raise self._fail(f"symbol_select failed for {self._config.symbol}")
        except BrokerError:
            self._mt5.shutdown()
            raise
        self._connected = True
        log.info("broker: connected (demo=%s, symbol=%s)", self._is_demo, self._config.symbol)

    def disconnect(self) -> None:
        if self._connected:
            self._mt5.shutdown()
        self._connected = False
        log.info("broker: disconnected")

    # --- reads -------------------------------------------------------------------

    def account_state(self) -> AccountState:
        self._require_connected()
        info = self._call("account_info")
        return self._map(
            "account",
            lambda: AccountState(
                time=self._clock(),
                currency=info.currency,
                balance=float(info.balance),
                equity=float(info.equity),
                margin_free=float(info.margin_free),
                is_demo=info.trade_mode == self._mt5.ACCOUNT_TRADE_MODE_DEMO,
            ),
        )

    def symbol_spec(self) -> SymbolSpec:
        self._require_connected()
        info = self._call("symbol_info", self._config.symbol)
        return self._map(
            "symbol",
            lambda: SymbolSpec(
                name=info.name,
                digits=int(info.digits),
                point=float(info.point),
                tick_size=float(info.trade_tick_size),
                tick_value=float(info.trade_tick_value),
                contract_size=float(info.trade_contract_size),
                volume_min=float(info.volume_min),
                volume_max=float(info.volume_max),
                volume_step=float(info.volume_step),
                stops_level=int(info.trade_stops_level),
                freeze_level=int(info.trade_freeze_level),
            ),
        )

    def tick(self) -> Tick:
        self._require_connected()
        info = self._call("symbol_info_tick", self._config.symbol)
        return self._map(
            "tick",
            lambda: Tick(
                symbol=self._config.symbol,
                time=self._utc(info.time_msc / 1000),
                bid=float(info.bid),
                ask=float(info.ask),
            ),
        )

    def candles(self, timeframe: Timeframe, count: int) -> list[Candle]:
        """Up to the last ``count`` CLOSED candles, oldest first.

        DEC-009: a row is closed only when its open time plus the timeframe
        length is at or before the latest server tick time; position 0 is not
        assumed to be forming (or closed) by position alone.
        """
        self._require_connected()
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise BrokerError("count must be an int >= 1")
        constant = getattr(self._mt5, f"TIMEFRAME_{timeframe.value}")
        rates = self._call("copy_rates_from_pos", self._config.symbol, constant, 0, count + 1)
        server_now = self.tick().time
        length = timedelta(seconds=timeframe.seconds)
        rows = [
            row for row in list(rates) if self._utc(int(row["time"])) + length <= server_now
        ][-count:]
        return self._map(
            "candle",
            lambda: [
                Candle(
                    symbol=self._config.symbol,
                    timeframe=timeframe,
                    open_time=self._utc(int(row["time"])),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    spread_points=float(row["spread"]),
                    tick_volume=int(row["tick_volume"]),
                )
                for row in rows
            ],
        )

    def margin_per_lot(self, direction: Direction) -> float:
        """Margin for 1 lot at the current price (order_calc_margin), account currency."""
        self._require_connected()
        tick = self.tick()
        if direction is Direction.BUY:
            action, price = self._mt5.ORDER_TYPE_BUY, tick.ask
        else:
            action, price = self._mt5.ORDER_TYPE_SELL, tick.bid
        margin = self._call("order_calc_margin", action, self._config.symbol, 1.0, price)
        if not isinstance(margin, (int, float)) or isinstance(margin, bool) or margin <= 0:
            raise self._fail("order_calc_margin returned an unusable value")
        return float(margin)

    def positions(self, magic: int | None = None) -> list[Position]:
        """Open positions on the symbol; ``magic`` filters bot positions."""
        self._require_connected()
        rows = self._call("positions_get", symbol=self._config.symbol)
        directions = {self._mt5.POSITION_TYPE_BUY: Direction.BUY, self._mt5.POSITION_TYPE_SELL: Direction.SELL}
        return self._map(
            "position",
            lambda: [
                Position(
                    ticket=int(row.ticket),
                    symbol=row.symbol,
                    direction=directions[row.type],
                    volume=float(row.volume),
                    open_price=float(row.price_open),
                    open_time=self._utc(row.time_msc / 1000),
                    sl=_price_or_none(row.sl),
                    tp=_price_or_none(row.tp),
                    magic=int(row.magic),
                    comment=row.comment,
                    profit=float(row.profit),
                )
                for row in rows
                if magic is None or row.magic == magic
            ],
        )

    def pending_orders(self, magic: int | None = None) -> list[PendingOrder]:
        """Pending LIMIT/STOP orders on the symbol; other order types = BrokerError."""
        self._require_connected()
        rows = self._call("orders_get", symbol=self._config.symbol)
        mt5 = self._mt5
        kinds = {
            mt5.ORDER_TYPE_BUY_LIMIT: (Direction.BUY, OrderType.LIMIT),
            mt5.ORDER_TYPE_SELL_LIMIT: (Direction.SELL, OrderType.LIMIT),
            mt5.ORDER_TYPE_BUY_STOP: (Direction.BUY, OrderType.STOP),
            mt5.ORDER_TYPE_SELL_STOP: (Direction.SELL, OrderType.STOP),
        }
        return self._map(
            "pending order",
            lambda: [
                PendingOrder(
                    ticket=int(row.ticket),
                    symbol=row.symbol,
                    direction=kinds[row.type][0],
                    order_type=kinds[row.type][1],
                    volume=float(row.volume_current),
                    price=float(row.price_open),
                    time_setup=self._utc(row.time_setup_msc / 1000),
                    sl=_price_or_none(row.sl),
                    tp=_price_or_none(row.tp),
                    magic=int(row.magic),
                    comment=row.comment,
                )
                for row in rows
                if magic is None or row.magic == magic
            ],
        )

    # --- history (v2, D-044) --------------------------------------------------

    def _history_range(self, since: datetime, until: datetime | None) -> tuple[datetime, datetime]:
        until = until or self._clock()
        for value in (since, until):
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise BrokerError("history range must be timezone-aware datetimes")
        return since, until

    def orders_history(self, magic: int, since: datetime, until: datetime | None = None) -> list[HistoryOrder]:
        """Orders in the history between ``since`` and ``until`` (default now) with ``magic``."""
        self._require_connected()
        start, end = self._history_range(since, until)
        rows = self._call("history_orders_get", start, end)
        mt5 = self._mt5
        kinds = {
            mt5.ORDER_TYPE_BUY: (Direction.BUY, OrderType.MARKET),
            mt5.ORDER_TYPE_SELL: (Direction.SELL, OrderType.MARKET),
            mt5.ORDER_TYPE_BUY_LIMIT: (Direction.BUY, OrderType.LIMIT),
            mt5.ORDER_TYPE_SELL_LIMIT: (Direction.SELL, OrderType.LIMIT),
            mt5.ORDER_TYPE_BUY_STOP: (Direction.BUY, OrderType.STOP),
            mt5.ORDER_TYPE_SELL_STOP: (Direction.SELL, OrderType.STOP),
        }
        return self._map(
            "history order",
            lambda: [
                HistoryOrder(
                    ticket=int(row.ticket),
                    position_id=int(row.position_id),
                    symbol=row.symbol,
                    direction=kinds[row.type][0],
                    order_type=kinds[row.type][1],
                    volume=float(row.volume_initial),
                    price=float(row.price_open),
                    state=int(row.state),
                    time_setup=self._utc(row.time_setup_msc / 1000),
                    time_done=self._utc(row.time_done_msc / 1000) if row.time_done_msc else None,
                    sl=_price_or_none(row.sl),
                    tp=_price_or_none(row.tp),
                    magic=int(row.magic),
                    comment=row.comment,
                )
                for row in rows
                if row.magic == magic
            ],
        )

    def deals_history(self, magic: int, since: datetime, until: datetime | None = None) -> list[Deal]:
        """Deals in the history between ``since`` and ``until`` (default now) with ``magic``."""
        self._require_connected()
        start, end = self._history_range(since, until)
        rows = self._call("history_deals_get", start, end)
        mt5 = self._mt5
        directions = {mt5.DEAL_TYPE_BUY: Direction.BUY, mt5.DEAL_TYPE_SELL: Direction.SELL}
        entries = {
            mt5.DEAL_ENTRY_IN: DealEntry.IN,
            mt5.DEAL_ENTRY_OUT: DealEntry.OUT,
            mt5.DEAL_ENTRY_INOUT: DealEntry.INOUT,
            mt5.DEAL_ENTRY_OUT_BY: DealEntry.OUT_BY,
        }
        return self._map(
            "deal",
            lambda: [
                Deal(
                    ticket=int(row.ticket),
                    order=int(row.order),
                    position_id=int(row.position_id),
                    symbol=row.symbol,
                    direction=directions[row.type],
                    entry=entries[row.entry],
                    volume=float(row.volume),
                    price=float(row.price),
                    time=self._utc(row.time_msc / 1000),
                    magic=int(row.magic),
                    comment=row.comment,
                    profit=float(row.profit),
                )
                for row in rows
                if row.magic == magic
            ],
        )

