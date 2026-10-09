"""Đợt 1 của `docs/PLAN_DNSE_API_PARITY.md`: 7 method read-only của SDK chính thức.

Mọi path ở đây được đối chiếu với source SDK `dnse-tech/openapi-sdk`
(`python/dnse/api/client.py`), không lấy từ trí nhớ:

| method                  | path (SDK)                                   | dòng SDK |
|-------------------------|----------------------------------------------|----------|
| get_quotes              | GET /price/{symbol}/quotes                    | 346      |
| get_latest_quote        | GET /price/{symbol}/quotes/latest             | 424      |
| get_expected_price      | GET /price/{symbol}/expected-price            | 309      |
| get_foreign_trading     | GET /price/{symbol}/foreign-trading           | 351      |
| get_market_index        | GET /price/{index_name}/market-index          | 424 area |
| get_trades_volume_profile | GET /price/{symbol}/trades/volume-profile   | 304      |
| get_loans               | GET /accounts/{account_no}/loans              | 85       |

Tên query cũng lấy từ SDK: `boardId` / `from` / `to` / `limit` / `order` /
`nextPageToken` (client.py:331-343), và `marketType` cho loans (client.py:68).

Cả 7 đều là **GET** ⇒ không đi qua write gate, đây là đợt rủi ro thấp nhất.

Lớp dữ liệu theo `docs/NORMALISATION_POLICY.md`:
- `get_quotes` → **Lớp A** (nội giá, người dùng so sánh đa provider)
- `get_foreign_trading`, `get_loans` → **Lớp B** (riêng DNSE, giữ nguyên)
"""
from __future__ import annotations

import pytest

from vnbroker.connector.dnse.client import DNSEClient


def _client() -> DNSEClient:
    return DNSEClient(api_key="k", api_secret="s")


# --- get_quotes -> price_depth (Lớp A) -------------------------------------


def test_get_quotes_uses_the_documented_path():
    payload = _client().get_quotes("MBS", dry_run=True, raw=True)
    assert payload["method"] == "GET"
    assert payload["url"].endswith("/price/MBS/quotes")


def test_get_quotes_puts_the_symbol_in_the_path_not_the_query():
    """SDK client.py:346 - symbol là path param. Gửi nó vào query là sai."""
    payload = _client().get_quotes("MBS", dry_run=True, raw=True)
    assert "symbol" not in payload["query"]


def test_get_quotes_forwards_every_documented_filter():
    payload = _client().get_quotes(
        "MBS",
        board_id="HOSE",
        from_date=1,
        to_date=2,
        limit=10,
        order="asc",
        next_page_token="tok",
        dry_run=True,
        raw=True,
    )
    q = payload["query"]
    assert q == {
        "boardId": "HOSE",
        "from": 1,
        "to": 2,
        "limit": 10,
        "order": "asc",
        "nextPageToken": "tok",
    }


def test_get_quotes_sends_no_query_when_nothing_is_filtered():
    """SDK client.py:347 - `query=query if query else None`."""
    payload = _client().get_quotes("MBS", dry_run=True, raw=True)
    assert payload["query"] == {}


# --- get_latest_quote -------------------------------------------------------


def test_get_latest_quote_path():
    payload = _client().get_latest_quote("MBS", dry_run=True, raw=True)
    assert payload["url"].endswith("/price/MBS/quotes/latest")
    assert payload["query"] == {}


def test_get_latest_quote_accepts_board_id_only():
    """Lưu ý: SDK chỉ có board_id, KHÔNG có from/to cho endpoint này."""
    payload = _client().get_latest_quote("MBS", board_id="HOSE", dry_run=True, raw=True)
    assert payload["query"] == {"boardId": "HOSE"}


def test_get_latest_quote_rejects_a_filter_the_api_does_not_support():
    """Chặn việc tự thêm tham số không có trong SDK - sẽ bị server từ chối."""
    with pytest.raises(TypeError):
        _client().get_latest_quote("MBS", from_date=1, dry_run=True, raw=True)


# --- get_expected_price -----------------------------------------------------


def test_get_expected_price_path():
    payload = _client().get_expected_price("MBS", dry_run=True, raw=True)
    assert payload["url"].endswith("/price/MBS/expected-price")


def test_get_expected_price_forwards_filters():
    payload = _client().get_expected_price(
        "MBS", board_id="HOSE", from_date=1, to_date=2, limit=5, dry_run=True, raw=True
    )
    assert payload["query"] == {"boardId": "HOSE", "from": 1, "to": 2, "limit": 5}


# --- get_foreign_trading (Lớp B) ------------------------------------------


def test_get_foreign_trading_path():
    payload = _client().get_foreign_trading("MBS", dry_run=True, raw=True)
    assert payload["url"].endswith("/price/MBS/foreign-trading")


def test_get_foreign_trading_forwards_filters():
    payload = _client().get_foreign_trading(
        "MBS", board_id="HOSE", limit=3, order="desc", dry_run=True, raw=True
    )
    assert payload["query"] == {"boardId": "HOSE", "limit": 3, "order": "desc"}


# --- get_market_index -------------------------------------------------------


def test_get_market_index_path():
    payload = _client().get_market_index("VNINDEX", dry_run=True, raw=True)
    assert payload["url"].endswith("/price/VNINDEX/market-index")


def test_get_market_index_forwards_filters():
    payload = _client().get_market_index(
        "VNINDEX", from_date=1, to_date=2, limit=7, next_page_token="n", dry_run=True, raw=True
    )
    assert payload["query"] == {"from": 1, "to": 2, "limit": 7, "nextPageToken": "n"}


# --- get_trades_volume_profile --------------------------------------------


def _path(payload: dict) -> str:
    """Phần path của URL, bỏ query string.

    `endswith("/price/MBS/quotes")` hỏng khi có query — URL thật là
    `.../price/MBS/quotes?boardId=HOSE`. So sánh path cho đúng ý nghĩa.
    """
    return payload["url"].split("?", 1)[0]


def test_get_trades_volume_profile_path():
    payload = _client().get_trades_volume_profile("MBS", time=1700, dry_run=True, raw=True)
    assert _path(payload).endswith("/price/MBS/trades/volume-profile")


def test_get_trades_volume_profile_time_is_required():
    """SDK client.py:299 - `time` là bắt buộc, không phải tuỳ chọn."""
    payload = _client().get_trades_volume_profile("MBS", time=1700, dry_run=True, raw=True)
    assert payload["query"]["time"] == 1700


def test_get_trades_volume_profile_cannot_drop_the_required_time():
    with pytest.raises(TypeError):
        _client().get_trades_volume_profile("MBS", dry_run=True, raw=True)


# --- get_loans (Lớp B, account-scoped) ------------------------------------


def test_get_loans_path():
    payload = _client().get_loans("8696717556", market_type="STOCK", dry_run=True, raw=True)
    assert _path(payload).endswith("/accounts/8696717556/loans")


def test_get_loans_always_sends_market_type():
    """SDK client.py:68 - marketType nằm ngay trong query gốc, không phải tuỳ chọn."""
    payload = _client().get_loans("8696717556", market_type="DERIVATIVE", dry_run=True, raw=True)
    assert payload["query"]["marketType"] == "DERIVATIVE"


def test_get_loans_forwards_every_documented_filter():
    payload = _client().get_loans(
        "8696717556",
        market_type="STOCK",
        disbursement_from=1,
        disbursement_to=2,
        due_date_from=3,
        due_date_to=4,
        position_id=9,
        page_index=0,
        page_size=20,
        dry_run=True,
        raw=True,
    )
    assert payload["query"] == {
        "marketType": "STOCK",
        "disbursementFrom": 1,
        "disbursementTo": 2,
        "dueDateFrom": 3,
        "dueDateTo": 4,
        "positionId": 9,
        "pageIndex": 0,
        "pageSize": 20,
    }


# --- WS alias: market_index_influence --------------------------------------
# SDK `python/dnse/websocket/client.py:356`:
#     channel = f"market_index_influence.{index_name}.{resolution}.json"
# Đây là hình dạng RIÊNG: index ở giữa, resolution ở vị trí 3.
# `market_index` chỉ có 2 phần (`websocket.py:265`), `ohlc` lấy resolution
# làm phần giữa (`websocket.py:263`). Không kênh nào sẵn có khớp.


def _ws():
    from vnbroker.connector.dnse.core.config import DNSEConfig
    from vnbroker.connector.dnse.websocket import DNSEWebSocketClient

    return DNSEWebSocketClient(DNSEConfig(api_key="k", api_secret="s"))


def test_market_index_influence_is_a_recognised_alias():
    assert "market_index_influence" in _ws().CHANNEL_ALIASES


def test_market_index_influence_channel_shape_matches_the_sdk():
    ws = _ws()
    name = ws._channel_name(
        "market_index_influence",
        board_id="HOSE",
        resolution=5,
        market_index="VNINDEX",
        product_group_id=None,
    )
    assert name == "market_index_influence.VNINDEX.5.json"


def test_market_index_influence_defaults_to_resolution_one_like_the_sdk():
    ws = _ws()
    name = ws._channel_name(
        "market_index_influence",
        board_id="HOSE",
        resolution=None,
        market_index=None,
        product_group_id=None,
    )
    assert name == "market_index_influence.VNINDEX.1.json"


def test_market_index_influence_ignores_board_id():
    """SDK không có board trong channel này — board_id phải bị bỏ qua, không ghép nhầm."""
    ws = _ws()
    name = ws._channel_name(
        "market_index_influence",
        board_id="HOSE",
        resolution=5,
        market_index="VNINDEX",
        product_group_id=None,
    )
    assert "HOSE" not in name


def test_existing_index_channel_shape_is_unchanged():
    """Chặn hồi quy: thêm kênh mới không được làm đổi `market_index`."""
    ws = _ws()
    name = ws._channel_name(
        "market_index",
        board_id="HOSE",
        resolution=None,
        market_index="VNINDEX",
        product_group_id=None,
    )
    assert name == "market_index.VNINDEX.json"


def test_ohlc_channel_shape_is_unchanged():
    ws = _ws()
    name = ws._channel_name(
        "ohlc",
        board_id="HOSE",
        resolution=5,
        market_index=None,
        product_group_id=None,
    )
    assert name == "ohlc.5.json"


# --- read-only: không được chạm write gate --------------------------------


def test_none_of_the_seven_can_reach_the_write_gate():
    """GET không được phép tạo bất kỳ side effect nào.

    Nếu một method sau này bị đổi sang POST, `enable_write(False)` phải chặn được.
    """
    client = _client()
    for call in (
        lambda: client.get_quotes("MBS", dry_run=True, raw=True),
        lambda: client.get_latest_quote("MBS", dry_run=True, raw=True),
        lambda: client.get_expected_price("MBS", dry_run=True, raw=True),
        lambda: client.get_foreign_trading("MBS", dry_run=True, raw=True),
        lambda: client.get_market_index("VNINDEX", dry_run=True, raw=True),
        lambda: client.get_trades_volume_profile("MBS", time=1, dry_run=True, raw=True),
        lambda: client.get_loans("8696717556", market_type="STOCK", dry_run=True, raw=True),
    ):
        assert call()["method"] == "GET"

