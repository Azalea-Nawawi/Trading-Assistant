"""Broker errors (D-041). Messages never contain credentials."""

from __future__ import annotations


class BrokerError(Exception):
    """A broker call failed or returned unusable data (fail-closed, D-041).

    ``code`` is the MetaTrader5 ``last_error`` code when available.
    """

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message if code is None else f"{message} (last_error {code})")
        self.code = code
