"""
vnbroker/explorer/ssi/_auth.py

Shared market-data-only auth for the SSI explorer lane.

One cached access token per credential pair (module-level, thread-safe).
Wraps the broker lane (SSICredentialConfig + BrokerSession + SSIHttpClient
+ SSIAuthService) without duplicating any wire logic.

SECURITY: never log api_key/api_secret/token. Tests use fake keys only.
"""

from __future__ import annotations

import os
import threading
from typing import Dict, Optional, Tuple

from vnbroker.broker.exceptions import BrokerError
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.ssi._transport import SSIHttpClient
from vnbroker.broker.ssi.auth import SSIAuthService
from vnbroker.broker.ssi.exceptions import BrokerSessionExpiredError
from vnbroker.broker.ssi.market import SSIMarketService
from vnbroker.core.utils.logger import get_logger

logger = get_logger(__name__)

_MISSING_KEY_MESSAGE = (
    "SSI cần api_key và api_secret. "
    "Đặt biến môi trường VNBROKER_BROKER_SSI_API_KEY và "
    "VNBROKER_BROKER_SSI_API_SECRET hoặc truyền trực tiếp. "
    "Xem hướng dẫn đăng ký trong docs/SSI_USAGE_GUIDE.md."
)


def resolve_credentials(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Resolve SSI credentials: explicit params first, then env.

    Raises:
        ValueError: If either credential is missing.
    """
    key = (api_key or os.getenv("VNBROKER_BROKER_SSI_API_KEY") or "").strip()
    secret = (api_secret or os.getenv("VNBROKER_BROKER_SSI_API_SECRET") or "").strip()
    if not key or not secret:
        raise ValueError(_MISSING_KEY_MESSAGE)
    return key, secret


class SSIExplorerSession:
    """
    Market-data-only SSI session for explorer providers.

    Lazy: no network traffic until the first ``ensure_token()`` call.
    Thread-safe: concurrent callers share a single authenticate/refresh.

    Args:
        api_key: SSI consumerID (falls back to ``VNBROKER_BROKER_SSI_API_KEY``).
        api_secret: SSI consumerSecret (falls back to ``VNBROKER_BROKER_SSI_API_SECRET``).
        api_url: Override REST base URL (default FastConnect v3).
        _session: Test hook — inject a ``BrokerSession``.
        _auth_service: Test hook — inject an auth-service double.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_url: Optional[str] = None,
        _session: Optional[BrokerSession] = None,
        _auth_service: Optional[SSIAuthService] = None,
    ) -> None:
        key, secret = resolve_credentials(api_key, api_secret)
        self._config = SSICredentialConfig(
            api_key=key,
            api_secret=secret,
            api_url=(api_url or "https://api.ssi.com.vn").rstrip("/"),
        )
        self._session = _session or BrokerSession(provider="SSI")
        self._lock = threading.Lock()
        self._ever_authenticated = False
        if _auth_service is not None:
            self._auth = _auth_service
            self._transport: Optional[SSIHttpClient] = None
        else:
            self._transport = SSIHttpClient(
                base_url=self._config.api_url,
                timeout=self._config.timeout_seconds,
                rate_limit_rps=self._config.rate_limit_rps,
                max_retries=self._config.max_retries,
            )
            self._auth = SSIAuthService(self._config, self._session, self._transport)

    @property
    def has_credentials(self) -> bool:
        """True when both credentials resolved (never exposes values)."""
        return bool(self._config.api_key.strip() and self._config.api_secret.strip())

    def ensure_token(self) -> str:
        """
        Return a valid market-data access token (authenticate/refresh lazily).

        Returns:
            Access token string.

        Raises:
            BrokerError: When SSI refuses authentication.
        """
        with self._lock:
            try:
                return self._session.token
            except BrokerSessionExpiredError:
                pass
            if self._ever_authenticated:
                try:
                    return self._auth.refresh()
                except BrokerError:
                    logger.debug("SSI refresh failed, re-authenticating.")
            token = self._auth.authenticate()
            self._ever_authenticated = True
            return token

    def market_service(self) -> SSIMarketService:
        """
        Build a read-only market service bound to this session.

        Raises:
            RuntimeError: When constructed with an injected test auth double
                (production transport unavailable).
        """
        if self._transport is None:
            raise RuntimeError(
                "market_service() unavailable with injected auth double."
            )
        self.ensure_token()
        return SSIMarketService(self._config, self._session, self._transport)

    def stream_manager(self) -> "SSIStreamManager":
        """Build a WS stream manager bound to this session (P2 live lane)."""
        from vnbroker.broker.ssi.stream import SSIStreamManager

        self.ensure_token()
        return SSIStreamManager(self._config, self._session)


_shared_lock = threading.Lock()
_shared_sessions: Dict[Tuple[str, str], SSIExplorerSession] = {}


def get_shared_session(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
) -> SSIExplorerSession:
    """
    Return the process-wide cached session for a credential pair.

    Args:
        api_key: SSI consumerID (falls back to env).
        api_secret: SSI consumerSecret (falls back to env).

    Raises:
        ValueError: If credentials are missing.
    """
    key, secret = resolve_credentials(api_key, api_secret)
    cache_key = (key, secret)
    with _shared_lock:
        session = _shared_sessions.get(cache_key)
        if session is None:
            session = SSIExplorerSession(api_key=key, api_secret=secret)
            _shared_sessions[cache_key] = session
        return session


def reset_shared_sessions() -> None:
    """Drop the shared session cache (tests only)."""
    with _shared_lock:
        _shared_sessions.clear()
