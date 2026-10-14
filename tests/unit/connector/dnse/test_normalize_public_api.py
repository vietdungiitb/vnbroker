"""Chuẩn hoá + chọn ``marketType`` phải là việc của vnbroker, không phải của caller.

VNBROKER-REQ-005: vninvest đang tự viết ``vnbroker_dnse_compat.py`` để chuẩn
hoá DataFrame/list/dict và thử lần lượt ``ALL/STOCK/EQUITY``. Audit lúc đó đo
được hai lỗi thật, cả hai đều do **thiếu API công khai** ở đây:

1. ``fetch_account_balance`` luôn trả 0. ``get_balances(raw=False)`` trả
   ``DataFrame``; code kiểm ``isinstance(raw, list)`` / ``isinstance(raw, dict)``
   — ``DataFrame`` không thuộc loại nào nên rơi vào ``else: data = {}``. Đo:
   payload có ``cash: 5000000`` → ``{'cash': 0.0, 'stock_value': 0.0,
   'debt': 0.0, 'net_equity': 0.0}``.

2. Vòng retry là code chết. ``break`` ngay sau lần gọi đầu tiên không raise:
   ``market_type actually called: ['ALL']``.

Cách đúng không phải "thêm một vòng retry nữa" mà là:
* chuẩn hoá là **API công khai** một chỗ, nhận cả DataFrame lẫn list lẫn dict;
* đọc nhiều market là **tường minh**, có nhãn ``market_type`` trên mỗi dòng,
  và lỗi thì nổi lên chứ không bị nuốt.

Test ở đây khóa đúng hai điều đó.
"""
from __future__ import annotations

import pandas as pd
import pytest

from vnbroker.connector.dnse.client import DNSEClient
from vnbroker.connector.dnse.constants import MARKET_TYPES
from vnbroker.connector.dnse.core.errors import DNSEBaseError


# --- Chuẩn hoá là API công khai -------------------------------------------

def test_normalize_returns_a_dataframe_by_default():
    client = DNSEClient(api_key="k", api_secret="s")
    out = client.normalize_payload({"accounts": [{"accountNo": "1"}]})
    assert isinstance(out, pd.DataFrame)
    assert out.iloc[0]["accountNo"] == "1"


def test_normalize_can_return_records():
    """Đây là thứ vninvest đang tự chế lại (`_dataframe_to_records`)."""
    client = DNSEClient(api_key="k", api_secret="s")
    out = client.normalize_payload([{"a": 1}, {"a": 2}], as_records=True)
    assert out == [{"a": 1}, {"a": 2}]


def test_normalize_accepts_a_dataframe_without_touching_it():
    """Caller đã có DataFrame (từ ``raw=False``) thì không phải làm lại."""
    client = DNSEClient(api_key="k", api_secret="s")
    df = pd.DataFrame([{"a": 1}])
    out = client.normalize_payload(df, as_records=True)
    assert out == [{"a": 1}]


@pytest.mark.parametrize("empty", [None, [], {}])
def test_normalize_of_empty_gives_an_empty_dataframe_not_an_error(empty):
    client = DNSEClient(api_key="k", api_secret="s")
    out = client.normalize_payload(empty)
    assert isinstance(out, pd.DataFrame)
    assert out.empty


def test_records_of_a_dataframe_are_never_empty_but_a_dict_of_records():
    """Bẫy đã gặp ở vninvest: `to_dict("records")` lỗi -> nuốt -> `[]`.
    Ở đây phải cho lỗi nổi lên, không biến thành danh sách rỗng."""
    client = DNSEClient(api_key="k", api_secret="s")

    class Hostile(pd.DataFrame):
        def to_dict(self, *args, **kwargs):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        client.normalize_payload(Hostile({"a": [1]}), as_records=True)


# --- Đọc nhiều market: tường minh, có nhãn, lỗi thì nổi lên ---------------

class _PositionsStub(DNSEClient):
    """Ghi lại marketType thực sự được hỏi, trả DataFrame riêng cho từng market."""

    def __init__(self) -> None:
        super().__init__(api_key="k", api_secret="s")
        self.asked: list[str] = []

    def get_positions(self, account_no, market_type, dry_run=False, raw=False):
        self.asked.append(market_type)
        return pd.DataFrame([{"symbol": "ACB", "market_type": market_type}])


def test_all_markets_asks_every_supported_market():
    stub = _PositionsStub()
    stub.get_positions_all_markets("0123456789")
    assert sorted(stub.asked) == sorted(MARKET_TYPES)


def test_all_markets_labels_every_row_so_the_caller_cannot_mix_them_up():
    """Nguyên nhân gốc của vòng retry: người gọi không biết dòng nào thuộc
    market nào. Kết quả phải tự mang nhãn."""
    stub = _PositionsStub()
    out = stub.get_positions_all_markets("0123456789")
    assert set(out["market_type"]) == set(MARKET_TYPES)


def test_all_markets_defaults_to_the_documented_full_set():
    stub = _PositionsStub()
    out = stub.get_positions_all_markets("0123456789")
    # 1 dòng cho mỗi market (stub trả về 1 dòng mỗi lần)
    assert len(out) == len(MARKET_TYPES)


def test_all_markets_accepts_an_explicit_subset():
    stub = _PositionsStub()
    stub.get_positions_all_markets("0123456789", market_types=["STOCK"])
    assert stub.asked == ["STOCK"]


def test_all_markets_rejects_an_unknown_market_in_the_subset():
    """Đây chính là giá trị mà vninvest đang thử mù. Giờ nó bị chặn trước khi
    hỏi ai — kiểm trên ``error_code`` (bề mặt máy đọc được), không phải
    ``str(exc)``; convention của repo là tách hai thứ đó."""
    from vnbroker.connector.dnse.core.errors import DNSEValidationError

    stub = _PositionsStub()
    with pytest.raises(DNSEValidationError) as excinfo:
        stub.get_positions_all_markets("0123456789", market_types=["ALL"])
    assert excinfo.value.error_code == "INVALID_MARKET_TYPE"
    assert stub.asked == [], "phải chặn trước cả lần hỏi đầu tiên"


def test_all_markets_keeps_the_label_column_even_when_a_market_is_empty():
    """Một market không có dữ liệu không được làm mất cột nhãn — nếu không
    người gọi lại phải đoán lại từ đâu."""
    class PartialStub(_PositionsStub):
        def get_positions(self, account_no, market_type, dry_run=False, raw=False):
            self.asked.append(market_type)
            if market_type == "STOCK":
                return pd.DataFrame([{"symbol": "ACB", "market_type": market_type}])
            return pd.DataFrame()

    out = PartialStub().get_positions_all_markets("0123456789")
    assert "market_type" in out.columns
    assert list(out["market_type"]) == ["STOCK"]


def test_all_markets_propagates_a_failure_instead_of_returning_partial_data():
    """Fail-closed. Báo 'có 1 market lỗi' còn hơn trả bảng thiếu dữ liệu mà
    người đọc tưởng là đủ — đúng L-R01."""
    class FailingStub(_PositionsStub):
        def get_positions(self, account_no, market_type, dry_run=False, raw=False):
            self.asked.append(market_type)
            if market_type == "DERIVATIVE":
                raise DNSEBaseError("network down")
            return pd.DataFrame([{"symbol": "ACB", "market_type": market_type}])

    with pytest.raises(DNSEBaseError):
        FailingStub().get_positions_all_markets("0123456789")


# --- Cũng vậy cho lịch sử lệnh (thứ vninvest thật sự gọi) ------------------

class _HistoryStub(DNSEClient):
    def __init__(self) -> None:
        super().__init__(api_key="k", api_secret="s")
        self.asked: list[str] = []

    def get_order_history(self, account_no, market_type, from_date=None, to_date=None, **kw):
        self.asked.append(market_type)
        return pd.DataFrame([{"order_id": "1", "market_type": market_type}])


def test_order_history_all_markets_labels_rows():
    stub = _HistoryStub()
    out = stub.get_order_history_all_markets("0123456789", "2026-01-01", "2026-01-31")
    assert set(out["market_type"]) == set(MARKET_TYPES)
    assert sorted(stub.asked) == sorted(MARKET_TYPES)
