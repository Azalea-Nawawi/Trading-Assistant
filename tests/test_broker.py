"""Tests for src/broker v1 (D-041) with a fake MetaTrader5 module."""

import importlib.util
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.broker import (
    BrokerConfig,
    broker_config_from_mapping,
    BrokerError,
    Credentials,
    MT5Broker,
    credentials_from_env,
    load_broker_config,
    parse_env_text,
    server_epoch_to_utc,
)
from src.models import DealEntry, Direction, OrderType, Timeframe

ROOT = Path(__file__).resolve().parent.parent
LOGIN = 98765432
PASSWORD = "s3cret-Pa55"
SERVER = "Exness-MT5Trial"
NOW = datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc)


def wall_epoch(text):
    """Server wall clock 'YYYY-MM-DDTHH:MM' stored as an epoch, the way MT5 does."""
    return int(datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp())


class FakeMT5:
    """Minimal stand-in for the MetaTrader5 module (read functions only)."""

    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_REAL = 2
    TIMEFRAME_M5 = 5
    TIMEFRAME_H1 = 16385
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TYPE_BUY_STOP = 4
    ORDER_TYPE_SELL_STOP = 5
    ORDER_TYPE_BUY_STOP_LIMIT = 6
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 6
    TRADE_ACTION_REMOVE = 8
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1
    DEAL_ENTRY_IN = 0
    DEAL_ENTRY_OUT = 1
    DEAL_ENTRY_INOUT = 2
    DEAL_ENTRY_OUT_BY = 3

    def __init__(self, trade_mode=0, server=SERVER):
        self.calls = []
        self.error = (1, "Success")
        self.account = SimpleNamespace(
            login=LOGIN,
            server=server,
            trade_mode=trade_mode,
            currency="USD",
            balance=1000.0,
            equity=995.5,
            margin_free=990.0,
        )
        self.symbol = SimpleNamespace(
            name="XAUUSDm",
            digits=3,
            point=0.001,
            trade_tick_size=0.001,
            trade_tick_value=0.1,
            trade_contract_size=100.0,
            volume_min=0.01,
            volume_max=200.0,
            volume_step=0.01,
            trade_stops_level=0,
            trade_freeze_level=0,
        )
        self.tick = SimpleNamespace(time_msc=wall_epoch("2026-10-20T11:00") * 1000 + 250, bid=4100.0, ask=4100.24)
        self.rates = [
            {"time": wall_epoch("2026-10-20T10:50"), "open": 4099.0, "high": 4101.0, "low": 4098.5,
             "close": 4100.0, "tick_volume": 120, "spread": 240, "real_volume": 0},
            {"time": wall_epoch("2026-10-20T10:55"), "open": 4100.0, "high": 4100.5, "low": 4099.5,
             "close": 4100.2, "tick_volume": 98, "spread": 230, "real_volume": 0},
            {"time": wall_epoch("2026-10-20T11:00"), "open": 4100.2, "high": 4100.3, "low": 4100.0,
             "close": 4100.1, "tick_volume": 5, "spread": 240, "real_volume": 0},  # position 0: forming
        ]
        self.margin = 41.0
        self.open_positions = (
            SimpleNamespace(ticket=11, symbol="XAUUSDm", type=1, volume=0.02, price_open=4105.0,
                            time_msc=wall_epoch("2026-10-20T09:30") * 1000, sl=4110.0, tp=0.0,
                            magic=2026, comment="setup-1", profit=-1.5),
            SimpleNamespace(ticket=12, symbol="XAUUSDm", type=0, volume=0.01, price_open=4090.0,
                            time_msc=wall_epoch("2026-10-20T08:00") * 1000, sl=0.0, tp=0.0,
                            magic=7, comment="manual", profit=10.0),
        )
        self.orders = (
            SimpleNamespace(ticket=21, symbol="XAUUSDm", type=2, volume_current=0.03, price_open=4095.0,
                            time_setup_msc=wall_epoch("2026-10-20T10:00") * 1000, sl=4090.0, tp=4110.0,
                            magic=2026, comment="setup-2"),
        )
        self.none_for = set()
        self.sent = []
        self.send_result = SimpleNamespace(retcode=10009, order=501, deal=601, comment="ok")
        done = wall_epoch("2026-10-20T10:00") * 1000
        self.deals = (
            SimpleNamespace(ticket=601, order=501, position_id=701, symbol="XAUUSDm", type=0, entry=0,
                            volume=0.01, price=4100.24, time_msc=done, magic=260044,
                            comment="BS2-2610210735", profit=0.0),
            SimpleNamespace(ticket=602, order=502, position_id=701, symbol="XAUUSDm", type=1, entry=1,
                            volume=0.01, price=4104.0, time_msc=done + 60000, magic=260044,
                            comment="", profit=3.76),
            SimpleNamespace(ticket=603, order=0, position_id=0, symbol="", type=2, entry=0,
                            volume=0.0, price=0.0, time_msc=done, magic=0, comment="balance", profit=0.0),
        )
        self.history_orders = (
            SimpleNamespace(ticket=501, position_id=701, symbol="XAUUSDm", type=0, volume_initial=0.01,
                            price_open=0.0, state=4, time_setup_msc=done, time_done_msc=done,
                            sl=4095.0, tp=0.0, magic=260044, comment="BS2-2610210735"),
            SimpleNamespace(ticket=503, position_id=0, symbol="XAUUSDm", type=2, volume_initial=0.01,
                            price_open=4000.0, state=2, time_setup_msc=done, time_done_msc=0,
                            sl=3990.0, tp=0.0, magic=7, comment="manual"),
        )

    def _record(self, name, value):
        self.calls.append(name)
        return None if name in self.none_for else value

    def initialize(self, **kwargs):
        self.init_kwargs = kwargs
        return self._record("initialize", True)

    def shutdown(self):
        self.calls.append("shutdown")

    def last_error(self):
        return self.error

    def account_info(self):
        return self._record("account_info", self.account)

    def symbol_select(self, symbol, enable):
        return self._record("symbol_select", True)

    def symbol_info(self, symbol):
        return self._record("symbol_info", self.symbol)

    def symbol_info_tick(self, symbol):
        return self._record("symbol_info_tick", self.tick)

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        self.rates_request = (symbol, timeframe, start, count)
        return self._record("copy_rates_from_pos", self.rates[-count:])

    def order_calc_margin(self, action, symbol, volume, price):
        self.margin_request = (action, symbol, volume, price)
        return self._record("order_calc_margin", self.margin)

    def positions_get(self, symbol=None):
        return self._record("positions_get", self.open_positions)

    def orders_get(self, symbol=None):
        return self._record("orders_get", self.orders)

    def order_send(self, request):
        self.sent.append(dict(request))
        if isinstance(self.send_result, Exception):
            raise self.send_result
        return self.send_result

    def history_deals_get(self, date_from, date_to):
        self.history_range = (date_from, date_to)
        return self._record("history_deals_get", self.deals)

    def history_orders_get(self, date_from, date_to):
        self.history_range = (date_from, date_to)
        return self._record("history_orders_get", self.history_orders)


CREDS = Credentials(login=LOGIN, password=PASSWORD, server=SERVER)


def make_config(timezone_name="UTC", allow_live=False):
    return BrokerConfig(
        symbol="XAUUSDm",
        server_timezone=timezone_name,
        allow_live=allow_live,
        magic=260044,
        deviation=20,
        market_filling="IOC",
        pending_filling="RETURN",
        max_comment_length=24,
    )


def make_broker(fake=None, timezone_name="UTC", allow_live=False, connect=True):
    fake = fake or FakeMT5()
    broker = MT5Broker(fake, make_config(timezone_name, allow_live), CREDS, clock=lambda: NOW)
    if connect:
        broker.connect()
    return broker, fake


# --- Time conversion ---------------------------------------------------------------


def test_server_time_to_utc():
    assert server_epoch_to_utc(wall_epoch("2026-01-07T10:00"), "UTC") == datetime(2026, 1, 7, 10, tzinfo=timezone.utc)
    # XM-style server: Europe/Athens is UTC+2 in winter, UTC+3 in summer.
    assert server_epoch_to_utc(wall_epoch("2026-01-07T10:00"), "Europe/Athens") == datetime(
        2026, 1, 7, 8, tzinfo=timezone.utc
    )
    assert server_epoch_to_utc(wall_epoch("2026-07-07T10:00"), "Europe/Athens") == datetime(
        2026, 7, 7, 7, tzinfo=timezone.utc
    )


def test_candle_and_tick_times_use_server_timezone():
    broker, _ = make_broker(timezone_name="Europe/Athens")
    candles = broker.candles(Timeframe.M5, 2)
    assert candles[0].open_time == datetime(2026, 10, 20, 7, 50, tzinfo=timezone.utc)  # EEST = UTC+3
    assert broker.tick().time == datetime(2026, 10, 20, 8, 0, 0, 250000, tzinfo=timezone.utc)


# --- Connection and demo guard -------------------------------------------------------


def test_connect_demo_account():
    broker, fake = make_broker()
    assert fake.init_kwargs == {"login": LOGIN, "password": PASSWORD, "server": SERVER}
    assert "symbol_select" in fake.calls
    broker.disconnect()
    assert fake.calls[-1] == "shutdown"


def test_live_account_refused_when_allow_live_false():
    fake = FakeMT5(trade_mode=FakeMT5.ACCOUNT_TRADE_MODE_REAL)
    with pytest.raises(BrokerError, match="not demo"):
        make_broker(fake)
    assert fake.calls[-1] == "shutdown"
    broker, _ = make_broker(FakeMT5(trade_mode=FakeMT5.ACCOUNT_TRADE_MODE_REAL), allow_live=True)
    assert broker.account_state().is_demo is False


def test_server_mismatch_refused():
    with pytest.raises(BrokerError, match="MT5_SERVER"):
        make_broker(FakeMT5(server="Other-Server"))


def test_reads_require_connection():
    broker, _ = make_broker(connect=False)
    with pytest.raises(BrokerError, match="not connected"):
        broker.account_state()


# --- Fail-closed -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("call", "mt5_name"),
    [
        (lambda b: b.account_state(), "account_info"),
        (lambda b: b.symbol_spec(), "symbol_info"),
        (lambda b: b.tick(), "symbol_info_tick"),
        (lambda b: b.candles(Timeframe.M5, 2), "copy_rates_from_pos"),
        (lambda b: b.margin_per_lot(Direction.BUY), "order_calc_margin"),
        (lambda b: b.positions(), "positions_get"),
        (lambda b: b.pending_orders(), "orders_get"),
    ],
)
def test_none_reply_raises_broker_error_with_code(call, mt5_name):
    broker, fake = make_broker()
    fake.none_for.add(mt5_name)
    fake.error = (-10004, "No IPC connection")
    with pytest.raises(BrokerError) as info:
        call(broker)
    assert info.value.code == -10004


def test_initialize_none_raises():
    fake = FakeMT5()
    fake.none_for.add("initialize")
    with pytest.raises(BrokerError):
        make_broker(fake)


def test_unusable_data_gives_no_partial_result():
    broker, fake = make_broker()
    fake.open_positions = fake.open_positions + (
        SimpleNamespace(ticket=13, symbol="XAUUSDm", type=9, volume=0.01, price_open=4000.0,
                        time_msc=0, sl=0.0, tp=0.0, magic=2026, comment="", profit=0.0),
    )
    with pytest.raises(BrokerError, match="unusable position"):
        broker.positions()
    fake.orders = fake.orders + (
        SimpleNamespace(ticket=22, symbol="XAUUSDm", type=FakeMT5.ORDER_TYPE_BUY_STOP_LIMIT, volume_current=0.01,
                        price_open=4000.0, time_setup_msc=0, sl=0.0, tp=0.0, magic=2026, comment=""),
    )
    with pytest.raises(BrokerError, match="unusable pending order"):
        broker.pending_orders()
    fake.rates[0]["high"] = 1.0  # invalid OHLC
    with pytest.raises(BrokerError, match="unusable candle"):
        broker.candles(Timeframe.M5, 2)


# --- Mapping MT5 -> models ---------------------------------------------------------------


def test_account_and_symbol_mapping():
    broker, _ = make_broker()
    account = broker.account_state()
    assert (account.time, account.currency, account.balance, account.equity, account.margin_free, account.is_demo) == (
        NOW, "USD", 1000.0, 995.5, 990.0, True
    )
    spec = broker.symbol_spec()
    assert (spec.name, spec.digits, spec.point, spec.tick_size, spec.tick_value, spec.contract_size) == (
        "XAUUSDm", 3, 0.001, 0.001, 0.1, 100.0
    )
    assert (spec.volume_min, spec.volume_max, spec.volume_step, spec.stops_level, spec.freeze_level) == (
        0.01, 200.0, 0.01, 0, 0
    )


def test_tick_mapping():
    broker, _ = make_broker()
    tick = broker.tick()
    assert (tick.symbol, tick.bid, tick.ask) == ("XAUUSDm", 4100.0, 4100.24)
    assert tick.spread == pytest.approx(0.24)


def test_candles_drop_position_zero():
    broker, fake = make_broker()
    candles = broker.candles(Timeframe.M5, 2)
    assert fake.rates_request == ("XAUUSDm", FakeMT5.TIMEFRAME_M5, 0, 3)
    assert [c.open_time for c in candles] == [
        datetime(2026, 10, 20, 10, 50, tzinfo=timezone.utc),
        datetime(2026, 10, 20, 10, 55, tzinfo=timezone.utc),
    ]
    first = candles[0]
    assert (first.open, first.high, first.low, first.close, first.spread_points, first.tick_volume) == (
        4099.0, 4101.0, 4098.5, 4100.0, 240, 120
    )
    assert first.timeframe is Timeframe.M5


def test_margin_per_lot_uses_side_price():
    broker, fake = make_broker()
    assert broker.margin_per_lot(Direction.BUY) == 41.0
    assert fake.margin_request == (FakeMT5.ORDER_TYPE_BUY, "XAUUSDm", 1.0, 4100.24)
    broker.margin_per_lot(Direction.SELL)
    assert fake.margin_request == (FakeMT5.ORDER_TYPE_SELL, "XAUUSDm", 1.0, 4100.0)
    fake.margin = 0.0
    with pytest.raises(BrokerError):
        broker.margin_per_lot(Direction.BUY)


def test_positions_mapping_and_magic_filter():
    broker, _ = make_broker()
    assert len(broker.positions()) == 2
    (position,) = broker.positions(magic=2026)
    assert (position.ticket, position.direction, position.volume, position.open_price) == (
        11, Direction.SELL, 0.02, 4105.0
    )
    assert (position.sl, position.tp, position.magic, position.comment, position.profit) == (
        4110.0, None, 2026, "setup-1", -1.5
    )
    assert position.open_time == datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc)
    manual = broker.positions(magic=7)[0]
    assert manual.sl is None and manual.direction is Direction.BUY


def test_pending_orders_mapping_and_magic_filter():
    broker, _ = make_broker()
    (order,) = broker.pending_orders(magic=2026)
    assert (order.ticket, order.direction, order.order_type, order.volume, order.price) == (
        21, Direction.BUY, OrderType.LIMIT, 0.03, 4095.0
    )
    assert (order.sl, order.tp, order.comment) == (4090.0, 4110.0, "setup-2")
    assert order.time_setup == datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)
    assert broker.pending_orders(magic=999) == []




# --- Credentials never shown ---------------------------------------------------------------


def test_credentials_hidden_in_repr_logs_and_errors(caplog):
    assert PASSWORD not in repr(CREDS) and str(LOGIN) not in repr(CREDS)
    assert PASSWORD not in str(CREDS)
    caplog.set_level(logging.DEBUG)
    broker, fake = make_broker()
    assert PASSWORD not in repr(broker) and str(LOGIN) not in repr(broker)
    fake.none_for.add("account_info")
    fake.error = (-6, f"Authorization failed for {LOGIN} with {PASSWORD}")
    with pytest.raises(BrokerError) as info:
        broker.account_state()
    fake.none_for.add("initialize")
    with pytest.raises(BrokerError) as init_info:
        make_broker(fake)
    for text in (str(info.value), str(init_info.value), caplog.text):
        assert PASSWORD not in text and str(LOGIN) not in text


def test_credentials_from_env():
    env = parse_env_text(f"# demo\nMT5_LOGIN={LOGIN}\nMT5_PASSWORD='{PASSWORD}'\nMT5_SERVER={SERVER}\n")
    assert credentials_from_env(env) == CREDS
    with pytest.raises(ValueError) as info:
        credentials_from_env({"MT5_LOGIN": "abc", "MT5_PASSWORD": PASSWORD, "MT5_SERVER": "ISI_MT5_SERVER_DISINI"})
    assert "MT5_LOGIN" in str(info.value) and "MT5_SERVER" in str(info.value)
    assert PASSWORD not in str(info.value)


def test_repo_broker_config():
    config = load_broker_config(ROOT / "config" / "broker.toml")
    assert config == make_config()
    with pytest.raises(Exception):
        make_config(timezone_name="Mars/Base")
    with pytest.raises(ValueError):
        broker_config_from_mapping({k: v for k, v in vars(config).items() if k != "magic"})
    with pytest.raises(ValueError):
        broker_config_from_mapping(dict(vars(config), market_filling="BOC"))


# --- scripts/broker_check.py ------------------------------------------------------------------


def load_check_script():
    spec = importlib.util.spec_from_file_location("broker_check_under_test", ROOT / "scripts" / "broker_check.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_broker_check_summary_has_no_credentials():
    check = load_check_script()
    broker, _ = make_broker()
    lines = check.run_check(broker)
    text = "\n".join(lines)
    assert "positions: 2; pending orders: 1" in text
    assert PASSWORD not in text and str(LOGIN) not in text


def test_broker_check_refuses_non_demo():
    check = load_check_script()
    broker, _ = make_broker(FakeMT5(trade_mode=FakeMT5.ACCOUNT_TRADE_MODE_REAL), allow_live=True)
    with pytest.raises(BrokerError, match="demo"):
        check.run_check(broker)


# --- v2 order functions (D-044) ------------------------------------------------------------


def send_result(retcode=10009, order=501, deal=601, comment="ok"):
    return SimpleNamespace(retcode=retcode, order=order, deal=deal, comment=comment)


def test_send_market_buy_request():
    broker, fake = make_broker()
    reply = broker.send_market(Direction.BUY, 0.01, sl=4095.0, tp=4110.0, comment="BS2-2610210735")
    request = fake.sent[-1]
    assert request == {
        "action": FakeMT5.TRADE_ACTION_DEAL,
        "symbol": "XAUUSDm",
        "volume": 0.01,
        "type": FakeMT5.ORDER_TYPE_BUY,
        "price": 4100.24,  # ask
        "deviation": 20,
        "type_filling": FakeMT5.ORDER_FILLING_IOC,
        "sl": 4095.0,
        "magic": 260044,
        "comment": "BS2-2610210735",
        "type_time": FakeMT5.ORDER_TIME_GTC,
        "tp": 4110.0,
    }
    assert (reply.action, reply.retcode, reply.order, reply.deal, reply.comment) == ("send_market", 10009, 501, 601, "ok")
    assert reply.request == request and reply.time == NOW and reply.error == ""


def test_send_market_sell_uses_bid_and_omits_missing_tp():
    broker, fake = make_broker()
    broker.send_market(Direction.SELL, 0.02, sl=4105.0)
    request = fake.sent[-1]
    assert request["type"] == FakeMT5.ORDER_TYPE_SELL and request["price"] == 4100.0
    assert "tp" not in request


def test_send_limit_request_uses_pending_filling():
    broker, fake = make_broker()
    reply = broker.send_limit(Direction.SELL, 0.01, price=4120.0, sl=4125.0, tp=4110.0, comment="SS2-2610210740")
    request = fake.sent[-1]
    assert request["action"] == FakeMT5.TRADE_ACTION_PENDING
    assert request["type"] == FakeMT5.ORDER_TYPE_SELL_LIMIT
    assert request["price"] == 4120.0 and request["type_filling"] == FakeMT5.ORDER_FILLING_RETURN
    assert "deviation" not in request and request["magic"] == 260044
    assert reply.action == "send_limit"


def test_modify_close_cancel_requests():
    broker, fake = make_broker()
    broker.modify_sltp(11, sl=4108.0, tp=None)
    assert fake.sent[-1] == {
        "action": FakeMT5.TRADE_ACTION_SLTP, "symbol": "XAUUSDm", "position": 11, "sl": 4108.0, "tp": 0.0, "magic": 260044,
    }
    broker.close_position(11, comment="close")  # SELL position 0.02 -> BUY at ask
    request = fake.sent[-1]
    assert (request["action"], request["position"], request["volume"]) == (FakeMT5.TRADE_ACTION_DEAL, 11, 0.02)
    assert (request["type"], request["price"]) == (FakeMT5.ORDER_TYPE_BUY, 4100.24)
    assert request["type_filling"] == FakeMT5.ORDER_FILLING_IOC and request["magic"] == 260044
    broker.cancel_order(21)
    assert fake.sent[-1] == {"action": FakeMT5.TRADE_ACTION_REMOVE, "order": 21, "magic": 260044}


@pytest.mark.parametrize(
    "call",
    [
        lambda b: b.send_market(Direction.BUY, 0.01, sl=None),
        lambda b: b.send_limit(Direction.BUY, 0.01, price=4090.0, sl=None),
        lambda b: b.modify_sltp(11, sl=None),
        lambda b: b.send_market(Direction.BUY, 0.01, sl=4095.0, comment="x" * 25),
        lambda b: b.close_position(11, comment="x" * 25),
        lambda b: b.send_order(OrderType.STOP, Direction.BUY, 0.01, sl=4095.0, price=4110.0),
        lambda b: b.send_market(Direction.BUY, 0.0, sl=4095.0),
        lambda b: b.send_limit(Direction.BUY, 0.01, price=None, sl=4085.0),
        lambda b: b.close_position(999),
        lambda b: b.cancel_order(0),
    ],
    ids=["no-sl", "limit-no-sl", "modify-no-sl", "comment-25", "close-comment-25", "stop", "volume-0",
         "limit-no-price", "unknown-position", "bad-ticket"],
)
def test_unsendable_requests_never_call_order_send(call):
    broker, fake = make_broker()
    with pytest.raises(BrokerError, match="not sent"):
        call(broker)
    assert fake.sent == []


def test_comment_of_24_characters_is_sent():
    broker, fake = make_broker()
    broker.send_market(Direction.BUY, 0.01, sl=4095.0, comment="x" * 24)
    assert fake.sent[-1]["comment"] == "x" * 24


def test_none_and_exception_become_reply_with_retcode_none():
    broker, fake = make_broker()
    fake.send_result = None
    fake.error = (-2, "Invalid params")
    reply = broker.send_market(Direction.BUY, 0.01, sl=4095.0)
    assert reply.retcode is None and reply.order is None and "last_error -2" in reply.error
    fake.send_result = RuntimeError("terminal gone")
    reply = broker.send_market(Direction.BUY, 0.01, sl=4095.0)
    assert reply.retcode is None and reply.error == "order_send raised RuntimeError"


def test_reply_is_raw_not_classified():
    broker, fake = make_broker()
    fake.send_result = send_result(retcode=10031, order=0, deal=0, comment="No connection")
    reply = broker.send_market(Direction.BUY, 0.01, sl=4095.0)
    assert (reply.retcode, reply.order, reply.deal, reply.comment) == (10031, None, None, "No connection")
    assert not hasattr(reply, "outcome")


def test_credentials_never_in_reply(caplog):
    caplog.set_level(logging.DEBUG)
    broker, fake = make_broker()
    fake.send_result = send_result(comment=f"login {LOGIN} pass {PASSWORD}")
    reply = broker.send_market(Direction.BUY, 0.01, sl=4095.0)
    for text in (repr(reply), str(reply.request), reply.comment, caplog.text):
        assert PASSWORD not in text and str(LOGIN) not in text


def test_broker_has_no_retry_or_classification():
    names = {name for name in dir(MT5Broker) if not name.startswith("_")}
    assert not {n for n in names if "retry" in n or "classif" in n or "outcome" in n}


def test_order_functions_require_connection():
    broker, fake = make_broker(connect=False)
    with pytest.raises(BrokerError, match="not connected"):
        broker.send_market(Direction.BUY, 0.01, sl=4095.0)
    assert fake.sent == []


# --- v2 history (D-044) ------------------------------------------------------------------------


def test_deals_history_mapping_and_magic_filter():
    broker, fake = make_broker()
    since = datetime(2026, 10, 20, tzinfo=timezone.utc)
    deals = broker.deals_history(260044, since)
    assert fake.history_range == (since, NOW)
    assert [(d.ticket, d.entry, d.direction) for d in deals] == [(601, DealEntry.IN, Direction.BUY), (602, DealEntry.OUT, Direction.SELL)]
    first = deals[0]
    assert (first.order, first.position_id, first.volume, first.price, first.comment) == (501, 701, 0.01, 4100.24, "BS2-2610210735")
    assert first.time == datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)


def test_orders_history_mapping_and_magic_filter():
    broker, fake = make_broker()
    (order,) = broker.orders_history(260044, datetime(2026, 10, 20, tzinfo=timezone.utc))
    assert (order.ticket, order.position_id, order.direction, order.order_type) == (501, 701, Direction.BUY, OrderType.MARKET)
    assert (order.volume, order.state, order.sl, order.tp) == (0.01, 4, 4095.0, None)
    assert order.time_done == datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)


def test_history_none_and_naive_range_raise():
    broker, fake = make_broker()
    with pytest.raises(BrokerError):
        broker.deals_history(260044, datetime(2026, 10, 20))
    fake.none_for.add("history_deals_get")
    with pytest.raises(BrokerError):
        broker.deals_history(260044, datetime(2026, 10, 20, tzinfo=timezone.utc))
