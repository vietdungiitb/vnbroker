"""
vnbroker.broker.ssi.exceptions — Re-export broker exception hierarchy cho SSI context.

Tất cả exception class định nghĩa tại vnbroker.broker.exceptions (broker-level),
mirror pattern vnbroker/broker/tcbs/exceptions.py.
"""

from vnbroker.broker.exceptions import (  # noqa: F401 — re-export
    BrokerError,
    BrokerAuthError,
    BrokerSessionExpiredError,
    BrokerPermissionError,
    BrokerValidationError,
    BrokerRateLimitError,
    BrokerOrderError,
    BrokerNetworkError,
)

__all__ = [
    "BrokerError",
    "BrokerAuthError",
    "BrokerSessionExpiredError",
    "BrokerPermissionError",
    "BrokerValidationError",
    "BrokerRateLimitError",
    "BrokerOrderError",
    "BrokerNetworkError",
]
