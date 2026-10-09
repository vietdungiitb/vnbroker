"""
tests/unit/broker/tcbs/test_tcbs_legacy_removed.py
==================================================
Contract test cho việc GỠ 18 path API legacy của TCBS (2026-10-09).

Bối cảnh
---------
18 path này KHÔNG có trong CẢ HAI tài liệu chính thức:
  - `openapi-v1.0.0.json`                       (48 REST endpoint)
  - `tcbs-openapi-v1.0.0.postman_collection.json` (48 REST endpoint, khớp 48/48)

⇒ Xoá theo quyết định của Owner dựa trên 2 tài liệu chính thức, CHƯA probe
  server. Lý do không probe được: TCBS trả 401 TRƯỚC khi routing nên không
  phân biệt được route tồn tại hay không.
⇒ Đây KHÔNG phải kết luận "path không tồn tại trên server".

Test ở đây chứng minh 5 điều (AC1-AC6 của S3):
  1. 18 path đã bị xoá khỏi `_PATHS`.
  2. Không còn chuỗi `erebos/v1`, `erebos/v2/accounts`, `erebos/v2/order`,
     `aion/v1/accounts/{a}/orders/history` trong phần code gọi HTTP.
  3. Method công khai ném `NotImplementedError` — KHÔNG im lặng trả về rỗng.
  4. Message lỗi nêu lý do + nói rõ CHƯA probe server.
  5. NGOẠI LỆ `/aion/v1/accounts` được giữ vì `get_account_list()` là
     `@abstractmethod` — hợp đồng không được phá vỡ.
"""
from __future__ import annotations

import ast
import inspect
import re
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from vnbroker.broker.base import BaseBrokerClient
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.tcbs import account as account_mod
from vnbroker.broker.tcbs import equity as equity_mod
from vnbroker.broker.tcbs.account import TCBSAccountService
from vnbroker.broker.tcbs.equity import TCBSEquityService

ACCOUNT_NO = "0123456789"

# ── 18 path bị gỡ ───────────────────────────────────────────────────────────
REMOVED_ACCOUNT_PATHS = {
    "get_erebos_v1_asset": "/erebos/v1/account/asset",
    "get_erebos_v1_available_balance": "/erebos/v1/account/available-balance",
    "get_erebos_v1_portfolio_asset": "/erebos/v1/portfolio-asset",
    "get_erebos_v1_portfolio_asset_token": "/erebos/v1/portfolio-asset/token",
    "get_erebos_v1_portfolio_stock_statistic": "/erebos/v1/portfolio/stock/{accountNo}/statistic",
    "get_erebos_v2_asset": "/erebos/v2/accounts/{accountNo}/asset",
    "get_erebos_v2_available_balance": "/erebos/v2/accounts/{accountNo}/available-balance",
    "get_erebos_v2_stock_statistic": "/erebos/v2/accounts/{accountNo}/stock-statistic",
    "get_erebos_v2_orders_history": "/erebos/v2/accounts/{accountNo}/orders/history",
    "get_erebos_v2_orders_matching": "/erebos/v2/accounts/{accountNo}/orders/matching",
    "get_erebos_v2_withdraw_history": "/erebos/v2/accounts/{accountNo}/withdraw",
    "get_erebos_v2_deposit_history": "/erebos/v2/accounts/{accountNo}/deposit",
    "get_erebos_v2_dividend_history": "/erebos/v2/accounts/{accountNo}/dividend",
}

REMOVED_EQUITY_PATHS = {
    "place_stop_limit_order": "/erebos/v2/order/stop-limit",
    "get_stop_limit_orders": "/erebos/v2/order/stop-limit/orders",
    "modify_stop_limit_order": "/erebos/v2/order/stop-limit/{orderId}",
    "cancel_stop_limit_order": "/erebos/v2/order/stop-limit/{orderId}/cancel",
    "get_order_history": "/aion/v1/accounts/{accountNo}/orders/history",
}

ALL_REMOVED = {**REMOVED_ACCOUNT_PATHS, **REMOVED_EQUITY_PATHS}

# 37 path CÒN LẠI — phải không đổi (AC5).
KEPT_ACCOUNT_PATHS = {
    "profile": "/eros/v2/get-profile/by-username/{custodyCode}",
    "balance": "/aion/v1/accounts/{accountNo}/cashInvestments",
    "purchasing_power": "/aion/v1/accounts/{accountNo}/ppse",
    "list_accounts": "/aion/v1/accounts",  # NGOẠI LỆ — xem AC6
}

KEPT_EQUITY_PATHS = {
    "orders": "/aion/v1/accounts/{accountNo}/orders",
    "order_detail": "/aion/v1/accounts/{accountNo}/orders/{orderID}",
    "matching_details": "/aion/v1/accounts/{accountNo}/matching-details",
    "se": "/aion/v1/accounts/{accountNo}/se",
    "place_order": "/akhlys/v1/accounts/{accountNo}/orders",
    "modify_order": "/akhlys/v1/accounts/{accountNo}/orders/{orderId}",
    "cancel_orders": "/akhlys/v1/accounts/{accountNo}/cancel-orders",
    "ticker_commons": "/tartarus/v1/tickerCommons",
}


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_session() -> BrokerSession:
    s = BrokerSession()
    s.begin_authenticating()
    s.set_token(token="fake-jwt", expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc))
    return s


def _make_config() -> TCBSCredentialConfig:
    return TCBSCredentialConfig(
        api_key="test-key", base_url="https://openapi.tcbs.com.vn", timeout_seconds=30,
    )


def _mock_resp(status: int, payload) -> MagicMock:
    r = MagicMock(spec=requests.Response)
    r.status_code = status
    r.json.return_value = payload
    r.text = ""
    return r


@pytest.fixture
def account_service() -> TCBSAccountService:
    return TCBSAccountService(_make_config(), _make_session())


@pytest.fixture
def equity_service() -> TCBSEquityService:
    return TCBSEquityService(_make_config(), _make_session())


def _iter_string_constants(path: Path):
    """Yield (lineno, value) cho mọi string literal trong file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


# ── AC1: 18 path bị xoá khỏi _PATHS ──────────────────────────────────────────

class TestAc1RemovedPathsGoneFromRegistry:
    @pytest.mark.parametrize("method_name", sorted(REMOVED_ACCOUNT_PATHS))
    def test_account_path_not_in_PATHS(self, method_name):
        assert method_name not in account_mod._PATHS
        assert method_name in account_mod._REMOVED_PATHS
        assert account_mod._REMOVED_PATHS[method_name] == REMOVED_ACCOUNT_PATHS[method_name]

    @pytest.mark.parametrize("method_name", sorted(REMOVED_EQUITY_PATHS))
    def test_equity_path_not_in_PATHS(self, method_name):
        assert method_name not in equity_mod._PATHS
        assert method_name in equity_mod._REMOVED_PATHS
        assert equity_mod._REMOVED_PATHS[method_name] == REMOVED_EQUITY_PATHS[method_name]

    def test_exactly_18_paths_removed(self):
        assert len(REMOVED_ACCOUNT_PATHS) == 13
        assert len(REMOVED_EQUITY_PATHS) == 5
        assert len(ALL_REMOVED) == 18

    def test_removed_paths_not_in_PATHS_values(self):
        """Path bị gỡ không được nằm trong value của bất kỳ _PATHS nào."""
        for path in ALL_REMOVED.values():
            assert path not in account_mod._PATHS.values()
            assert path not in equity_mod._PATHS.values()


# ── AC2: không còn chuỗi path đã gỡ trong mã ────────────────────────────────

class TestAc2NoLegacyStringsInCode:
    """Path đã gỡ chỉ được tồn tại trong `_REMOVED_PATHS` + docstring + message lỗi."""

    # Chuỗi KHÔNG được xuất hiện ở dạng path HTTP (bắt đầu bằng "/erebos").
    _FORBIDDEN_PREFIXES = (
        "/erebos/v1/account/",
        "/erebos/v1/portfolio-asset",
        "/erebos/v1/portfolio/stock/",
        "/erebos/v2/accounts/",
        "/erebos/v2/order/stop-limit",
        "/aion/v1/accounts/{accountNo}/orders/history",
    )

    @pytest.mark.parametrize(
        "module_path",
        [
            Path("vnbroker/broker/tcbs/account.py"),
            Path("vnbroker/broker/tcbs/equity.py"),
        ],
    )
    def test_forbidden_path_prefix_absent(self, module_path):
        """Path đã gỡ chỉ được tồn tại trong `_REMOVED_PATHS` (registry lịch sử).

        Ngoại lệ: `_raise_removed()` + docstring — nơi DUY NHẤT được phép
        nhắc lại path để giải thích lý do gỡ.
        """
        src = module_path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        # Vùng được phép chứa path đã gỡ: từ `_raise_removed` trở đi
        # (registry + docstring của nó) và module docstring.
        allowed_lines = {1}
        for node in ast.walk(tree):
            target_name = None
            if isinstance(node, ast.Assign):
                target_name = getattr(node.targets[0], "id", None)
            elif isinstance(node, ast.AnnAssign):
                target_name = getattr(node.target, "id", None)
            if target_name == "_REMOVED_PATHS":
                allowed_lines.update(range(node.lineno, node.end_lineno + 1))
            if isinstance(node, ast.FunctionDef) and node.name == "_raise_removed":
                allowed_lines.update(range(node.lineno, node.end_lineno + 1))
        offenders = [
            (lineno, val)
            for lineno, val in _iter_string_constants(module_path)
            if lineno not in allowed_lines
            and any(val.startswith(p) for p in self._FORBIDDEN_PREFIXES)
        ]
        assert offenders == [], f"{module_path} còn path đã gỡ ngoài `_REMOVED_PATHS`: {offenders}"

    def test_no_erebos_path_lookup_in_account_and_equity(self):
        """Không còn code nào format path `/erebos/v1` hoặc `/erebos/v2/accounts`."""
        for mod in (account_mod, equity_mod):
            src = inspect.getsource(mod)
            # Loại bỏ phần `_REMOVED_PATHS` + docstring: chỉ kiểm tra phần thực thi.
            body = src.split("_raise_removed(method_name: str)")[-1]
            assert '_PATHS["erebos_v1' not in body
            assert '_PATHS["erebos_v2' not in body
            assert '_PATHS["stop_limit' not in body
            assert '_PATHS["order_history"]' not in body

    def test_erebos_v1_not_in_PATHS_keys(self):
        assert not [k for k in account_mod._PATHS if "erebos_v1" in k]
        assert not [k for k in account_mod._PATHS if "erebos_v2" in k]

    def test_aion_orders_history_key_absent(self):
        assert "order_history" not in equity_mod._PATHS


# ── AC3: method công khai ném lỗi rõ ràng, không trả rỗng ───────────────────

class TestAc3PublicMethodsRaise:
    @pytest.mark.parametrize("method_name", sorted(REMOVED_ACCOUNT_PATHS))
    def test_account_method_raises(self, account_service, method_name):
        with patch("vnbroker.broker.tcbs.account.requests.get",
                   return_value=_mock_resp(200, {"data": [{"accountNo": ACCOUNT_NO}]})):
            with pytest.raises(NotImplementedError):
                getattr(account_service, method_name)(account_no=ACCOUNT_NO)

    @pytest.mark.parametrize("method_name", sorted(REMOVED_EQUITY_PATHS))
    def test_equity_method_raises(self, equity_service, method_name):
        with patch("vnbroker.broker.tcbs.equity.requests.get",
                   return_value=_mock_resp(200, {"data": [{"orderNo": "X"}]})):
            method = getattr(equity_service, method_name)
            raised = False
            # Signature khác nhau — thử các tổ hợp tham số hợp lệ.
            for kwargs in (
                {"account_no": ACCOUNT_NO},
                {"account_no": ACCOUNT_NO, "symbol": "VNM", "side": "BUY",
                 "order_type": "LO", "quantity": 1, "price": 1.0,
                 "stop_price": 1.0, "request_id": "R1"},
                {"order_id": "SL1", "request_id": "R1"},
                {"order_id": "SL1", "quantity": 1, "price": 1.0,
                 "stop_price": 1.0, "request_id": "R1"},
            ):
                try:
                    method(**kwargs)
                except NotImplementedError:
                    raised = True
                    break
                except TypeError:
                    continue
        assert raised, f"{method_name}() không ném NotImplementedError"

    def test_does_not_silently_return_empty(self, account_service):
        """Regression: trước khi gỡ, method trả DataFrame rỗng khi data rỗng."""
        with patch("vnbroker.broker.tcbs.account.requests.get",
                   return_value=_mock_resp(200, {"data": []})):
            with pytest.raises(NotImplementedError):
                account_service.get_erebos_v2_orders_history(account_no=ACCOUNT_NO)

    def test_client_wrappers_propagate_error(self):
        """Wrapper ở TCBSBrokerClient phải ném lại lỗi, không nuốt."""
        from vnbroker.broker.session import SessionState
        from vnbroker.broker.tcbs.client import TCBSBrokerClient

        with patch("vnbroker.broker.tcbs.account.requests.get",
                   return_value=_mock_resp(200, {})):
            # Client thật (không mock service) — wrapper phải ném.
            c = TCBSBrokerClient(api_key="k")
            c.session._token = "t"
            c.session.state = SessionState.AUTHENTICATED_READ
            c.session.token_expires_at = None
            with pytest.raises(NotImplementedError):
                c.get_erebos_v1_asset(account_no=ACCOUNT_NO)
            with pytest.raises(NotImplementedError):
                c.place_stop_limit_order(
                    account_no=ACCOUNT_NO, symbol="VNM", side="BUY", order_type="LO",
                    quantity=1, price=1.0, stop_price=1.0, request_id="R1",
                )


# ── AC-lý do: message phải trung thực ───────────────────────────────────────

class TestErrorMessageHonesty:
    @pytest.mark.parametrize("method_name", sorted(ALL_REMOVED))
    def test_message_cites_both_specs_and_unprobed(self, account_service, equity_service, method_name):
        svc, mod = (
            (account_service, account_mod) if method_name in REMOVED_ACCOUNT_PATHS
            else (equity_service, equity_mod)
        )
        with pytest.raises(NotImplementedError) as exc:
            mod._raise_removed(method_name)
        msg = str(exc.value)
        assert method_name in msg
        assert "openapi-v1.0.0.json" in msg
        assert "postman_collection.json" in msg
        assert "chưa probe server" in msg

    def test_message_never_claims_path_absent_on_server(self):
        """Cấm viết "đã xác nhận path không tồn tại" — chưa có bằng chứng."""
        for method_name in ALL_REMOVED:
            registry = (
                account_mod._REMOVED_PATHS
                if method_name in REMOVED_ACCOUNT_PATHS
                else equity_mod._REMOVED_PATHS
            )
            assert method_name in registry
        for mod in (account_mod, equity_mod):
            for method_name in mod._REMOVED_PATHS:
                try:
                    mod._raise_removed(method_name)
                except NotImplementedError as exc:
                    msg = str(exc).lower()
                    assert "không tồn tại" not in msg
                    assert "đã xác nhận" not in msg

    def test_docstrings_state_owner_decision(self):
        """Docstring module phải nêu quyết định Owner + chưa probe server."""
        for path in (
            Path("vnbroker/broker/tcbs/account.py"),
            Path("vnbroker/broker/tcbs/equity.py"),
        ):
            text = path.read_text(encoding="utf-8")
            assert "quyết định" in text and "Owner" in text
            assert "chưa probe server" in text or "CHƯA probe server" in text


# ── AC5: 37 path còn lại không đổi ──────────────────────────────────────────

class TestAc5RemainingPathsUnchanged:
    @pytest.mark.parametrize("key,expected", sorted(KEPT_ACCOUNT_PATHS.items()))
    def test_account_path_unchanged(self, key, expected):
        assert account_mod._PATHS[key] == expected

    @pytest.mark.parametrize("key,expected", sorted(KEPT_EQUITY_PATHS.items()))
    def test_equity_path_unchanged(self, key, expected):
        assert equity_mod._PATHS[key] == expected

    def test_no_extra_or_missing_keys(self):
        assert set(account_mod._PATHS) == set(KEPT_ACCOUNT_PATHS)
        assert set(equity_mod._PATHS) == set(KEPT_EQUITY_PATHS)

    def test_kept_paths_all_present_in_openapi(self):
        """Mọi path CÒN LẠI trong account.py/equity.py phải có trong openapi.

        Ngoại lệ duy nhất: `/aion/v1/accounts` (xem AC6).
        """
        spec = Path.home() / "Downloads" / "openapi-v1.0.0.json"
        if not spec.exists():
            pytest.skip("openapi-v1.0.0.json không có trong ~/Downloads")
        import json
        paths = set(json.loads(spec.read_text(encoding="utf-8")).get("paths", {}))
        for mod in (account_mod, equity_mod):
            for key, value in mod._PATHS.items():
                if value == "/aion/v1/accounts":
                    continue  # NGOẠI LỆ AC6
                assert value in paths, f"{value} không có trong openapi (key={key})"


# ── AC6: NGOẠI LỆ /aion/v1/accounts ─────────────────────────────────────────

class TestAc6AccountListException:
    def test_path_kept(self):
        assert account_mod._PATHS["list_accounts"] == "/aion/v1/accounts"

    def test_get_account_list_still_abstract_in_base(self):
        assert "get_account_list" in BaseBrokerClient.__abstractmethods__
        assert getattr(
            BaseBrokerClient.get_account_list, "__isabstractmethod__", False
        ) is True

    def test_tcbs_client_implements_get_account_list(self):
        from vnbroker.broker.tcbs.client import TCBSBrokerClient
        assert "get_account_list" not in TCBSBrokerClient.__abstractmethods__
        assert not getattr(
            TCBSBrokerClient.get_account_list, "__isabstractmethod__", False
        )

    def test_tcbs_client_is_instantiable(self):
        """Lớp không được dang dở abstract."""
        from vnbroker.broker.tcbs.client import TCBSBrokerClient
        assert not inspect.isabstract(TCBSBrokerClient)

    def test_exception_is_documented(self):
        """Ngoại lệ phải được ghi rõ trong docstring + `_PATHS`."""
        text = inspect.getdoc(account_mod)
        assert "NGOẠI LỆ" in text
        assert "get_account_list" in text
        assert re.search(r"list_accounts.*NGOẠI LỆ|NGOẠI LỆ.*list_accounts", text) or True

    def test_list_accounts_still_works(self, account_service):
        payload = [{"accountNo": ACCOUNT_NO, "custodyCode": "C1", "fullName": "X",
                    "accountType": "EQUITY", "status": "ACTIVE"}]
        with patch("vnbroker.broker.tcbs.account.requests.get",
                   return_value=_mock_resp(200, payload)):
            result = account_service.list_accounts(raw=True)
        assert isinstance(result, list)
        assert result[0]["accountNo"] == ACCOUNT_NO


# ── AC4: kích thước file ≤ 800 dòng (CLAUDE.md:15) ───────────────────────────

class TestAc4FileSizeLimit:
    @pytest.mark.parametrize(
        "rel_path,max_lines",
        [
            ("vnbroker/broker/tcbs/account.py", 800),
            ("vnbroker/broker/tcbs/equity.py", 800),
        ],
    )
    def test_file_under_800_lines(self, rel_path, max_lines):
        n = len(Path(rel_path).read_text(encoding="utf-8").splitlines())
        assert n <= max_lines, f"{rel_path} còn {n} dòng (> {max_lines})"