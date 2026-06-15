"""
Gateway HTTP Client for vnbroker PAT-based authentication.

This module handles all communication with the vninvest SaaS Gateway,
including PAT authentication, request routing, caching, and emergency fallback.
"""

import os
import time
import logging
from typing import Dict, Any, Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from vnbroker.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    QuotaExceededError,
    ProviderError,
    GatewayUnavailableError,
    EmergencyQuotaExceededError,
    InvalidPATFormatError,
)

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_GATEWAY_URL = "https://api.vnstocks.com"
DEFAULT_PAT = "vninvest_pat_dev_free_default_unregistered_key"
EMERGENCY_DAILY_LIMIT = 10
GATEWAY_TIMEOUT = 5.0  # seconds


class GatewayHttpClient:
    """
    HTTP Client for communicating with vninvest SaaS Gateway.
    
    Features:
    - PAT-based authentication (Bearer token)
    - Automatic retry with exponential backoff
    - Emergency fallback when Gateway is unreachable
    - Client-side emergency quota tracking (10 calls/day)
    - Request/response logging
    """
    
    def __init__(
        self,
        pat_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = GATEWAY_TIMEOUT,
        show_log: bool = True,
    ):
        """
        Initialize Gateway HTTP Client.
        
        Args:
            pat_key: Personal Access Token (defaults to env VNBROKER_PAT_KEY or DEFAULT_PAT)
            base_url: Gateway base URL (defaults to env VNBROKER_GATEWAY_URL or DEFAULT_GATEWAY_URL)
            timeout: Request timeout in seconds
            show_log: Whether to log requests
        """
        # Resolve PAT key: explicit > env > default
        self.pat_key = pat_key or os.getenv("VNBROKER_PAT_KEY") or DEFAULT_PAT
        
        # Validate PAT format
        if not self.pat_key.startswith("vninvest_pat_"):
            raise InvalidPATFormatError(
                f"Invalid PAT format: '{self.pat_key[:20]}...'. Token must start with 'vninvest_pat_'."
            )
        
        self.base_url = (base_url or os.getenv("VNBROKER_GATEWAY_URL") or DEFAULT_GATEWAY_URL).rstrip("/")
        self.timeout = timeout
        self.show_log = show_log
        
        # Emergency fallback tracking
        self._emergency_calls_today = 0
        self._last_reset_time = time.time()
        self._emergency_limit = EMERGENCY_DAILY_LIMIT
        
        # Configure session with retry strategy
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.pat_key}",
            "Content-Type": "application/json",
            "User-Agent": "vnbroker-client-python/1.0.2",
        })
        
        # Retry strategy for transient errors
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        if self.show_log:
            logger.info(f"GatewayHttpClient initialized: {self.base_url}")
            logger.debug(f"PAT Key: {self.pat_key[:20]}...")

    def _reset_emergency_counter_if_needed(self) -> None:
        """Reset emergency call counter after 24 hours."""
        if time.time() - self._last_reset_time > 86400:  # 24 hours
            self._emergency_calls_today = 0
            self._last_reset_time = time.time()
            if self.show_log:
                logger.info("Emergency fallback counter reset (24h elapsed)")

    def request(
        self,
        endpoint: str,
        method: str = "POST",
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send request to Gateway with automatic fallback on failure.
        
        Args:
            endpoint: API endpoint (e.g., "/api/v1/quote/history")
            method: HTTP method (GET, POST, etc.)
            json_data: JSON payload for POST/PUT requests
            params: Query parameters for GET requests
            
        Returns:
            Parsed JSON response from Gateway
            
        Raises:
            AuthenticationError: Invalid/expired PAT (401)
            AuthorizationError: Insufficient scope (403)
            QuotaExceededError: Quota exceeded (429)
            ProviderError: Gateway returned error
            EmergencyQuotaExceededError: Emergency fallback quota exceeded
        """
        # Reset emergency counter if 24h passed
        self._reset_emergency_counter_if_needed()
        
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))
        
        if self.show_log:
            logger.debug(f"Gateway Request: {method} {url}")
            if json_data:
                logger.debug(f"Payload: {json_data}")
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=json_data,
                params=params,
                timeout=self.timeout,
            )
            
            if self.show_log:
                logger.debug(f"Gateway Response: {response.status_code}")
            
            # Handle specific HTTP status codes
            if response.status_code == 401:
                raise AuthenticationError(
                    "PAT Token không hợp lệ hoặc đã hết hạn.",
                    details={"status_code": 401, "endpoint": endpoint}
                )
            elif response.status_code == 403:
                raise AuthorizationError(
                    "Token không có quyền (scope) thực hiện tác vụ này.",
                    details={"status_code": 403, "endpoint": endpoint}
                )
            elif response.status_code == 429:
                # Try to get retry-after header
                retry_after = response.headers.get("Retry-After")
                raise QuotaExceededError(
                    "Hết hạn mức cuộc gọi trong ngày. Vui lòng nâng cấp gói để tiếp tục.",
                    details={
                        "status_code": 429,
                        "endpoint": endpoint,
                        "retry_after": retry_after
                    }
                )
            
            response.raise_for_status()
            return response.json()
            
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            # Gateway unreachable - trigger emergency fallback
            if self.show_log:
                logger.warning(f"Gateway unreachable: {e}. Activating emergency fallback.")
            raise GatewayUnavailableError(
                f"Gateway connection failed: {str(e)}",
                details={"endpoint": endpoint, "error": str(e)}
            )
        except requests.exceptions.HTTPError as e:
            # Other HTTP errors
            raise ProviderError(
                f"Gateway returned error: {e}",
                provider="gateway",
                details={"status_code": e.response.status_code if e.response else None, "endpoint": endpoint}
            )

    def _emergency_fallback(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Emergency fallback: call local explorers directly when Gateway is down.
        
        This is called by the Vnbroker class when GatewayHttpClient.request()
        raises GatewayUnavailableError.
        
        Args:
            endpoint: API endpoint
            json_data: Request payload
            params: Query parameters
            
        Returns:
            Response from local explorer
            
        Raises:
            EmergencyQuotaExceededError: If emergency daily limit exceeded
        """
        self._reset_emergency_counter_if_needed()
        
        if self._emergency_calls_today >= self._emergency_limit:
            raise EmergencyQuotaExceededError(
                f"Gateway hiện tại không khả dụng và bạn đã dùng hết hạn mức dự phòng khẩn cấp "
                f"({self._emergency_limit} calls/ngày).",
                details={
                    "emergency_calls_used": self._emergency_calls_today,
                    "emergency_limit": self._emergency_limit,
                    "endpoint": endpoint
                }
            )
        
        self._emergency_calls_today += 1
        
        if self.show_log:
            logger.warning(
                f"Emergency fallback activated ({self._emergency_calls_today}/{self._emergency_limit} today): "
                f"{endpoint}"
            )
        
        # Delegate to local dispatch module
        from vnbroker.core.dispatch import local_dispatch_fallback
        return local_dispatch_fallback(endpoint, json_data, params)

    def get_emergency_status(self) -> Dict[str, Any]:
        """Get current emergency fallback usage status."""
        self._reset_emergency_counter_if_needed()
        return {
            "emergency_calls_used_today": self._emergency_calls_today,
            "emergency_daily_limit": self._emergency_limit,
            "emergency_calls_remaining": max(0, self._emergency_limit - self._emergency_calls_today),
            "is_emergency_mode": self._emergency_calls_today > 0,
        }

    def health_check(self) -> Dict[str, Any]:
        """Check Gateway health status."""
        try:
            response = self.session.get(
                urljoin(self.base_url + "/", "/health"),
                timeout=3.0
            )
            return {
                "status": "healthy" if response.status_code == 200 else "degraded",
                "status_code": response.status_code,
                "gateway_url": self.base_url,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "gateway_url": self.base_url,
            }


# Convenience function for quick initialization
def create_gateway_client(
    pat_key: Optional[str] = None,
    base_url: Optional[str] = None,
    **kwargs
) -> GatewayHttpClient:
    """Factory function to create GatewayHttpClient with defaults."""
    return GatewayHttpClient(pat_key=pat_key, base_url=base_url, **kwargs)