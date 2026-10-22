"""MT5 credentials from .env (D-003, D-041). Never logged or shown."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

ENV_KEYS = ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER")
PLACEHOLDER = re.compile(r"^ISI_[A-Z0-9_]*_DISINI$")
MASK = "***"


def parse_env_text(text: str) -> dict[str, str]:
    """Parse simple KEY=VALUE lines; ignores blanks and comments."""
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


@dataclass(frozen=True)
class Credentials:
    """Login, password, and server. ``repr`` masks login and password."""

    login: int = field(repr=False)
    password: str = field(repr=False)
    server: str

    def __repr__(self) -> str:
        return f"Credentials(login={MASK}, password={MASK}, server={self.server!r})"

    __str__ = __repr__

    def scrub(self, text: str) -> str:
        """Remove login and password from any text before it is shown."""
        for secret in (self.password, str(self.login)):
            if secret:
                text = text.replace(secret, MASK)
        return text


def credentials_from_env(env: Mapping[str, str]) -> Credentials:
    """Build Credentials; the error names missing keys, never their values."""
    unusable = [key for key in ENV_KEYS if not env.get(key) or PLACEHOLDER.match(env[key])]
    if "MT5_LOGIN" not in unusable and not env["MT5_LOGIN"].isdigit():
        unusable.append("MT5_LOGIN")
    if unusable:
        raise ValueError(f".env missing or invalid: {', '.join(unusable)}")
    return Credentials(login=int(env["MT5_LOGIN"]), password=env["MT5_PASSWORD"], server=env["MT5_SERVER"])
