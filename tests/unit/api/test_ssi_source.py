"""Unit tests for lane api/ with source="ssi" (AC-W1.3, offline, no network)."""

from __future__ import annotations

import pytest

from vnbroker.api.company import Company
from vnbroker.api.financial import Finance
from vnbroker.api.listing import Listing
from vnbroker.api.news import News
from vnbroker.api.quote import Quote
from vnbroker.api.trading import Trading
from vnbroker.core.types import DataSource
from vnbroker.explorer.ssi.company import SSICompany
from vnbroker.explorer.ssi.financial import SSIFinancial
from vnbroker.explorer.ssi.listing import SSIListing
from vnbroker.explorer.ssi.news import SSINews
from vnbroker.explorer.ssi.quote import SSIQuote
from vnbroker.explorer.ssi.trading import SSITrading

_KEYS = {"api_key": "test-ssi-key", "api_secret": "test-ssi-secret"}


class TestSSIApiGate:
    """AC-W1.3(b): DataSource gate includes ssi."""

    def test_datasource_includes_ssi(self) -> None:
        assert "ssi" in DataSource.all_sources()


class TestSSIApiAdapters:
    """AC-W1.3(c): adapters accept source=ssi and wire the SSI provider."""

    def test_quote(self) -> None:
        q = Quote(source="ssi", symbol="ACB", show_log=False, **_KEYS)
        assert isinstance(q.provider, SSIQuote)

    def test_company(self) -> None:
        c = Company(source="ssi", symbol="ACB", show_log=False, **_KEYS)
        assert isinstance(c.provider, SSICompany)

    def test_financial(self) -> None:
        f = Finance(source="ssi", symbol="ACB", show_log=False, **_KEYS)
        assert isinstance(f.provider, SSIFinancial)

    def test_listing(self) -> None:
        lst = Listing(source="ssi", show_log=False, **_KEYS)
        assert isinstance(lst.provider, SSIListing)

    def test_trading(self) -> None:
        t = Trading(source="ssi", symbol="ACB", show_log=False, **_KEYS)
        assert isinstance(t.provider, SSITrading)

    def test_news(self) -> None:
        n = News(source="ssi", symbol="ACB", show_log=False, **_KEYS)
        assert isinstance(n.provider, SSINews)

    def test_invalid_source_still_rejected(self) -> None:
        with pytest.raises(ValueError):
            Quote(source="nope", symbol="ACB", show_log=False)
