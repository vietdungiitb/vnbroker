"""
vnbroker.broker.ssi — SSI broker lane (native FastConnect v3, không dependency ssi-sdk).

Services (mirror broker/tcbs, import trực tiếp từ submodule):
  - auth.py: SSIAuthService (OTP/Smart-OTP/refresh, token lifecycle)
  - account.py: SSIAccountService (list_accounts)
  - money.py: SSIMoneyService (balance, PPMMR, maxBuySell)
  - equity.py: SSIEquityService (place/modify/cancel, dry_run default)
  - market.py: SSIMarketService (OHLC, index, securities, master data)
  - portfolio.py: SSIPortfolioService (positions, orders, snapshot)
  - fco.py: SSIFCOService (7 lệnh điều kiện + query vòng đời)
  - stream.py: SSIStreamManager (WebSocket realtime)
  - client.py: SSIBrokerClient (unified facade, đăng ký BrokerRegistry "ssi")

Nền tảng (dùng trực tiếp, không qua facade):
  - _paths.py, _enums.py, _utils.py, _signing.py, _transport.py, exceptions.py

Đặc tả wire-protocol: docs/SSI_INTEGRATION_PLAN.md §1.
"""

from vnbroker.broker.ssi import _enums, _paths, _signing, _transport, _utils
from vnbroker.broker.ssi.account import SSIAccountService
from vnbroker.broker.ssi.auth import SSIAuthService
from vnbroker.broker.ssi.client import SSIBrokerClient
from vnbroker.broker.ssi.equity import SSIEquityService
from vnbroker.broker.ssi.exceptions import (
    BrokerError,
    BrokerAuthError,
    BrokerSessionExpiredError,
    BrokerPermissionError,
    BrokerValidationError,
    BrokerRateLimitError,
    BrokerOrderError,
    BrokerNetworkError,
)
from vnbroker.broker.ssi.fco import SSIFCOService
from vnbroker.broker.ssi.market import SSIMarketService
from vnbroker.broker.ssi.money import SSIMoneyService
from vnbroker.broker.ssi.portfolio import SSIPortfolioService
from vnbroker.broker.ssi.stream import SSIStreamManager

__all__ = [
    "_enums",
    "_paths",
    "_signing",
    "_transport",
    "_utils",
    "SSIAuthService",
    "SSIAccountService",
    "SSIMoneyService",
    "SSIEquityService",
    "SSIFCOService",
    "SSIMarketService",
    "SSIPortfolioService",
    "SSIStreamManager",
    "SSIBrokerClient",
    "BrokerError",
    "BrokerAuthError",
    "BrokerSessionExpiredError",
    "BrokerPermissionError",
    "BrokerValidationError",
    "BrokerRateLimitError",
    "BrokerOrderError",
    "BrokerNetworkError",
]
