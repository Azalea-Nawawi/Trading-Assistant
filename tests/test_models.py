"""Tests for src/models v1 (D-039): every validation passes and fails."""

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from src.models import (
    AccountState,
    Advice,
    Candle,
    Direction,
    KillSwitchLevel,
    LockStatus,
    AdvicePlan,
    AdviceStandby,
    Bias,
    NewsState,
    NewsStatus,
    ScheduledEvent,
    Session,
    Trend,
    OrderOutcome,
    OrderRequest,
    OrderResult,
    OrderStatus,
    OrderType,
    Position,
    RiskDecision,
    Signal,
    SymbolSpec,
    Timeframe,
)

UTC_TIME = datetime(2026, 10, 20, 8, 45, tzinfo=timezone.utc)
NAIVE_TIME = datetime(2026, 10, 20, 8, 45)
NON_UTC_TIME = datetime(2026, 10, 20, 8, 45, tzinfo=timezone(timedelta(hours=1)))


def candle(**overrides):
    values = dict(
        symbol="XAUUSDm",
        timeframe=Timeframe.M5,
        open_time=UTC_TIME,
        open=2000.0,
        high=2001.0,
        low=1999.0,
        close=2000.5,
        spread_points=179,
    )
    values.update(overrides)
    return Candle(**values)


def symbol_spec(**overrides):
    values = dict(
        name="XAUUSDm",
        digits=3,
        point=0.001,
        tick_size=0.001,
        tick_value=0.1,
        contract_size=100.0,
        volume_min=0.01,
        volume_max=200.0,
        volume_step=0.01,
    )
    values.update(overrides)
    return SymbolSpec(**values)


def account(**overrides):
    values = dict(time=UTC_TIME, currency="USD", balance=1000.0, equity=990.0, margin_free=900.0, is_demo=True)
    values.update(overrides)
    return AccountState(**values)


def signal(**overrides):
    values = dict(
        time=UTC_TIME,
        symbol="XAUUSDm",
        direction=Direction.BUY,
        entry=2000.0,
        sl=1995.0,
        tp=2010.0,
        setup_id="XAUUSDm-BUY-20261020T0845",
        reason_codes=("BIAS_H1_BUY",),
    )
    values.update(overrides)
    return Signal(**values)


def order_request(**overrides):
    values = dict(
        setup_id="XAUUSDm-BUY-20261020T0845",
        symbol="XAUUSDm",
        direction=Direction.BUY,
        order_type=OrderType.MARKET,
        volume=0.01,
        price=2000.0,
        sl=1995.0,
        tp=2010.0,
        magic=2026,
        comment="setup",
    )
    values.update(overrides)
    return OrderRequest(**values)


def position(**overrides):
    values = dict(
        ticket=1,
        symbol="XAUUSDm",
        direction=Direction.BUY,
        volume=0.01,
        open_price=2000.0,
        open_time=UTC_TIME,
        sl=1995.0,
    )
    values.update(overrides)
    return Position(**values)


def order_result(**overrides):
    values = dict(setup_id="s1", outcome=OrderOutcome.UNCERTAIN, time=UTC_TIME)
    values.update(overrides)
    return OrderResult(**values)


def advice(**overrides):
    """BUY advice of Semi-Auto Spec #1: E 2000,2, risk 2, TP1 1,5R, TP2 2,5R, LOW_ROOM."""
    values = dict(
        time=UTC_TIME,
        symbol="XAUUSDm",
        direction=Direction.BUY,
        entry_ref=2000.2,
        zone_low=1998.0,
        zone_high=2000.0,
        zone_level=1999.0,
        sl=1998.2,
        tp1=2003.2,
        tp2=2005.2,
        risk=2.0,
        risk_struct=2.0,
        risk_atr=2.8,
        opposite_level=2002.0,
        opposite_distance_r=0.9,
        low_room=True,
        cost_r=0.17,
        rr_net_tp1=1.33,
        rr_net_tp2=2.33,
        rr_net_opposite=0.73,
        reason_codes=("H1_BIAS_BULLISH", "LOW_ROOM"),
    )
    values.update(overrides)
    return Advice(**values)


ALL_FACTORIES = [candle, symbol_spec, account, signal, order_request, position, order_result, advice]


# --- Enums ------------------------------------------------------------------------


def test_enum_members_map_to_documented_terms():
    assert [o.value for o in OrderOutcome] == ["REJECTED_CONFIRMED", "SUCCESS", "UNCERTAIN"]
    assert [s.value for s in OrderStatus] == ["SENT", "PENDING", "FILLED", "REJECTED", "CANCELLED"]
    assert [s.value for s in LockStatus] == ["OPEN", "LOCKED_AUTO", "LOCKED_MANUAL"]
    assert [int(level) for level in KillSwitchLevel] == [0, 1, 2, 3]
    assert Timeframe.M5.seconds == 300 and Timeframe.H1.seconds == 3600
    assert Timeframe.M30.value == "M30" and Timeframe.M30.seconds == 1800


# --- Frozen -------------------------------------------------------------------------


@pytest.mark.parametrize("factory", ALL_FACTORIES + [lambda: RiskDecision("s1", approved=True, volume=0.01)])
def test_models_are_frozen(factory):
    obj = factory()
    first_field = dataclasses.fields(obj)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(obj, first_field, None)


# --- Time: timezone-aware UTC ------------------------------------------------------


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (candle, "open_time"),
        (account, "time"),
        (signal, "time"),
        (position, "open_time"),
        (order_result, "time"),
    ],
)
def test_time_must_be_utc_aware(factory, field):
    assert getattr(factory(**{field: UTC_TIME}), field) == UTC_TIME
    with pytest.raises(ValueError, match="naive"):
        factory(**{field: NAIVE_TIME})
    with pytest.raises(ValueError, match="UTC"):
        factory(**{field: NON_UTC_TIME})


# --- Candle: OHLC ------------------------------------------------------------------


def test_candle_valid_ohlc():
    assert candle(high=2000.5, low=2000.0).close == 2000.5  # high == close, low == open


@pytest.mark.parametrize(
    "overrides",
    [
        {"high": 2000.2},  # below close
        {"low": 2000.1},  # above open
        {"high": 1998.0, "low": 2002.0},
        {"open": 0.0},
        {"close": float("nan")},
        {"spread_points": -1},
    ],
)
def test_candle_invalid_ohlc(overrides):
    with pytest.raises(ValueError):
        candle(**overrides)


# --- SymbolSpec: volume range and step -----------------------------------------------


def test_symbol_spec_valid_volume_range():
    spec = symbol_spec(volume_min=0.01, volume_max=0.01)
    assert spec.volume_min == spec.volume_max


@pytest.mark.parametrize(
    "overrides",
    [{"volume_min": 1.0, "volume_max": 0.5}, {"volume_step": 0.0}, {"volume_step": -0.01}, {"point": 0.0}],
)
def test_symbol_spec_invalid_volume(overrides):
    with pytest.raises(ValueError):
        symbol_spec(**overrides)


# --- Signal and OrderRequest: SL/TP sides ---------------------------------------------


@pytest.mark.parametrize("factory, price_field", [(signal, "entry"), (order_request, "price")])
def test_sl_tp_on_correct_side(factory, price_field):
    factory(direction=Direction.BUY, **{price_field: 2000.0}, sl=1995.0, tp=2010.0)
    factory(direction=Direction.SELL, **{price_field: 2000.0}, sl=2005.0, tp=1990.0)
    factory(direction=Direction.BUY, **{price_field: 2000.0}, sl=1995.0, tp=None)


@pytest.mark.parametrize("factory, price_field", [(signal, "entry"), (order_request, "price")])
@pytest.mark.parametrize(
    ("direction", "sl", "tp"),
    [
        (Direction.BUY, 2005.0, 2010.0),  # SL above entry
        (Direction.BUY, 2000.0, 2010.0),  # SL at entry
        (Direction.BUY, 1995.0, 1990.0),  # TP below entry
        (Direction.SELL, 1995.0, 1990.0),  # SL below entry
        (Direction.SELL, 2005.0, 2010.0),  # TP above entry
    ],
)
def test_sl_tp_on_wrong_side_rejected(factory, price_field, direction, sl, tp):
    with pytest.raises(ValueError):
        factory(direction=direction, **{price_field: 2000.0}, sl=sl, tp=tp)


def test_order_request_without_sl_rejected():
    with pytest.raises(ValueError, match="requires an SL"):
        order_request(sl=None)


# --- Volume > 0 -----------------------------------------------------------------------


@pytest.mark.parametrize("factory", [order_request, position])
def test_volume_must_be_positive(factory):
    assert factory(volume=0.01).volume == 0.01
    for bad in (0.0, -0.01):
        with pytest.raises(ValueError):
            factory(volume=bad)


def test_risk_decision_volume():
    assert RiskDecision("s1", approved=True, volume=0.02).volume == 0.02
    assert RiskDecision("s1", approved=False, reason_codes=("LOT_MIN_ABOVE_BUDGET",)).volume is None
    with pytest.raises(ValueError):
        RiskDecision("s1", approved=True, volume=0.0)
    with pytest.raises(ValueError):
        RiskDecision("s1", approved=True)
    with pytest.raises(ValueError):
        RiskDecision("s1", approved=False, volume=0.01, reason_codes=("X",))
    with pytest.raises(ValueError):
        RiskDecision("s1", approved=False)


# --- Other fields -----------------------------------------------------------------------


def test_account_state_has_no_account_number():
    names = {f.name for f in dataclasses.fields(AccountState)}
    assert not names & {"login", "account", "account_number", "number"}


def test_position_without_sl_is_allowed_for_reconciliation():
    assert position(sl=None).sl is None  # D-011 condition 2 is represented, not rejected


def test_enum_fields_require_enum_values():
    with pytest.raises(ValueError):
        signal(direction="BUY")
    with pytest.raises(ValueError):
        order_result(outcome="SUCCESS")


# --- Tick and PendingOrder (D-041) ---------------------------------------------------------


def test_tick_validation():
    from src.models import Tick

    tick = Tick("XAUUSDm", UTC_TIME, 2000.0, 2000.24)
    assert tick.spread == pytest.approx(0.24)
    for args in ((UTC_TIME, 2000.3, 2000.24), (NAIVE_TIME, 2000.0, 2000.24), (UTC_TIME, 0.0, 2000.24)):
        with pytest.raises(ValueError):
            Tick("XAUUSDm", *args)
    with pytest.raises(dataclasses.FrozenInstanceError):
        tick.bid = 1.0


def test_pending_order_validation():
    from src.models import PendingOrder

    values = dict(ticket=21, symbol="XAUUSDm", direction=Direction.BUY, order_type=OrderType.LIMIT,
                  volume=0.01, price=1990.0, time_setup=UTC_TIME, sl=None)
    assert PendingOrder(**values).sl is None
    for overrides in ({"order_type": OrderType.MARKET}, {"volume": 0.0}, {"ticket": 0}, {"time_setup": NAIVE_TIME}):
        with pytest.raises(ValueError):
            PendingOrder(**dict(values, **overrides))


# --- BrokerReply, Deal, HistoryOrder (D-044) -------------------------------------------------


def test_broker_reply_validation():
    from src.models import BrokerReply

    reply = BrokerReply("send_market", UTC_TIME, {"action": 1}, None, error="order_send returned None")
    assert reply.retcode is None and reply.order is None
    for kwargs in ({"time": NAIVE_TIME}, {"retcode": "10009"}, {"request": None}, {"action": ""}):
        values = dict(action="send_market", time=UTC_TIME, request={}, retcode=10009)
        with pytest.raises(ValueError):
            BrokerReply(**dict(values, **kwargs))
    with pytest.raises(dataclasses.FrozenInstanceError):
        reply.retcode = 10009


def test_deal_and_history_order_validation():
    from src.models import Deal, DealEntry, HistoryOrder

    deal = Deal(1, 2, 3, "XAUUSDm", Direction.BUY, DealEntry.IN, 0.01, 2000.0, UTC_TIME)
    assert deal.entry is DealEntry.IN
    with pytest.raises(ValueError):
        Deal(1, 2, 3, "XAUUSDm", Direction.BUY, "IN", 0.01, 2000.0, UTC_TIME)
    order = HistoryOrder(5, 3, "XAUUSDm", Direction.SELL, OrderType.MARKET, 0.01, 0.0, 4, UTC_TIME, None)
    assert order.time_done is None
    with pytest.raises(ValueError):
        HistoryOrder(5, 3, "XAUUSDm", Direction.SELL, OrderType.MARKET, 0.01, 0.0, 4, NAIVE_TIME, None)


def test_execution_event_validation():
    from src.models import ExecutionEvent, ExecutionEventKind, OrderStatus

    event = ExecutionEvent("BS2-2610210735", UTC_TIME, ExecutionEventKind.FILLED, status=OrderStatus.FILLED, ticket=5)
    assert event.critical is False
    for overrides in ({"kind": "FILLED"}, {"time": NAIVE_TIME}, {"critical": 1}, {"setup_id": ""}, {"ticket": "5"}):
        values = dict(setup_id="BS2-2610210735", time=UTC_TIME, kind=ExecutionEventKind.FILLED)
        with pytest.raises(ValueError):
            ExecutionEvent(**dict(values, **overrides))


# --- Advice (Semi-Auto Spec #1, D-069) ----------------------------------------------


def test_advice_valid_buy_and_sell_without_opposite_level():
    assert advice().low_room is True
    sell = advice(
        direction=Direction.SELL, entry_ref=1999.8, zone_low=2000.0, zone_high=2002.0, zone_level=2001.0,
        sl=2001.8, tp1=1996.8, tp2=1994.8, opposite_level=None, opposite_distance_r=None,
        rr_net_opposite=None, low_room=False,
    )
    assert sell.direction is Direction.SELL


@pytest.mark.parametrize(
    "overrides",
    [
        {"time": NAIVE_TIME},
        {"symbol": ""},
        {"direction": "BUY"},
        {"sl": 2001.0},                       # SL on the winning side
        {"tp1": 1999.0},                      # TP1 on the losing side
        {"tp2": 2002.0},                      # TP2 not beyond TP1
        {"zone_level": 2001.0},               # level outside the zone
        {"risk": 0.0},
        {"cost_r": -0.1},
        {"opposite_level": None},             # opposite fields set together
        {"opposite_level": None, "opposite_distance_r": None, "rr_net_opposite": None},  # LOW_ROOM without level
        {"low_room": 1},
        {"reason_codes": ["LOW_ROOM"]},
        {"reason_codes": ("",)},
        {"rr_net_tp1": float("nan")},
    ],
)
def test_advice_rejects_invalid_fields(overrides):
    with pytest.raises(ValueError):
        advice(**overrides)


# --- NewsStatus (Semi-Auto F1, D-069) -------------------------------------------------


def test_news_status_valid_states():
    assert NewsStatus(NewsState.CLEAR).events == ()
    news = NewsStatus(NewsState.NEWS, ("GDP", "PCE"), UTC_TIME, -30.0)
    assert news.state is NewsState.NEWS and news.minutes == -30.0
    assert NewsStatus(NewsState.NO_CALENDAR).event_time is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"state": "NEWS"},
        {"state": NewsState.NEWS},                                         # NEWS without its event
        {"state": NewsState.CLEAR, "events": ("NFP",)},                     # partial details
        {"state": NewsState.CLEAR, "events": ["NFP"], "event_time": UTC_TIME, "minutes": 1.0},
        {"state": NewsState.CLEAR, "events": ("",), "event_time": UTC_TIME, "minutes": 1.0},
        {"state": NewsState.CLEAR, "events": ("NFP",), "event_time": NAIVE_TIME, "minutes": 1.0},
        {"state": NewsState.CLEAR, "events": ("NFP",), "event_time": UTC_TIME, "minutes": float("inf")},
    ],
)
def test_news_status_rejects_invalid(kwargs):
    with pytest.raises(ValueError):
        NewsStatus(**kwargs)


# --- RENCANA / STANDBY models (Semi-Auto section 5, D-070) ---------------------------------


def plan_model(**overrides):
    values = dict(
        time=UTC_TIME, symbol="XAUUSDm", session=Session.LONDON, bias_h1=Bias.BULLISH, bias_m30=Trend.UPTREND,
        bias_m15=Bias.BULLISH, overall=Bias.BULLISH, supports=(1999.0,), resistances=(2002.0,),
        news=(ScheduledEvent(UTC_TIME, ("NFP",)),), news_state=NewsState.CLEAR, spread_points=200.0,
    )
    values.update(overrides)
    return AdvicePlan(**values)


def test_plan_standby_and_event_valid():
    assert plan_model().overall is Bias.BULLISH
    assert AdviceStandby(UTC_TIME, "XAUUSDm", "F2_SPREAD").detail == ""
    assert AdviceStandby(UTC_TIME, "XAUUSDm", "F1_NEWS", "x", NewsStatus(NewsState.CLEAR)).news.state is NewsState.CLEAR


@pytest.mark.parametrize(
    "build",
    [
        lambda: plan_model(time=NAIVE_TIME),
        lambda: plan_model(session="LONDON"),
        lambda: plan_model(overall="BULLISH"),
        lambda: plan_model(supports=[1999.0]),
        lambda: plan_model(resistances=(0.0,)),
        lambda: plan_model(news=("NFP",)),
        lambda: plan_model(spread_points=-1.0),
        lambda: ScheduledEvent(UTC_TIME, ()),
        lambda: ScheduledEvent(NAIVE_TIME, ("NFP",)),
        lambda: AdviceStandby(UTC_TIME, "XAUUSDm", ""),
        lambda: AdviceStandby(UTC_TIME, "XAUUSDm", "X", None),
        lambda: AdviceStandby(UTC_TIME, "XAUUSDm", "X", "", "NEWS"),
    ],
)
def test_plan_standby_and_event_reject_invalid(build):
    with pytest.raises(ValueError):
        build()
