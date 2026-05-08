from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DNSEConfig:
    api_key: str
    api_secret: str
    base_url: str = "https://openapi.dnse.com.vn"
    algorithm: str = "hmac-sha256"
    hmac_nonce_enabled: bool = True
    timeout_seconds: float = 30.0
    show_log: bool = False

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        if not self.api_key:
            raise ValueError("api_key is required")
        if not self.api_secret:
            raise ValueError("api_secret is required")
