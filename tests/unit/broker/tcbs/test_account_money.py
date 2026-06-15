"""
tests.unit.broker.tcbs.test_account_money
==========================================
Unit tests cho TCBSAccountService và TCBSMoneyService.

Test categories:
  - TestAccountListAccounts  (6 tests)
  - TestAccountGetProfile    (5 tests)
  - TestAccountGetBalance    (5 tests)
  - TestAccountGetPurchasingPower (5 tests)
  - TestMoneyGetCash         (6 tests)
  - TestMoneyGetMargin       (5 tests)
  - TestHTTPErrorHandling    (7 tests — shared paths)
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
    BrokerPermissionError,
    BrokerSessionExpiredError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.session import BrokerSession, SessionState
from vnbroker.broker.tcbs.account import TCBSAccountService
from vnbroker.broker.tcbs.money import TCBSMoneyService

# ── Fixtures ─────────────────────────────────────────────────────────────────

ACCOUNT_NO = "0123456789"


def _make_session() -> BrokerSession:
    """Tạo session đã authenticated."""
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


def _make_mock_resp(status_code: int, json_data) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = ""
    return resp


# ── TCBSAccountService — list_accounts ───────────────────────────────────────

class TestAccountListAccounts:
    def _svc(self):
        return TCBSAccountService(_make_config(), _make_session())

    def test_list_accounts_returns_dataframe_by_default(self):
        payload = [
            {
                "accountNo": ACCOUNT_NO,
                "custodyCode": "C123456",
                "fullName": "NGUYEN VAN A",
                "accountType": "EQUITY",
                "status": "ACTIVE",
            }
        ]
        with patch("requests.get", return_value=_make_mock_resp(200, payload)):
            df = self._svc().list_accounts()
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["account_no", "custody_code", "full_name", "account_type", "status"]

    def test_list_accounts_raw_true_returns_list(self):
        payload = [{"accountNo": ACCOUNT_NO}]
        with patch("requests.get", return_value=_make_mock_resp(200, payload)):
            result = self._svc().list_accounts(raw=True)
        assert isinstance(result, list)
        assert result[0]["accountNo"] == ACCOUNT_NO

    def test_list_accounts_custody_code_masked_in_dataframe(self):
        payload = [
            {"accountNo": ACCOUNT_NO, "custodyCode": "C123456", "fullName": "X", "accountType": "EQUITY", "status": "ACTIVE"}
        ]
        with patch("requests.get", return_value=_make_mock_resp(200, payload)):
            df = self._svc().list_accounts()
        # custody_code phải bị mask
        assert "C123456" not in df["custody_code"].iloc[0]

    def test_list_accounts_account_type_is_category(self):
        payload = [{"accountNo": ACCOUNT_NO, "custodyCode": "X", "fullName": "X", "accountType": "EQUITY", "status": "ACTIVE"}]
        with patch("requests.get", return_value=_make_mock_resp(200, payload)):
            df = self._svc().list_accounts()
        assert df["account_type"].dtype.name == "category"

    def test_list_accounts_single_dict_response_also_works(self):
        """API trả về dict thay vì list — phải xử lý gracefully."""
        payload = {"accountNo": ACCOUNT_NO, "custodyCode": "C", "fullName": "X", "accountType": "EQUITY", "status": "ACTIVE"}
        with patch("requests.get", return_value=_make_mock_resp(200, payload)):
            df = self._svc().list_accounts()
        assert len(df) == 1

    def test_list_accounts_empty_list_returns_empty_df(self):
        with patch("requests.get", return_value=_make_mock_resp(200, [])):
            df = self._svc().list_accounts()
        assert isinstance(df, pd.DataFrame)
        assert df.empty


# ── TCBSAccountService — get_profile ─────────────────────────────────────────

class TestAccountGetProfile:
    def _svc(self):
        return TCBSAccountService(_make_config(), _make_session())

    def test_get_profile_returns_dataframe(self):
        payload = {
            "accountNo": ACCOUNT_NO,
            "custodyCode": "C123456",
            "fullName": "NGUYEN VAN A",
            "idNo": "123456789",
            "phone": "0901234567",
            "email": "test@example.com",
        }
        with patch("requests.get", return_value=_make_mock_resp(200, payload)):
            df = self._svc().get_profile(ACCOUNT_NO)
        assert isinstance(df, pd.DataFrame)

    def test_get_profile_pii_redacted_in_dataframe(self):
        payload = {
            "accountNo": ACCOUNT_NO,
            "custodyCode": "C123456",
            "fullName": "TEST",
            "idNo": "SECRET-ID",
            "phone": "PHONE-SECRET",
            "email": "secret@mail.com",
        }
        with patch("requests.get", return_value=_make_mock_resp(200, payload)):
            df = self._svc().get_profile(ACCOUNT_NO)
        # PII fields phải không còn value gốc
        row_dict = df.iloc[0].to_dict()
        all_values = " ".join(str(v) for v in row_dict.values())
        assert "SECRET-ID" not in all_values
        assert "PHONE-SECRET" not in all_values
        assert "secret@mail.com" not in all_values

    def test_get_profile_raw_true_returns_dict(self):
        payload = {"accountNo": ACCOUNT_NO, "idNo": "SECRET"}
        with patch("requests.get", return_value=_make_mock_resp(200, payload)):
            result = self._svc().get_profile(ACCOUNT_NO, raw=True)
        assert isinstance(result, dict)
        assert result["idNo"] == "SECRET"  # raw không redact

    def test_get_profile_empty_account_no_raises_validation_error(self):
        with pytest.raises(BrokerValidationError):
            self._svc().get_profile("")

    def test_get_profile_blank_account_no_raises_validation_error(self):
        with pytest.raises(BrokerValidationError):
            self._svc().get_profile("   ")


# ── TCBSAccountService — get_balance ─────────────────────────────────────────

class TestAccountGetBalance:
    def _svc(self):
        return TCBSAccountService(_make_config(), _make_session())

    _BALANCE_PAYLOAD = {
        "accountNo": ACCOUNT_NO,
        "totalAsset": 100_000_000,
        "cashBalance": 20_000_000,
        "stockValue": 80_000_000,
        "debtBalance": 0,
        "availableAdvanceAmount": 15_000_000,
    }

    def test_get_balance_returns_dataframe(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._BALANCE_PAYLOAD)):
            df = self._svc().get_balance(ACCOUNT_NO)
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == [
            "account_no", "total_asset", "cash_balance",
            "stock_value", "debt_balance", "available_advance_amount",
        ]

    def test_get_balance_numeric_dtypes(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._BALANCE_PAYLOAD)):
            df = self._svc().get_balance(ACCOUNT_NO)
        assert df["total_asset"].dtype == "float64"
        assert df["cash_balance"].dtype == "float64"

    def test_get_balance_values_correct(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._BALANCE_PAYLOAD)):
            df = self._svc().get_balance(ACCOUNT_NO)
        assert df["total_asset"].iloc[0] == 100_000_000.0

    def test_get_balance_raw_true_returns_dict(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._BALANCE_PAYLOAD)):
            result = self._svc().get_balance(ACCOUNT_NO, raw=True)
        assert isinstance(result, dict)

    def test_get_balance_empty_account_no_raises_validation_error(self):
        with pytest.raises(BrokerValidationError):
            self._svc().get_balance("")


# ── TCBSAccountService — get_purchasing_power ────────────────────────────────

class TestAccountGetPurchasingPower:
    def _svc(self):
        return TCBSAccountService(_make_config(), _make_session())

    _PP_PAYLOAD = {
        "accountNo": ACCOUNT_NO,
        "purchasingPower": 12_000_000,
        "marginPurchasingPower": 0,
        "marginRatio": 0.0,
    }

    def test_get_purchasing_power_returns_dataframe(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._PP_PAYLOAD)):
            df = self._svc().get_purchasing_power(ACCOUNT_NO)
        assert isinstance(df, pd.DataFrame)
        assert "purchasing_power" in df.columns
        assert "margin_ratio" in df.columns

    def test_get_purchasing_power_numeric_dtypes(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._PP_PAYLOAD)):
            df = self._svc().get_purchasing_power(ACCOUNT_NO)
        assert df["purchasing_power"].dtype == "float64"
        assert df["margin_ratio"].dtype == "float64"

    def test_get_purchasing_power_value_correct(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._PP_PAYLOAD)):
            df = self._svc().get_purchasing_power(ACCOUNT_NO)
        assert df["purchasing_power"].iloc[0] == 12_000_000.0

    def test_get_purchasing_power_raw_true_returns_dict(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._PP_PAYLOAD)):
            result = self._svc().get_purchasing_power(ACCOUNT_NO, raw=True)
        assert isinstance(result, dict)

    def test_get_purchasing_power_empty_account_no_raises(self):
        with pytest.raises(BrokerValidationError):
            self._svc().get_purchasing_power("")


# ── TCBSMoneyService — get_cash ───────────────────────────────────────────────

class TestMoneyGetCash:
    def _svc(self):
        return TCBSMoneyService(_make_config(), _make_session())

    _CASH_PAYLOAD = {
        "accountNo": ACCOUNT_NO,
        "withdrawableAmount": 10_000_000,
        "pendingSettlement": 5_000_000,
        "cashBalance": 20_000_000,
    }

    def test_get_cash_returns_dataframe(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._CASH_PAYLOAD)):
            df = self._svc().get_cash(ACCOUNT_NO)
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == [
            "account_no", "withdrawable_amount", "pending_settlement", "cash_balance"
        ]

    def test_get_cash_numeric_dtypes(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._CASH_PAYLOAD)):
            df = self._svc().get_cash(ACCOUNT_NO)
        assert df["withdrawable_amount"].dtype == "float64"
        assert df["cash_balance"].dtype == "float64"

    def test_get_cash_values_correct(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._CASH_PAYLOAD)):
            df = self._svc().get_cash(ACCOUNT_NO)
        assert df["withdrawable_amount"].iloc[0] == 10_000_000.0

    def test_get_cash_raw_true_returns_dict(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._CASH_PAYLOAD)):
            result = self._svc().get_cash(ACCOUNT_NO, raw=True)
        assert isinstance(result, dict)

    def test_get_cash_empty_account_no_raises(self):
        with pytest.raises(BrokerValidationError):
            self._svc().get_cash("")

    def test_get_cash_blank_account_no_raises(self):
        with pytest.raises(BrokerValidationError):
            self._svc().get_cash("  ")


# ── TCBSMoneyService — get_margin ────────────────────────────────────────────

class TestMoneyGetMargin:
    def _svc(self):
        return TCBSMoneyService(_make_config(), _make_session())

    _MARGIN_PAYLOAD = {
        "accountNo": ACCOUNT_NO,
        "marginLimit": 50_000_000,
        "marginUsed": 10_000_000,
        "marginAvailable": 40_000_000,
        "maintenanceMarginRate": 0.3,
    }

    def test_get_margin_returns_dataframe(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._MARGIN_PAYLOAD)):
            df = self._svc().get_margin(ACCOUNT_NO)
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == [
            "account_no", "margin_limit", "margin_used",
            "margin_available", "maintenance_margin_rate",
        ]

    def test_get_margin_numeric_dtypes(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._MARGIN_PAYLOAD)):
            df = self._svc().get_margin(ACCOUNT_NO)
        assert df["margin_limit"].dtype == "float64"
        assert df["maintenance_margin_rate"].dtype == "float64"

    def test_get_margin_rate_value_correct(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._MARGIN_PAYLOAD)):
            df = self._svc().get_margin(ACCOUNT_NO)
        assert df["maintenance_margin_rate"].iloc[0] == pytest.approx(0.3)

    def test_get_margin_raw_true_returns_dict(self):
        with patch("requests.get", return_value=_make_mock_resp(200, self._MARGIN_PAYLOAD)):
            result = self._svc().get_margin(ACCOUNT_NO, raw=True)
        assert isinstance(result, dict)

    def test_get_margin_empty_account_no_raises(self):
        with pytest.raises(BrokerValidationError):
            self._svc().get_margin("")


# ── HTTP Error Handling — shared across both services ─────────────────────────

class TestHTTPErrorHandling:
    """
    Test 401 → BrokerAuthError + session.revoke(),
         403 → BrokerPermissionError,
         500 → BrokerNetworkError,
         Timeout → BrokerNetworkError,
         Expired session → BrokerSessionExpiredError,
         No write-gate side-effects on read services
    """

    def _account_svc(self, session=None):
        s = session or _make_session()
        return TCBSAccountService(_make_config(), s)

    def _money_svc(self, session=None):
        s = session or _make_session()
        return TCBSMoneyService(_make_config(), s)

    def test_401_raises_auth_error_and_revokes_session_account(self):
        session = _make_session()
        svc = self._account_svc(session)
        with patch("requests.get", return_value=_make_mock_resp(401, {})):
            with pytest.raises(BrokerAuthError) as exc_info:
                svc.get_balance(ACCOUNT_NO)
        assert exc_info.value.http_status == 401
        assert session.state == SessionState.EXPIRED

    def test_401_raises_auth_error_and_revokes_session_money(self):
        session = _make_session()
        svc = self._money_svc(session)
        with patch("requests.get", return_value=_make_mock_resp(401, {})):
            with pytest.raises(BrokerAuthError):
                svc.get_cash(ACCOUNT_NO)
        assert session.state == SessionState.EXPIRED

    def test_403_raises_permission_error(self):
        with patch("requests.get", return_value=_make_mock_resp(403, {})):
            with pytest.raises(BrokerPermissionError):
                self._account_svc().get_balance(ACCOUNT_NO)

    def test_500_raises_network_error(self):
        with patch("requests.get", return_value=_make_mock_resp(500, {})):
            with pytest.raises(BrokerNetworkError):
                self._account_svc().get_balance(ACCOUNT_NO)

    def test_timeout_raises_network_error(self):
        with patch(
            "requests.get",
            side_effect=requests.exceptions.Timeout("timeout"),
        ):
            with pytest.raises(BrokerNetworkError) as exc_info:
                self._account_svc().get_balance(ACCOUNT_NO)
        assert "NETWORK_TIMEOUT" in exc_info.value.code

    def test_expired_session_raises_session_expired_error(self):
        session = _make_session()
        # Đặt expires_at về quá khứ
        session._token_expires_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        svc = self._account_svc(session)
        with pytest.raises(BrokerSessionExpiredError):
            svc.get_balance(ACCOUNT_NO)

    def test_no_write_gate_on_read_services(self):
        """Read services KHÔNG có @write_gate — không raise BrokerPermissionError cho dry_run."""
        session = _make_session()
        # write NOT enabled — nhưng read methods vẫn phải hoạt động
        assert not session.is_write_enabled
        svc = self._account_svc(session)
        payload = {
            "accountNo": ACCOUNT_NO,
            "totalAsset": 0,
            "cashBalance": 0,
            "stockValue": 0,
            "debtBalance": 0,
            "availableAdvanceAmount": 0,
        }
        with patch("requests.get", return_value=_make_mock_resp(200, payload)):
            df = svc.get_balance(ACCOUNT_NO)
        assert isinstance(df, pd.DataFrame)
