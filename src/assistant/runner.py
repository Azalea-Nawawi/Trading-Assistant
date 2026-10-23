"""Semi-auto analysis cycle entry point.

This module implements the runner flow from Spesifikasi Final v1.0:
read only closed candles from MT5, run H1/M30/M15/M5 analysis, run the News
filter, combine the results through assistant.planner.build_suggestion, then
print the Telegram-ready summary.

The runner uses UTC internally, never places or modifies orders, and returns
DATA_INVALID when required broker data or configuration cannot be obtained.
Credentials are loaded from .env and broker settings from config/broker.toml;
no credentials are hardcoded. Geopolitics and Macro filters are inactive in
v1.0 and are not part of the evaluation chain (DEC-002).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final

from src.analysis.h1_sr import calculate_h1_sr
from src.analysis.m15_bias import calculate_m15_bias
from src.analysis.m30_structure import calculate_m30_structure
from src.analysis.m5_rejection import calculate_m5_rejection
from src.assistant.planner import PlannerResult, build_suggestion
from src.broker import (
    MT5Broker,
    credentials_from_env,
    load_broker_config,
    load_mt5_module,
    parse_env_text,
)
from src.filters.news import DEFAULT_CALENDAR_PATH, check_news_filter
from src.models import Candle, Timeframe


DEFAULT_SYMBOL: Final[str] = "XAUUSDm"
DEFAULT_CONFIG_PATH: Final[Path] = Path("config") / "broker.toml"
DEFAULT_ENV_PATH: Final[Path] = Path(".env")
CANDLE_COUNTS: Final[dict[Timeframe, int]] = {
    Timeframe.H1: 60,
    Timeframe.M30: 50,
    Timeframe.M15: 60,
    Timeframe.M5: 15,
}

log = logging.getLogger(__name__)


class _StaleDataError(Exception):
    """Broker data is readable but too old to analyse (DATA_INVALID)."""


def _load_broker(symbol: str) -> MT5Broker:
    """Load non-secret config and credentials, then construct the read-only broker."""

    config = load_broker_config(DEFAULT_CONFIG_PATH)
    if config.symbol != symbol:
        config = replace(config, symbol=symbol)

    env_values = parse_env_text(DEFAULT_ENV_PATH.read_text(encoding="utf-8"))
    credentials = credentials_from_env(env_values)
    return MT5Broker(load_mt5_module(), config, credentials)


def _collect_candles(broker: MT5Broker) -> dict[Timeframe, list[Candle]]:
    """Fetch closed candles for each analysis timeframe from MT5."""

    # MT5Broker.candles drops the currently forming candle before returning.
    return {
        timeframe: broker.candles(timeframe, count)
        for timeframe, count in CANDLE_COUNTS.items()
    }


def _stale_data_reason(
    candles: dict[Timeframe, list[Candle]],
    now_utc: datetime,
) -> str | None:
    """Return why the candle data is stale, or None when every timeframe is fresh.

    The newest closed candle of each timeframe must be the one that closed
    within the last timeframe slot; otherwise the feed is frozen, the market is
    closed, or bars are missing (DEC-009, evaluation step 1).
    """

    for timeframe in CANDLE_COUNTS:
        series = candles.get(timeframe) or []
        if not series:
            return f"No closed {timeframe.value} candles were returned."
        length = timedelta(seconds=timeframe.seconds)
        newest_close = series[-1].open_time + length
        if newest_close < now_utc - length:
            return (
                f"{timeframe.value} data is stale: newest candle closed at "
                f"{newest_close.isoformat()}."
            )
    return None


def _invalid_result(reason: str) -> PlannerResult:
    """Create a planner-compatible failure result without fabricating analysis."""

    invalid_analysis = {"status": "DATA_INVALID", "reason": reason}
    unknown_filter = {"status": "NEWS_UNKNOWN", "reason": reason}
    return build_suggestion(
        h1=invalid_analysis,
        m30=invalid_analysis,
        m15=invalid_analysis,
        m5=invalid_analysis,
        news=unknown_filter,
        current_price=None,
    )


def _analyse_and_filter(
    candles: dict[Timeframe, list],
    now_utc: datetime,
    current_price: float,
) -> PlannerResult:
    """Run all analysis and filter modules, then pass their results to planner."""

    # Analysis is kept separate from broker reads so each module remains pure.
    h1 = calculate_h1_sr(candles[Timeframe.H1])
    m30 = calculate_m30_structure(candles[Timeframe.M30])
    m15 = calculate_m15_bias(candles[Timeframe.M15])

    m15_bias = m15["status"] if m15["status"] in ("BULLISH", "BEARISH", "NEUTRAL") else "NEUTRAL"
    m5 = calculate_m5_rejection(
        candles[Timeframe.M5],
        bias=m15_bias,
        h1_supports=h1["supports"],
        h1_resistances=h1["resistances"],
        m30_last_swing_high=m30["last_swing_high"],
        m30_prev_swing_high=m30["prev_swing_high"],
        m30_last_swing_low=m30["last_swing_low"],
        m30_prev_swing_low=m30["prev_swing_low"],
    )

    # News is the only active filter in v1.0 (DEC-002).
    news = check_news_filter(now_utc, DEFAULT_CALENDAR_PATH)

    # The planner applies the mandatory gate order and returns the final result.
    return build_suggestion(
        h1=h1,
        m30=m30,
        m15=m15,
        m5=m5,
        news=news,
        current_price=current_price,
    )


def _emit_summary(result: PlannerResult) -> None:
    """Print the final summary as the development notifier fallback."""

    try:
        print(result["summary_text"])
    except Exception:
        log.exception("runner: unable to print summary")


def run_once(
    symbol: str = DEFAULT_SYMBOL,
    *,
    emit: bool = True,
) -> dict[str, object]:
    """Run one complete semi-auto analysis cycle.

    Args:
        symbol: MT5 symbol to analyze. It defaults to XAUUSDm and overrides the
            non-secret symbol value loaded from config/broker.toml.
        emit: Whether to print summary_text as a notifier fallback. Defaults to
            True; CLI callers can set it to False to format the result themselves.

    Returns:
        A planner result containing analysis snapshots, filter snapshots,
        final status, optional plan, reason, and Telegram-ready summary_text.
        Configuration, broker, or data failures return status=DATA_INVALID.

    Raises:
        None. Operational exceptions are logged and converted to a
        DATA_INVALID planner result.
    """

    if not isinstance(symbol, str) or not symbol.strip():
        result = _invalid_result("Symbol must be a non-empty string.")
        if emit:
            _emit_summary(result)
        return dict(result)

    broker: MT5Broker | None = None
    try:
        now_utc = datetime.now(timezone.utc)

        # Entry point flow: config and connect, then read only closed candles.
        broker = _load_broker(symbol)
        broker.connect()
        candles = _collect_candles(broker)
        stale_reason = _stale_data_reason(candles, now_utc)
        if stale_reason is not None:
            raise _StaleDataError(stale_reason)
        # Bid matches the candle price basis; used for Entry Zone expiry (DEC-006).
        current_price = broker.tick().bid

        # Run analysis, filters, and the final planner in one deterministic cycle.
        result = _analyse_and_filter(candles, now_utc, current_price)
    except _StaleDataError as error:
        log.warning("runner: %s", error)
        result = _invalid_result(str(error))
    except Exception as error:
        log.exception("runner: analysis cycle failed: %s", error)
        result = _invalid_result(
            f"Analysis cycle failed safely with {type(error).__name__}."
        )
    finally:
        if broker is not None:
            try:
                broker.disconnect()
            except Exception:
                log.exception("runner: broker disconnect failed")

    if emit:
        _emit_summary(result)
    return dict(result)


__all__ = [
    "CANDLE_COUNTS",
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_ENV_PATH",
    "DEFAULT_SYMBOL",
    "run_once",
]
