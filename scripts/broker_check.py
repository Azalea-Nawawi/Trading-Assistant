"""Verify src/broker v1 (read-only) on the Exness demo account (D-041).

Calls every v1 function once and prints a summary without login, password,
or account number. Refuses non-demo accounts, whatever ``allow_live`` says.
Never sends, modifies, closes, or cancels orders.

Run on Windows with the MT5 terminal installed:

    python scripts/broker_check.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.broker import (  # noqa: E402
    BrokerError,
    MT5Broker,
    credentials_from_env,
    load_broker_config,
    parse_env_text,
)
from src.models import Direction, Timeframe  # noqa: E402

DEFAULT_CONFIG = ROOT / "config" / "broker.toml"
DEFAULT_ENV = ROOT / ".env"
CANDLE_COUNT = 5


def run_check(broker: MT5Broker) -> list[str]:
    """Call every v1 read and return summary lines (no credentials or account number)."""
    account = broker.account_state()
    if not account.is_demo:
        raise BrokerError("broker_check only runs on a demo account")
    spec = broker.symbol_spec()
    tick = broker.tick()
    candles = broker.candles(Timeframe.M5, CANDLE_COUNT)
    margin_buy = broker.margin_per_lot(Direction.BUY)
    margin_sell = broker.margin_per_lot(Direction.SELL)
    positions = broker.positions()
    pending = broker.pending_orders()
    last = candles[-1] if candles else None
    return [
        f"account: demo={account.is_demo} currency={account.currency} equity={account.equity:.2f}",
        f"symbol: {spec.name} digits={spec.digits} point={spec.point} tick_size={spec.tick_size} "
        f"tick_value={spec.tick_value} contract={spec.contract_size} "
        f"volume={spec.volume_min}-{spec.volume_max} step {spec.volume_step} "
        f"stops_level={spec.stops_level} freeze_level={spec.freeze_level}",
        f"tick: {tick.time.isoformat()} bid={tick.bid} ask={tick.ask} spread={tick.spread:.3f}",
        f"candles M5: {len(candles)} closed; last open {last.open_time.isoformat() if last else '-'} UTC",
        f"margin per lot: BUY {margin_buy:.2f}, SELL {margin_sell:.2f} {account.currency}",
        f"positions: {len(positions)}; pending orders: {len(pending)}",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="src/broker v1 read-only check (D-041)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV)
    args = parser.parse_args(argv)

    config = load_broker_config(args.config)
    try:
        credentials = credentials_from_env(parse_env_text(args.env.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        print(f"STOP: {error}", file=sys.stderr)
        return 2

    import MetaTrader5 as mt5  # Windows only (requirements-mt5.txt, D-028)

    broker = MT5Broker(mt5, config, credentials)
    try:
        broker.connect()
        for line in run_check(broker):
            print(line)
    except BrokerError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    finally:
        broker.disconnect()
    print("OK: semua fungsi broker v1 terbaca")
    return 0


if __name__ == "__main__":
    sys.exit(main())
