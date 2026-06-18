"""
vnbroker.broker.ssi.auth — SSI Auth Service.

Handles authentication with SSI FastConnect API.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.exceptions import BrokerAuthError

_logger = logging.getLogger("vnbroker.broker.ssi.auth")


class SSIAuthService:
    """
    SSI FastConnect Authentication Service.
    
    SSI uses OAuth2 client credentials flow with consumer_id and consumer_secret.
    """

    def __init__(self, config: SSICredentialConfig, session: BrokerSession) -> None:
        self._config = config
        self._session = session
        self._token_url = f"{config.base_url}/oauth2/token"

    def authenticate(self, consumer_id: Optional[str] = None, consumer_secret: Optional[str] = None) -> None:
        """
        Authenticate with SSI FastConnect using client credentials.
        
        Args:
            consumer_id: SSI consumer ID (optional, uses config if not provided)
            consumer_secret: SSI consumer secret (optional, uses config if not provided)
            
        Raises:
            BrokerAuthError: If authentication fails
        """
        consumer_id = consumer_id or self._config.consumer_id
        consumer_secret = consumer_secret or self._config.consumer_secret
        
        if not consumer_id or not consumer_secret:
            raise BrokerAuthError(
                "SSI authentication requires consumer_id and consumer_secret. "
                "Provide them as arguments or set VNBROKER_BROKER_SSI_CONSUMER_ID "
                "and VNBROKER_BROKER_SSI_CONSUMER_SECRET environment variables."
            )
        
        payload = {
            "grant_type": "client_credentials",
            "client_id": consumer_id,
            "client_secret": consumer_secret,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        try:
            response = requests.post(
                self._token_url,
                data=payload,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            
            access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            
            if not access_token:
                raise BrokerAuthError(f"SSI auth response missing access_token: {data}")
            
            # Store token in session
            self._session.set_token(
                access_token=access_token,
                expires_at=time.time() + expires_in - 60,  # 60s buffer
            )
            
            _logger.info("SSI authentication successful")
            
        except requests.RequestException as e:
            _logger.error(f"SSI authentication request failed: {e}")
            raise BrokerAuthError(f"SSI authentication failed: {e}") from e
        except ValueError as e:
            _logger.error(f"SSI authentication response parsing failed: {e}")
            raise BrokerAuthError(f"SSI authentication response invalid: {e}") from e

    def is_token_valid(self) -> bool:
        """Check if current token is still valid."""
        return self._session.is_token_valid()

    def revoke(self) -> None:
        """Revoke current session (clear token)."""
        self._session.clear_token()
        _logger.info("SSI session revoked")