"""
Base broker client abstraction.

Defines the interface contract for all broker providers.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class BrokerCredentials:
    """Broker authentication credentials."""
    api_key: str
    base_url: str = "https://openapi.tcbs.com.vn"
    auth_token: Optional[str] = None


class BaseBrokerClient(ABC):
    """
    Abstract base class for broker clients.

    All broker providers must implement this interface.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'TCBS')."""
        pass

    @abstractmethod
    def authenticate(self, otp: str) -> str:
        """
        Authenticate with OTP and return JWT token.

        Args:
            otp: 6-digit OTP from broker app

        Returns:
            JWT token string

        Raises:
            BrokerAuthError: If authentication fails
        """
        pass

    @property
    @abstractmethod
    def is_authenticated(self) -> bool:
        """Check if client has valid authentication."""
        pass

    @abstractmethod
    def get_account_list(self) -> list[dict[str, Any]]:
        """Get list of accounts for authenticated user."""
        pass

    @abstractmethod
    def get_account_balance(self, account_no: str) -> dict[str, Any]:
        """Get account balance for given account number."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close any open connections."""
        pass

    def __enter__(self) -> "BaseBrokerClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()