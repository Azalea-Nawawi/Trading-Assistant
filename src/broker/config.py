"""Broker settings from config/broker.toml (D-041, D-044); no secrets here."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

FILLING_NAMES = ("FOK", "IOC", "RETURN")


@dataclass(frozen=True)
class BrokerConfig:
    """``server_timezone`` is an IANA zone (D-025); ``allow_live`` false
    refuses any non-demo account on connect. Order settings (D-043, D-044):
    ``magic`` marks bot orders, ``deviation`` is in points, filling names are
    MT5 ORDER_FILLING_* suffixes, ``max_comment_length`` caps comments."""

    symbol: str
    server_timezone: str
    allow_live: bool
    magic: int
    deviation: int
    market_filling: str
    pending_filling: str
    max_comment_length: int

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        ZoneInfo(self.server_timezone)  # raises for an unknown zone
        if not isinstance(self.allow_live, bool):
            raise ValueError("allow_live must be a bool")
        for name, minimum in (("magic", 1), ("deviation", 0), ("max_comment_length", 1)):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise ValueError(f"{name} must be an int >= {minimum}")
        for name in ("market_filling", "pending_filling"):
            if getattr(self, name) not in FILLING_NAMES:
                raise ValueError(f"{name} must be one of {FILLING_NAMES}")


def broker_config_from_mapping(data: dict[str, Any]) -> BrokerConfig:
    keys = {f.name for f in fields(BrokerConfig)}
    unknown, missing = sorted(set(data) - keys), sorted(keys - set(data))
    if unknown or missing:
        raise ValueError(f"broker config: missing {missing}, unknown {unknown}")
    return BrokerConfig(**data)


def load_broker_config(path: Path, symbol: str | None = None) -> BrokerConfig:
    """Load broker settings and optionally override the configured symbol.

    Args:
        path: Path to the TOML broker configuration.
        symbol: Requested MT5 symbol from the caller, or None to use the TOML
            value.

    Returns:
        A validated BrokerConfig whose symbol matches the explicit override
        when one is supplied.

    Raises:
        OSError: If the configuration file cannot be read.
        tomllib.TOMLDecodeError: If the file is not valid TOML.
        ValueError: If settings are missing, unknown, or invalid.
    """

    with open(path, "rb") as handle:
        data = tomllib.load(handle)
    if symbol is not None:
        data["symbol"] = symbol
    return broker_config_from_mapping(data)
