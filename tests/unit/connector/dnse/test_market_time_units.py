"""Slice A — đơn vị thời gian của DNSE price endpoints (D8) + chặn market_index (D9).

Kế hoạch: `docs/PLAN_DNSE_FIX_20261016.md` §5 lát A.
Đo được 2026-10-16 trên production (không VPN):

- `from`/`to` là **unix GIÂY**. Truyền milliseconds ⇒
  `400 range exceeds maximum time range`. Đây không phải suy đoán: cùng một
  cặp tham số, chỉ khác đơn vị, cho 200 vs 400.
- `get_market_index` cần `from`/`to` **cùng một ngày** (Asia/Ho_Chi_Minh);
  khác ngày ⇒ `400 from and to must be in the same date`.

Vì sao cần chặn ở client: 5 method khai `from_date: int | None` mà không nói
đơn vị (`services/market_service.py`), nên `int(time.time() * 1000)` — thói quen
phổ biến — là hỏng mà không có dấu hiệu gì từ phía vnbroker.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import requests

from vnbroker.connector.dnse.client import DNSEClient
from vnbroker.connector.dnse.core.errors import DNSEValidationError
from vnbroker.connector.dnse.core.time_utils import to_unix_seconds, vn_day_bounds

ICT = ZoneInfo("Asia/Ho_Chi_Minh")

# Hằng số epoch ĐO BẰNG MÁY, không gõ từ trí nhớ:
#   int(datetime(2026,10,16,0,0,tz=ICT).timestamp())  == 1792083600
#   int(datetime(2026,10,16,15,0,tz=ICT).timestamp()) == 1792137600
# Lần gõ tay đầu tiên ra 1791498000/1791552000 — tức lệch đúng 7 ngày, vì
# quên mất mốc là UTC chứ không phải giờ VN. Đó là lý do
# `test_naive_datetime_is_read_as_vietnam_time_not_utc` tồn tại.
DAY_OPEN_S = 1792083600
NOON_S = 1792137600


class _EgressCounter:
    """Đếm số request thật đi ra. Không cấm — để test biết con số."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __enter__(self) -> "_EgressCounter":
        self._original = requests.Session.request

        def _spy(_self, method, url, *args, **kwargs):
            self.calls.append(f"{method} {url}")
            raise AssertionError(f"không được gửi request: {method} {url}")

        requests.Session.request = _spy  # type: ignore[method-assign]
        return self

    def __exit__(self, *_exc) -> None:
        requests.Session.request = self._original  # type: ignore[method-assign]


def _client() -> DNSEClient:
    return DNSEClient(api_key="k", api_secret="s")


# --- AC-A1: đơn vị là GIÂY, và milliseconds phải được nhận ra ---------------


def test_datetime_becomes_seconds_not_milliseconds():
    value = to_unix_seconds(datetime(2026, 10, 16, 15, 0, tzinfo=ICT))
    assert value == NOON_S
    # 1.7e9 = giây. 1.7e12 = milliseconds. Chênh 1000 lần.
    assert value < 10**11


def test_a_bare_int_is_left_alone_when_it_already_looks_like_seconds():
    assert to_unix_seconds(DAY_OPEN_S) == DAY_OPEN_S


def test_milliseconds_are_converted_because_that_is_the_measured_footgun():
    """int(time.time() * 1000) là cách mọi người hay viết — server trả 400."""
    assert to_unix_seconds(NOON_S * 1000) == NOON_S


def test_iso_date_string_is_parsed_as_midnight_in_vietnam_time():
    assert to_unix_seconds("2026-10-16") == DAY_OPEN_S


def test_naive_datetime_is_read_as_vietnam_time_not_utc():
    """Không có tzinfo thì phải giả định giờ VN, không phải UTC.

    Giả định UTC lệch 7 tiếng ⇒ 'cùng ngày' thành 'khác ngày'.
    """
    assert to_unix_seconds(datetime(2026, 10, 16, 0, 0)) == DAY_OPEN_S


def test_vn_day_bounds_returns_both_edges_of_the_same_day():
    start, end = vn_day_bounds("2026-10-16")
    assert start == DAY_OPEN_S
    assert end > start
    assert (
        datetime.fromtimestamp(start, ICT).date()
        == datetime.fromtimestamp(end, ICT).date()
    )


# --- AC-A2: market_index khác ngày -> chặn TRƯỚC network ---------------------


def test_market_index_across_two_days_raises_before_any_request():
    with _EgressCounter() as egress, pytest.raises(DNSEValidationError) as excinfo:
        _client().get_market_index(
            "VNINDEX", from_date=DAY_OPEN_S, to_date=DAY_OPEN_S + 86400, dry_run=True
        )
    assert excinfo.value.error_code == "MARKET_INDEX_RANGE_NOT_SAME_DAY"
    assert egress.calls == [], "request đã đi ra dù tham số sai"


def test_the_rejection_message_names_both_edges():
    """Thông điệp phải nói rõ cửa sổ hợp lệ, không chỉ 'invalid'."""
    with pytest.raises(DNSEValidationError) as excinfo:
        _client().get_market_index(
            "VNINDEX", from_date=DAY_OPEN_S, to_date=DAY_OPEN_S + 86400, dry_run=True
        )
    message = str(excinfo.value)
    assert "2026-10-16" in message


# --- AC-A3: cùng ngày -> đi thẳng, giữ nguyên giá trị -----------------------


def test_market_index_within_one_day_passes_the_values_through_untouched():
    payload = _client().get_market_index(
        "VNINDEX", from_date=DAY_OPEN_S, to_date=NOON_S, dry_run=True, raw=True
    )
    assert payload["query"]["from"] == DAY_OPEN_S
    assert payload["query"]["to"] == NOON_S


def test_market_index_late_evening_to_next_midnight_is_still_one_day():
    """23:59 hôm nay → 00:05 mai là KHÔNG cùng ngày. Đây là điều kiện thật."""
    end_of_day = DAY_OPEN_S + 86400 - 60
    with pytest.raises(DNSEValidationError):
        _client().get_market_index(
            "VNINDEX", from_date=end_of_day, to_date=DAY_OPEN_S + 86400 + 300, dry_run=True
        )


# --- AC-A1 (bổ sung sau audit): D8 phải thật sự bị chặn ở đường đi thật ----
#
# `to_unix_seconds` chỉ tồn tại mà không được gọi ở đâu thì D8 vẫn reachable
# qua API công khai — module + test tạo cảm giác an toàn giả (audit major #3).
# Các test dưới đây gọi đúng API công khai như một người dùng thật.


def test_public_api_converts_milliseconds_to_seconds():
    """Đo: ms => `400 range exceeds maximum time range`; giây => 200."""
    payload = _client().get_quotes(
        "MBS", from_date=NOON_S * 1000, to_date=(NOON_S + 60) * 1000,
        dry_run=True, raw=True,
    )
    assert payload["query"]["from"] == NOON_S
    assert payload["query"]["to"] == NOON_S + 60


def test_public_api_leaves_real_seconds_untouched():
    payload = _client().get_quotes(
        "MBS", from_date=DAY_OPEN_S, to_date=NOON_S, dry_run=True, raw=True
    )
    assert payload["query"]["from"] == DAY_OPEN_S


@pytest.mark.parametrize(
    "method",
    ["get_quotes", "get_trades", "get_expected_price", "get_foreign_trading"],
)
def test_every_paginated_method_normalises_milliseconds(method):
    """Cả 4 endpoint đi qua `_history_query` nên phải chuẩn hoá như nhau."""
    payload = getattr(_client(), method)(
        "MBS", from_date=NOON_S * 1000, to_date=NOON_S * 1000, dry_run=True, raw=True
    )
    assert payload["query"]["from"] == NOON_S


def test_a_datetime_is_accepted_where_the_api_used_to_demand_an_int():
    """`to_unix_seconds` nhận datetime — người gọi không còn phải tự tính."""
    payload = _client().get_quotes(
        "MBS", from_date=datetime(2026, 10, 16, 15, 0, tzinfo=ICT),
        to_date=datetime(2026, 10, 16, 15, 1, tzinfo=ICT),
        dry_run=True, raw=True,
    )
    assert payload["query"]["from"] == NOON_S


# --- ranh giới ngày: 0 là falsy, `or` sẽ chọn nhầm (audit minor #8) ----------


def test_market_index_error_message_uses_from_when_from_is_zero():
    """`from_date=0` (1970) là falsy. Nếu code viết `from_date or to_date` thì
    thông báo sẽ chỉ ngày của `to_date` — sai ngày trong chính thông điệp lỗi."""
    with pytest.raises(DNSEValidationError) as excinfo:
        _client().get_market_index(
            "VNINDEX", from_date=0, to_date=NOON_S, dry_run=True
        )
    message = str(excinfo.value)
    assert "1970-01-01" in message, f"phải nhắc ngày của from_date=0: {message}"


def test_get_trades_delegates_to_the_shared_history_query(monkeypatch):
    """Chặn việc ai đó dựng lại dict thủ công.

    Nếu test này chỉ so dict của `get_trades` với dict của `get_quotes` thì nó
    là hệ quả tất nhiên — xanh cả khi lỗi còn. Phải chặn đúng *cơ chế*.
    """
    seen: list[str] = []
    original = DNSEClient.__mro__  # noqa: N806 - chỉ để giữ type checker ổn

    from vnbroker.connector.dnse.services import market_service

    real = market_service.MarketService._history_query

    def _spy(*args, **kwargs):
        seen.append("called")
        return real(*args, **kwargs)

    monkeypatch.setattr(
        market_service.MarketService, "_history_query", staticmethod(_spy)
    )

    client = _client()
    client.get_trades("MBS", from_date=1, to_date=2, dry_run=True, raw=True)
    client.get_quotes("MBS", from_date=1, to_date=2, dry_run=True, raw=True)

    assert len(seen) == 2, "get_trades phải đi qua _history_query giống get_quotes"
    assert original  # giữ tham chiếu cho ruff/mypy


# --- docstring: đơn vị phải được ghi, không để người đọc phải đoán ----------


@pytest.mark.parametrize(
    "name",
    ["get_quotes", "get_trades", "get_expected_price", "get_foreign_trading",
     "get_market_index"],
)
def test_every_paginated_method_documents_the_unit(name):
    """Ghi đơn vị trong docstring là hợp đồng với người đọc, không phải thừa.

    Đây chính là thứ vắng mặt khiến D8 xảy ra.

    ⚠ Không được viết `assert "gi" in doc.lower()`. Tiếng Việt có "gi" trong rất
    nhiều từ ("Giá", "Giao", "giới"), nên assertion đó **vẫn xanh sau khi xoá
    hẳn cả ghi chú** — đã thử, cả 5/5 vẫn PASS. Đây là loại test xanh bằng vô
    nghĩa, và chính plan đã cảnh báo về nó (audit N1).
    """
    doc = getattr(DNSEClient, name).__doc__ or ""
    assert "GIÂY" in doc, f"{name} không nói from/to là unix GIÂY"