"""
vnbroker.broker.vndirect.auth — VNDirect Auth Service.

Handles authentication with VNDirect OpenAPI.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from vnbroker.broker.security.credentials import VNDirectCredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.exceptions import BrokerAuthError

_logger = logging.getLogger("vnbroker.broker.vndirect.auth")


class VNDirectAuthService:
    """
    VNDirect OpenAPI Authentication Service.
    
    VNDirect uses API key based authentication.
    """

    def __init__(self, config: VNDirectCredentialConfig, session: BrokerSession) -> None:
        self._config = config
        self._session = session
        self._base_url = config.base_url

    def authenticate(self, api_key: Optional[str] = None) -> None:
        """
        Authenticate with VNDirect using API key.
        
        Args:
            api_key: VNDirect API key (optional, uses config if not provided)
            
        Raises:
            BrokerAuthError: If authentication fails
        """
        api_key = api_key or self._config.api_key
        
        if not api_key:
            raise BrokerAuthError(
                "VNDirect authentication requires api_key. "
                "Provide it as argument or set VNBROKER_BROKER_VNDIRECT_API_KEY "
                "environment variable."
            )
        
        # VNDirect uses API key in header, no token exchange needed
        # Validate the API key by making a test request
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            response = requests.get(
                f"{self._base_url}/api/v1/account/info",
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            
            # Store API key as token in session
            self._session.set_token(
                access_token=api_key,
                expires_at=time.time() + 86400,  # 24 hours
            )
            
            _logger.info("VNDirect authentication successful")
            
        except requests.RequestException as e:
            _logger.error(f"VNDirect authentication request failed: {e}")
            raise BrokerAuthError(f"VNDirect authentication failed: {e}") from e

    def is_token_valid(self) -> bool:
        """Check if current token is still valid."""
        return self._session.is_token_valid()

    def revoke(self) -> None:
        """Revoke current session (clear token)."""
        self._session.clear_token()
        _logger.info("VNDirect session revoked")