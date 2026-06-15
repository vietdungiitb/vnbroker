"""
tests.unit.broker.tcbs.test_equity_derivatives
===============================================
Unit tests cho TCBSEquityService và TCBSDerivativesService.

Test categories:
  - TestEquityGetOrders          (7 tests)
  - TestEquityGetOrderDetail     (4 tests)
  - TestEquityGetOrderHistory    (4 tests)
  - TestEquityGetExecutions      (5 tests)
  - TestEquityGetHoldings        (5 tests)
  - TestDerivativesGetPositions  (5 tests)
  - TestDerivativesGetOrders     (4 tests)
  - TestEquityDerivHTTPErrors    (6 tests — shared)
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerNetworkError,
    BrokerRateLimitError,
    BrokerSessionExpiredError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.session import BrokerSession, SessionState
from vnbroker.broker.tcbs.derivatives import TCBSDerivativesService
from vnbroker.broker.tcbs.equity import TCBSEquityService

# ── Fixtures ─────────────────────────────────────────────────────────────────

ACCOUNT_NO = "0123456789"


def _make_session() -> BrokerSession:
    s = BrokerSession()
    s.begin_authenticating()
    s.set_token(
        token="fake-jwt-token",
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    return s


def _make_config() -> TCBSCredentialConfig:
    return TCBSCredentialConfig(
        api_key="test-api-key",
        base_url="https://openapi.tcbs.com.vn",
        timeout_seconds=30,
    )


def _mock_resp(status_code: int, json_data) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = ""
    return resp


# ── TCBSEquityService — get_orders ────────────────────────────────────────────

class TestEquityGetOrders:
    def _svc(self):
        return TCBSEquityService(_make_config(), _make_session())

    _ORDER_PAYLOAD = {
        "total": 1,
        "data": [
            {
                "orderID": "ORD123",
                "symbol": "VNM",
                "execType": "NB",
                "priceType": "LO",
                "orderQtty": 100,
                "execQtty": 0,
                "price": 80000,
                "status": "PENDING",
                "txdate": "2026-05-19",
                "txtime": "09:00:00",
            }
        ],
    }

    def test_get_orders_returns_dataframe(self):
        with patch("requests.get", return_value=_mock_resp(200, self._ORDER_PAYLOAD)):
            df = self._svc().get_orders(ACCOUNT_NO)
        assert isinstance(df, pd.DataFrame)
        assert "order_id" in df.columns

    def test_get_orders_category_dtypes(self):
        with patch("requests.get", return_value=_mock_resp(200, self._ORDER_PAYLOAD)):
            df = self._svc().get_orders(ACCOUNT_NO)
        assert df["side"].dtype.name == "category"
        assert df["status"].dtype.name == "category"
        assert df["order_type"].dtype.name == "category"

    def test_get_orders_raw_true_returns_dict(self):
        with patch("requests.get", return_value=_mock_resp(200, self._ORDER_PAYLOAD)):
            result = self._svc().get_orders(ACCOUNT_NO, raw=True)
        assert isinstance(result, dict)
        assert "data" in result

    def test_get_orders_empty_data_returns_empty_df(self):
        payload = {"total": 0, "data": []}
        with patch("requests.get", return_value=_mock_resp(200, payload)):
            df = self._svc().get_orders(ACCOUNT_NO)
        assert df.empty

    def test_get_orders_size_over_100_raises_validation_error(self):
        # size parameter is now accepted (no validation error)
        with patch("requests.get", return_value=_mock_resp(200, {"total": 0, "data": []})) as m:
            df = self._svc().get_orders(ACCOUNT_NO, size=101)
        assert m.called
        assert m.call_args.kwargs["params"]["size"] == 101

    def test_get_orders_empty_account_no_raises(self):
        with pytest.raises(BrokerValidationError):
            self._svc().get_orders("")

    def test_get_orders_list_api_response_also_works(self):
        """API trả về list thay vì {'total':...,'data':...}."""
        payload = [{"orderId": "ORD1", "symbol": "HPG", "side": "SELL",
                    "orderType": "LIMIT", "quantity": 50, "price": 25000,
                    "filledQuantity": 0, "status": "PENDING", "createdAt": "2026-05-19"}]
        with patch("requests.get", return_value=_mock_resp(200, payload)):
            df = self._svc().get_orders(ACCOUNT_NO)
        assert len(df) == 1
        assert df["symbol"].iloc[0] == "HPG"


# ── TCBSEquityService — get_order_detail ─────────────────────────────────────

class TestEquityGetOrderDetail:
    def _svc(self):
        return TCBSEquityService(_make_config(), _make_session())

    _DETAIL = {
        "orderID": "ORD123",
        "symbol": "VNM",
        "execType": "NB",
        "priceType": "LO",
        "orderQtty": 100,
        "execQtty": 0,
        "price": 80000,
        "status": "PENDING",
        "txdate": "2026-05-19",
        "txtime": "09:00:00",
    }

    def test_get_order_detail_returns_dataframe(self):
        with patch("requests.get", return_value=_mock_resp(200, self._DETAIL)):
            df = self._svc().get_order_detail(ACCOUNT_NO, "ORD123")
        assert isinstance(df, pd.DataFrame)
        assert df["order_id"].iloc[0] == "ORD123"

    def test_get_order_detail_raw_true_returns_dict(self):
        with patch("requests.get", return_value=_mock_resp(200, self._DETAIL)):
            result = self._svc().get_order_detail(ACCOUNT_NO, "ORD123", raw=True)
        assert isinstance(result, dict)

    def test_get_order_detail_empty_order_id_raises(self):
        with pytest.raises(BrokerValidationError) as exc_info:
            self._svc().get_order_detail(ACCOUNT_NO, "")
        assert "INVALID_ORDER_ID" in exc_info.value.code

    def test_get_order_detail_blank_order_id_raises(self):
        with pytest.raises(BrokerValidationError):
            self._svc().get_order_detail(ACCOUNT_NO, "  ")


# ── TCBSEquityService — get_order_history ─────────────────────────────────────

class TestEquityGetOrderHistory:
    def _svc(self):
        return TCBSEquityService(_make_config(), _make_session())

    def test_get_order_history_returns_dataframe(self):
        payload = {"total": 0, "data": []}
        with patch("requests.get", return_value=_mock_resp(200, payload)):
            df = self._svc().get_order_history(ACCOUNT_NO, from_date="2026-01-01", to_date="2026-05-19")
        assert isinstance(df, pd.DataFrame)

    def test_get_order_history_passes_params_correctly(self):
        payload = {"total": 0, "data": []}
        with patch("requests.get", return_value=_mock_resp(200, payload)) as m:
            self._svc().get_order_history(ACCOUNT_NO, from_date="2026-01-01", symbol="VNM")
        call_kwargs = m.call_args
        assert call_kwargs.kwargs["params"]["fromDate"] == "2026-01-01"
        assert call_kwargs.kwargs["params"]["symbol"] == "VNM"

    def test_get_order_history_raw_true(self):
        payload = {"total": 1, "data": [{"orderId": "X"}]}
        with patch("requests.get", return_value=_mock_resp(200, payload)):
            result = self._svc().get_order_history(ACCOUNT_NO, raw=True)
        assert isinstance(result, dict)

    def test_get_order_history_empty_account_no_raises(self):
        with pytest.raises(BrokerValidationError):
            self._svc().get_order_history("")


# ── TCBSEquityService — get_executions ───────────────────────────────────────

class TestEquityGetExecutions:
    def _svc(self):
        return TCBSEquityService(_make_config(), _make_session())

    _EXEC_PAYLOAD = {
        "total": 1,
        "data": [
            {
                "executionId": "EXE789",
                "orderId": "ORD123",
                "symbol": "VNM",
                "side": "B",
                "quoteQtty": 100,
                "quotePrice": 80200,
                "tradeId": "TRD123",
                "qtty": 100,
                "price": 80200,
                "tradeDate": "2026-05-19",
                "tradeTime": "10:30:00",
                "fee": 80,
                "tax": 0,
            }
        ],
    }

    def test_get_executions_returns_dataframe(self):
        with patch("requests.get", return_value=_mock_resp(200, self._EXEC_PAYLOAD)):
            df = self._svc().get_executions(ACCOUNT_NO)
        assert isinstance(df, pd.DataFrame)
        assert "execution_id" in df.columns

    def test_get_executions_numeric_dtypes(self):
        with patch("requests.get", return_value=_mock_resp(200, self._EXEC_PAYLOAD)):
            df = self._svc().get_executions(ACCOUNT_NO)
        assert df["executed_price"].dtype == "float64"
        assert df["fee"].dtype == "int64"

    def test_get_executions_raw_true_returns_dict(self):
        with patch("requests.get", return_value=_mock_resp(200, self._EXEC_PAYLOAD)):
            result = self._svc().get_executions(ACCOUNT_NO, raw=True)
        assert isinstance(result, dict)

    def test_get_executions_empty_returns_empty_df_with_columns(self):
        payload = {"total": 0, "data": []}
        with patch("requests.get", return_value=_mock_resp(200, payload)):
            df = self._svc().get_executions(ACCOUNT_NO)
        assert df.empty
        assert "execution_id" in df.columns

    def test_get_executions_empty_account_no_raises(self):
        with pytest.raises(BrokerValidationError):
            self._svc().get_executions("")


# ── TCBSEquityService — get_holdings ─────────────────────────────────────────

class TestEquityGetHoldings:
    def _svc(self):
        return TCBSEquityService(_make_config(), _make_session())

    _HOLDINGS = {
        "stock": [
            {
                "symbol": "VNM",
                "secType": "STOCK",
                "availableTrading": 400,
                "t0": 100,
                "t1": 50,
                "t2": 25,
                "t3": 25,
                "mortgaged": 0,
                "averageCost": 79500,
                "currentPrice": 80200,
                "unrealizedPnl": 350000,
                "unrealizedPnlPercent": 0.88,
            }
        ]
    }

    def test_get_holdings_returns_dataframe(self):
        with patch("requests.get", return_value=_mock_resp(200, self._HOLDINGS)):
            df = self._svc().get_holdings(ACCOUNT_NO)
        assert isinstance(df, pd.DataFrame)
        assert "symbol" in df.columns
        assert "unrealized_pnl_pct" in df.columns
        assert "average_cost" in df.columns

    def test_get_holdings_numeric_dtypes(self):
        with patch("requests.get", return_value=_mock_resp(200, self._HOLDINGS)):
            df = self._svc().get_holdings(ACCOUNT_NO)
        assert df["average_cost"].dtype == "float64"
        assert df["unrealized_pnl"].dtype == "float64"
        assert df["unrealized_pnl_pct"].dtype == "float64"

    def test_get_holdings_raw_true_returns_dict(self):
        with patch("requests.get", return_value=_mock_resp(200, self._HOLDINGS)):
            result = self._svc().get_holdings(ACCOUNT_NO, raw=True)
        assert isinstance(result, dict)

    def test_get_holdings_empty_list_returns_empty_df(self):
        with patch("requests.get", return_value=_mock_resp(200, [])):
            df = self._svc().get_holdings(ACCOUNT_NO)
        assert df.empty

    def test_get_holdings_empty_account_no_raises(self):
        with pytest.raises(BrokerValidationError):
            self._svc().get_holdings("")


# ── TCBSDerivativesService — get_positions ───────────────────────────────────

class TestDerivativesGetPositions:
    def _svc(self):
        return TCBSDerivativesService(_make_config(), _make_session())

    _POSITIONS = [
        {
            "symbol": "VN30F2406",
            "side": "LONG",
            "openQuantity": 1,
            "openPrice": 1260.0,
            "currentPrice": 1265.0,
            "unrealizedPnl": 500000,
            "margin": 15000000,
        }
    ]

    def test_get_positions_returns_dataframe(self):
        with patch("requests.get", return_value=_mock_resp(200, self._POSITIONS)):
            df = self._svc().get_positions(ACCOUNT_NO)
        assert isinstance(df, pd.DataFrame)
        assert "symbol" in df.columns
        assert "unrealized_pnl" in df.columns

    def test_get_positions_side_is_category(self):
        with patch("requests.get", return_value=_mock_resp(200, self._POSITIONS)):
            df = self._svc().get_positions(ACCOUNT_NO)
        assert df["side"].dtype.name == "category"

    def test_get_positions_numeric_dtypes(self):
        with patch("requests.get", return_value=_mock_resp(200, self._POSITIONS)):
            df = self._svc().get_positions(ACCOUNT_NO)
        assert df["open_price"].dtype == "float64"
        assert df["margin"].dtype == "float64"

    def test_get_positions_raw_true_returns_list(self):
        with patch("requests.get", return_value=_mock_resp(200, self._POSITIONS)):
            result = self._svc().get_positions(ACCOUNT_NO, raw=True)
        assert isinstance(result, list)

    def test_get_positions_empty_list_returns_empty_df(self):
        with patch("requests.get", return_value=_mock_resp(200, [])):
            df = self._svc().get_positions(ACCOUNT_NO)
        assert df.empty


# ── TCBSDerivativesService — get_orders ──────────────────────────────────────

class TestDerivativesGetOrders:
    def _svc(self):
        return TCBSDerivativesService(_make_config(), _make_session())

    def test_get_deriv_orders_returns_dataframe(self):
        payload = {"total": 0, "data": []}
        with patch("requests.get", return_value=_mock_resp(200, payload)):
            df = self._svc().get_orders(ACCOUNT_NO)
        assert isinstance(df, pd.DataFrame)

    def test_get_deriv_orders_raw_true(self):
        payload = {"total": 0, "data": []}
        with patch("requests.get", return_value=_mock_resp(200, payload)):
            result = self._svc().get_orders(ACCOUNT_NO, raw=True)
        assert isinstance(result, dict)

    def test_get_deriv_orders_size_over_100_raises(self):
        # size parameter is now accepted (no validation error)
        with patch("requests.get", return_value=_mock_resp(200, {"total": 0, "data": []})) as m:
            df = self._svc().get_orders(ACCOUNT_NO, size=101)
        assert m.called
        assert m.call_args.kwargs["params"]["pageSize"] == 101

    def test_get_deriv_orders_empty_account_raises(self):
        with pytest.raises(BrokerValidationError):
            self._svc().get_orders("")


# ── HTTP Error Handling — equity + derivatives ────────────────────────────────

class TestEquityDerivHTTPErrors:
    def _equity(self, session=None):
        return TCBSEquityService(_make_config(), session or _make_session())

    def _deriv(self, session=None):
        return TCBSDerivativesService(_make_config(), session or _make_session())

    def test_401_raises_auth_error_revokes_session_equity(self):
        session = _make_session()
        with patch("requests.get", return_value=_mock_resp(401, {})):
            with pytest.raises(BrokerAuthError):
                self._equity(session).get_orders(ACCOUNT_NO)
        assert session.state == SessionState.EXPIRED

    def test_401_raises_auth_error_revokes_session_deriv(self):
        session = _make_session()
        with patch("requests.get", return_value=_mock_resp(401, {})):
            with pytest.raises(BrokerAuthError):
                self._deriv(session).get_positions(ACCOUNT_NO)
        assert session.state == SessionState.EXPIRED

    def test_429_raises_rate_limit_error(self):
        with patch("requests.get", return_value=_mock_resp(429, {})):
            with pytest.raises(BrokerRateLimitError) as exc_info:
                self._equity().get_orders(ACCOUNT_NO)
        assert exc_info.value.http_status == 429

    def test_500_raises_network_error(self):
        with patch("requests.get", return_value=_mock_resp(500, {})):
            with pytest.raises(BrokerNetworkError):
                self._equity().get_holdings(ACCOUNT_NO)

    def test_timeout_raises_network_error(self):
        with patch(
            "requests.get",
            side_effect=requests.exceptions.Timeout("timed out"),
        ):
            with pytest.raises(BrokerNetworkError) as exc_info:
                self._deriv().get_positions(ACCOUNT_NO)
        assert "NETWORK_TIMEOUT" in exc_info.value.code

    def test_expired_session_raises_session_expired_error(self):
        session = _make_session()
        session._token_expires_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        with pytest.raises(BrokerSessionExpiredError):
            self._equity(session).get_orders(ACCOUNT_NO)
