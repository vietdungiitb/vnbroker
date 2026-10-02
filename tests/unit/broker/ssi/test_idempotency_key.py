"""P0-1 (phần 2): caller phải giữ được idempotency key khi thử lại.

Vì sao quan trọng
-----------------
Sau khi bỏ retry tự động trên POST, người dùng sẽ **tự** đặt lại khi gặp lỗi
mạng. Nếu mỗi lần gọi lại đều sinh `clientRequestId` khác nhau thì dedupe phía
server không có tác dụng — đặt lại vẫn là **lệnh trùng**, chỉ là do user bấm.

Hợp đồng:
- ``request_id`` truyền vào phải được giữ nguyên xuyên suốt các lần thử.
- Không có cơ chế "tự sinh rồi quên": ``request_id`` luôn được trả về cho caller
  qua exception/response để họ dùng lại được.
"""

from __future__ import annotations

import pytest

from vnbroker.broker.exceptions import BrokerNetworkError
from vnbroker.broker.ssi._transport import SSIHttpClient


class FakeResponse:
    status_code = 200
    text = '{"orderId":"SRV-1","orderStatus":"NEW"}'
    headers: dict = {}
    encoding = "utf-8"

    def json(self):
        return {"orderId": "SRV-1", "orderStatus": "NEW"}


class LostResponseSession:
    """Server nhận lệnh rồi mất response — không giả lập được dedupe ở đây."""

    def __init__(self) -> None:
        self.headers: dict = {}
        self.bodies: list[str] = []

    def request(self, method, url, **kw):
        self.bodies.append(str(kw.get("raw_content") or kw.get("json") or ""))
        import requests

        raise requests.exceptions.ConnectionError("connection reset by peer")

    def close(self) -> None:
        pass


def _client() -> SSIHttpClient:
    c = SSIHttpClient(base_url="https://fake.api.ssi.com.vn", rate_limit_rps=0)
    c._session = LostResponseSession()
    return c


ORDER_BODY = {
    "symbol": "ACB",
    "side": "B",
    "quantity": 100,
    "clientRequestId": "FIXED-KEY-123",
}


def test_manual_retry_with_same_request_id_is_safe():
    """Gọi lại với CÙNG clientRequestId → server dedupe được, không trùng lệnh."""
    client = _client()

    for _ in range(3):
        with pytest.raises(BrokerNetworkError):
            client.request(
                "POST",
                "/api/v3/trading/order",
                json_body=dict(ORDER_BODY),
            )

    bodies = client._session.bodies
    assert len(bodies) == 3
    # Cùng key mọi lần → broker nhận 1 lệnh, trả lại lệnh cũ cho các lần sau.
    for b in bodies:
        assert "FIXED-KEY-123" in b, f"clientRequestId phải giữ nguyên: {b}"


def test_error_message_exposes_how_to_retry_safely():
    """Lỗi phải hướng dẫn cụ thể cách thử lại an toàn."""
    client = _client()

    with pytest.raises(BrokerNetworkError) as exc:
        client.request("POST", "/api/v3/trading/order", json_body=dict(ORDER_BODY))

    msg = str(exc.value)
    assert "clientRequestId" in msg, (
        f"Lỗi phải nhắc tới clientRequestId để user biết tra cứu/đặt lại: {msg}"
    )
    assert exc.value.code == "NETWORK_ERROR_NON_IDEMPOTENT"