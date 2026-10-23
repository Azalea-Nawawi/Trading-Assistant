"""Command-line entry point for one semi-auto Trading Assistant cycle.

Run this script manually or from a scheduler; it parses the symbol, configures
logging, calls src.assistant.runner.run_once(), and prints the resulting plan.
It contains no analysis or order-execution logic.

Usage examples:
    python scripts/run_assistant.py
    python scripts/run_assistant.py --symbol XAUUSDm

This entry point follows Spesifikasi Final v1.0. It is semi-auto only: the bot
does not place, modify, or close trading orders, and the final decision remains
with the trader.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

# Make direct execution from the repository root work without installing a package.
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.assistant.runner import DEFAULT_SYMBOL, run_once


log = logging.getLogger(__name__)
VALID_STATUSES: Final[frozenset[str]] = frozenset({"VALID", "STANDBY"})


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    Returns:
        An argument parser accepting the MT5 symbol to analyze.
    """

    parser = argparse.ArgumentParser(
        description="Run one semi-auto Trading Assistant analysis cycle."
    )
    parser.add_argument(
        "--symbol",
        default=DEFAULT_SYMBOL,
        help=f"MT5 symbol to analyze (default: {DEFAULT_SYMBOL}).",
    )
    return parser


def _format_price(value: object) -> str:
    """Format a numeric price for terminal display.

    Args:
        value: Candidate numeric price.

    Returns:
        A two-decimal price string, or '-' when the value is unavailable.
    """

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:.2f}"
    return "-"


def _print_result(result: Mapping[str, object], symbol: str) -> None:
    """Print the planner result in a compact terminal-friendly format.

    Args:
        result: Complete result returned by runner.run_once().
        symbol: Symbol shown in the terminal banner.

    Returns:
        None.
    """

    status = result.get("status", "DATA_INVALID")
    plan = result.get("plan")
    plan_mapping = plan if isinstance(plan, Mapping) else {}

    direction = plan_mapping.get("direction")
    entry_zone = plan_mapping.get("entry_zone")
    entry_mapping = entry_zone if isinstance(entry_zone, Mapping) else {}

    print("=" * 40)
    print(f"  SEMI-AUTO ASSISTANT - {symbol}")
    print("=" * 40)
    print(f"Status     : {status}")
    print(f"Direction  : {direction or '-'}")

    if entry_mapping:
        low = _format_price(entry_mapping.get("low"))
        high = _format_price(entry_mapping.get("high"))
        entry_text = f"{low} - {high}"
    else:
        entry_text = "-"
    print(f"Entry Zone : {entry_text}")
    print(f"SL Saran   : {_format_price(plan_mapping.get('sl_suggested'))}")
    print(f"TP1        : {_format_price(plan_mapping.get('tp1'))}")
    print(f"TP2        : {_format_price(plan_mapping.get('tp2'))}")
    print()

    summary_text = result.get("summary_text")
    if isinstance(summary_text, str) and summary_text.strip():
        print(summary_text)
    else:
        print(f"Reason     : {result.get('reason', 'No summary returned.')}")

    print()
    print("=" * 40)


def main(argv: Sequence[str] | None = None) -> int:
    """Run one analysis cycle and return a process exit code.

    Args:
        argv: Optional argument sequence for tests or embedding. When omitted,
            argparse reads the process command line.

    Returns:
        0 for VALID or STANDBY results; 1 for errors, invalid data, or an
        unexpected planner status.
    """

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        # The runner owns all analysis and broker orchestration; this script only
        # requests the result without letting the runner print a duplicate summary.
        result = run_once(args.symbol, emit=False)
    except Exception:
        log.exception("Unable to run the assistant cycle.")
        print("Error: assistant cycle failed. Check the log for details.", file=sys.stderr)
        return 1

    _print_result(result, args.symbol)
    status = result.get("status")
    if status not in VALID_STATUSES:
        log.error("Assistant cycle finished with status %s.", status)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
