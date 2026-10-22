"""MetaTrader 5 broker: v1 reads (D-041), v2 order actions (D-044).

The MetaTrader5 module is injected so tests use a fake; this package never
imports it at module level. v2 is the "hands": it builds and sends order
requests and returns the raw BrokerReply. It never classifies replies,
retries, or decides anything; that is ``execution`` (D-012 item 5, D-044).

MT5 times are the server wall clock stored as an epoch; they are read in
``server_timezone`` (IANA, from config) and converted to UTC.
Fail-closed: a None reply, an error, or unmappable data raises BrokerError;
no partial data is returned.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from src.models import (
    AccountState,
    BrokerReply,
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
        """The last ``count`` CLOSED candles, oldest first; position 0 (forming) is dropped."""
        self._require_connected()
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise BrokerError("count must be an int >= 1")
        constant = getattr(self._mt5, f"TIMEFRAME_{timeframe.value}")
        rates = self._call("copy_rates_from_pos", self._config.symbol, constant, 0, count + 1)
        rows = list(rates)[:-1]  # oldest first; the last row is position 0
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


    # --- orders (v2, D-044): build, send once, return the raw reply -------------
    #
    # Preconditions that make a request unsendable (no SL, comment too long,
    # unsupported order type) raise BrokerError and nothing is sent. Once a
    # request is sent, every outcome, including None or an exception from
    # order_send, is returned as a BrokerReply and never raised.

    def _filling(self, name: str) -> int:
        return getattr(self._mt5, f"ORDER_FILLING_{name}")

    def _check_comment(self, comment: str) -> None:
        if not isinstance(comment, str) or len(comment) > self._config.max_comment_length:
            raise BrokerError(f"comment longer than {self._config.max_comment_length} characters; not sent")

    @staticmethod
    def _check_price(name: str, value: float | None, required: bool) -> None:
        if value is None:
            if required:
                raise BrokerError(f"{name} is required; not sent")
            return
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise BrokerError(f"{name} must be a positive price; not sent")

    @staticmethod
    def _check_ticket(ticket: int) -> None:
        if not isinstance(ticket, int) or isinstance(ticket, bool) or ticket <= 0:
            raise BrokerError("ticket must be a positive int; not sent")

    @staticmethod
    def _ticket_or_none(value: Any) -> int | None:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number or None

    def _order_send(self, action: str, request: dict[str, Any]) -> BrokerReply:
        """Send once; return the reply as is. None or an exception = retcode None."""
        sent = dict(request)
        try:
            result = self._mt5.order_send(request)
        except Exception as exc:
            reply = BrokerReply(action, self._clock(), sent, None, error=f"order_send raised {type(exc).__name__}")
        else:
            if result is None:
                try:
                    error = self._mt5.last_error()
                    code = int(error[0]) if error else None
                except Exception:
                    code = None
                reply = BrokerReply(action, self._clock(), sent, None, error=f"order_send returned None (last_error {code})")
            else:
                try:
                    retcode = int(result.retcode)
                except (AttributeError, TypeError, ValueError):
                    retcode = None
                reply = BrokerReply(
                    action,
                    self._clock(),
                    sent,
                    retcode,
                    order=self._ticket_or_none(getattr(result, "order", None)),
                    deal=self._ticket_or_none(getattr(result, "deal", None)),
                    comment=self._credentials.scrub(str(getattr(result, "comment", ""))),
                )
        log.info(
            "broker: %s retcode=%s order=%s deal=%s comment=%r %s",
            action, reply.retcode, reply.order, reply.deal, reply.comment, reply.error,
        )
        return reply

    def send_order(
        self,
        order_type: OrderType,
        direction: Direction,
        volume: float,
        sl: float,
        tp: float | None = None,
        comment: str = "",
        price: float | None = None,
    ) -> BrokerReply:
        """Send a MARKET or LIMIT order with SL (mandatory) and optional TP.

        MARKET uses the current ask (BUY) or bid (SELL) and the market
        filling; LIMIT needs ``price`` and uses the pending filling. Magic and
        deviation come from config. STOP and other types are refused.
        """
        self._require_connected()
        if order_type not in (OrderType.MARKET, OrderType.LIMIT):
            raise BrokerError(f"order type {getattr(order_type, 'value', order_type)} not supported; not sent")
        if direction not in (Direction.BUY, Direction.SELL):
            raise BrokerError("direction must be BUY or SELL; not sent")
        if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not math.isfinite(volume) or volume <= 0:
            raise BrokerError("volume must be > 0; not sent")
        self._check_price("sl", sl, required=True)
        self._check_price("tp", tp, required=False)
        self._check_comment(comment)
        mt5, buy = self._mt5, direction is Direction.BUY
        request: dict[str, Any] = {"symbol": self._config.symbol, "volume": float(volume)}
        if order_type is OrderType.MARKET:
            tick = self.tick()
            action = "send_market"
            request.update(
                action=mt5.TRADE_ACTION_DEAL,
                type=mt5.ORDER_TYPE_BUY if buy else mt5.ORDER_TYPE_SELL,
                price=tick.ask if buy else tick.bid,
                deviation=self._config.deviation,
                type_filling=self._filling(self._config.market_filling),
            )
        else:
            self._check_price("price", price, required=True)
            action = "send_limit"
            request.update(
                action=mt5.TRADE_ACTION_PENDING,
                type=mt5.ORDER_TYPE_BUY_LIMIT if buy else mt5.ORDER_TYPE_SELL_LIMIT,
                price=float(price),
                type_filling=self._filling(self._config.pending_filling),
            )
        request.update(sl=float(sl), magic=self._config.magic, comment=comment, type_time=mt5.ORDER_TIME_GTC)
        if tp is not None:
            request["tp"] = float(tp)
        return self._order_send(action, request)

    def send_market(
        self, direction: Direction, volume: float, sl: float, tp: float | None = None, comment: str = ""
    ) -> BrokerReply:
        return self.send_order(OrderType.MARKET, direction, volume, sl, tp, comment)

    def send_limit(
        self, direction: Direction, volume: float, price: float, sl: float, tp: float | None = None, comment: str = ""
    ) -> BrokerReply:
        return self.send_order(OrderType.LIMIT, direction, volume, sl, tp, comment, price=price)

    def modify_sltp(self, ticket: int, sl: float, tp: float | None = None) -> BrokerReply:
        """Set SL (mandatory) and TP on an open position; ``tp`` None sends 0.0 (no TP)."""
        self._require_connected()
        self._check_ticket(ticket)
        self._check_price("sl", sl, required=True)
        self._check_price("tp", tp, required=False)
        request = {
            "action": self._mt5.TRADE_ACTION_SLTP,
            "symbol": self._config.symbol,
            "position": ticket,
            "sl": float(sl),
            "tp": float(tp) if tp is not None else 0.0,
            "magic": self._config.magic,
        }
        return self._order_send("modify_sltp", request)

    def close_position(self, ticket: int, comment: str = "") -> BrokerReply:
        """Close a whole open position at market (bid for BUY, ask for SELL)."""
        self._require_connected()
        self._check_ticket(ticket)
        self._check_comment(comment)
        matches = [p for p in self.positions() if p.ticket == ticket]
        if not matches:
            raise BrokerError(f"position {ticket} not found; not sent")
        position, tick, mt5 = matches[0], self.tick(), self._mt5
        buy = position.direction is Direction.BUY
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self._config.symbol,
            "position": ticket,
            "volume": position.volume,
            "type": mt5.ORDER_TYPE_SELL if buy else mt5.ORDER_TYPE_BUY,
            "price": tick.bid if buy else tick.ask,
            "deviation": self._config.deviation,
            "magic": self._config.magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling(self._config.market_filling),
        }
        return self._order_send("close_position", request)

    def cancel_order(self, ticket: int) -> BrokerReply:
        """Remove a pending order."""
        self._require_connected()
        self._check_ticket(ticket)
        request = {"action": self._mt5.TRADE_ACTION_REMOVE, "order": ticket, "magic": self._config.magic}
        return self._order_send("cancel_order", request)

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

