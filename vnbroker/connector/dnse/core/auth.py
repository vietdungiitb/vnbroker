from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DNSEAuthContext:
    api_key: str
    api_secret: str
    trading_token: str | None = None
