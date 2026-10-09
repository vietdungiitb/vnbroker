"""`price_depth()` không được trả DataFrame rỗng thay vì báo lỗi.

Đo thật trên production (2026-10-09), `openapi.dnse.com.vn` không thông:

    DNSEQuote("MBS").history()      -> ConnectionError (ném lên)      OK
    DNSEQuote("MBS").price_depth()  -> shape=(0, 0), cols=[]           SAI

Lỗi mạng biến thành "hôm nay không có dữ liệu". Người dùng đọc `len(df) == 0`
rồi kết luận thị trường đóng, trong khi thật ra DNSE không trả lời.

`common/data.py:442` đã định nghĩa đúng ranh giới: **0 cột** là kết quả không
dùng được, còn **0 dòng nhưng đủ cột** là ngày nghỉ hợp lệ. `price_depth` trả
frame không cột, tức rơi vào nhóm đầu — nhưng lại đi vòng qua cơ chế đó bằng
cách nuốt lỗi tại chỗ.
"""
from __future__ import annotations

import pandas as pd
import pytest

from vnbroker.common.data import EmptyProviderResult
from vnbroker.connector.dnse.core.errors import DNSEBaseError
from vnbroker.explorer.dnse.quote import DNSEQuote


def _quote(monkeypatch, market) -> DNSEQuote:
    q = DNSEQuote("MBS", api_key="k", api_secret="s")
    monkeypatch.setattr(q, "_market", market, raising=False)
    return q


class _Market:
    def __init__(self, exc=None, body=None):
        self._exc = exc
        self._body = body

    def get_security_definition(self, **kwargs):
        if self._exc is not None:
            raise self._exc
        return 200, self._body


# --- lỗi vận chuyển phải nổi lên, không bị nuốt ---------------------------


def test_network_error_is_not_swallowed(monkeypatch):
    q = _quote(monkeypatch, _Market(exc=OSError("Connection reset by peer")))

    with pytest.raises(OSError):
        q.price_depth()


def test_dnse_transport_error_is_not_swallowed(monkeypatch):
    """Lỗi DNSE ném ra rồi thì phải giữ nguyên, không đổi thành DataFrame rỗng."""
    q = _quote(monkeypatch, _Market(exc=DNSEBaseError(message="Read timed out")))

    with pytest.raises(DNSEBaseError):
        q.price_depth()


def test_auth_error_must_not_look_like_no_data(monkeypatch):
    """403 hết quota là lỗi, tuyệt đối không phải 'không có giao dịch'."""
    q = _quote(monkeypatch, _Market(exc=DNSEBaseError(message="Quota exceeded")))

    with pytest.raises(DNSEBaseError):
        q.price_depth()


# --- provider trả về rỗng thì báo rõ, không trả frame 0 cột ----------------


def test_empty_body_raises_empty_provider_result(monkeypatch):
    q = _quote(monkeypatch, _Market(body=None))

    with pytest.raises(EmptyProviderResult):
        q.price_depth()


def test_never_returns_a_zero_column_frame(monkeypatch):
    """Đây là hợp đồng quan trọng nhất: không có đường nào trả frame không cột."""
    for market in (
        _Market(body=None),
        _Market(exc=OSError("boom")),
        _Market(body={}),
        _Market(body="raw text"),
        _Market(body=42),
    ):
        q = _quote(monkeypatch, market)
        with pytest.raises((EmptyProviderResult, Exception)) as exc:
            df = q.price_depth()
            assert list(df.columns), "tra ve DataFrame khong co cot"
        assert not isinstance(exc.value, AssertionError), (
            f"price_depth tra DataFrame khong co cot thay vi nem loi: {market!r}"
        )


# --- dữ liệu thật thì vẫn trả về bình thường ------------------------------


def test_a_real_body_still_returns_a_frame(monkeypatch):
    body = {"symbol": "MBS", "boardId": "HOSE", "basicPrice": 17500}
    q = _quote(monkeypatch, _Market(body=body))

    df = q.price_depth()

    assert isinstance(df, pd.DataFrame)
    assert "symbol" in df.columns


def test_a_list_body_still_returns_a_frame(monkeypatch):
    q = _quote(monkeypatch, _Market(body=[{"symbol": "MBS"}]))

    df = q.price_depth()

    assert isinstance(df, pd.DataFrame)
    assert "symbol" in df.columns