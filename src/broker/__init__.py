"""MetaTrader 5 broker access (D-010, D-041); the only package allowed to use MetaTrader5.

v1 is read-only. The MetaTrader5 module is injected into MT5Broker.
"""

from .client import MT5Broker, load_mt5_module, server_epoch_to_utc
from .config import BrokerConfig, broker_config_from_mapping, load_broker_config
from .credentials import Credentials, credentials_from_env, parse_env_text
from .errors import BrokerError

__all__ = [
    "BrokerConfig",
    "BrokerError",
    "Credentials",
    "MT5Broker",
    "broker_config_from_mapping",
    "credentials_from_env",
    "load_broker_config",
    "load_mt5_module",
    "parse_env_text",
    "server_epoch_to_utc",
]
