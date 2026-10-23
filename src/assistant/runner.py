"""Semi-auto analysis cycle entry point.

This module implements the active runner flow from Spesifikasi Final v1.0:
read only closed candles from MT5, run H1/M30/M15/M5 analysis, run the active
News filter, combine those results through assistant.planner.build_suggestion,
then print the Telegram-ready summary.

The runner uses UTC internally, never places or modifies orders, and returns
DATA_INVALID when required broker data or configuration cannot be obtained.
Credentials are loaded from .env and broker settings from config/broker.toml;
no credentials are hardcoded.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
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
INACTIVE_FILTER_STATUS: Final[str] = "INACTIVE"
INACTIVE_FILTER_REASON: Final[str] = "Disabled in Spesifikasi Final v1.0."

log = logging.getLogger(__name__)


def _load_broker(symbol: str) -> MT5Broker:
    """Load non-secret config and credentials, then construct the read-only broker."""

    config = load_broker_config(DEFAULT_CONFIG_PATH, symbol=symbol)
    log.info("runner: using requested broker symbol=%s", config.symbol)

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


def _inactive_filter_result() -> dict[str, str]:
    """Return the non-evaluated filter snapshot used by v1.0."""

    return {
        "status": INACTIVE_FILTER_STATUS,
        "reason": INACTIVE_FILTER_REASON,
    }


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
    )


def _analyse_and_filter(
    candles: dict[Timeframe, list],
    now_utc: datetime,
) -> PlannerResult:
    """Run active analysis and News filtering, then pass results to planner."""

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

    # News is the only active external filter in v1.0.
    news = check_news_filter(now_utc, DEFAULT_CALENDAR_PATH)

    # The planner applies the active gate order and returns the final result.
    return build_suggestion(
        h1=h1,
        m30=m30,
        m15=m15,
        m5=m5,
        news=news,
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

        # Run analysis, filters, and the final planner in one deterministic cycle.
        result = _analyse_and_filter(candles, now_utc)
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
