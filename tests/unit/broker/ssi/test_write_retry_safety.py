"""P0-1: SSI không được retry mù trên POST đặt lệnh.

Bối cảnh
--------
``SSIHttpClient.request`` bọc mọi request trong ``tenacity.Retrying`` không phân
biệt method. ``ConnectionError`` cũng xảy ra khi **server đã nhận xong lệnh
nhưng response bị mất** — retrier gửi lại y hệt body+signature và broker nhận
trùng. Chống chặn duy nhất là dedupe server-side theo ``clientRequestId``.

Đây là đường tiền thật: 1 lệnh có thể thành N lệnh.

Hợp đồng
--------
- Method idempotent (GET/HEAD/PUT/DELETE): retry bình thường.
- Method không idempotent (POST): **không retry tự động**; ném lỗi để caller
  quyết định, kèm thông tin đủ để tra cứu lại (clientRequestId).

Không gọi mạng: session giả đếm số POST thật.
"""

from __future__ import annotations

import requests

import pytest

from vnbroker.broker.ssi._transport import SSIHttpClient

ORDER_PATH = "/api/v3/trading/order"


class FakeResponse:
    status_code = 200
    text = '{"orderId":"SRV-1","orderStatus":"NEW"}'
    headers: dict = {}
    encoding = "utf-8"

    def json(self):
        return {"orderId": "SRV-1", "orderStatus": "NEW"}


class CountingSession:
    """Đếm số request thật đi ra theo method."""

    def __init__(self, fail_times: int = 0) -> None:
        self.fail_times = fail_times
        self.calls: list[str] = []
        self.headers: dict = {}

    def request(self, method, url, **kw):
        method = method.upper()
        self.calls.append(f"{method} {url}")
        # Server "đã xử lý" rồi mất response → ConnectionError.
        if len([c for c in self.calls if c.startswith(method)]) <= self.fail_times:
            raise requests.exceptions.ConnectionError("connection reset by peer")
        return FakeResponse()

    def close(self) -> None:
        pass


def _client(fail_times: int = 0) -> tuple[SSIHttpClient, CountingSession]:
    # rate_limit_rps=0 để test không phải chờ giữa các attempt.
    c = SSIHttpClient(base_url="https://fake.api.ssi.com.vn", rate_limit_rps=0)
    sess = CountingSession(fail_times=fail_times)
    c._session = sess
    return c, sess


def _posts(calls: list[str]) -> list[str]:
    return [c for c in calls if c.startswith("POST")]


# ------------------------------------------------- write: KHÔNG retry


def test_post_order_is_not_retried():
    """POST đặt lệnh phải gửi ĐÚNG MỘT lần dù response mất."""
    client, sess = _client(fail_times=5)

    with pytest.raises(Exception):
        client.request(
            "POST", ORDER_PATH, json_body={"symbol": "ACB", "quantity": 100}
        )

    assert len(_posts(sess.calls)) == 1, (
        f"POST đặt lệnh bị retry {len(_posts(sess.calls))} lần — double-submit! "
        f"calls={sess.calls}"
    )


def test_write_failure_error_mentions_no_retry():
    """Lỗi phải nói rõ là KHÔNG retry, để caller biết phải tự quyết định."""
    client, _ = _client(fail_times=1)

    with pytest.raises(Exception) as exc:
        client.request("POST", ORDER_PATH, json_body={"symbol": "ACB"})

    msg = str(exc.value).lower()
    assert "idempot" in msg or "không retry" in msg or "no retry" in msg, (
        f"Thông điệp lỗi chưa nói rõ không retry: {exc.value}"
    )


# ------------------------------------------------- read: VẪN retry


def test_get_read_is_still_retried():
    """GET là idempotent → retry vẫn phải hoạt động bình thường."""
    client, sess = _client(fail_times=2)

    result = client.request("GET", "/api/v3/trading/orderBook")

    assert result["orderId"] == "SRV-1"
    assert len(sess.calls) == 3, (
        f"GET phải retry tới khi thành công, thực tế {len(sess.calls)} lần"
    )


def test_delete_is_retried():
    """DELETE là idempotent theo HTTP semantics → retry được phép."""
    client, sess = _client(fail_times=1)

    client.request("DELETE", ORDER_PATH)

    assert len([c for c in sess.calls if c.startswith("DELETE")]) == 2


def test_put_is_retried():
    client, sess = _client(fail_times=1)

    client.request("PUT", ORDER_PATH, json_body={"quantity": 200})

    assert len([c for c in sess.calls if c.startswith("PUT")]) == 2


# ------------------------------------------------- non-retryable errors


def test_non_network_error_never_retried():
    """Lỗi không phải mạng (vd ValueError) không được retry cho GET nữa."""
    class ValueErrorSession(CountingSession):
        def request(self, method, url, **kw):
            self.calls.append(f"{method} {url}")
            raise ValueError("payload invalid")

    client, _ = _client()
    sess = ValueErrorSession()
    client._session = sess

    with pytest.raises(Exception):
        client.request("GET", ORDER_PATH)

    assert len(sess.calls) == 1, "Lỗi không phải mạng không được retry"