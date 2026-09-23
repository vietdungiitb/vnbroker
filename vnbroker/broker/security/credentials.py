"""
Credential resolution for TCBS broker.

Handles secure credential loading from environment variables
with proper namespace separation from explorer/public lane.
"""

import os
from dataclasses import dataclass
from typing import Any, Optional


_ENV_PRIORITY = (
    "VNBROKER_BROKER_TCBS_API_KEY",
    "VNBROKER_TCBS_OPENAPI_API_KEY",
    "TCBS_OPENAPI_API_KEY",
    "TCBS_API_KEY",
)

_DEFAULT_BASE_URL = "https://openapi.tcbs.com.vn"
_DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class TCBSCredentialConfig:
    """
    TCBS Broker credential configuration.

    Uses dedicated namespace VNBROKER_BROKER_TCBS_* to avoid
    conflicts with explorer/public provider credentials.
    """

    api_key: str
    base_url: str = _DEFAULT_BASE_URL
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS
    auth_token: Optional[str] = None

    def __repr__(self) -> str:
        """Repr that redacts sensitive fields."""
        return (
            f"TCBSCredentialConfig(api_key=REDACTED, "
            f"base_url={self.base_url!r}, "
            f"timeout_seconds={self.timeout_seconds!r}, "
            f"auth_token=REDACTED)"
        )

    @classmethod
    def from_env(cls) -> "TCBSCredentialConfig":
        """
        Load credentials from environment variables.

        Priority order:
        1. VNBROKER_BROKER_TCBS_API_KEY (standard namespace)
        2. VNBROKER_TCBS_OPENAPI_API_KEY (compat from explorer)
        3. TCBS_OPENAPI_API_KEY (legacy)
        4. TCBS_API_KEY (legacy final)

        Returns:
            TCBSCredentialConfig instance

        Raises:
            ValueError: If required credentials not found
        """
        api_key = (
            os.getenv("VNBROKER_BROKER_TCBS_API_KEY")
            or os.getenv("VNBROKER_TCBS_OPENAPI_API_KEY")
            or os.getenv("TCBS_OPENAPI_API_KEY")
            or os.getenv("TCBS_API_KEY")
        )

        if not api_key or not api_key.strip():
            raise ValueError(
                "Missing TCBS API key. Set one of: "
                "VNBROKER_BROKER_TCBS_API_KEY, "
                "VNBROKER_TCBS_OPENAPI_API_KEY, "
                "TCBS_OPENAPI_API_KEY, "
                "TCBS_API_KEY"
            )

        base_url = (
            os.getenv("VNBROKER_BROKER_TCBS_BASE_URL")
            or os.getenv("TCBS_OPENAPI_BASE_URL")
            or _DEFAULT_BASE_URL
        ).rstrip("/")

        timeout_seconds = float(
            os.getenv("VNBROKER_BROKER_TCBS_TIMEOUT_SECONDS")
            or _DEFAULT_TIMEOUT_SECONDS
        )

        auth_token = os.getenv("VNBROKER_BROKER_TCBS_AUTH_TOKEN") or os.getenv(
            "TCBS_AUTH_TOKEN"
        )

        return cls(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            auth_token=auth_token,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TCBSCredentialConfig":
        """Create from dictionary (for testing)."""
        return cls(
            api_key=data.get("api_key", ""),
            base_url=data.get("base_url", _DEFAULT_BASE_URL),
            timeout_seconds=data.get("timeout_seconds", _DEFAULT_TIMEOUT_SECONDS),
            auth_token=data.get("auth_token"),
        )


@dataclass(frozen=True)
class SSICredentialConfig:
    """
    SSI Broker credential configuration (native FastConnect v3).

    Namespace VNBROKER_BROKER_SSI_* tách biệt lane khác.
    api_key + api_secret bắt buộc (kể cả market-data-only);
    client_id cần cho balance/positions; private_key cần cho write ký RSA.
    """

    api_key: str
    api_secret: str
    client_id: str = ""
    private_key: str = ""
    api_url: str = "https://api.ssi.com.vn"
    stream_url: str = "wss://stream.ssi.com.vn/ws/v3"
    device_id: str = "A1:B2:C3:D4:E5:F6"
    timeout_seconds: float = 60.0
    rate_limit_rps: float = 10.0
    max_retries: int = 5

    def __repr__(self) -> str:
        """Repr redact toàn bộ secret."""
        return (
            "SSICredentialConfig(api_key=REDACTED, api_secret=REDACTED, "
            f"client_id={self.client_id!r}, private_key=REDACTED, "
            f"api_url={self.api_url!r}, stream_url={self.stream_url!r}, "
            f"device_id={self.device_id!r}, "
            f"timeout_seconds={self.timeout_seconds!r}, "
            f"rate_limit_rps={self.rate_limit_rps!r}, "
            f"max_retries={self.max_retries!r})"
        )

    @classmethod
    def from_env(cls) -> "SSICredentialConfig":
        """
        Load từ biến môi trường VNBROKER_BROKER_SSI_*.

        Raises:
            ValueError: Nếu thiếu api_key hoặc api_secret.
        """
        api_key = os.getenv("VNBROKER_BROKER_SSI_API_KEY") or ""
        api_secret = os.getenv("VNBROKER_BROKER_SSI_API_SECRET") or ""
        if not api_key.strip() or not api_secret.strip():
            raise ValueError(
                "Missing SSI credentials. Set VNBROKER_BROKER_SSI_API_KEY "
                "and VNBROKER_BROKER_SSI_API_SECRET"
            )
        return cls(
            api_key=api_key,
            api_secret=api_secret,
            client_id=os.getenv("VNBROKER_BROKER_SSI_CLIENT_ID") or "",
            private_key=os.getenv("VNBROKER_BROKER_SSI_PRIVATE_KEY") or "",
            api_url=(
                os.getenv("VNBROKER_BROKER_SSI_API_URL") or "https://api.ssi.com.vn"
            ).rstrip("/"),
            stream_url=(
                os.getenv("VNBROKER_BROKER_SSI_STREAM_URL")
                or "wss://stream.ssi.com.vn/ws/v3"
            ),
            device_id=(
                os.getenv("VNBROKER_BROKER_SSI_DEVICE_ID") or "A1:B2:C3:D4:E5:F6"
            ),
            timeout_seconds=float(
                os.getenv("VNBROKER_BROKER_SSI_TIMEOUT_SECONDS") or 60.0
            ),
            rate_limit_rps=float(
                os.getenv("VNBROKER_BROKER_SSI_RATE_LIMIT_RPS") or 10.0
            ),
            max_retries=int(os.getenv("VNBROKER_BROKER_SSI_MAX_RETRIES") or 5),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SSICredentialConfig":
        """Create from dictionary (for testing)."""
        return cls(
            api_key=data.get("api_key", ""),
            api_secret=data.get("api_secret", ""),
            client_id=data.get("client_id", ""),
            private_key=data.get("private_key", ""),
            api_url=data.get("api_url", "https://api.ssi.com.vn"),
            stream_url=data.get("stream_url", "wss://stream.ssi.com.vn/ws/v3"),
            device_id=data.get("device_id", "A1:B2:C3:D4:E5:F6"),
            timeout_seconds=data.get("timeout_seconds", 60.0),
            rate_limit_rps=data.get("rate_limit_rps", 10.0),
            max_retries=data.get("max_retries", 5),
        )


def resolve_tcbs_credentials(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    auth_token: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
) -> TCBSCredentialConfig:
    """
    Resolve TCBS credentials with explicit params taking priority over env.

    Args:
        api_key: Explicit API key (overrides env)
        base_url: Explicit base URL (overrides env)
        auth_token: Explicit auth token (overrides env)
        timeout_seconds: Explicit timeout (overrides env)

    Returns:
        Resolved TCBSCredentialConfig

    Raises:
        ValueError: If no api_key provided via params or env
    """
    # If explicit api_key provided, build config directly
    if api_key:
        if base_url:
            return TCBSCredentialConfig(
                api_key=api_key,
                base_url=base_url,
                timeout_seconds=timeout_seconds or _DEFAULT_TIMEOUT_SECONDS,
                auth_token=auth_token,
            )
        # Need to check env for base_url
        env_base_url = (
            os.getenv("VNBROKER_BROKER_TCBS_BASE_URL")
            or os.getenv("TCBS_OPENAPI_BASE_URL")
            or _DEFAULT_BASE_URL
        ).rstrip("/")
        env_timeout = float(
            os.getenv("VNBROKER_BROKER_TCBS_TIMEOUT_SECONDS")
            or _DEFAULT_TIMEOUT_SECONDS
        )
        env_auth_token = os.getenv("VNBROKER_BROKER_TCBS_AUTH_TOKEN") or os.getenv(
            "TCBS_AUTH_TOKEN"
        )
        return TCBSCredentialConfig(
            api_key=api_key,
            base_url=base_url or env_base_url,
            timeout_seconds=timeout_seconds or env_timeout,
            auth_token=auth_token or env_auth_token,
        )

    # No explicit api_key - try from_env
    try:
        config = TCBSCredentialConfig.from_env()
    except ValueError as e:
        raise ValueError(
            "Missing TCBS API key. Set one of: "
            "VNBROKER_BROKER_TCBS_API_KEY, "
            "VNBROKER_TCBS_OPENAPI_API_KEY, "
            "TCBS_OPENAPI_API_KEY, "
            "TCBS_API_KEY"
        ) from e

    if base_url or timeout_seconds or auth_token:
        return TCBSCredentialConfig(
            api_key=config.api_key,
            base_url=base_url or config.base_url,
            timeout_seconds=timeout_seconds or config.timeout_seconds,
            auth_token=auth_token if auth_token is not None else config.auth_token,
        )

    return config
