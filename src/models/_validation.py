"""Field checks used by the model dataclasses (D-039). Raise ValueError."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from .enums import Direction


def require_utc(name: str, value: datetime) -> None:
    """Times must be timezone-aware UTC; naive or other offsets are rejected."""
    if not isinstance(value, datetime):
        raise ValueError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware (UTC), got naive datetime")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be UTC, got offset {value.utcoffset()}")


def require_finite(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value!r}")


def require_positive(name: str, value: float) -> None:
    require_finite(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be > 0, got {value!r}")


def require_non_negative(name: str, value: float) -> None:
    require_finite(name, value)
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value!r}")


def require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def require_enum(name: str, value: object, enum_type: type) -> None:
    if not isinstance(value, enum_type):
        raise ValueError(f"{name} must be {enum_type.__name__}, got {value!r}")


def require_protective_sides(direction: Direction, price: float, sl: float, tp: float | None) -> None:
    """SL on the losing side and TP on the winning side of ``price``.

    BUY: sl < price < tp. SELL: tp < price < sl.
    """
    require_positive("sl", sl)
    if tp is not None:
        require_positive("tp", tp)
    if direction is Direction.BUY:
        if not sl < price:
            raise ValueError(f"BUY sl {sl} must be below price {price}")
        if tp is not None and not tp > price:
            raise ValueError(f"BUY tp {tp} must be above price {price}")
    else:
        if not sl > price:
            raise ValueError(f"SELL sl {sl} must be above price {price}")
        if tp is not None and not tp < price:
            raise ValueError(f"SELL tp {tp} must be below price {price}")
