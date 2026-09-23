"""
tests/integration/tcbs/test_tcbs_full_acb.py — Full TCBS provider test với ACB.

Kiểm thử toàn bộ các phase đã implement:
  - Phase 1: Erebos v1/v2 account endpoints
  - Phase 2: Money/margin endpoints
  - Phase 3.4: Stop-limit order endpoints
  - Phase 4: Derivatives endpoints
  - Market: Ticker info, intraday, BSA (public, không cần auth)
  - WebSocket: Connection và message parsing

Test symbol: ACB (Ngân hàng TMCP Á Châu)

Cách chạy:
  # Unit tests (mocked, không cần API key):
  pytest tests/integration/tcbs/test_tcbs_full_acb.py -v -k "unit"

  # Integration tests (cần TCBS_API_KEY env):
  pytest tests/integration/tcbs/test_tcbs_full_acb.py -v -k "integration"

  # Tất cả tests:
  pytest tests/integration/tcbs/test_tcbs_full_acb.py -v
"""
from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

import pytest

from vnbroker.broker.tcbs.client import TCBSBrokerClient
from vnbroker.broker.tcbs.account import TCBSAccountService
from vnbroker.broker.tcbs.money import TCBSMoneyService
from vnbroker.broker.tcbs.equity import TCBSEquityService
from vnbroker.broker.tcbs.derivatives import TCBSDerivativesService
from vnbroker.broker.tcbs.market import TCBSMarketService
from vnbroker.broker.session import BrokerSession, SessionState
from vnbroker.broker.security.credentials import TCBSCredentialConfig

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

SYMBOL = "ACB"
ACCOUNT_NO = "0001170730"
CUSTODY_CODE = "105C000001"
ACCOUNT_ID = "105C000001"
SUB_ACCOUNT_ID = "0001170730"
FAKE_API_KEY = "vninvest_pat_dGVzdF9rZXlfZm9yX3VuaXRfdGVzdGluZw=="
FAKE_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature"
REQUEST_ID = f"test-{int(time.time())}"


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_config():
    """TCBSCredentialConfig với fake API key."""
    return TCBSCredentialConfig(api_key=FAKE_API_KEY)


@pytest.fixture
def mock_session():
    """BrokerSession đã authenticated với fake token."""
    session = BrokerSession()
    session._token = FAKE_TOKEN
    session._authenticated = True
    session.state = SessionState.AUTHENTICATED_READ
    return session


@pytest.fixture
def mock_session_write(mock_session):
    """BrokerSession đã enable write."""
    mock_session.enable_write()
    return mock_session


@pytest.fixture
def mock_response():
    """Mock response object cho requests."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": [], "total": 0}
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def market_service(mock_config, mock_session):
    """TCBSMarketService instance."""
    return TCBSMarketService(config=mock_config, session=mock_session)


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — Market Endpoints (Public, không cần auth)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestMarketEndpointsACB:
    """Test market endpoints với ACB symbol."""

    def test_get_ticker_info_acb(self, market_service):
        """GET /tartarus/v1/tickerCommons?tickers=ACB"""
        with patch("vnbroker.broker.tcbs.market.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "data": [{
                    "ticker": SYMBOL,
                    "exchange": "HSX",
                    "industry": "Ngân hàng",
                    "basicPrice": 25000,
                    "ceiling": 27500,
                    "floor": 22500,
                }]
            }
            result = market_service.get_ticker_info(tickers=[SYMBOL])
            assert result is not None
            assert not result.empty
            assert result.iloc[0]["ticker"] == SYMBOL

    def test_get_intraday_history_acb(self, market_service):
        """GET /tartarus/v1/intraday/{ticker}/histories"""
        with patch("vnbroker.broker.tcbs.market.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "data": [
                    {"time": "09:00:00", "price": 25100, "volume": 100},
                    {"time": "09:01:00", "price": 25200, "volume": 200},
                ]
            }
            result = market_service.get_intraday_history(ticker=SYMBOL)
            assert result is not None
            assert len(result) == 2

    def test_get_bsa_acb(self, market_service):
        """GET /tartarus/v1/bsa/{ticker}"""
        with patch("vnbroker.broker.tcbs.market.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "data": [
                    {"date": "2026-06-20", "buy": 1000, "sell": 800, "net": 200},
                ]
            }
            result = market_service.get_bsa(ticker=SYMBOL)
            assert result is not None
            assert len(result) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — Phase 1: Erebos Account Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestPhase1ErebosAccount:
    """Test Phase 1: Erebos v1/v2 account endpoints."""

    @pytest.fixture
    def account_service(self, mock_config, mock_session):
        return TCBSAccountService(config=mock_config, session=mock_session)

    def test_get_erebos_v1_asset(self, account_service, mock_response):
        """GET /erebos/v1/account/asset"""
        mock_response.json.return_value = {
            "data": {"accountNo": ACCOUNT_NO, "cash": 100000000, "stock": 250000000}
        }
        with patch("vnbroker.broker.tcbs.account.requests.get", return_value=mock_response):
            result = account_service.get_erebos_v1_asset(account_no=ACCOUNT_NO)
            assert result is not None

    def test_get_erebos_v1_available_balance(self, account_service, mock_response):
        """GET /erebos/v1/account/available-balance"""
        mock_response.json.return_value = {
            "data": {"accountNo": ACCOUNT_NO, "availableCash": 50000000}
        }
        with patch("vnbroker.broker.tcbs.account.requests.get", return_value=mock_response):
            result = account_service.get_erebos_v1_available_balance(account_no=ACCOUNT_NO)
            assert result is not None

    def test_get_erebos_v1_portfolio_asset(self, account_service, mock_response):
        """GET /erebos/v1/portfolio-asset"""
        mock_response.json.return_value = {
            "data": [{"ticker": SYMBOL, "quantity": 1000, "avgPrice": 25000}]
        }
        with patch("vnbroker.broker.tcbs.account.requests.get", return_value=mock_response):
            result = account_service.get_erebos_v1_portfolio_asset(account_no=ACCOUNT_NO)
            assert result is not None

    def test_get_erebos_v1_portfolio_asset_token(self, account_service, mock_response):
        """GET /erebos/v1/portfolio-asset/token"""
        mock_response.json.return_value = {
            "data": [
                {"symbol": SYMBOL, "secType": "STOCK", "quantity": 1000, "averageCost": 25000}
            ]
        }
        with patch("vnbroker.broker.tcbs.account.requests.get", return_value=mock_response):
            result = account_service.get_erebos_v1_portfolio_asset_token(account_no=ACCOUNT_NO)
            assert result is not None
            assert len(result) == 1

    def test_get_erebos_v1_portfolio_stock_statistic(self, account_service, mock_response):
        """GET /erebos/v1/portfolio/stock/{accountNo}/statistic"""
        mock_response.json.return_value = {
            "data": {"totalStocks": 5, "totalValue": 500000000}
        }
        with patch("vnbroker.broker.tcbs.account.requests.get", return_value=mock_response):
            result = account_service.get_erebos_v1_portfolio_stock_statistic(account_no=ACCOUNT_NO)
            assert result is not None

    def test_get_erebos_v2_asset(self, account_service, mock_response):
        """GET /erebos/v2/accounts/{accountNo}/asset"""
        mock_response.json.return_value = {
            "data": {"accountNo": ACCOUNT_NO, "netAsset": 350000000}
        }
        with patch("vnbroker.broker.tcbs.account.requests.get", return_value=mock_response):
            result = account_service.get_erebos_v2_asset(account_no=ACCOUNT_NO)
            assert result is not None

    def test_get_erebos_v2_available_balance(self, account_service, mock_response):
        """GET /erebos/v2/accounts/{accountNo}/available-balance"""
        mock_response.json.return_value = {
            "data": {"availableCash": 75000000, "availableMargin": 200000000}
        }
        with patch("vnbroker.broker.tcbs.account.requests.get", return_value=mock_response):
            result = account_service.get_erebos_v2_available_balance(account_no=ACCOUNT_NO)
            assert result is not None

    def test_get_erebos_v2_stock_statistic(self, account_service, mock_response):
        """GET /erebos/v2/accounts/{accountNo}/stock-statistic"""
        mock_response.json.return_value = {
            "data": {"totalStocks": 3, "profitLoss": 15000000}
        }
        with patch("vnbroker.broker.tcbs.account.requests.get", return_value=mock_response):
            result = account_service.get_erebos_v2_stock_statistic(account_no=ACCOUNT_NO)
            assert result is not None

    def test_get_erebos_v2_orders_history(self, account_service, mock_response):
        """GET /erebos/v2/accounts/{accountNo}/orders/history"""
        mock_response.json.return_value = {
            "data": [
                {"orderNo": "123", "ticker": SYMBOL, "side": "BUY", "status": "MATCHED"}
            ],
            "total": 1,
        }
        with patch("vnbroker.broker.tcbs.account.requests.get", return_value=mock_response):
            result = account_service.get_erebos_v2_orders_history(
                account_no=ACCOUNT_NO, from_date="2026-06-01", to_date="2026-06-20"
            )
            assert result is not None
            assert len(result) == 1

    def test_get_erebos_v2_orders_matching(self, account_service, mock_response):
        """GET /erebos/v2/accounts/{accountNo}/orders/matching"""
        mock_response.json.return_value = {
            "data": [
                {"orderNo": "123", "ticker": SYMBOL, "matchedVolume": 100, "matchedPrice": 25100}
            ],
            "total": 1,
        }
        with patch("vnbroker.broker.tcbs.account.requests.get", return_value=mock_response):
            result = account_service.get_erebos_v2_orders_matching(account_no=ACCOUNT_NO)
            assert result is not None

    def test_get_erebos_v2_withdraw_history(self, account_service, mock_response):
        """GET /erebos/v2/accounts/{accountNo}/withdraw"""
        mock_response.json.return_value = {
            "data": [{"withdrawId": "W001", "amount": 50000000, "status": "COMPLETED"}],
            "total": 1,
        }
        with patch("vnbroker.broker.tcbs.account.requests.get", return_value=mock_response):
            result = account_service.get_erebos_v2_withdraw_history(account_no=ACCOUNT_NO)
            assert result is not None

    def test_get_erebos_v2_deposit_history(self, account_service, mock_response):
        """GET /erebos/v2/accounts/{accountNo}/deposit"""
        mock_response.json.return_value = {
            "data": [{"depositId": "D001", "amount": 100000000, "status": "COMPLETED"}],
            "total": 1,
        }
        with patch("vnbroker.broker.tcbs.account.requests.get", return_value=mock_response):
            result = account_service.get_erebos_v2_deposit_history(account_no=ACCOUNT_NO)
            assert result is not None

    def test_get_erebos_v2_dividend_history(self, account_service, mock_response):
        """GET /erebos/v2/accounts/{accountNo}/dividend"""
        mock_response.json.return_value = {
            "data": [{"ticker": SYMBOL, "dividendAmount": 2500, "payDate": "2026-06-15"}],
            "total": 1,
        }
        with patch("vnbroker.broker.tcbs.account.requests.get", return_value=mock_response):
            result = account_service.get_erebos_v2_dividend_history(account_no=ACCOUNT_NO)
            assert result is not None


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — Phase 2: Money/Margin Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestPhase2MoneyMargin:
    """Test Phase 2: Money/margin endpoints."""

    @pytest.fixture
    def money_service(self, mock_config, mock_session):
        return TCBSMoneyService(config=mock_config, session=mock_session)

    def test_get_purchasing_power_by_symbol(self, money_service, mock_response):
        """GET /aion/v1/accounts/{accountNo}/ppse/{symbol}"""
        mock_response.json.return_value = {
            "data": {"symbol": SYMBOL, "maxQuantity": 5000, "maxValue": 125000000}
        }
        with patch("vnbroker.broker.tcbs.money.requests.get", return_value=mock_response):
            result = money_service.get_purchasing_power_by_symbol(
                account_no=ACCOUNT_NO, symbol=SYMBOL
            )
            assert result is not None

    def test_get_purchasing_power_by_symbol_price(self, money_service, mock_response):
        """GET /aion/v1/accounts/{accountNo}/ppse/{symbol}/{price}"""
        mock_response.json.return_value = {
            "data": {"symbol": SYMBOL, "price": 25000, "maxQuantity": 4000}
        }
        with patch("vnbroker.broker.tcbs.money.requests.get", return_value=mock_response):
            result = money_service.get_purchasing_power_by_symbol_price(
                account_no=ACCOUNT_NO, symbol=SYMBOL, price=25000.0
            )
            assert result is not None

    def test_get_customer_accounts(self, money_service, mock_response):
        """GET /aion/v1/customers/{custodyId}/accounts"""
        mock_response.json.return_value = {
            "data": [
                {"accountNo": ACCOUNT_NO, "type": "margin", "status": "active"}
            ]
        }
        with patch("vnbroker.broker.tcbs.money.requests.get", return_value=mock_response):
            result = money_service.get_customer_accounts(custody_id=CUSTODY_CODE)
            assert result is not None

    def test_get_margin_risk(self, money_service, mock_response):
        """GET /hydros/v1/account/{accountNo}/risk"""
        mock_response.json.return_value = {
            "data": {"marginRatio": 0.65, "riskLevel": "LOW", "marginCall": False}
        }
        with patch("vnbroker.broker.tcbs.money.requests.get", return_value=mock_response):
            result = money_service.get_margin_risk(account_no=ACCOUNT_NO)
            assert result is not None

    def test_get_margin_subscription_detail(self, money_service, mock_response):
        """GET /campaign-management/v1/margin/subscription/{accountNo}/addons/detail"""
        mock_response.json.return_value = {
            "data": {"subscriptionId": "SUB001", "interestRate": 0.12, "status": "active"}
        }
        with patch("vnbroker.broker.tcbs.money.requests.get", return_value=mock_response):
            result = money_service.get_margin_subscription_detail(account_no=ACCOUNT_NO)
            assert result is not None

    def test_get_loan_list(self, money_service, mock_response):
        """GET /khaos/v1/loan/{accountNo}"""
        mock_response.json.return_value = {
            "data": [
                {"loanId": "L001", "amount": 200000000, "interestRate": 0.12, "status": "active"}
            ]
        }
        with patch("vnbroker.broker.tcbs.money.requests.get", return_value=mock_response):
            result = money_service.get_loan_list(account_no=ACCOUNT_NO)
            assert result is not None

    def test_get_cash_statements(self, money_service, mock_response):
        """GET /erebos/v2/digital/trans-hist-cashStatements"""
        mock_response.json.return_value = {
            "data": [
                {"date": "2026-06-20", "type": "DEPOSIT", "amount": 100000000}
            ],
            "total": 1,
        }
        with patch("vnbroker.broker.tcbs.money.requests.get", return_value=mock_response):
            result = money_service.get_cash_statements(
                account_no=ACCOUNT_NO, from_date="2026-06-01", to_date="2026-06-20"
            )
            assert result is not None


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — Phase 3.4: Stop-Limit Order Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestPhase3StopLimitOrders:
    """Test Phase 3.4: Stop-limit order endpoints."""

    @pytest.fixture
    def equity_service(self, mock_config, mock_session_write):
        return TCBSEquityService(config=mock_config, session=mock_session_write)

    def test_place_stop_limit_order_dry_run(self, equity_service):
        """Đặt lệnh stop-limit (dry_run=True)."""
        result = equity_service.place_stop_limit_order(
            account_no=ACCOUNT_NO,
            symbol=SYMBOL,
            side="BUY",
            order_type="LO",
            quantity=100,
            price=25000,
            stop_price=24500,
            request_id=REQUEST_ID,
            dry_run=True,
        )
        assert result["dry_run"] is True
        assert "place_stop_limit" in result["operation"]

    def test_place_stop_limit_order_write_disabled(self, mock_config, mock_session):
        """Đặt lệnh stop-limit khi write disabled → raise."""
        service = TCBSEquityService(config=mock_config, session=mock_session)
        with pytest.raises(Exception):
            service.place_stop_limit_order(
                account_no=ACCOUNT_NO, symbol=SYMBOL, side="BUY",
                order_type="LO", quantity=100, price=25000,
                stop_price=24500, request_id=REQUEST_ID, dry_run=False,
            )

    def test_get_stop_limit_orders(self, equity_service, mock_response):
        """GET /erebos/v1/orders/condition"""
        mock_response.json.return_value = {
            "data": [
                {
                    "orderNo": "SL001",
                    "ticker": SYMBOL,
                    "side": "BUY",
                    "stopPrice": 24500,
                    "price": 25000,
                    "status": "PENDING",
                }
            ],
            "total": 1,
        }
        with patch("vnbroker.broker.tcbs.equity.requests.get", return_value=mock_response):
            result = equity_service.get_stop_limit_orders(account_no=ACCOUNT_NO)
            assert result is not None

    def test_cancel_stop_limit_order_dry_run(self, equity_service):
        """Hủy lệnh stop-limit (dry_run=True)."""
        result = equity_service.cancel_stop_limit_order(
            order_id="SL001", request_id=REQUEST_ID, dry_run=True,
        )
        assert result["dry_run"] is True
        assert "cancel_stop_limit" in result["operation"]

    def test_modify_stop_limit_order_dry_run(self, equity_service):
        """Sửa lệnh stop-limit (dry_run=True)."""
        result = equity_service.modify_stop_limit_order(
            order_id="SL001", quantity=200, price=25500,
            stop_price=25000, request_id=REQUEST_ID, dry_run=True,
        )
        assert result["dry_run"] is True
        assert "modify_stop_limit" in result["operation"]


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — Phase 4: Derivatives Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestPhase4Derivatives:
    """Test Phase 4: Derivatives endpoints."""

    @pytest.fixture
    def derivatives_service(self, mock_config, mock_session):
        return TCBSDerivativesService(config=mock_config, session=mock_session)

    @pytest.fixture
    def derivatives_service_write(self, mock_config, mock_session_write):
        return TCBSDerivativesService(config=mock_config, session=mock_session_write)

    def test_get_closed_positions(self, derivatives_service, mock_response):
        """GET /khronos/v1/account/portfolio/position/close"""
        mock_response.json.return_value = {
            "data": [
                {
                    "symbol": "VN30F1M",
                    "closedVolume": 10,
                    "avgPrice": 1250.0,
                    "profitLoss": 5000000,
                }
            ],
            "total": 1,
        }
        with patch("vnbroker.broker.tcbs.derivatives.requests.get", return_value=mock_response):
            result = derivatives_service.get_closed_positions(
                account_id=ACCOUNT_ID, sub_account_id=SUB_ACCOUNT_ID
            )
            assert result is not None

    def test_get_condition_orders(self, derivatives_service, mock_response):
        """GET /khronos/v1/order/condition/detail"""
        mock_response.json.return_value = {
            "data": [
                {
                    "orderNo": "COND001",
                    "symbol": "VN30F1M",
                    "side": "BUY",
                    "triggerPrice": 1240.0,
                    "status": "PENDING",
                }
            ],
            "total": 1,
        }
        with patch("vnbroker.broker.tcbs.derivatives.requests.get", return_value=mock_response):
            result = derivatives_service.get_condition_orders(
                account_id=ACCOUNT_ID, sub_account_id=SUB_ACCOUNT_ID
            )
            assert result is not None

    def test_place_derivative_order_dry_run(self, derivatives_service_write):
        """Đặt lệnh phái sinh (dry_run=True)."""
        result = derivatives_service_write.place_derivative_order(
            account_id=ACCOUNT_ID,
            sub_account_id=SUB_ACCOUNT_ID,
            symbol="VN30F1M",
            side="BUY",
            order_type="LO",
            quantity=10,
            price=1250.0,
            request_id=REQUEST_ID,
            dry_run=True,
        )
        assert result["dry_run"] is True
        assert "place_derivative_order" in result["operation"]

    def test_place_derivative_condition_order_dry_run(self, derivatives_service_write):
        """Đặt lệnh phái sinh điều kiện (dry_run=True)."""
        result = derivatives_service_write.place_derivative_condition_order(
            account_id=ACCOUNT_ID,
            sub_account_id=SUB_ACCOUNT_ID,
            symbol="VN30F1M",
            side="BUY",
            order_type="LO",
            quantity=10,
            price=1250.0,
            trigger_price=1240.0,
            request_id=REQUEST_ID,
            dry_run=True,
        )
        assert result["dry_run"] is True
        assert "place_derivative_condition" in result["operation"]

    def test_change_derivative_order_dry_run(self, derivatives_service_write):
        """Sửa lệnh phái sinh (dry_run=True)."""
        result = derivatives_service_write.change_derivative_order(
            order_id="ORD001", quantity=20, price=1260.0,
            request_id=REQUEST_ID, dry_run=True,
        )
        assert result["dry_run"] is True
        assert "change_derivative_order" in result["operation"]

    def test_change_derivative_condition_order_dry_run(self, derivatives_service_write):
        """Sửa lệnh phái sinh điều kiện (dry_run=True)."""
        result = derivatives_service_write.change_derivative_condition_order(
            order_id="COND001", quantity=15, price=1255.0,
            trigger_price=1245.0, request_id=REQUEST_ID, dry_run=True,
        )
        assert result["dry_run"] is True
        assert "change_derivative_condition" in result["operation"]

    def test_cancel_derivative_order_dry_run(self, derivatives_service_write):
        """Hủy lệnh phái sinh (dry_run=True)."""
        result = derivatives_service_write.cancel_derivative_order(
            order_id="ORD001", request_id=REQUEST_ID, dry_run=True,
        )
        assert result["dry_run"] is True
        assert "cancel_derivative_order" in result["operation"]


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — Client Facade
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestClientFacadeACB:
    """Test TCBSBrokerClient facade với ACB."""

    @pytest.fixture
    def client(self):
        """TCBSBrokerClient với mocked services."""
        with patch("vnbroker.broker.tcbs.client.TCBSAccountService"), \
             patch("vnbroker.broker.tcbs.client.TCBSMoneyService"), \
             patch("vnbroker.broker.tcbs.client.TCBSEquityService"), \
             patch("vnbroker.broker.tcbs.client.TCBSDerivativesService"), \
             patch("vnbroker.broker.tcbs.client.TCBSMarketService"), \
             patch("vnbroker.broker.tcbs.client.TCBSAuthService"):
            c = TCBSBrokerClient(api_key=FAKE_API_KEY)
            c.session._token = FAKE_TOKEN
            c.session.state = SessionState.AUTHENTICATED_READ
            c.session.token_expires_at = None  # No expiration for tests
            return c

    def test_client_repr(self, client):
        """repr không expose token."""
        r = repr(client)
        assert "TCBSBrokerClient" in r
        assert FAKE_TOKEN not in r
        assert FAKE_API_KEY not in r

    def test_client_is_authenticated(self, client):
        """is_authenticated property."""
        assert client.is_authenticated is True

    def test_client_has_all_new_methods(self, client):
        """Verify tất cả methods mới tồn tại."""
        methods = [
            "get_erebos_v1_asset", "get_erebos_v1_available_balance",
            "get_erebos_v1_portfolio_asset", "get_erebos_v1_portfolio_asset_token",
            "get_erebos_v1_portfolio_stock_statistic",
            "get_erebos_v2_asset", "get_erebos_v2_available_balance",
            "get_erebos_v2_stock_statistic", "get_erebos_v2_orders_history",
            "get_erebos_v2_orders_matching", "get_erebos_v2_withdraw_history",
            "get_erebos_v2_deposit_history", "get_erebos_v2_dividend_history",
            "get_purchasing_power_by_symbol", "get_purchasing_power_by_symbol_price",
            "get_customer_accounts", "get_margin_risk",
            "get_margin_subscription_detail", "get_loan_list",
            "get_cash_statements",
            "place_stop_limit_order", "get_stop_limit_orders",
            "cancel_stop_limit_order", "modify_stop_limit_order",
            "get_derivative_closed_positions", "get_derivative_condition_orders",
            "place_derivative_order", "place_derivative_condition_order",
            "change_derivative_order", "change_derivative_condition_order",
            "cancel_derivative_order",
        ]
        for method in methods:
            assert hasattr(client, method), f"Missing method: {method}"


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — WebSocket Models
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestWebSocketModels:
    """Test WebSocket data models."""

    def test_ohlc_creation(self):
        """OHLC dataclass creation."""
        from datetime import datetime
        from vnbroker.explorer.tcbs.ws_models import OHLC
        now = datetime.now()
        ohlc = OHLC(
            symbol=SYMBOL, time=now, interval="1m",
            open=25000, high=25200, low=24900, close=25100, volume=1000,
        )
        assert ohlc.symbol == SYMBOL
        assert ohlc.high > ohlc.low

    def test_order_book_creation(self):
        """OrderBook dataclass creation."""
        from datetime import datetime
        from vnbroker.explorer.tcbs.ws_models import OrderBook, OrderBookLevel
        now = datetime.now()
        ob = OrderBook(
            symbol=SYMBOL, time=now,
            bids=[OrderBookLevel(price=25000, volume=100)],
            asks=[OrderBookLevel(price=25100, volume=200)],
        )
        assert len(ob.bids) == 1
        assert len(ob.asks) == 1

    def test_ticker_creation(self):
        """Ticker dataclass creation."""
        from datetime import datetime
        from vnbroker.explorer.tcbs.ws_models import Ticker
        now = datetime.now()
        ticker = Ticker(
            symbol=SYMBOL, time=now,
            last_price=25100, volume=100000,
            high=25500, low=24800, open=25000,
        )
        assert ticker.symbol == SYMBOL
        assert ticker.last_price == 25100

    def test_trade_creation(self):
        """Trade dataclass creation."""
        from datetime import datetime
        from vnbroker.explorer.tcbs.ws_models import Trade
        now = datetime.now()
        trade = Trade(
            symbol=SYMBOL, time=now,
            price=25100, volume=100,
        )
        assert trade.price == 25100
        assert trade.volume == 100


# ──────────────────────────────────────────────────────────────────────────────
# Integration Tests — Requires TCBS_API_KEY
# ──────────────────────────────────────────────────────────────────────────────

def _has_api_key() -> bool:
    """Check if TCBS API key is available."""
    return bool(
        os.getenv("TCBS_API_KEY")
        or os.getenv("VNBROKER_BROKER_TCBS_API_KEY")
        or os.getenv("vnbroker_TCBS_OPENAPI_API_KEY")
    )


@pytest.mark.integration
@pytest.mark.skipif(not _has_api_key(), reason="TCBS_API_KEY not set")
class TestIntegrationMarketACB:
    """Integration tests — market endpoints (public, không cần auth)."""

    def test_get_ticker_info_acb_live(self):
        """Live test: GET ticker info cho ACB."""
        client = TCBSBrokerClient()
        result = client.get_ticker_info(tickers=[SYMBOL])
        assert result is not None
        assert not result.empty
        assert SYMBOL in result["ticker"].values

    def test_get_intraday_history_acb_live(self):
        """Live test: GET intraday history cho ACB."""
        client = TCBSBrokerClient()
        result = client.get_intraday_history(ticker=SYMBOL)
        assert result is not None

    def test_get_bsa_acb_live(self):
        """Live test: GET BSA cho ACB."""
        client = TCBSBrokerClient()
        result = client.get_bsa(ticker=SYMBOL)
        assert result is not None


@pytest.mark.integration
@pytest.mark.skipif(not _has_api_key(), reason="TCBS_API_KEY not set")
class TestIntegrationAuthenticated:
    """Integration tests — authenticated endpoints (cần OTP)."""

    def test_authenticate_and_get_profile(self):
        """Live test: Authenticate → get_profile."""
        otp = os.getenv("TCBS_TEST_OTP")
        if not otp:
            pytest.skip("TCBS_TEST_OTP not set")

        client = TCBSBrokerClient()
        client.authenticate(otp=otp)
        assert client.is_authenticated

        custody_code = os.getenv("TCBS_CUSTODY_CODE", CUSTODY_CODE)
        profile = client.get_profile(custody_code=custody_code)
        assert profile is not None
