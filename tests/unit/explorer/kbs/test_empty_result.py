"""HANG1 S4 — provider lỗi phải ném, không trả frame rỗng có cột (BL-6).

Trên base pre-S4, `explorer/kbs/listing.py` nuốt mọi exception thành
`pd.DataFrame(columns=[...])` — frame CÓ cột nên `_is_unusable_provider_result`
coi là dùng được ⇒ `record_success` + cache 24h. Không test nào gọi mạng.
"""

import pandas as pd
import pytest
import requests

from vnbroker.common.data import EmptyProviderResult, _is_unusable_provider_result
from vnbroker.core.utils.cache import get_listing_cache
from vnbroker.explorer.kbs.listing import Listing as KBSListing
from vnbroker.explorer.kbs.trading import Trading as KBSTrading
from vnbroker.explorer.vci.quote import Quote as VCIQuote


@pytest.fixture(autouse=True)
def _clean_listing_cache():
    cache = get_listing_cache()
    cache.clear()
    yield
    cache.clear()


def _kbs_listing():
    return KBSListing(show_log=False)


# ------------------------------------------------------- kbs/listing.py


def test_all_symbols_reraises_transport_error(monkeypatch):
    """Lỗi transport phải nổi lên nguyên dạng (để failover/retry nhìn thấy)."""
    lst = _kbs_listing()

    def boom(**kw):
        raise ConnectionError("KBS down")

    monkeypatch.setattr(lst, "_get_full_stock_data", boom)

    with pytest.raises(ConnectionError):
        lst.all_symbols()


def test_all_symbols_empty_payload_is_unusable(monkeypatch):
    """API trả rỗng cho full listing ⇒ EmptyProviderResult, không frame rỗng."""
    lst = _kbs_listing()
    monkeypatch.setattr(lst, "_get_full_stock_data", lambda **kw: [])

    with pytest.raises(EmptyProviderResult):
        lst.all_symbols()


def test_symbols_by_exchange_reraises_transport_error(monkeypatch):
    lst = _kbs_listing()

    def boom(**kw):
        raise ConnectionError("KBS down")

    monkeypatch.setattr(lst, "_get_full_stock_data", boom)

    with pytest.raises(ConnectionError):
        lst.symbols_by_exchange()


def test_symbols_by_exchange_empty_payload_is_unusable(monkeypatch):
    lst = _kbs_listing()
    monkeypatch.setattr(lst, "_get_full_stock_data", lambda **kw: [])

    with pytest.raises(EmptyProviderResult):
        lst.symbols_by_exchange()


def test_symbols_by_industries_error_is_not_cached_as_success(monkeypatch):
    """Ngành lỗi ⇒ ném ra, không frame rỗng có cột để cache 24h."""
    lst = _kbs_listing()

    def boom(**kw):
        raise ConnectionError("KBS down")

    monkeypatch.setattr(lst, "_get_industries_internal", boom)

    with pytest.raises(ConnectionError):
        lst.symbols_by_industries()


def test_symbols_by_industries_all_failed_is_unusable(monkeypatch):
    """Mọi ngành đều lỗi ⇒ aggregate rỗng là lỗi, không phải đáp án rỗng."""
    lst = _kbs_listing()
    monkeypatch.setattr(lst, "_get_industries_internal", lambda **kw: [])
    monkeypatch.setattr(lst, "_get_symbols_by_industry_internal", lambda **kw: [])

    with pytest.raises(EmptyProviderResult):
        lst.symbols_by_industries()


# ------------------------------------------------------- kbs/trading.py


def _kbs_trading():
    return KBSTrading(symbol="ACB", show_log=False)


class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code not in (200, 201):
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_price_board_non_200_raises(monkeypatch):
    """429/500 ở bảng giá phải ném (để failover nhìn thấy), không frame rỗng."""
    trading = _kbs_trading()
    monkeypatch.setattr("requests.post", lambda *a, **k: _Resp(500, []))

    with pytest.raises(requests.HTTPError):
        trading._fetch_stock_board(["ACB"])


def test_price_board_exception_reraises(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("net down")

    monkeypatch.setattr("requests.post", boom)

    with pytest.raises(ConnectionError):
        _kbs_trading()._fetch_stock_board(["ACB"])


def test_price_board_empty_payload_is_unusable(monkeypatch):
    """200 + body rỗng cho bảng giá ⇒ EmptyProviderResult."""
    monkeypatch.setattr("requests.post", lambda *a, **k: _Resp(200, []))

    with pytest.raises(EmptyProviderResult):
        _kbs_trading()._fetch_stock_board(["ACB"])


# ------------------------------------------------------- vci/quote.py


def test_vci_malformed_ohlc_raises():
    """Payload hỏng (không phải lỗi mạng) phải ném ra, không thành frame rỗng."""
    bad = [{"o": [1.0], "t": 5, "h": [], "l": [], "c": [], "v": []}]

    with pytest.raises(TypeError):
        VCIQuote._normalize_ohlc_response(bad)


# ------------------------------------------------------- khóa hợp đồng rỗng


def test_holiday_shaped_frame_stays_usable():
    """Khóa AC S4: frame rỗng CÓ cột (ngày nghỉ) vẫn là đáp án dùng được."""
    df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    assert _is_unusable_provider_result(df) is False


def test_columnless_frame_stays_unusable():
    assert _is_unusable_provider_result(pd.DataFrame()) is True
    assert _is_unusable_provider_result(None) is True
