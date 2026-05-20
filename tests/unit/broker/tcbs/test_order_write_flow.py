"""
tests.unit.broker.tcbs.test_order_write_flow
=============================================
Unit tests cho write methods của TCBSEquityService:
  place_order(), modify_order(), cancel_order()

Test categories:
  - TestPlaceOrderDryRun         (6 tests — dry_run=True gate)
  - TestPlaceOrderValidation     (7 tests — input validation)
  - TestPlaceOrderLiveExecution  (5 tests — dry_run=False happy path + errors)
  - TestModifyOrderDryRun        (3 tests)
  - TestModifyOrderValidation    (4 tests)
  - TestModifyOrderLive          (3 tests)
  - TestCancelOrderDryRun        (3 tests)
  - TestCancelOrderValidation    (3 tests)
  - TestCancelOrderLive          (3 tests)
  - TestWriteGateIntegration     (4 tests — guard behaviors)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerNetworkError,
    BrokerOrderError,
    BrokerPermissionError,
    BrokerRateLimitError,
    BrokerSessionExpiredError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.session import BrokerSession, SessionState
from vnbroker.broker.tcbs.equity import TCBSEquityService

# ── Fixtures ─────────────────────────────────────────────────────────────────

ACCOUNT_NO = "0123456789"
ORDER_ID = "ORD123456"
REQUEST_ID = str(uuid.uuid4())
PIN = "123456"


def _make_session(write_enabled: bool = False) -> BrokerSession:
    s = BrokerSession()
    s.begin_authenticating()
    s.set_token(
        token="fake-jwt-token",
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    if write_enabled:
        s.enable_write()
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
    resp.text = str(json_data)
    return resp


def _svc(write_enabled: bool = False) -> TCBSEquityService:
    return TCBSEquityService(_make_config(), _make_session(write_enabled))


# ── TestPlaceOrderDryRun ─────────────────────────────────────────────────────

class TestPlaceOrderDryRun:
    def test_dry_run_returns_dict_without_http_call(self):
        svc = _svc(write_enabled=False)
        with patch("requests.request") as m:
            result = svc.place_order(
                ACCOUNT_NO, "VNM", "BUY", "LIMIT", 100, 80000, PIN, REQUEST_ID,
                dry_run=True,
            )
        m.assert_not_called()
        assert isinstance(result, dict)
        assert result["dry_run"] is True

    def test_dry_run_contains_operation_name(self):
        result = _svc().place_order(
            ACCOUNT_NO, "VNM", "BUY", "LIMIT", 100, 80000, PIN, REQUEST_ID,
            dry_run=True,
        )
        assert result["operation"] == "_gated_place_order"

    def test_dry_run_default_is_true(self):
        """Gọi không truyền dry_run → phải là dry_run=True mặc định."""
        result = _svc().place_order(
            ACCOUNT_NO, "VNM", "BUY", "LIMIT", 100, 80000, PIN, REQUEST_ID,
        )
        assert result["dry_run"] is True

    def test_dry_run_does_not_require_write_enabled(self):
        """dry_run=True không cần session.enable_write()."""
        svc = _svc(write_enabled=False)
        result = svc.place_order(
            ACCOUNT_NO, "VNM", "BUY", "LIMIT", 100, 80000, PIN, REQUEST_ID,
            dry_run=True,
        )
        assert result["dry_run"] is True

    def test_dry_run_pin_not_exposed_in_result(self):
        """Kết quả dry_run KHÔNG được chứa pin_code value."""
        result = _svc().place_order(
            ACCOUNT_NO, "VNM", "BUY", "LIMIT", 100, 80000, "654321", REQUEST_ID,
            dry_run=True,
        )
        result_str = str(result)
        assert "654321" not in result_str

    def test_dry_run_modify_returns_dict_no_http(self):
        with patch("requests.request") as m:
            result = _svc().modify_order(ACCOUNT_NO, ORDER_ID, 200, 79000, REQUEST_ID, dry_run=True)
        m.assert_not_called()
        assert result["dry_run"] is True

    def test_dry_run_cancel_returns_dict_no_http(self):
        with patch("requests.request") as m:
            result = _svc().cancel_order(ACCOUNT_NO, ORDER_ID, REQUEST_ID, dry_run=True)
        m.assert_not_called()
        assert result["dry_run"] is True


# ── TestPlaceOrderValidation ─────────────────────────────────────────────────

class TestPlaceOrderValidation:
    """Validation xảy ra TRƯỚC write_gate check (dry_run cũng validate)."""

    def _place(self, **overrides):
        defaults = dict(
            account_no=ACCOUNT_NO,
            symbol="VNM",
            side="BUY",
            order_type="LIMIT",
            quantity=100,
            price=80000,
            pin_code=PIN,
            request_id=REQUEST_ID,
            dry_run=True,
        )
        defaults.update(overrides)
        svc = _svc()
        return svc.place_order(**defaults)

    def test_empty_account_no_raises(self):
        with pytest.raises(BrokerValidationError) as exc_info:
            self._place(account_no="")
        assert "INVALID_ACCOUNT_NO" in exc_info.value.code

    def test_empty_symbol_raises(self):
        with pytest.raises(BrokerValidationError) as exc_info:
            self._place(symbol="")
        assert "INVALID_SYMBOL" in exc_info.value.code

    def test_invalid_side_raises(self):
        with pytest.raises(BrokerValidationError) as exc_info:
            self._place(side="LONG")
        assert "INVALID_SIDE" in exc_info.value.code

    def test_invalid_order_type_raises(self):
        with pytest.raises(BrokerValidationError) as exc_info:
            self._place(order_type="FOO")
        assert "INVALID_ORDER_TYPE" in exc_info.value.code

    def test_negative_quantity_raises(self):
        with pytest.raises(BrokerValidationError) as exc_info:
            self._place(quantity=-1)
        assert "INVALID_QUANTITY" in exc_info.value.code

    def test_zero_quantity_raises(self):
        with pytest.raises(BrokerValidationError) as exc_info:
            self._place(quantity=0)
        assert "INVALID_QUANTITY" in exc_info.value.code

    def test_empty_request_id_raises(self):
        with pytest.raises(BrokerValidationError) as exc_info:
            self._place(request_id="")
        assert "MISSING_REQUEST_ID" in exc_info.value.code


# ── TestPlaceOrderLiveExecution ───────────────────────────────────────────────

class TestPlaceOrderLiveExecution:
    def _live_svc(self):
        return _svc(write_enabled=True)

    _SUCCESS = {
        "orderId": "ORD999",
        "symbol": "VNM",
        "status": "PENDING",
        "createdAt": "2026-05-19T09:15:00+07:00",
    }

    def test_place_order_live_calls_post(self):
        with patch("requests.request", return_value=_mock_resp(201, self._SUCCESS)) as m:
            result = self._live_svc().place_order(
                ACCOUNT_NO, "VNM", "BUY", "LIMIT", 100, 80000, PIN, REQUEST_ID,
                dry_run=False,
            )
        assert m.called
        assert m.call_args.args[0] == "POST"
        assert result["orderId"] == "ORD999"

    def test_place_order_live_422_raises_order_error(self):
        with patch("requests.request", return_value=_mock_resp(422, {"error": "OUT_OF_HOURS"})):
            with pytest.raises(BrokerOrderError) as exc_info:
                self._live_svc().place_order(
                    ACCOUNT_NO, "VNM", "BUY", "LIMIT", 100, 80000, PIN, REQUEST_ID,
                    dry_run=False,
                )
        assert exc_info.value.http_status == 422

    def test_place_order_live_401_revokes_session(self):
        session = _make_session(write_enabled=True)
        svc = TCBSEquityService(_make_config(), session)
        with patch("requests.request", return_value=_mock_resp(401, {})):
            with pytest.raises(BrokerAuthError):
                svc.place_order(
                    ACCOUNT_NO, "VNM", "BUY", "LIMIT", 100, 80000, PIN, REQUEST_ID,
                    dry_run=False,
                )
        assert session.state == SessionState.EXPIRED

    def test_place_order_live_500_raises_network_error(self):
        with patch("requests.request", return_value=_mock_resp(500, {})):
            with pytest.raises(BrokerNetworkError):
                self._live_svc().place_order(
                    ACCOUNT_NO, "VNM", "BUY", "LIMIT", 100, 80000, PIN, REQUEST_ID,
                    dry_run=False,
                )

    def test_place_order_live_timeout_raises_network_error(self):
        with patch("requests.request", side_effect=requests.exceptions.Timeout()):
            with pytest.raises(BrokerNetworkError) as exc_info:
                self._live_svc().place_order(
                    ACCOUNT_NO, "VNM", "BUY", "LIMIT", 100, 80000, PIN, REQUEST_ID,
                    dry_run=False,
                )
        assert "NETWORK_TIMEOUT" in exc_info.value.code


# ── TestModifyOrderDryRun ─────────────────────────────────────────────────────

class TestModifyOrderDryRun:
    def test_modify_dry_run_default_true(self):
        result = _svc().modify_order(ACCOUNT_NO, ORDER_ID, 200, 79000, REQUEST_ID)
        assert result["dry_run"] is True

    def test_modify_dry_run_operation_name(self):
        result = _svc().modify_order(ACCOUNT_NO, ORDER_ID, 200, 79000, REQUEST_ID, dry_run=True)
        assert result["operation"] == "_gated_modify_order"

    def test_modify_dry_run_no_write_required(self):
        svc = _svc(write_enabled=False)
        result = svc.modify_order(ACCOUNT_NO, ORDER_ID, 200, 79000, REQUEST_ID, dry_run=True)
        assert result["dry_run"] is True


# ── TestModifyOrderValidation ─────────────────────────────────────────────────

class TestModifyOrderValidation:
    def test_empty_order_id_raises(self):
        with pytest.raises(BrokerValidationError):
            _svc().modify_order(ACCOUNT_NO, "", 200, 79000, REQUEST_ID, dry_run=False)

    def test_zero_quantity_raises(self):
        with pytest.raises(BrokerValidationError):
            _svc(write_enabled=True).modify_order(ACCOUNT_NO, ORDER_ID, 0, 79000, REQUEST_ID, dry_run=False)

    def test_negative_price_raises(self):
        with pytest.raises(BrokerValidationError):
            _svc(write_enabled=True).modify_order(ACCOUNT_NO, ORDER_ID, 100, -1, REQUEST_ID, dry_run=False)

    def test_empty_request_id_raises(self):
        with pytest.raises(BrokerValidationError):
            _svc(write_enabled=True).modify_order(ACCOUNT_NO, ORDER_ID, 100, 79000, "", dry_run=False)


# ── TestModifyOrderLive ───────────────────────────────────────────────────────

class TestModifyOrderLive:
    def _live_svc(self):
        return _svc(write_enabled=True)

    def test_modify_order_live_calls_put(self):
        with patch("requests.request", return_value=_mock_resp(200, {"orderId": ORDER_ID})) as m:
            result = self._live_svc().modify_order(ACCOUNT_NO, ORDER_ID, 200, 79000, REQUEST_ID, dry_run=False)
        assert m.call_args.args[0] == "PUT"
        assert result["orderId"] == ORDER_ID

    def test_modify_order_live_422_raises_order_error(self):
        with patch("requests.request", return_value=_mock_resp(422, {})):
            with pytest.raises(BrokerOrderError):
                self._live_svc().modify_order(ACCOUNT_NO, ORDER_ID, 200, 79000, REQUEST_ID, dry_run=False)

    def test_modify_order_live_429_raises_rate_limit(self):
        with patch("requests.request", return_value=_mock_resp(429, {})):
            with pytest.raises(BrokerRateLimitError):
                self._live_svc().modify_order(ACCOUNT_NO, ORDER_ID, 200, 79000, REQUEST_ID, dry_run=False)


# ── TestCancelOrderDryRun ─────────────────────────────────────────────────────

class TestCancelOrderDryRun:
    def test_cancel_dry_run_default_true(self):
        result = _svc().cancel_order(ACCOUNT_NO, ORDER_ID, REQUEST_ID)
        assert result["dry_run"] is True

    def test_cancel_dry_run_operation_name(self):
        result = _svc().cancel_order(ACCOUNT_NO, ORDER_ID, REQUEST_ID, dry_run=True)
        assert result["operation"] == "_gated_cancel_order"

    def test_cancel_dry_run_no_write_required(self):
        result = _svc(write_enabled=False).cancel_order(ACCOUNT_NO, ORDER_ID, REQUEST_ID, dry_run=True)
        assert result["dry_run"] is True


# ── TestCancelOrderValidation ─────────────────────────────────────────────────

class TestCancelOrderValidation:
    def test_empty_order_id_raises(self):
        with pytest.raises(BrokerValidationError):
            _svc(write_enabled=True).cancel_order(ACCOUNT_NO, "", REQUEST_ID, dry_run=False)

    def test_empty_request_id_raises(self):
        with pytest.raises(BrokerValidationError):
            _svc(write_enabled=True).cancel_order(ACCOUNT_NO, ORDER_ID, "", dry_run=False)

    def test_blank_order_id_raises(self):
        with pytest.raises(BrokerValidationError):
            _svc(write_enabled=True).cancel_order(ACCOUNT_NO, "  ", REQUEST_ID, dry_run=False)


# ── TestCancelOrderLive ───────────────────────────────────────────────────────

class TestCancelOrderLive:
    def _live_svc(self):
        return _svc(write_enabled=True)

    def test_cancel_order_live_calls_delete(self):
        with patch("requests.request", return_value=_mock_resp(200, {"message": "OK"})) as m:
            result = self._live_svc().cancel_order(ACCOUNT_NO, ORDER_ID, REQUEST_ID, dry_run=False)
        assert m.call_args.args[0] == "DELETE"
        assert "message" in result

    def test_cancel_order_live_422_raises_order_error(self):
        with patch("requests.request", return_value=_mock_resp(422, {})):
            with pytest.raises(BrokerOrderError):
                self._live_svc().cancel_order(ACCOUNT_NO, ORDER_ID, REQUEST_ID, dry_run=False)

    def test_cancel_order_live_500_raises_network_error(self):
        with patch("requests.request", return_value=_mock_resp(500, {})):
            with pytest.raises(BrokerNetworkError):
                self._live_svc().cancel_order(ACCOUNT_NO, ORDER_ID, REQUEST_ID, dry_run=False)


# ── TestWriteGateIntegration ─────────────────────────────────────────────────

class TestWriteGateIntegration:
    """Write gate: dry_run=False + write NOT enabled → BrokerPermissionError."""

    def test_place_order_write_not_enabled_raises_permission_error(self):
        svc = _svc(write_enabled=False)
        with pytest.raises(BrokerPermissionError) as exc_info:
            svc.place_order(
                ACCOUNT_NO, "VNM", "BUY", "LIMIT", 100, 80000, PIN, REQUEST_ID,
                dry_run=False,
            )
        assert exc_info.value.code == "WRITE_NOT_ENABLED"

    def test_modify_order_write_not_enabled_raises_permission_error(self):
        svc = _svc(write_enabled=False)
        with pytest.raises(BrokerPermissionError) as exc_info:
            svc.modify_order(ACCOUNT_NO, ORDER_ID, 100, 79000, REQUEST_ID, dry_run=False)
        assert exc_info.value.code == "WRITE_NOT_ENABLED"

    def test_cancel_order_write_not_enabled_raises_permission_error(self):
        svc = _svc(write_enabled=False)
        with pytest.raises(BrokerPermissionError) as exc_info:
            svc.cancel_order(ACCOUNT_NO, ORDER_ID, REQUEST_ID, dry_run=False)
        assert exc_info.value.code == "WRITE_NOT_ENABLED"

    def test_place_order_write_enabled_live_calls_http(self):
        svc = _svc(write_enabled=True)
        with patch("requests.request", return_value=_mock_resp(201, {"orderId": "ORD1"})) as m:
            result = svc.place_order(
                ACCOUNT_NO, "VNM", "BUY", "LIMIT", 100, 80000, PIN, REQUEST_ID,
                dry_run=False,
            )
        assert m.called
        assert not result.get("dry_run", False)
