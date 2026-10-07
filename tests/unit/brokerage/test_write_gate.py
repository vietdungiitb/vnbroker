"""Test cho hàng rào ghi của lớp `brokerage/` (WriteGateMixin + guarded_write).

Bối cảnh: `vnbroker/brokerage/` trước đây KHÔNG có hàng rào nào — 3 write method
(`place_order`, `cancel_order`, `modify_order`) gửi HTTP ngay khi được gọi, không
`dry_run`, không cổng quyền. Đây là rủi ro P1 đã ghi trong `docs/PLAN_VNSAAS.md`.

Test này khoá 3 nhánh của hàng rào, và khoá luôn các bất biến quan trọng nhất:
  - KHÔNG có HTTP call nào khi dry_run (nhánh 1)
  - KHÔNG có HTTP call nào khi chưa enable_write (nhánh 2)
  - CHỈ nhánh 3 (dry_run=False + đã enable_write) mới chạm HTTP
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vnbroker.broker.exceptions import BrokerPermissionError
from vnbroker.brokerage.base import OrderRequest, OrderSide
from vnbroker.brokerage.guards import (
    DryRunResult,
    WriteGateMixin,
    guarded_write,
    guarded_writes,
)
from vnbroker.brokerage.tcbs.client import TCBSClient

API_KEY = "test-api-key"
SECRET = "dGVzdC1zZWNyZXQ="  # base64("test-secret")
ACCOUNT = "0123456789"


def _client() -> TCBSClient:
    """TCBSClient với HTTP client được mock — không có network thật."""
    c = TCBSClient(api_key=API_KEY, secret=SECRET, account_no=ACCOUNT)
    c._client = MagicMock()
    return c


def _order() -> OrderRequest:
    return OrderRequest(symbol="ACB", side=OrderSide.BUY, quantity=100, price=25000.0)


# ===========================================================================
# Nhóm 1 — dry_run=True (mặc định): KHÔNG được chạm HTTP
# ===========================================================================
class TestDryRunIsDefault:
    def test_place_order_default_does_not_call_http(self):
        c = _client()
        result = c.place_order(_order())

        assert isinstance(result, DryRunResult)
        assert result.dry_run is True
        assert result.blocked is True
        assert result.operation == "place_order"
        c._client.request.assert_not_called()

    def test_cancel_order_default_does_not_call_http(self):
        c = _client()
        result = c.cancel_order("ORDER-1")

        assert isinstance(result, DryRunResult)
        assert result.blocked is True
        c._client.request.assert_not_called()

    def test_modify_order_default_does_not_call_http(self):
        c = _client()
        result = c.modify_order("ORDER-1", price=26000.0)

        assert isinstance(result, DryRunResult)
        assert result.blocked is True
        c._client.request.assert_not_called()

    def test_explicit_dry_run_true_also_blocks(self):
        c = _client()
        result = c.place_order(_order(), dry_run=True)

        assert result.blocked is True
        c._client.request.assert_not_called()


# ===========================================================================
# Nhóm 2 — dry_run=False nhưng CHƯA enable_write(): raise, KHÔNG chạm HTTP
# ===========================================================================
class TestBlockedWithoutEnableWrite:
    def test_place_order_raises_permission_error(self):
        c = _client()
        with pytest.raises(BrokerPermissionError) as exc:
            c.place_order(_order(), dry_run=False)

        assert exc.value.code == "WRITE_NOT_ENABLED"
        assert exc.value.http_status == 403
        c._client.request.assert_not_called()

    def test_cancel_order_raises_permission_error(self):
        c = _client()
        with pytest.raises(BrokerPermissionError):
            c.cancel_order("ORDER-1", dry_run=False)
        c._client.request.assert_not_called()

    def test_modify_order_raises_permission_error(self):
        c = _client()
        with pytest.raises(BrokerPermissionError):
            c.modify_order("ORDER-1", price=26000.0, dry_run=False)
        c._client.request.assert_not_called()

    def test_is_write_enabled_defaults_false(self):
        assert _client().is_write_enabled is False


# ===========================================================================
# Nhóm 3 — dry_run=False + đã enable_write(): ĐƯỢC chạm HTTP
# ===========================================================================
class TestEnabledWriteReachesHttp:
    def test_place_order_calls_http_when_enabled(self):
        c = _client()
        c._client.request.return_value = MagicMock(
            **{
                "json.return_value": {
                    "data": {
                        "orderId": "O-1",
                        "symbol": "ACB",
                        "side": "BUY",
                        "quantity": 100,
                        "filledQuantity": 0,
                        "price": 25000.0,
                        "orderType": "LO",
                        "status": "PENDING",
                        "createdAt": "2026-10-07T10:00:00",
                        "updatedAt": "2026-10-07T10:00:00",
                        "accountNo": ACCOUNT,
                    }
                }
            }
        )
        c.enable_write()
        assert c.is_write_enabled is True

        c.place_order(_order(), dry_run=False)

        c._client.request.assert_called_once()
        assert c._client.request.call_args[0][0] == "POST"

    def test_disable_write_closes_the_gate_again(self):
        c = _client()
        c.enable_write()
        c.disable_write()

        assert c.is_write_enabled is False
        with pytest.raises(BrokerPermissionError):
            c.place_order(_order(), dry_run=False)
        c._client.request.assert_not_called()


# ===========================================================================
# Nhóm 4 — bất biến của mixin: không có đường bypass
# ===========================================================================
class TestNoBypass:
    def test_read_methods_are_not_gated(self):
        """Đọc dữ liệu KHÔNG bị cổng chặn — chỉ write mới có cổng."""
        c = _client()
        c._client.request.return_value = MagicMock(
            **{"json.return_value": {"data": {"availableCash": 0.0, "blockedCash": 0.0,
                                              "totalCash": 0.0, "totalEquity": 0.0}}}
        )
        c.get_balance()  # không raise
        c._client.request.assert_called_once()

    def test_dry_run_result_redacts_secret_like_kwargs(self):
        c = _client()
        result = c.modify_order("ORDER-1", price=1.0, secret="SUPER-SECRET-VALUE")
        assert "SUPER-SECRET-VALUE" not in str(result.to_dict())
        assert result.kwargs.get("secret") == "<redacted>"

    def test_dry_run_result_is_not_order_response(self):
        """Cố ý khác kiểu để code gọi không vô tình coi là lệnh đã đặt."""
        from vnbroker.brokerage.base import OrderResponse

        c = _client()
        result = c.place_order(_order())
        assert not isinstance(result, OrderResponse)

    def test_guarded_write_rejects_non_mixin_class(self):
        class NotAMixin:
            @guarded_write
            def do_write(self, *, dry_run: bool = True):
                return "sent"

        with pytest.raises(TypeError, match="WriteGateMixin"):
            NotAMixin().do_write()

    def test_guarded_writes_rejects_unknown_method_name(self):
        with pytest.raises(TypeError, match="không có method"):

            @guarded_writes("method_khong_ton_tai")
            class Whatever(WriteGateMixin):
                pass
