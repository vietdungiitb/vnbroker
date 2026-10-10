"""
tests.unit.broker.tcbs.test_tcbs_condition_order
===============================================
Unit tests cho `vnbroker.broker.tcbs.condition_orders` (lát E của TCBS Round 2).

Nguồn chuẩn: `docs/references/openapi-v1.0.0.json` (sha256 7f97d27b…42bd4a)
- ``POST /khronos/v1/order/condition/cancel``
  - requestBody ``required: ['accountId', 'orderNo']``
  - properties: ``accountId``, ``subAccountId``, ``orderNo``
  - response 200: ``{rc, rs, data[]}``

Test categories:
  - TestPathTrongSpec          (path tồn tại trong spec + khớp hằng `_PATHS`)
  - TestPayloadTheoSpec        (E1 — đúng tên field, KHÔNG `requestId`)
  - TestValidation             (validate required field trước khi gọi gate)
  - TestCancelConditionOrderDryRun   (E4 — dry_run=True không gửi HTTP)
  - TestWriteGate              (E4 — dry_run=False chưa enable_write ⇒ PermissionError)
  - TestLiveExecution          (dry_run=False + enable_write ⇒ HTTP đúng URL/payload)
  - TestHttpErrorMapping       (bản copy `_post` giữ nguyên ngữ nghĩa lỗi)
  - TestSignature              (`dry_run` keyword-only — bẫy guards.py:46)
"""
from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerNetworkError,
    BrokerOrderError,
    BrokerPermissionError,
    BrokerRateLimitError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.tcbs.condition_orders import (
    _PATHS,
    TCBSConditionOrderService,
)

# ── Hằng test ───────────────────────────────────────────────────────────────

SPEC_PATH = Path(__file__).resolve().parents[4] / "docs" / "references" / "openapi-v1.0.0.json"
SPEC_PATH_TEXT = "/khronos/v1/order/condition/cancel"

ACCOUNT_ID = "105C334455"
SUB_ACCOUNT_ID = "D1234"
ORDER_NO = "pk_order_0001"

BASE_URL = "https://openapi.tcbs.com.vn"


def _spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


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
        base_url=BASE_URL,
        timeout_seconds=30,
    )


def _mock_resp(status_code: int, json_data) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


def _svc(write_enabled: bool = False) -> TCBSConditionOrderService:
    return TCBSConditionOrderService(_make_config(), _make_session(write_enabled))


def _ok_response() -> MagicMock:
    return _mock_resp(200, {"rc": "1", "rs": "", "data": []})


# ── TestPathTrongSpec ───────────────────────────────────────────────────────


class TestPathTrongSpec:
    def test_path_ton_tai_trong_spec(self):
        assert SPEC_PATH_TEXT in _spec()["paths"]

    def test_verb_la_post(self):
        assert "post" in _spec()["paths"][SPEC_PATH_TEXT]

    def test_hang_paths_khop_spec(self):
        assert _PATHS["cancel"] == SPEC_PATH_TEXT


# ── TestPayloadTheoSpec (E1) ───────────────────────────────────────────────


class TestPayloadTheoSpec:
    def test_required_trong_spec_la_account_id_va_order_no(self):
        schema = _spec()["paths"][SPEC_PATH_TEXT]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
        assert schema["required"] == ["accountId", "orderNo"]

    def test_payload_dung_ten_field_trong_spec(self):
        """E1 — payload phải là {accountId, subAccountId, orderNo}, đúng tên trong spec."""
        svc = _svc(write_enabled=True)
        with patch("requests.request", return_value=_ok_response()) as m:
            svc.cancel_condition_order(
                ACCOUNT_ID, ORDER_NO, SUB_ACCOUNT_ID, dry_run=False
            )
        payload = m.call_args.kwargs["json"]
        schema = _spec()["paths"][SPEC_PATH_TEXT]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
        assert set(payload) == set(schema["properties"])
        assert payload == {
            "accountId": ACCOUNT_ID,
            "subAccountId": SUB_ACCOUNT_ID,
            "orderNo": ORDER_NO,
        }

    def test_payload_khong_co_requestId(self):
        """P5 — `requestId` không tồn tại trong spec (đếm chuỗi trong toàn spec = 0 lần)."""
        svc = _svc(write_enabled=True)
        with patch("requests.request", return_value=_ok_response()) as m:
            svc.cancel_condition_order(ACCOUNT_ID, ORDER_NO, SUB_ACCOUNT_ID, dry_run=False)
        assert "requestId" not in m.call_args.kwargs["json"]

    def test_ten_field_lay_tu_spec_khong_tu_dien_tay(self):
        """Mọi key gửi đi phải là key có thật trong spec."""
        schema = _spec()["paths"][SPEC_PATH_TEXT]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
        svc = _svc(write_enabled=True)
        with patch("requests.request", return_value=_ok_response()) as m:
            svc.cancel_condition_order(ACCOUNT_ID, ORDER_NO, SUB_ACCOUNT_ID, dry_run=False)
        assert set(m.call_args.kwargs["json"]).issubset(schema["properties"])

    def test_sub_account_id_bo_trong_khi_rong(self):
        """`subAccountId` không nằm trong `required` → bỏ trống thì không gửi chuỗi rỗng."""
        svc = _svc(write_enabled=True)
        with patch("requests.request", return_value=_ok_response()) as m:
            svc.cancel_condition_order(ACCOUNT_ID, ORDER_NO, "", dry_run=False)
        assert m.call_args.kwargs["json"] == {"accountId": ACCOUNT_ID, "orderNo": ORDER_NO}

    def test_url_dung_base_url_cong_path(self):
        svc = _svc(write_enabled=True)
        with patch("requests.request", return_value=_ok_response()) as m:
            svc.cancel_condition_order(ACCOUNT_ID, ORDER_NO, SUB_ACCOUNT_ID, dry_run=False)
        assert m.call_args.args[0] == "POST"
        assert m.call_args.args[1] == f"{BASE_URL}{SPEC_PATH_TEXT}"

    def test_response_raw_dict(self):
        svc = _svc(write_enabled=True)
        payload = {"rc": "1", "rs": "", "data": []}
        with patch("requests.request", return_value=_mock_resp(200, payload)):
            assert svc.cancel_condition_order(
                ACCOUNT_ID, ORDER_NO, SUB_ACCOUNT_ID, dry_run=False
            ) == payload


# ── TestValidation ──────────────────────────────────────────────────────────


class TestValidation:
    def test_account_id_rong_raise(self):
        with patch("requests.request") as m:
            with pytest.raises(BrokerValidationError) as exc:
                _svc().cancel_condition_order("", ORDER_NO)
        assert exc.value.code == "INVALID_ACCOUNT_ID"
        m.assert_not_called()

    def test_account_id_toan_khoang_raise(self):
        with patch("requests.request") as m:
            with pytest.raises(BrokerValidationError) as exc:
                _svc().cancel_condition_order("   ", ORDER_NO)
        assert exc.value.code == "INVALID_ACCOUNT_ID"
        m.assert_not_called()

    def test_order_no_rong_raise(self):
        with patch("requests.request") as m:
            with pytest.raises(BrokerValidationError) as exc:
                _svc().cancel_condition_order(ACCOUNT_ID, "  ")
        assert exc.value.code == "INVALID_ORDER_NO"
        m.assert_not_called()

    def test_validation_chay_truoc_gate(self):
        """dry_run=False + write chưa bật: lỗi validate phải báo trước PermissionError."""
        with patch("requests.request") as m:
            with pytest.raises(BrokerValidationError):
                _svc(write_enabled=False).cancel_condition_order("", "", dry_run=False)
        m.assert_not_called()

    def test_gia_tri_dau_trang_boc(self):
        svc = _svc(write_enabled=True)
        with patch("requests.request", return_value=_ok_response()) as m:
            svc.cancel_condition_order("  105C334455  ", " pk_1 ", dry_run=False)
        assert m.call_args.kwargs["json"] == {
            "accountId": "105C334455",
            "orderNo": "pk_1",
        }


# ── TestCancelConditionOrderDryRun (E4) ────────────────────────────────────


class TestCancelConditionOrderDryRun:
    def test_dry_run_khong_gui_http(self):
        with patch("requests.request") as m:
            result = _svc().cancel_condition_order(
                ACCOUNT_ID, ORDER_NO, SUB_ACCOUNT_ID, dry_run=True
            )
        m.assert_not_called()
        assert isinstance(result, dict)
        assert result["dry_run"] is True

    def test_dry_run_mac_dinh_la_true(self):
        """Gọi không truyền dry_run → phải là dry_run=True mặc định."""
        with patch("requests.request") as m:
            result = _svc().cancel_condition_order(ACCOUNT_ID, ORDER_NO)
        m.assert_not_called()
        assert result["dry_run"] is True

    def test_dry_run_khong_need_write_enabled(self):
        with patch("requests.request") as m:
            result = _svc(write_enabled=False).cancel_condition_order(
                ACCOUNT_ID, ORDER_NO, SUB_ACCOUNT_ID, dry_run=True
            )
        m.assert_not_called()
        assert result["dry_run"] is True

    def test_dry_run_envelope_co_operation_name(self):
        result = _svc().cancel_condition_order(ACCOUNT_ID, ORDER_NO, dry_run=True)
        assert result["operation"] == "_gated_cancel_condition_order"


# ── TestWriteGate (E4) ─────────────────────────────────────────────────────


class TestWriteGate:
    def test_dry_run_false_chua_enable_write_raise_permission(self):
        with patch("requests.request") as m:
            with pytest.raises(BrokerPermissionError) as exc:
                _svc(write_enabled=False).cancel_condition_order(
                    ACCOUNT_ID, ORDER_NO, SUB_ACCOUNT_ID, dry_run=False
                )
        assert exc.value.code == "WRITE_NOT_ENABLED"
        m.assert_not_called()

    def test_gated_method_co_write_gate(self):
        """`@write_gate` phải bọc đúng method gửi HTTP."""
        assert hasattr(TCBSConditionOrderService, "_gated_cancel_condition_order")


# ── TestLiveExecution ───────────────────────────────────────────────────────


class TestLiveExecution:
    def test_dry_run_false_co_enable_write_thi_http(self):
        with patch("requests.request", return_value=_ok_response()) as m:
            result = _svc(write_enabled=True).cancel_condition_order(
                ACCOUNT_ID, ORDER_NO, SUB_ACCOUNT_ID, dry_run=False
            )
        m.assert_called_once()
        assert result["rc"] == "1"

    def test_bearer_header_va_timeout(self):
        with patch("requests.request", return_value=_ok_response()) as m:
            _svc(write_enabled=True).cancel_condition_order(
                ACCOUNT_ID, ORDER_NO, SUB_ACCOUNT_ID, dry_run=False
            )
        kwargs = m.call_args.kwargs
        assert kwargs["headers"] == {"Authorization": "Bearer fake-jwt-token"}
        assert kwargs["timeout"] == 30


# ── TestHttpErrorMapping ────────────────────────────────────────────────────


class TestHttpErrorMapping:
    @pytest.mark.parametrize(
        "status,exc_type,code",
        [
            (400, BrokerValidationError, "BAD_REQUEST"),
            (401, BrokerAuthError, "TOKEN_EXPIRED"),
            (403, BrokerPermissionError, "FORBIDDEN"),
            (422, BrokerOrderError, "ORDER_REJECTED"),
            (429, BrokerRateLimitError, "RATE_LIMIT"),
            (500, BrokerNetworkError, "SERVER_ERROR"),
        ],
    )
    def test_http_error_mapping(self, status, exc_type, code):
        with patch("requests.request", return_value=_mock_resp(status, {"e": 1})):
            with pytest.raises(exc_type) as exc:
                _svc(write_enabled=True).cancel_condition_order(
                    ACCOUNT_ID, ORDER_NO, SUB_ACCOUNT_ID, dry_run=False
                )
        assert exc.value.code == code

    def test_timeout_raise_network_error(self):
        with patch("requests.request", side_effect=requests.exceptions.Timeout()):
            with pytest.raises(BrokerNetworkError) as exc:
                _svc(write_enabled=True).cancel_condition_order(
                    ACCOUNT_ID, ORDER_NO, SUB_ACCOUNT_ID, dry_run=False
                )
        assert exc.value.code == "NETWORK_TIMEOUT"

    def test_request_exception_raise_network_error(self):
        with patch("requests.request", side_effect=requests.exceptions.ConnectionError()):
            with pytest.raises(BrokerNetworkError) as exc:
                _svc(write_enabled=True).cancel_condition_order(
                    ACCOUNT_ID, ORDER_NO, SUB_ACCOUNT_ID, dry_run=False
                )
        assert exc.value.code == "NETWORK_ERROR"

    def test_401_revoke_session(self):
        svc = _svc(write_enabled=True)
        with patch("requests.request", return_value=_mock_resp(401, {})):
            with pytest.raises(BrokerAuthError):
                svc.cancel_condition_order(ACCOUNT_ID, ORDER_NO, dry_run=False)
        assert svc._session._token is None


# ── TestSignature ───────────────────────────────────────────────────────────


class TestSignature:
    def test_dry_run_keyword_only_default_true(self):
        """guards.py:46 đọc `dry_run` từ kwargs — nếu positional thì gate không bắt được."""
        for name in ("cancel_condition_order", "_gated_cancel_condition_order"):
            sig = inspect.signature(getattr(TCBSConditionOrderService, name))
            param = sig.parameters["dry_run"]
            assert param.kind is inspect.Parameter.KEYWORD_ONLY, name
            assert param.default is True, name

    def test_write_gate_duoc_dung(self):
        """`@write_gate` bọc method gửi HTTP (`_gated_*`), method public chỉ validate + delegate."""
        assert hasattr(TCBSConditionOrderService._gated_cancel_condition_order, "__wrapped__")
        assert not hasattr(TCBSConditionOrderService.cancel_condition_order, "__wrapped__")