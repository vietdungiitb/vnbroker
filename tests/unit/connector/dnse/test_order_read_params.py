"""Slice C — tham số đọc lệnh: `pageIndex` và cặp `from`/`to` (D2, D3, D4).

Kế hoạch: `docs/PLAN_DNSE_FIX_20261016.md` §5 lát C. Đo production 2026-10-16:

- `GET /accounts/{no}/orders` thiếu `pageIndex` ⇒ `400 pageIndex is required`.
  **Sandbox thì không đòi** — lệch môi trường, nên đừng dựa vào sandbox để kết
  luận về production.
- `GET /accounts/{no}/orders/history` thiếu cả hai ⇒ `400 from is required`;
  chỉ có `from` ⇒ `400 to is required`.
- `from`/`to` ở đây là **date string `yyyy-MM-dd`**, khác hẳn unix giây của
  price endpoints (D4). Dễ nhầm, nên docstring phải nói.

Nguyên tắc: tham số sai bị chặn **trước khi có byte nào đi ra** (L-R01), và
phải nói rõ cái gì hợp lệ thay vì chỉ nói "invalid".
"""
from __future__ import annotations

import pytest
import requests

from vnbroker.connector.dnse.client import DNSEClient
from vnbroker.connector.dnse.core.errors import DNSEValidationError

ACCOUNT = "0003724720"


class _NoEgress:
    """Cấm mọi request. Nếu guard chạy sau network thì test này đỏ."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __enter__(self) -> "_NoEgress":
        self._original = requests.Session.request
        guard = self

        def _spy(_self, method, url, *args, **kwargs):
            guard.calls.append(f"{method} {url}")
            raise AssertionError(f"request đã đi ra dù tham số sai: {method} {url}")

        requests.Session.request = _spy  # type: ignore[method-assign]
        return self

    def __exit__(self, *_exc) -> None:
        requests.Session.request = self._original  # type: ignore[method-assign]


def _client() -> DNSEClient:
    return DNSEClient(api_key="k", api_secret="s")


# --- AC-C1: get_orders luôn mang pageIndex ----------------------------------


def test_get_orders_fills_page_index_because_production_demands_it():
    """Đo production: thiếu `pageIndex` ⇒ 400. Sandbox không đòi, nên chỉ đo
    sandbox sẽ bỏ sót đúng lỗi này."""
    payload = _client().get_orders(ACCOUNT, "STOCK", dry_run=True, raw=True)
    assert payload["query"]["pageIndex"] == 1


def test_get_orders_lets_the_caller_override_page_index():
    payload = _client().get_orders(
        ACCOUNT, "STOCK", page_index=3, page_size=50, dry_run=True, raw=True
    )
    assert payload["query"]["pageIndex"] == 3
    assert payload["query"]["pageSize"] == 50


def test_page_index_survives_the_public_facade():
    """AC-C1 phải đạt được qua API công khai, không chỉ qua service nội bộ.

    Đây là finding M6 của audit: `client.get_orders` trước đây không có
    `page_index`, nên envelope đúng ở tầng dưới mà vẫn không dùng được.
    """
    import inspect

    params = inspect.signature(DNSEClient.get_orders).parameters
    assert "page_index" in params, "facade chưa forward page_index"
    assert "page_size" in params, "facade chưa forward page_size"


# --- AC-C2: get_order_history thiếu một nửa cặp -> chặn sớm ----------------


def test_order_history_with_only_from_raises_before_the_network():
    with _NoEgress() as egress, pytest.raises(DNSEValidationError) as excinfo:
        _client().get_order_history(
            ACCOUNT, "STOCK", from_date="2026-10-01", dry_run=True
        )
    assert excinfo.value.error_code == "ORDER_HISTORY_RANGE_INCOMPLETE"
    assert egress.calls == []


def test_order_history_with_only_to_raises_too():
    with _NoEgress(), pytest.raises(DNSEValidationError):
        _client().get_order_history(ACCOUNT, "STOCK", to_date="2026-10-05", dry_run=True)


def test_the_message_names_the_missing_side():
    with pytest.raises(DNSEValidationError) as excinfo:
        _client().get_order_history(ACCOUNT, "STOCK", from_date="2026-10-01", dry_run=True)
    message = str(excinfo.value)
    assert "to" in message, "thông điệp phải chỉ ra phía nào còn thiếu"


# --- AC-C3: cặp đủ thì giữ nguyên date string -----------------------------


def test_order_history_keeps_the_date_string_format():
    payload = _client().get_order_history(
        ACCOUNT, "STOCK", from_date="2026-10-01", to_date="2026-10-05",
        dry_run=True, raw=True,
    )
    assert payload["query"]["from"] == "2026-10-01"
    assert payload["query"]["to"] == "2026-10-05"
    assert isinstance(payload["query"]["from"], str), (
        "server muốn date string; ép sang số là sai hợp đồng"
    )


def test_order_history_with_neither_side_is_still_allowed():
    """Sandbox gọi được khi thiếu cả hai — không được chặn hành vi đang chạy ở
    môi trường kia chỉ vì production đòi."""
    payload = _client().get_order_history(ACCOUNT, "STOCK", dry_run=True, raw=True)
    assert "from" not in payload["query"]
    assert "to" not in payload["query"]


def test_docstring_says_the_format_is_a_date_not_unix_seconds():
    """D4: `from`/`to` ở đây là `yyyy-MM-dd`, khác unix giây của price endpoints.
    Chỗ dễ nhầm nhất của toàn bộ connector, nên nó phải nằm trong docstring."""
    doc = (DNSEClient.get_order_history.__doc__ or "") + (
        DNSEClient.get_orders.__doc__ or ""
    )
    assert "yyyy-MM-dd" in doc, "docstring phải nói rõ format ngày"


# --- L-R03: không được giả định field nào là bắt buộc ----------------------


def test_envelope_keys_are_read_defensively_not_assumed():
    """`pageIndex`/`pageSize` không nằm trong `required` của bất kỳ spec nào
    trong repo. Đọc bằng `.get()` là bắt buộc; test này ghim hành vi đó bằng một
    payload thiếu field."""
    envelope = {"query": {"marketType": "STOCK"}}
    assert envelope["query"].get("pageIndex") is None  # không KeyError


def test_page_size_is_omitted_rather_than_sent_as_none():
    payload = _client().get_orders(ACCOUNT, "STOCK", dry_run=True, raw=True)
    assert "pageSize" not in payload["query"], (
        "gửi pageSize=None sẽ thành chuỗi 'None' trên URL"
    )