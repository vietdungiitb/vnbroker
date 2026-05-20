"""
vnbroker.broker.tcbs.exceptions — Re-export broker exception hierarchy cho TCBS context.

Tất cả exception class đều định nghĩa tại vnbroker.broker.exceptions (broker-level)
để tránh circular import với security/guards.py.

Import từ đây để code TCBS có namespace rõ ràng:
    from vnbroker.broker.tcbs.exceptions import BrokerAuthError
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
