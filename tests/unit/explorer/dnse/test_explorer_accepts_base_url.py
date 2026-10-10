"""`DNSEQuote`/`DNSEListing` phải truyền tiếp `base_url` xuống `DNSEClient`.

Cả hai `__init__` nhận `**kwargs` nhưng **nuốt mất** — `DNSEClient` luôn được
dựng với `base_url` mặc định là production. Hệ quả: không tồn tại bất kỳ cách
nào chạy đường explorer trên sandbox (`https://sb-openapi.dnse.com.vn`), nên
tầng explorer **không kiểm chứng được** bằng dữ liệu thật.

Đo thật 2026-10-09: production timeout, còn sandbox trả 200. Không có
`base_url` thì lớp test không có chỗ nào để chứng minh code chạy được.
"""
from __future__ import annotations

import pytest

from vnbroker.explorer.dnse.listing import DNSEListing
from vnbroker.explorer.dnse.quote import DNSEQuote

SANDBOX = "https://sb-openapi.dnse.com.vn"
PRODUCTION = "https://openapi.dnse.com.vn"


def test_quote_defaults_to_production():
    q = DNSEQuote("MBS", api_key="k", api_secret="s")
    assert q._client._config.base_url == PRODUCTION


def test_quote_accepts_base_url():
    q = DNSEQuote("MBS", api_key="k", api_secret="s", base_url=SANDBOX)
    assert q._client._config.base_url == SANDBOX


def test_quote_accepts_base_url_via_kwargs():
    """Đường gọi thực tế của người dùng là keyword, phải đi qua **kwargs."""
    q = DNSEQuote("MBS", api_key="k", api_secret="s", **{"base_url": SANDBOX})
    assert q._client._config.base_url == SANDBOX


def test_listing_defaults_to_production():
    li = DNSEListing(api_key="k", api_secret="s")
    assert li._client._config.base_url == PRODUCTION


def test_listing_accepts_base_url():
    li = DNSEListing(api_key="k", api_secret="s", base_url=SANDBOX)
    assert li._client._config.base_url == SANDBOX


def test_timeout_is_forwarded_too():
    """base_url mà không timeout thì test lỗi mạng sẽ treo 30s mỗi lần."""
    q = DNSEQuote("MBS", api_key="k", api_secret="s", base_url=SANDBOX, timeout_seconds=5)
    assert q._client._config.timeout_seconds == 5


def test_api_version_can_be_pinned_by_the_caller():
    q = DNSEQuote("MBS", api_key="k", api_secret="s", api_version="2026-05-07")
    assert q._client._config.api_version == "2026-05-07"


def test_unknown_kwargs_still_do_not_crash():
    """Truoc day **kwargs bi nuot nen len sai; gio phai trong qua mot cach an toan."""
    q = DNSEQuote("MBS", api_key="k", api_secret="s", something_unknown=123)
    assert q.symbol == "MBS"


def test_market_service_still_reachable_after_the_change():
    """`self._market` được chặn từ `_client`; phải giữ nguyên."""
    q = DNSEQuote("MBS", api_key="k", api_secret="s", base_url=SANDBOX)
    assert q._market is q._client._market


@pytest.mark.parametrize(
    "cls, positional",
    [
        (DNSEQuote, ("MBS",)),  # Quote bắt buộc có symbol
        (DNSEListing, ()),
    ],
)
def test_both_classes_take_the_same_arguments(cls, positional):
    obj = cls(*positional, api_key="k", api_secret="s", base_url=SANDBOX)
    assert obj._client._config.base_url == SANDBOX