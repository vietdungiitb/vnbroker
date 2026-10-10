"""
vnbroker.broker.tcbs — TCBS broker client package.

Full implementation of TCBS iFlash OpenAPI endpoints (REST + WebSocket):
  - auth.py: TCBSAuthService (OTP → JWT, apiKey info/extend)
  - token_manager.py: TokenManager (giải mã JWT cục bộ, cache trong bộ nhớ)
  - account.py: TCBSAccountService (profile, erebos v1/v2 account info, history)
  - money.py: TCBSMoneyService (cash, margin, purchasing power, loans, tiền nộp/rút/chuyển)
  - equity.py: TCBSEquityService (orders, holdings, place/modify/cancel, stop-limit)
  - condition_orders.py: TCBSConditionOrderService (huỷ lệnh điều kiện phái sinh)
  - derivatives.py: TCBSDerivativesService (positions, orders, place/modify/cancel)
  - market.py: TCBSMarketService (ticker, intraday, BSA, derivatives info)
  - portfolio.py: TCBSPortfolioEngine (PnL, reconciliation, snapshot)
  - client.py: TCBSBrokerClient (unified facade)
  - exceptions.py: TCBS-specific exceptions
"""

from vnbroker.broker.tcbs.auth import TCBSAuthService
from vnbroker.broker.tcbs.token_manager import TokenManager
from vnbroker.broker.tcbs.account import TCBSAccountService
from vnbroker.broker.tcbs.money import TCBSMoneyService
from vnbroker.broker.tcbs.equity import TCBSEquityService
from vnbroker.broker.tcbs.condition_orders import TCBSConditionOrderService
from vnbroker.broker.tcbs.derivatives import TCBSDerivativesService
from vnbroker.broker.tcbs.market import TCBSMarketService
from vnbroker.broker.tcbs.portfolio import TCBSPortfolioEngine
from vnbroker.broker.tcbs.client import TCBSBrokerClient

__all__ = [
    "TCBSAuthService",
    "TokenManager",
    "TCBSAccountService",
    "TCBSMoneyService",
    "TCBSEquityService",
    "TCBSConditionOrderService",
    "TCBSDerivativesService",
    "TCBSMarketService",
    "TCBSPortfolioEngine",
    "TCBSBrokerClient",
]
