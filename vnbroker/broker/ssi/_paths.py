"""
vnbroker.broker.ssi._paths — SSI FastConnect v3 endpoint paths.

Single source of truth cho mọi URL. Server đổi path → sửa 1 chỗ duy nhất.
Đối chiếu: ssi-sdk-python constant.py + ssi-sdk-go (transport/endpoints).
Chi tiết kiểm toán: docs/SSI_INTEGRATION_PLAN.md §1.2 (20 paths).
"""

from __future__ import annotations

# ── Authentication ───────────────────────────────────────────────────────────
EP_ACCESS_TOKEN = "/api/v3/auth/token"
EP_REFRESH_TOKEN = "/api/v3/auth/refresh"
EP_REQUEST_OTP = "/api/v3/auth/requestOtp"

# Smart OTP push-approval pending: HTTP 202 + body {"code": 401114}.
SMART_OTP_PENDING_STATUS = 202
SMART_OTP_PENDING_CODE = 401114
SMART_OTP_POLL_INTERVAL = 5.0
SMART_OTP_POLL_MAX_RETRIES = 5

# ── Market Data ──────────────────────────────────────────────────────────────
EP_DATA_OHLC = "/api/v3/data/ohlc"
EP_DATA_OHLC_DOWNLOAD = "/api/v3/data/ohlc/download"  # NotImplemented phía server SDK
EP_DATA_MASTER_DATA = "/api/v3/data/masterdata"
EP_DATA_INDEX_LIST = "/api/v3/data/indexList"
EP_DATA_INDEX_SUMMARY = "/api/v3/data/indexSummary"
EP_DATA_SECURITIES_BY_BOARD = "/api/v3/data/securitiesByBoard"
EP_DATA_SECURITIES_SUMMARY = "/api/v3/data/securitiesSummary"

# ── Trading ──────────────────────────────────────────────────────────────────
EP_TRADING_ORDER = "/api/v3/trading/order"  # POST place / PUT modify / DELETE cancel
EP_TRADING_MAX_BUY_SELL = "/api/v3/trading/maxBuySell"
EP_TRADING_FCO_ORDER = "/api/v3/trading/fco/order"  # POST place / DELETE cancel
EP_TRADING_FCO_LIST = "/api/v3/trading/fco/list"
EP_TRADING_FCO_ORDER_BOOK = "/api/v3/trading/fco/orderbook"

# ── Portfolio & Account ──────────────────────────────────────────────────────
EP_ACCOUNT_INFO = "/api/v3/account/info"
EP_ACCOUNT_BALANCE = "/api/v3/trading/accountBalance"
EP_ACCOUNT_PPMMR = "/api/v3/trading/ppmmrAccount"
EP_POSITIONS = "/api/v3/trading/position"
EP_ORDER_HISTORY = "/api/v3/trading/orderBook"

# ── Base URLs (defaults, override qua SSICredentialConfig) ───────────────────
DEFAULT_API_URL = "https://api.ssi.com.vn"
DEFAULT_STREAMING_URL = "wss://stream.ssi.com.vn/ws/v3"

# ── Transport defaults ───────────────────────────────────────────────────────
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_RETRIES = 5
DEFAULT_RATE_LIMIT_RPS = 10.0
