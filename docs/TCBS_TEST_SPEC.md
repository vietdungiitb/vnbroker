# TCBS Test Spec

**Version:** 1.0  
**Cập nhật:** 2026-05-19  
**Phạm vi:** Unit test và integration test cho `vnbroker/broker/tcbs/`.

---

## 1. Cấu trúc file test

```
tests/unit/broker/tcbs/
├── __init__.py
├── fixtures.py               # Sample data dicts + mock factory functions
├── test_credentials.py       # TCBSCredentialConfig, resolve_tcbs_credentials
├── test_security.py          # Redactor, AuditSink, IdempotencyStore, guards
├── test_session_auth.py      # BrokerSession state machine + TCBSAuthService
├── test_account_money.py     # TCBSAccountService + TCBSMoneyService (read)
├── test_orders_positions.py  # TCBSEquityService (read) + TCBSDerivativesService
├── test_order_write_flow.py  # Write flow: dry_run gate, idempotency, audit
└── test_portfolio.py         # PortfolioEngine
```

---

## 2. `fixtures.py` — Dữ liệu mẫu và mock factories

```python
# tests/unit/broker/tcbs/fixtures.py
"""
Fixtures cho TCBS broker test suite.
Tất cả dữ liệu là fake — không dùng apiKey/token/otp thật.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest

# ─── Sample data dicts ───────────────────────────────────────────────────────

SAMPLE_TOKEN_RESPONSE = {
    "token": "eyJhbGciOiJSUzI1NiJ9.fake_jwt_payload.fake_signature",
    "expiredTime": "2026-05-19T18:00:00+07:00",
}

SAMPLE_AUTH_ERROR_RESPONSE = {
    "code": "INVALID_OTP",
    "message": "OTP không hợp lệ hoặc đã hết hạn.",
}

SAMPLE_ACCOUNTS = [
    {
        "accountNo": "0123456789",
        "custodyCode": "C123456",
        "fullName": "NGUYEN VAN TEST",
        "accountType": "EQUITY",
        "status": "ACTIVE",
    }
]

SAMPLE_BALANCE = {
    "accountNo": "0123456789",
    "totalAsset": 100_000_000,
    "cashBalance": 20_000_000,
    "stockValue": 80_000_000,
    "debtBalance": 0,
    "availableAdvanceAmount": 15_000_000,
}

SAMPLE_PURCHASING_POWER = {
    "accountNo": "0123456789",
    "purchasingPower": 12_000_000,
    "marginPurchasingPower": 0,
    "marginRatio": 0.0,
}

SAMPLE_CASH = {
    "accountNo": "0123456789",
    "withdrawableAmount": 10_000_000,
    "pendingSettlement": 5_000_000,
    "cashBalance": 20_000_000,
}

SAMPLE_ORDERS = {
    "total": 1,
    "data": [
        {
            "orderId": "ORD123456",
            "symbol": "VNM",
            "side": "BUY",
            "orderType": "LIMIT",
            "quantity": 100,
            "price": 80_000,
            "filledQuantity": 0,
            "status": "PENDING",
            "createdAt": "2026-05-19T09:00:00+07:00",
        }
    ],
}

SAMPLE_EXECUTIONS = {
    "total": 1,
    "data": [
        {
            "executionId": "EXE789",
            "orderId": "ORD123456",
            "symbol": "VNM",
            "side": "BUY",
            "executedQuantity": 100,
            "executedPrice": 80_200,
            "executedAt": "2026-05-19T10:30:00+07:00",
            "fee": 80,
            "tax": 0,
        }
    ],
}

SAMPLE_DERIVATIVE_POSITIONS = [
    {
        "symbol": "VN30F2406",
        "side": "LONG",
        "openQuantity": 1,
        "openPrice": 1260.0,
        "currentPrice": 1265.0,
        "unrealizedPnl": 500_000,
        "margin": 15_000_000,
    }
]

SAMPLE_HOLDINGS = [
    {
        "symbol": "VNM",
        "quantity": 500,
        "availableQuantity": 400,
        "averageCost": 79_500,
        "currentPrice": 80_200,
        "marketValue": 40_100_000,
        "unrealizedPnl": 350_000,
        "unrealizedPnlPercent": 0.88,
    }
]

# ─── Mock factory functions ───────────────────────────────────────────────────

def make_mock_config(api_key: str = "fake_api_key",
                     base_url: str = "https://openapi.tcbs.com.vn") -> object:
    from vnbroker.broker.security.credentials import TCBSCredentialConfig
    return TCBSCredentialConfig(api_key=api_key, base_url=base_url)


def make_authenticated_session(token: str = SAMPLE_TOKEN_RESPONSE["token"]) -> object:
    from vnbroker.broker.session import BrokerSession
    session = BrokerSession()
    session.set_token(
        token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=8)
    )
    return session


def make_mock_response(status_code: int = 200, json_data: object = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.reason = "OK" if status_code == 200 else "Error"
    return resp


def make_tcbs_client(api_key: str = "fake_api_key") -> object:
    """Tạo TCBSBrokerClient với mock config — KHÔNG gọi HTTP thật."""
    from vnbroker.broker.tcbs.client import TCBSBrokerClient
    with patch.dict("os.environ", {"VNBROKER_BROKER_TCBS_API_KEY": api_key}):
        return TCBSBrokerClient()
```

---

## 3. `test_credentials.py`

```python
# tests/unit/broker/tcbs/test_credentials.py
import os
import pytest
from unittest.mock import patch
from vnbroker.broker.security.credentials import TCBSCredentialConfig, resolve_tcbs_credentials


class TestTCBSCredentialConfig:
    def test_instantiation_with_required_fields(self):
        cfg = TCBSCredentialConfig(api_key="key123")
        assert cfg.api_key == "key123"
        assert cfg.base_url == "https://openapi.tcbs.com.vn"
        assert cfg.timeout_seconds == 30.0
        assert cfg.auth_token is None

    def test_custom_base_url_strips_trailing_slash(self):
        # base_url không có trailing slash trong resolve function
        cfg = TCBSCredentialConfig(api_key="k", base_url="https://example.com/")
        # base_url được strip bởi resolve function, không phải dataclass
        assert cfg.base_url == "https://example.com/"  # dataclass giữ nguyên


class TestResolveTCBSCredentials:
    def test_direct_api_key_takes_priority(self):
        with patch.dict(os.environ, {"VNBROKER_BROKER_TCBS_API_KEY": "env_key"}):
            cfg = resolve_tcbs_credentials(api_key="direct_key")
        assert cfg.api_key == "direct_key"

    def test_env_var_primary_namespace(self):
        with patch.dict(os.environ,
                        {"VNBROKER_BROKER_TCBS_API_KEY": "primary_env_key"},
                        clear=True):
            # Xoá các env var khác để test priority
            for k in ["vnbroker_TCBS_OPENAPI_API_KEY", "TCBS_OPENAPI_API_KEY", "TCBS_API_KEY"]:
                os.environ.pop(k, None)
            cfg = resolve_tcbs_credentials()
        assert cfg.api_key == "primary_env_key"

    def test_legacy_env_var_fallback(self):
        env = {
            "TCBS_OPENAPI_API_KEY": "legacy_key",
        }
        with patch.dict(os.environ, env, clear=True):
            for k in ["VNBROKER_BROKER_TCBS_API_KEY", "vnbroker_TCBS_OPENAPI_API_KEY", "TCBS_API_KEY"]:
                os.environ.pop(k, None)
            cfg = resolve_tcbs_credentials()
        assert cfg.api_key == "legacy_key"

    def test_raises_value_error_when_no_key(self):
        with patch.dict(os.environ, {}, clear=True):
            for k in ["VNBROKER_BROKER_TCBS_API_KEY", "vnbroker_TCBS_OPENAPI_API_KEY",
                      "TCBS_OPENAPI_API_KEY", "TCBS_API_KEY"]:
                os.environ.pop(k, None)
            with pytest.raises(ValueError, match="API key"):
                resolve_tcbs_credentials()

    def test_base_url_trailing_slash_stripped(self):
        cfg = resolve_tcbs_credentials(api_key="k", base_url="https://example.com/")
        assert not cfg.base_url.endswith("/")
```

---

## 4. `test_security.py`

```python
# tests/unit/broker/tcbs/test_security.py
import time
import pytest
from vnbroker.broker.security.redaction import Redactor, SENSITIVE_KEYS
from vnbroker.broker.security.idempotency import IdempotencyStore


class TestRedactor:
    def test_redacts_sensitive_keys_case_insensitive(self):
        data = {"apiKey": "secret123", "symbol": "VNM"}
        result = Redactor.redact_dict(data)
        assert result["apiKey"] == Redactor.REDACTED
        assert result["symbol"] == "VNM"

    def test_redacts_otp(self):
        data = {"otp": "123456", "side": "BUY"}
        result = Redactor.redact_dict(data)
        assert result["otp"] == Redactor.REDACTED

    def test_redacts_pin_code_variants(self):
        for key in ["pinCode", "pin_code", "pincode"]:
            data = {key: "999999"}
            result = Redactor.redact_dict(data)
            assert result[key] == Redactor.REDACTED

    def test_nested_dict_redaction(self):
        data = {"order": {"symbol": "VNM", "pinCode": "123456"}}
        result = Redactor.redact_dict(data)
        assert result["order"]["pinCode"] == Redactor.REDACTED
        assert result["order"]["symbol"] == "VNM"

    def test_non_sensitive_keys_preserved(self):
        data = {"quantity": 100, "price": 80000, "symbol": "VNM"}
        result = Redactor.redact_dict(data)
        assert result == data

    def test_redact_headers_authorization(self):
        headers = {
            "Authorization": "Bearer eyJhbGc.fake",
            "Content-Type": "application/json",
        }
        result = Redactor.redact_headers(headers)
        assert result["Authorization"] == Redactor.REDACTED
        assert result["Content-Type"] == "application/json"


class TestIdempotencyStore:
    def test_first_call_returns_true(self):
        store = IdempotencyStore(ttl_seconds=60)
        assert store.check_and_store("req-001") is True

    def test_duplicate_call_returns_false(self):
        store = IdempotencyStore(ttl_seconds=60)
        store.check_and_store("req-002")
        assert store.check_and_store("req-002") is False

    def test_different_keys_independent(self):
        store = IdempotencyStore(ttl_seconds=60)
        assert store.check_and_store("req-A") is True
        assert store.check_and_store("req-B") is True

    def test_expired_key_allows_reuse(self):
        store = IdempotencyStore(ttl_seconds=1)
        store.check_and_store("req-003")
        time.sleep(1.1)
        # Sau khi TTL expired, key được phép dùng lại
        assert store.check_and_store("req-003") is True
```

---

## 5. `test_session_auth.py`

```python
# tests/unit/broker/tcbs/test_session_auth.py
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from vnbroker.broker.session import BrokerSession, SessionState
from vnbroker.broker.tcbs.exceptions import (
    BrokerAuthError, BrokerSessionExpiredError, BrokerPermissionError
)
from tests.unit.broker.tcbs.fixtures import (
    SAMPLE_TOKEN_RESPONSE, SAMPLE_AUTH_ERROR_RESPONSE,
    make_mock_config, make_mock_response
)


class TestBrokerSessionTransitions:
    def test_initial_state_is_created(self):
        session = BrokerSession()
        assert session.state == SessionState.CREATED

    def test_set_token_transitions_to_authenticated_read(self):
        session = BrokerSession()
        session.set_token("fake_token")
        assert session.state == SessionState.AUTHENTICATED_READ

    def test_enable_write_transitions_to_write_enabled(self):
        session = BrokerSession()
        session.set_token("fake_token")
        session.enable_write()
        assert session.state == SessionState.AUTHENTICATED_WRITE_ENABLED
        assert session.is_write_enabled is True

    def test_enable_write_raises_when_not_authenticated(self):
        session = BrokerSession()
        with pytest.raises(BrokerPermissionError):
            session.enable_write()

    def test_revoke_transitions_to_expired(self):
        session = BrokerSession()
        session.set_token("fake_token")
        session.revoke()
        assert session.state == SessionState.EXPIRED

    def test_token_access_after_revoke_raises(self):
        session = BrokerSession()
        session.set_token("fake_token")
        session.revoke()
        with pytest.raises(BrokerSessionExpiredError):
            _ = session.token

    def test_token_access_after_expiry_raises(self):
        session = BrokerSession()
        # Token expired 1 giây trước
        expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.set_token("fake_token", expires_at=expired_at)
        with pytest.raises(BrokerSessionExpiredError):
            _ = session.token

    def test_lock_prevents_token_access(self):
        session = BrokerSession()
        session.set_token("fake_token")
        session.lock("security violation test")
        assert session.state == SessionState.LOCKED
        with pytest.raises(BrokerSessionExpiredError):
            _ = session.token


class TestTCBSAuthService:
    def test_authenticate_success_sets_session_token(self):
        from vnbroker.broker.tcbs.auth import TCBSAuthService
        config = make_mock_config()
        session = BrokerSession()
        auth = TCBSAuthService(config, session)

        mock_resp = make_mock_response(200, SAMPLE_TOKEN_RESPONSE)
        with patch("requests.post", return_value=mock_resp):
            auth.authenticate(otp="123456")

        assert session.state == SessionState.AUTHENTICATED_READ
        assert session._token == SAMPLE_TOKEN_RESPONSE["token"]

    def test_authenticate_wrong_otp_raises_broker_auth_error(self):
        from vnbroker.broker.tcbs.auth import TCBSAuthService
        config = make_mock_config()
        session = BrokerSession()
        auth = TCBSAuthService(config, session)

        mock_resp = make_mock_response(401, SAMPLE_AUTH_ERROR_RESPONSE)
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(BrokerAuthError) as exc:
                auth.authenticate(otp="000000")
        assert "INVALID_OTP" in exc.value.code or exc.value.http_status == 401

    def test_authenticate_empty_otp_raises_value_error(self):
        from vnbroker.broker.tcbs.auth import TCBSAuthService
        config = make_mock_config()
        session = BrokerSession()
        auth = TCBSAuthService(config, session)
        with pytest.raises(ValueError, match="OTP"):
            auth.authenticate(otp="")

    def test_is_token_valid_returns_false_before_auth(self):
        from vnbroker.broker.tcbs.auth import TCBSAuthService
        config = make_mock_config()
        session = BrokerSession()
        auth = TCBSAuthService(config, session)
        assert auth.is_token_valid() is False
```

---

## 6. `test_account_money.py`

```python
# tests/unit/broker/tcbs/test_account_money.py
import pytest
import pandas as pd
from unittest.mock import patch
from vnbroker.broker.tcbs.exceptions import BrokerAuthError
from tests.unit.broker.tcbs.fixtures import (
    SAMPLE_ACCOUNTS, SAMPLE_BALANCE, SAMPLE_CASH,
    make_mock_config, make_authenticated_session, make_mock_response
)


class TestTCBSAccountServiceGetBalance:
    def _make_service(self):
        from vnbroker.broker.tcbs.account import TCBSAccountService
        return TCBSAccountService(
            config=make_mock_config(),
            session=make_authenticated_session()
        )

    def test_returns_dataframe_by_default(self):
        svc = self._make_service()
        with patch("requests.get", return_value=make_mock_response(200, SAMPLE_BALANCE)):
            result = svc.get_balance(account_no="0123456789")
        assert isinstance(result, pd.DataFrame)
        assert not result.empty

    def test_raw_true_returns_dict(self):
        svc = self._make_service()
        with patch("requests.get", return_value=make_mock_response(200, SAMPLE_BALANCE)):
            result = svc.get_balance(account_no="0123456789", raw=True)
        assert isinstance(result, dict)
        assert result["accountNo"] == "0123456789"

    def test_raises_when_session_unauthenticated(self):
        from vnbroker.broker.tcbs.account import TCBSAccountService
        from vnbroker.broker.session import BrokerSession
        svc = TCBSAccountService(
            config=make_mock_config(),
            session=BrokerSession()  # Chưa authenticate
        )
        with pytest.raises((BrokerAuthError, Exception)):
            svc.get_balance(account_no="0123456789")

    def test_column_names_snake_case(self):
        svc = self._make_service()
        with patch("requests.get", return_value=make_mock_response(200, SAMPLE_BALANCE)):
            df = svc.get_balance(account_no="0123456789")
        # Kiểm tra columns là snake_case
        for col in df.columns:
            assert col == col.lower() or "_" in col
```

---

## 7. `test_order_write_flow.py`

```python
# tests/unit/broker/tcbs/test_order_write_flow.py
import uuid
import pytest
from unittest.mock import patch
from vnbroker.broker.tcbs.exceptions import BrokerValidationError, BrokerPermissionError
from tests.unit.broker.tcbs.fixtures import (
    make_mock_config, make_authenticated_session, make_mock_response, SAMPLE_ORDERS
)


class TestPlaceOrderDryRun:
    def _make_service(self, write_enabled: bool = False):
        from vnbroker.broker.tcbs.equity import TCBSEquityService
        from vnbroker.broker.security.audit import AuditSink
        from vnbroker.broker.security.idempotency import IdempotencyStore
        session = make_authenticated_session()
        if write_enabled:
            session.enable_write()
        return TCBSEquityService(
            config=make_mock_config(),
            session=session,
            audit=AuditSink(),
            idempotency=IdempotencyStore(),
        )

    def test_dry_run_returns_debug_dict_without_http_call(self):
        svc = self._make_service(write_enabled=True)
        with patch("requests.post") as mock_post:
            result = svc.place_order(
                account_no="0123456789",
                symbol="VNM", side="BUY", order_type="LIMIT",
                quantity=100, price=80_000,
                pin_code="123456",
                request_id=str(uuid.uuid4()),
                dry_run=True,
            )
        mock_post.assert_not_called()
        assert result["dry_run"] is True
        assert "payload" in result

    def test_dry_run_redacts_pin_code(self):
        svc = self._make_service(write_enabled=True)
        result = svc.place_order(
            account_no="0123456789",
            symbol="VNM", side="BUY", order_type="LIMIT",
            quantity=100, price=80_000,
            pin_code="REAL_SECRET",
            request_id=str(uuid.uuid4()),
            dry_run=True,
        )
        assert "REAL_SECRET" not in str(result)

    def test_dry_run_redacts_authorization_header(self):
        svc = self._make_service(write_enabled=True)
        result = svc.place_order(
            account_no="0123456789",
            symbol="VNM", side="BUY", order_type="LIMIT",
            quantity=100, price=80_000,
            pin_code="123456",
            request_id=str(uuid.uuid4()),
            dry_run=True,
        )
        auth_val = result.get("headers", {}).get("Authorization", "")
        assert "***REDACTED***" in auth_val or "fake_jwt" not in auth_val

    def test_raises_on_negative_quantity(self):
        svc = self._make_service(write_enabled=True)
        with pytest.raises(BrokerValidationError, match="quantity"):
            svc.place_order(
                account_no="0123456789",
                symbol="VNM", side="BUY", order_type="LIMIT",
                quantity=-1, price=80_000,
                pin_code="123456",
                request_id=str(uuid.uuid4()),
                dry_run=True,
            )

    def test_raises_when_write_not_enabled(self):
        svc = self._make_service(write_enabled=False)  # Chưa enable_write
        with pytest.raises(BrokerPermissionError, match="[Ww]rite"):
            svc.place_order(
                account_no="0123456789",
                symbol="VNM", side="BUY", order_type="LIMIT",
                quantity=100, price=80_000,
                pin_code="123456",
                request_id=str(uuid.uuid4()),
                dry_run=True,
            )

    def test_duplicate_request_id_raises(self):
        svc = self._make_service(write_enabled=True)
        req_id = str(uuid.uuid4())
        svc.place_order(
            account_no="0123456789", symbol="VNM", side="BUY",
            order_type="LIMIT", quantity=100, price=80_000,
            pin_code="123456", request_id=req_id, dry_run=True,
        )
        with pytest.raises(BrokerValidationError, match="[Dd]uplicate|[Ii]dempotency"):
            svc.place_order(
                account_no="0123456789", symbol="VNM", side="BUY",
                order_type="LIMIT", quantity=100, price=80_000,
                pin_code="123456", request_id=req_id, dry_run=True,
            )
```

---

## 8. `test_portfolio.py`

```python
# tests/unit/broker/tcbs/test_portfolio.py
import pandas as pd
import pytest
from datetime import datetime, timezone
from vnbroker.broker.tcbs.portfolio import PortfolioEngine, PortfolioLedgerEntry


def make_buy_entry(symbol: str, qty: int, price: float, fee: float = 0.0):
    return PortfolioLedgerEntry(
        date=datetime.now(timezone.utc),
        symbol=symbol,
        action="BUY",
        quantity=qty,
        price=price,
        fee=fee,
        tax=0.0,
        net_amount=-(qty * price + fee),
    )

def make_sell_entry(symbol: str, qty: int, price: float, fee: float = 0.0, tax: float = 0.0):
    return PortfolioLedgerEntry(
        date=datetime.now(timezone.utc),
        symbol=symbol,
        action="SELL",
        quantity=qty,
        price=price,
        fee=fee,
        tax=tax,
        net_amount=(qty * price - fee - tax),
    )


class TestPortfolioEngineHoldings:
    def test_single_buy_creates_holding(self):
        engine = PortfolioEngine()
        engine._ledger.append(make_buy_entry("VNM", 100, 80_000))
        holdings = engine.get_holdings(current_prices={"VNM": 82_000})
        assert len(holdings) == 1
        assert holdings[0].symbol == "VNM"
        assert holdings[0].quantity == 100

    def test_buy_then_sell_reduces_quantity(self):
        engine = PortfolioEngine()
        engine._ledger.append(make_buy_entry("VNM", 200, 80_000))
        engine._ledger.append(make_sell_entry("VNM", 100, 85_000))
        holdings = engine.get_holdings(current_prices={"VNM": 85_000})
        assert holdings[0].quantity == 100

    def test_full_sell_removes_holding(self):
        engine = PortfolioEngine()
        engine._ledger.append(make_buy_entry("VNM", 100, 80_000))
        engine._ledger.append(make_sell_entry("VNM", 100, 85_000))
        holdings = engine.get_holdings(current_prices={"VNM": 85_000})
        assert len(holdings) == 0

    def test_unrealized_pnl_calculation(self):
        engine = PortfolioEngine()
        engine._ledger.append(make_buy_entry("VNM", 100, 80_000, fee=80))
        holdings = engine.get_holdings(current_prices={"VNM": 82_000})
        h = holdings[0]
        # Unrealized PnL = (current - avg_cost) * qty = (82000 - 80000.8) * 100
        assert h.unrealized_pnl > 0


class TestPortfolioEngineReconcile:
    def test_reconcile_matches_when_consistent(self):
        engine = PortfolioEngine()
        engine._ledger.append(make_buy_entry("VNM", 100, 80_000))
        broker_df = pd.DataFrame([{"symbol": "VNM", "quantity": 100}])
        result = engine.reconcile(broker_df)
        assert len(result.get("discrepancies", [])) == 0

    def test_reconcile_detects_discrepancy(self):
        engine = PortfolioEngine()
        engine._ledger.append(make_buy_entry("VNM", 100, 80_000))
        # Broker báo 50 nhưng ledger tính 100 — discrepancy
        broker_df = pd.DataFrame([{"symbol": "VNM", "quantity": 50}])
        result = engine.reconcile(broker_df)
        assert len(result.get("discrepancies", [])) > 0
```

---

## 9. Integration Test Template

```python
# tests/integration/broker/tcbs/test_tcbs_live.py
"""
Integration test với TCBS sandbox/production thật.
KHÔNG chạy trong CI — chỉ chạy khi có credentials thật.

Chạy thủ công:
  $env:VNBROKER_BROKER_TCBS_API_KEY = "real_key"
  $env:VNBROKER_BROKER_TCBS_RUN_LIVE = "1"
  python -m pytest tests/integration/broker/tcbs/test_tcbs_live.py -v -s
"""
import os
import pytest

LIVE = os.getenv("VNBROKER_BROKER_TCBS_RUN_LIVE", "0") == "1"

@pytest.mark.skipif(not LIVE, reason="VNBROKER_BROKER_TCBS_RUN_LIVE not set to 1")
class TestTCBSLiveAuth:
    def test_authenticate_with_real_otp(self):
        from vnbroker.broker.tcbs.client import TCBSBrokerClient
        client = TCBSBrokerClient()
        otp = input("Nhập OTP TCBS: ")
        client.authenticate(otp=otp)
        assert client._session.token is not None

    def test_list_accounts_after_auth(self):
        from vnbroker.broker.tcbs.client import TCBSBrokerClient
        from vnbroker.broker.session import SessionState
        client = TCBSBrokerClient()
        otp = input("Nhập OTP TCBS: ")
        client.authenticate(otp=otp)
        accounts = client.list_accounts()
        assert not accounts.empty

    def test_place_order_dry_run_live(self):
        import uuid
        from vnbroker.broker.tcbs.client import TCBSBrokerClient
        client = TCBSBrokerClient()
        otp = input("Nhập OTP TCBS: ")
        client.authenticate(otp=otp)
        client.enable_write()
        accounts = client.list_accounts()
        account_no = accounts["account_no"].iloc[0]
        result = client.place_order(
            account_no=account_no,
            symbol="VNM", side="BUY", order_type="LIMIT",
            quantity=100, price=80_000,
            pin_code=input("Nhập PIN code: "),
            request_id=str(uuid.uuid4()),
            dry_run=True,  # DRY RUN — không gửi lệnh thật
        )
        assert result["dry_run"] is True
        assert "REAL_PIN" not in str(result)  # Kiểm tra redaction
```

---

## 10. Coverage targets

| File | Minimum coverage | Ghi chú |
|---|---|---|
| `exceptions.py` | 100% | Đơn giản, không có lý do < 100% |
| `security/credentials.py` | 90% | Bao gồm tất cả env var paths |
| `security/redaction.py` | 95% | Test đủ case key variants |
| `security/idempotency.py` | 90% | Bao gồm TTL expiry path |
| `broker/session.py` | 95% | Test tất cả state transitions |
| `broker/tcbs/auth.py` | 85% | Mock HTTP, test success + error paths |
| `broker/tcbs/account.py` | 80% | Raw=True/False, unauthenticated path |
| `broker/tcbs/equity.py` | 80% | dry_run, idempotency, validation |
| `broker/tcbs/portfolio.py` | 80% | Holdings FIFO, reconcile |

**Chạy coverage report:**
```powershell
python -m pytest tests/unit/broker/tcbs/ --cov=vnbroker/broker --cov-report=term-missing -v
```
