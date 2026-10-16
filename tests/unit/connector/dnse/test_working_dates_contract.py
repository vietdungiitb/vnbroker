"""Slice B — `get_working_dates` phải gọi endpoint thật, không trả "thành công rỗng".

Kế hoạch: `docs/PLAN_DNSE_FIX_20261016.md` §5 lát B. Bằng chứng D1.

**Defect (đo):** `services/market_service.py` trả một tuple hằng `({"dates": []},
None)` — không gọi network, tốn 0ms. `_resolve_output` unpack `(status, body)`
nên lấy nhầm `body = None`. Người gọi thấy "không có ngày giao dịch nào" thay vì
"chưa ai hỏi server" — đúng mẫu fail-open mà `docs/LESSONS/broker-risk.md` đã
ghi (L-R01).

**Docstring trong code nói sai:** *"DNSE OpenAPI does not have a dedicated
working-dates endpoint."* Đo production 2026-10-16 (không VPN):

    GET /market/working-dates -> 200, {"workingDates": [257 phần tử]}

Nên đây là **path sai / thiếu**, không phải endpoint không tồn tại.

Ba lỗi phái sinh cũng được khóa ở đây:

1. `_to_dataframe` không có `workingDates` trong danh sách key ⇒ `raw=False` trả
   DataFrame **1 dòng** chứa một cell là list. Đó là bug gốc được tái tạo dưới
   hình dạng khác — nếu chỉ sửa path thì sửa bằng một lỗi khác.
2. **Tầng explorer cũng phải tách dòng.** `DNSEQuote.working_dates` từng gọi
   `pd.json_normalize(body)` trực tiếp ⇒ shape `(1, 1)` thay vì `(3, 1)`, trong
   khi `DNSEClient._to_dataframe` cho `(3, 1)`. Đây chính là hình thức "thành
   công rỗng" mà lát B sinh ra để chữa, chỉ là ở tầng khác — audit code đã bắt
   được sau khi nó đã được viết ra docstring là đã xử lý.
3. `explorer/dnse/quote.py::working_dates` nay sẽ **gọi network thật**; trên
   sandbox `/market/*` là 404 nên nó rơi vào `except` và trả DataFrame rỗng
   **im lặng** — đúng kiểu im lặng mà lát này sinh ra để chữa.
"""
from __future__ import annotations

import pandas as pd
import pytest

from vnbroker.connector.dnse.client import DNSEClient
from vnbroker.explorer.dnse.quote import DNSEQuote


def _client() -> DNSEClient:
    return DNSEClient(api_key="k", api_secret="s")


def _explorer(symbol: str = "HPG") -> DNSEQuote:
    return DNSEQuote(symbol=symbol, api_key="k", api_secret="s")


class _StubMarket:
    """Thay `_market` bằng object trả sẵn payload — không chạm network."""

    def __init__(self, body: object) -> None:
        self._body = body

    def get_working_dates(self, *_args, **_kwargs):
        return None, self._body


class _BoomMarket:
    def get_working_dates(self, *_args, **_kwargs):
        raise RuntimeError("404 not found")


# --- AC-B1: path thật, không mang theo marketType ---------------------------


def test_working_dates_calls_the_documented_endpoint():
    payload = _client().get_working_dates(dry_run=True, raw=True)
    assert payload["method"] == "GET"
    assert payload["url"].endswith("/market/working-dates")


def test_working_dates_sends_no_query_at_all():
    """Đo production: thêm `marketType` ⇒ 404. Endpoint này không chấp nhận nó.

    Gửi `marketType=None` thì không phải 404, nhưng vẫn là một tham số không có
    trong hợp đồng. Rỗng là trạng thái đúng.
    """
    payload = _client().get_working_dates(dry_run=True, raw=True)
    assert payload["query"] == {}


def test_working_dates_no_longer_returns_a_hardcoded_empty_tuple():
    """Chặn đúng cái bug tuple-order: `body` phải là envelope của dry-run."""
    status, body = _client()._market.get_working_dates(dry_run=True)
    assert status is None, "dry-run không được có HTTP status"
    assert isinstance(body, dict), f"body phải là dict, nhận {type(body).__name__}"


# --- AC-B2: raw=False phải ra NHIỀU DÒNG, không phải 1 dòng ---------------


def test_to_dataframe_unwraps_working_dates_instead_of_keeping_one_row():
    payload = {"workingDates": ["2026-10-15", "2026-10-16"]}
    frame = DNSEClient._to_dataframe(payload)
    assert isinstance(frame, pd.DataFrame)
    assert len(frame) == 2, (
        "1 dòng nghĩa là payload bị bọc lại nguyên khối — "
        "json_normalize trên dict không tách list ra được"
    )
    assert "workingDates" in frame.columns


def test_raw_false_returns_one_row_per_trading_day():
    frame = DNSEClient._to_dataframe(
        {"workingDates": ["2026-01-05", "2026-01-06", "2026-01-07"]}
    )
    assert len(frame) == 3


# --- AC-B3: TẦNG EXPLORER cũng phải tách dòng ------------------------------


def test_explorer_returns_one_row_per_trading_day():
    quote = _explorer()
    quote._market = _StubMarket({"workingDates": ["2026-10-14", "2026-10-15", "2026-10-16"]})
    frame = quote.working_dates()
    assert len(frame) == 3, (
        f"phải một dòng mỗi ngày, nhận {len(frame)} — "
        f"json_normalize trên dict bọc nguyên khối thành 1 dòng"
    )


def test_explorer_does_not_regress_to_a_single_row():
    """Chốt lại: đây là hồi quy đã xảy ra một lần, không được xảy ra lần hai."""
    quote = _explorer()
    quote._market = _StubMarket({"workingDates": ["2026-01-05", "2026-01-06"]})
    frame = quote.working_dates()
    assert not isinstance(frame.iloc[0, 0], list), (
        "cell đầu vẫn là list ⇒ đã quay lại json_normalize trực tiếp"
    )


def test_explorer_returns_empty_frame_on_error():
    """Lỗi phải ra DataFrame rỗng kèm log, không được ném lỗi lên người gọi."""
    quote = _explorer()
    quote._market = _BoomMarket()
    assert quote.working_dates().empty


def test_explorer_always_returns_a_dataframe_even_for_a_scalar_body():
    """`normalize_payload` là pass-through với mọi thứ không phải dict/list.

    Method khai `-> pd.DataFrame`; nếu server trả về thứ lạ thì phải vẫn ra
    DataFrame, không được trả `str` rồi để người gọi gặp `TypeError` khi
    `len(df)`.
    """
    quote = _explorer()
    quote._market = _StubMarket("2026-10-16")
    assert isinstance(quote.working_dates(), pd.DataFrame)


def test_explorer_docstring_says_it_hits_the_network():
    """Nay method này gọi server. Docstring phải nói, để người đọc không giả
    định nó rẻ và không giả định nó miễn phí khi sandbox trả 404."""
    doc = DNSEQuote.working_dates.__doc__ or ""
    lowered = doc.lower()
    assert "network" in lowered or "server" in lowered, (
        "docstring phải nói rõ đây là lời gọi network thật"
    )


# --- hợp đồng cấu trúc đầu ra ----------------------------------------------


def test_working_dates_column_is_stable_for_downstream_code():
    """Explorer trả DataFrame — tên cột là hợp đồng với phía tiêu thụ."""
    frame = DNSEClient._to_dataframe({"workingDates": ["2026-10-16"]})
    assert list(frame.columns) == ["workingDates"]


@pytest.mark.parametrize("payload", [{"workingDates": []}, {"workingDates": None}])
def test_empty_or_missing_list_does_not_raise(payload):
    frame = DNSEClient._to_dataframe(payload)
    assert isinstance(frame, pd.DataFrame)