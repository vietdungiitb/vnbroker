"""
tests.unit.broker.tcbs.test_tcbs_money_endpoints
================================================
Unit tests cho 4 endpoint mới của TCBSMoneyService (PLAN_TCBS_ROUND2 §3, lát M):

  GET  /hydros/v1/account/{accountNo}/pricing-policy  → get_pricing_policy()   (M1)
  POST /khronos/v1/cash/deposit/update                → deposit_margin()       (M2)
  POST /khronos/v1/cash/withdraw/update               → withdraw_margin()      (M3)
  POST /physis/v1/stock/transfer                      → transfer_between_sub_accounts() (M4)

Test categories:
  - TestPricingPolicyRead      (6 tests — M1)
  - TestDepositMargin          (8 tests — M2)
  - TestWithdrawMargin         (5 tests — M3)
  - TestStockTransfer          (6 tests — M4)
  - TestWriteGateBothBranches  (6 tests — M5: dry_run=True VÀ dry_run=False khi
                                         chưa enable_write(); cả hai đều KHÔNG
                                         gửi HTTP)
  - TestBodyMatchesSpec        (5 tests — M6: tên field đúng spec, không requestId)
  - TestMissingResponseFields  (4 tests — M7: field null vắng mặt ⇒ không KeyError)
  - TestMoneyModuleContract    (3 tests — M8 ngân sách dòng, M9 docstring, M6 grep)

Toàn bộ test OFFLINE: `requests.get`/`requests.post` được monkeypatch, không
gọi mạng. Nguồn sự thật cho tên field là docs/references/openapi-v1.0.0.json.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from vnbroker.broker.exceptions import (
    BrokerPermissionError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.tcbs.money import TCBSMoneyService

# ── Fixtures ─────────────────────────────────────────────────────────────────

ACCOUNT_NO = "0123456789"
SUB_ACCOUNT_ID = "D1234567"
DEPOSIT_PATH = "/khronos/v1/cash/deposit/update"
WITHDRAW_PATH = "/khronos/v1/cash/withdraw/update"
TRANSFER_PATH = "/physis/v1/stock/transfer"
PRICING_PATH = "/hydros/v1/account/0123456789/pricing-policy"


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


def _svc(write_enabled: bool = False) -> TCBSMoneyService:
    return TCBSMoneyService(_make_config(), _make_session(write_enabled))


def _calls(method: str):
    """Trả về payload dict đã gửi, theo đúng key trong `requests.<method>`."""
    return method.call_args.kwargs["json"]


# ── TestPricingPolicyRead — M1 ───────────────────────────────────────────────

class TestPricingPolicyRead:
    def test_path_dung_spec(self):
        with patch("requests.get") as m:
            m.return_value = _mock_resp(200, {"policies": []})
            _svc().get_pricing_policy(ACCOUNT_NO)
        assert m.call_args.args[0].endswith(PRICING_PATH)

    def test_product_id_none_khong_gui(self):
        """M1: productId=None ⇒ KHÔNG gửi query param."""
        with patch("requests.get") as m:
            m.return_value = _mock_resp(200, {})
            _svc().get_pricing_policy(ACCOUNT_NO, product_id=None)
        assert m.call_args.kwargs["params"] == {}

    def test_product_id_rong_khong_gui(self):
        with patch("requests.get") as m:
            m.return_value = _mock_resp(200, {})
            _svc().get_pricing_policy(ACCOUNT_NO, product_id="")
        assert m.call_args.kwargs["params"] == {}

    def test_product_id_co_duoc_gui(self):
        with patch("requests.get") as m:
            m.return_value = _mock_resp(200, {})
            _svc().get_pricing_policy(ACCOUNT_NO, product_id=42)
        assert m.call_args.kwargs["params"] == {"productId": 42}

    def test_account_no_rong_bi_tu_choi_truoc_khi_goi_http(self):
        """M1: validate account_no qua _validate_account_no."""
        with patch("requests.get") as m:
            with pytest.raises(BrokerValidationError):
                _svc().get_pricing_policy("")
        m.assert_not_called()

    def test_tra_dict_nguyen_goc(self):
        payload = {"data": [{"productId": 1, "rate": 12.5}]}
        with patch("requests.get", return_value=_mock_resp(200, payload)):
            result = _svc().get_pricing_policy(ACCOUNT_NO)
        assert result == payload


# ── TestDepositMargin — M2 ───────────────────────────────────────────────────

class TestDepositMargin:
    def test_dry_run_mac_dinh_khong_gui_http(self):
        with patch("requests.post") as m:
            result = _svc().deposit_margin(ACCOUNT_NO, SUB_ACCOUNT_ID, 1_000_000)
        m.assert_not_called()
        assert result["dry_run"] is True

    def test_dry_run_ten_operation(self):
        result = _svc().deposit_margin(ACCOUNT_NO, SUB_ACCOUNT_ID, 1_000_000)
        assert result["operation"] == "_gated_deposit_margin"

    def test_amount_am_validate_truoc_gate(self):
        """M2: amount <= 0 phải ném TRƯỚC gate — dù dry_run=True cũng phải ném.

        Nếu gate chạy trước validation thì dry_run=True sẽ trả envelope và
        test này fail ⇒ đây là bằng chứng thứ tự validation/gate, không chỉ
        là bằng chứng 'có validate'.
        """
        for bad in (0, -1):
            with patch("requests.post") as m:
                with pytest.raises(BrokerValidationError) as exc:
                    _svc().deposit_margin(ACCOUNT_NO, SUB_ACCOUNT_ID, bad)
                m.assert_not_called()
            assert exc.value.code == "INVALID_AMOUNT"

    def test_amount_khong_phai_so_bi_tu_choi(self):
        with pytest.raises(BrokerValidationError):
            _svc().deposit_margin(ACCOUNT_NO, SUB_ACCOUNT_ID, "abc")

    def test_account_id_rong_bi_tu_choi(self):
        with pytest.raises(BrokerValidationError) as exc:
            _svc().deposit_margin("", SUB_ACCOUNT_ID, 1000)
        assert exc.value.code == "INVALID_ACCOUNT_ID"

    def test_sub_account_id_rong_bi_tu_choi(self):
        with pytest.raises(BrokerValidationError) as exc:
            _svc().deposit_margin(ACCOUNT_NO, "   ", 1000)
        assert exc.value.code == "INVALID_SUB_ACCOUNT_ID"

    def test_live_voi_write_enabled_gui_http(self):
        body = {"cmd": "deposit", "rc": "1", "oID": "TXN001", "data": [{"transactionId": "T1"}]}
        with patch("requests.post", return_value=_mock_resp(200, body)) as m:
            result = _svc(write_enabled=True).deposit_margin(ACCOUNT_NO, SUB_ACCOUNT_ID, 1_000_000, dry_run=False)
        assert m.call_args.args[0].endswith(DEPOSIT_PATH)
        assert result == body


# ── TestWithdrawMargin — M3 ──────────────────────────────────────────────────

class TestWithdrawMargin:
    def test_dry_run_mac_dinh_khong_gui_http(self):
        with patch("requests.post") as m:
            result = _svc().withdraw_margin(ACCOUNT_NO, SUB_ACCOUNT_ID, 500_000)
        m.assert_not_called()
        assert result["dry_run"] is True

    def test_amount_am_validate(self):
        with pytest.raises(BrokerValidationError):
            _svc().withdraw_margin(ACCOUNT_NO, SUB_ACCOUNT_ID, -5)

    def test_live_duong_dung_nhanh(self):
        with patch("requests.post", return_value=_mock_resp(200, {"rc": "1"})) as m:
            _svc(write_enabled=True).withdraw_margin(ACCOUNT_NO, SUB_ACCOUNT_ID, 500_000, dry_run=False)
        assert m.call_args.args[0].endswith(WITHDRAW_PATH)

    def test_live_khong_tron_path_cua_deposit(self):
        with patch("requests.post", return_value=_mock_resp(200, {})) as m:
            _svc(write_enabled=True).withdraw_margin(ACCOUNT_NO, SUB_ACCOUNT_ID, 500_000, dry_run=False)
        assert m.call_args.args[0] != f"https://openapi.tcbs.com.vn{DEPOSIT_PATH}"

    def test_validation_chay_truoc_gate(self):
        with patch("requests.post") as m:
            with pytest.raises(BrokerValidationError):
                _svc().withdraw_margin("", "", 0)
        m.assert_not_called()


# ── TestStockTransfer — M4 ───────────────────────────────────────────────────

class TestStockTransfer:
    def test_dry_run_mac_dinh_khong_gui_http(self):
        with patch("requests.post") as m:
            result = _svc().transfer_between_sub_accounts(
                ACCOUNT_NO, SUB_ACCOUNT_ID, 100_000, "chuyen noi bo",
            )
        m.assert_not_called()
        assert result["dry_run"] is True

    def test_description_rong_bi_tu_choi(self):
        """M4: description là bắt buộc theo spec."""
        for bad in ("", "   "):
            with patch("requests.post") as m:
                with pytest.raises(BrokerValidationError) as exc:
                    _svc().transfer_between_sub_accounts(ACCOUNT_NO, SUB_ACCOUNT_ID, 100_000, bad)
                m.assert_not_called()
            assert exc.value.code == "MISSING_DESCRIPTION"

    def test_source_rong_bi_tu_choi(self):
        with pytest.raises(BrokerValidationError) as exc:
            _svc().transfer_between_sub_accounts("", SUB_ACCOUNT_ID, 100_000, "mo ta")
        assert exc.value.code == "INVALID_SOURCE_ACCOUNT"

    def test_destination_rong_bi_tu_choi(self):
        with pytest.raises(BrokerValidationError) as exc:
            _svc().transfer_between_sub_accounts(ACCOUNT_NO, "", 100_000, "mo ta")
        assert exc.value.code == "INVALID_DESTINATION_ACCOUNT"

    def test_amount_am_validate(self):
        with pytest.raises(BrokerValidationError):
            _svc().transfer_between_sub_accounts(ACCOUNT_NO, SUB_ACCOUNT_ID, 0, "mo ta")

    def test_live_duong_dung_nhanh(self):
        with patch("requests.post", return_value=_mock_resp(200, {"code": "200"})) as m:
            result = _svc(write_enabled=True).transfer_between_sub_accounts(
                ACCOUNT_NO, SUB_ACCOUNT_ID, 100_000, "chuyen noi bo", dry_run=False,
            )
        assert m.call_args.args[0].endswith(TRANSFER_PATH)
        assert result == {"code": "200"}


# ── TestWriteGateBothBranches — M5 ───────────────────────────────────────────
# Cả 2 nhánh của @write_gate, cho CẢ 3 write endpoint:
#   dry_run=True  → trả envelope, KHÔNG gửi HTTP
#   dry_run=False khi chưa enable_write() → BrokerPermissionError, KHÔNG gửi HTTP

class TestWriteGateBothBranches:
    _CALLS = {
        "deposit_margin": lambda s, **kw: s.deposit_margin(ACCOUNT_NO, SUB_ACCOUNT_ID, 1_000_000, **kw),
        "withdraw_margin": lambda s, **kw: s.withdraw_margin(ACCOUNT_NO, SUB_ACCOUNT_ID, 1_000_000, **kw),
        "transfer_between_sub_accounts": lambda s, **kw: s.transfer_between_sub_accounts(
            ACCOUNT_NO, SUB_ACCOUNT_ID, 1_000_000, "mo ta chuyen", **kw,
        ),
    }

    @pytest.mark.parametrize("method_name", sorted(_CALLS))
    def test_dry_run_true_tra_envelope_khong_gui_http(self, method_name):
        with patch("requests.post") as post, patch("requests.get") as get:
            result = self._CALLS[method_name](_svc(write_enabled=False), dry_run=True)
        post.assert_not_called()
        get.assert_not_called()
        assert result["dry_run"] is True
        assert result["operation"].startswith("_gated_")

    @pytest.mark.parametrize("method_name", sorted(_CALLS))
    def test_dry_run_false_chua_enable_write_raises(self, method_name):
        with patch("requests.post") as post:
            with pytest.raises(BrokerPermissionError) as exc:
                self._CALLS[method_name](_svc(write_enabled=False), dry_run=False)
        post.assert_not_called()
        assert exc.value.code == "WRITE_NOT_ENABLED"
        assert exc.value.http_status == 403

    @pytest.mark.parametrize("method_name", sorted(_CALLS))
    def test_dry_run_false_co_enable_write_thi_moi_gui_http(self, method_name):
        with patch("requests.post", return_value=_mock_resp(200, {"rc": "1"})) as post:
            result = self._CALLS[method_name](_svc(write_enabled=True), dry_run=False)
        post.assert_called_once()
        assert "dry_run" not in result

    @pytest.mark.parametrize(
        "method_name",
        ["deposit_margin", "withdraw_margin", "transfer_between_sub_accounts"],
    )
    def test_dry_run_la_keyword_only(self, method_name):
        """guards.py:46 đọc dry_run từ kwargs — truyền vị trí sẽ không qua gate."""
        sig = inspect.signature(getattr(TCBSMoneyService, method_name))
        param = sig.parameters["dry_run"]
        assert param.kind is inspect.Parameter.KEYWORD_ONLY
        assert param.default is True


# ── TestBodyMatchesSpec — M6 ─────────────────────────────────────────────────

class TestBodyMatchesSpec:
    def test_deposit_body_dung_ten_field_trong_spec(self):
        with patch("requests.post", return_value=_mock_resp(200, {})) as m:
            _svc(write_enabled=True).deposit_margin(
                ACCOUNT_NO, SUB_ACCOUNT_ID, 1_000_000, "nap tien margin", dry_run=False,
            )
        body = _calls(m)
        assert body == {
            "accountId": ACCOUNT_NO,
            "subAccountId": SUB_ACCOUNT_ID,
            "amount": 1_000_000.0,
            "paymentContent": "nap tien margin",
        }

    def test_payment_content_rong_thi_khong_gui(self):
        """paymentContent không nằm trong `required` của spec."""
        with patch("requests.post", return_value=_mock_resp(200, {})) as m:
            _svc(write_enabled=True).deposit_margin(ACCOUNT_NO, SUB_ACCOUNT_ID, 1000, dry_run=False)
        assert "paymentContent" not in _calls(m)

    def test_withdraw_body_dung_ten_field_trong_spec(self):
        with patch("requests.post", return_value=_mock_resp(200, {})) as m:
            _svc(write_enabled=True).withdraw_margin(ACCOUNT_NO, SUB_ACCOUNT_ID, 250_000, dry_run=False)
        assert set(_calls(m)) == {"accountId", "subAccountId", "amount"}

    def test_transfer_body_dung_ten_field_trong_spec(self):
        with patch("requests.post", return_value=_mock_resp(200, {})) as m:
            _svc(write_enabled=True).transfer_between_sub_accounts(
                ACCOUNT_NO, SUB_ACCOUNT_ID, 100_000, "chuyen noi bo", dry_run=False,
            )
        assert _calls(m) == {
            "sourceAccountNumber": ACCOUNT_NO,
            "destinationAccountNumber": SUB_ACCOUNT_ID,
            "amount": 100_000.0,
            "description": "chuyen noi bo",
        }

    def test_khong_endpoint_nao_gui_request_id(self):
        """M6/P5: `requestId` không tồn tại trong spec (đếm 0 lần) — body
        của cả 3 write endpoint không được có field này."""
        seen = []
        with patch("requests.post", return_value=_mock_resp(200, {})) as m:
            live = _svc(write_enabled=True)
            live.deposit_margin(ACCOUNT_NO, SUB_ACCOUNT_ID, 1_000_000, "nap", dry_run=False)
            seen.append(_calls(m))
            live.withdraw_margin(ACCOUNT_NO, SUB_ACCOUNT_ID, 1_000_000, "rut", dry_run=False)
            seen.append(_calls(m))
            live.transfer_between_sub_accounts(
                ACCOUNT_NO, SUB_ACCOUNT_ID, 1_000_000, "chuyen", dry_run=False,
            )
            seen.append(_calls(m))
        for body in seen:
            assert "requestId" not in body


# ── TestMissingResponseFields — M7 ───────────────────────────────────────────
# /data-types/: "Response chỉ chứa field có giá trị. Field null sẽ không xuất
# hiện trong JSON" ⇒ đọc bằng [...] sẽ KeyError. money.py không được index.

class TestMissingResponseFields:
    def test_deposit_response_chi_con_rc(self):
        body = {"rc": "1"}
        with patch("requests.post", return_value=_mock_resp(200, body)):
            result = _svc(write_enabled=True).deposit_margin(
                ACCOUNT_NO, SUB_ACCOUNT_ID, 1_000_000, dry_run=False,
            )
        assert result == body

    def test_withdraw_response_khong_con_oID_va_rs(self):
        body = {"cmd": "withdraw", "rc": "1"}
        with patch("requests.post", return_value=_mock_resp(200, body)):
            result = _svc(write_enabled=True).withdraw_margin(
                ACCOUNT_NO, SUB_ACCOUNT_ID, 1_000_000, dry_run=False,
            )
        assert result == body

    def test_transfer_response_khong_con_message(self):
        body = {"code": "200"}
        with patch("requests.post", return_value=_mock_resp(200, body)):
            result = _svc(write_enabled=True).transfer_between_sub_accounts(
                ACCOUNT_NO, SUB_ACCOUNT_ID, 1_000_000, "chuyen", dry_run=False,
            )
        assert result == body

    def test_pricing_policy_response_rong(self):
        with patch("requests.get", return_value=_mock_resp(200, {})):
            assert _svc().get_pricing_policy(ACCOUNT_NO) == {}

    def test_money_py_khong_dung_index_de_doc_response(self):
        """Chốt M1: không có `data["..."]` nào trong money.py."""
        src = Path("vnbroker/broker/tcbs/money.py").read_text(encoding="utf-8")
        assert 'data["' not in src and "data['" not in src
        assert 'record["' not in src and "row['" not in src


# ── TestMoneyModuleContract — M8, M9 ─────────────────────────────────────────

class TestMoneyModuleContract:
    def test_money_py_khong_vuot_800_dong(self):
        n = len(Path("vnbroker/broker/tcbs/money.py").read_text(encoding="utf-8").splitlines())
        assert n <= 800, f"money.py còn {n} dòng (> 800)"

    def test_docstring_khong_con_noi_khong_co_write_method(self):
        doc = (Path("vnbroker/broker/tcbs/money.py").read_text(encoding="utf-8"))[:2000]
        assert "RULE: Không có write method" not in doc
        assert "read-only" not in doc

    def test_docstring_liet_ke_4_endpoint_moi(self):
        doc = Path("vnbroker/broker/tcbs/money.py").read_text(encoding="utf-8")[:2000]
        for path in ("/pricing-policy", "/khronos/v1/cash/deposit/update",
                     "/khronos/v1/cash/withdraw/update", "/physis/v1/stock/transfer"):
            assert path in doc