from __future__ import annotations

from unittest.mock import MagicMock, patch

from vnbroker.common.client import Vnbroker
from vnbroker.api.quote import Quote as QuoteAdapter
from vnbroker.api.listing import Listing as ListingAdapter
from vnbroker.api.company import Company as CompanyAdapter
from vnbroker.api.financial import Finance as FinanceAdapter


def _mock_dnse_client() -> MagicMock:
    client = MagicMock()
    client._market = MagicMock()
    return client


def test_public_adapters_support_dnse(monkeypatch):
    monkeypatch.setenv("DNSE_API_KEY", "key")
    monkeypatch.setenv("DNSE_API_SECRET", "secret")

    with patch("vnbroker.connector.dnse.client.DNSEClient") as mock_cls:
        mock_cls.return_value = _mock_dnse_client()

        quote = QuoteAdapter(source="dnse", symbol="VNM", api_key="key", api_secret="secret")
        listing = ListingAdapter(source="dnse", api_key="key", api_secret="secret")
        company = CompanyAdapter(source="dnse", symbol="VNM", api_key="key", api_secret="secret")
        finance = FinanceAdapter(source="dnse", symbol="VNM", api_key="key", api_secret="secret")

    assert type(quote.provider).__name__ == "DNSEQuote"
    assert type(listing.provider).__name__ == "DNSEListing"
    assert type(company.provider).__name__ == "DNSECompany"
    assert type(finance.provider).__name__ == "DNSEFinance"


def test_vnbroker_stock_supports_dnse(monkeypatch):
    monkeypatch.setenv("DNSE_API_KEY", "key")
    monkeypatch.setenv("DNSE_API_SECRET", "secret")

    with patch("vnbroker.connector.dnse.client.DNSEClient") as mock_cls:
        mock_cls.return_value = _mock_dnse_client()

        stock = Vnbroker(show_log=False).stock(
            "VNM",
            source="DNSE",
            api_key="key",
            api_secret="secret",
        )

    assert type(stock.quote.data_source).__name__ == "DNSEQuote"
    assert type(stock.listing.data_source).__name__ == "DNSEListing"
    # Company and Finance should now be initialized (not None) for DNSE
    assert stock.company is not None
    assert stock.finance is not None
    # Company and Finance components use API adapters, so check the provider attribute
    assert type(stock.company.data_source.provider).__name__ == "DNSECompany"
    assert type(stock.finance.data_source.provider).__name__ == "DNSEFinance"