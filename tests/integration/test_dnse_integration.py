"""Integration tests for DNSE client.

These tests require DNSE credentials in environment variables.
"""

from __future__ import annotations

import os

import pytest

from vnstock.connector.dnse.client import DNSEClient


_REQUIRED_ENV = ["DNSE_API_KEY", "DNSE_API_SECRET", "DNSE_ACCOUNT_NO"]


def _missing_env() -> list[str]:
    return [key for key in _REQUIRED_ENV if not os.getenv(key)]


@pytest.mark.integration
@pytest.mark.smoke
class TestDNSEIntegration:
    @pytest.fixture(scope="class")
    def client(self):
        missing = _missing_env()
        if missing:
            pytest.skip(f"Missing DNSE env vars: {', '.join(missing)}")
        return DNSEClient(
            api_key=os.getenv("DNSE_API_KEY", ""),
            api_secret=os.getenv("DNSE_API_SECRET", ""),
            base_url=os.getenv("DNSE_BASE_URL", "https://openapi.dnse.com.vn"),
            show_log=False,
        )

    @pytest.fixture(scope="class")
    def account_no(self) -> str:
        return os.getenv("DNSE_ACCOUNT_NO", "")

    def test_get_accounts_raw(self, client: DNSEClient):
        payload = client.get_accounts(raw=True)
        assert payload is not None

    def test_get_balances_raw(self, client: DNSEClient, account_no: str):
        payload = client.get_balances(account_no=account_no, raw=True)
        assert payload is not None

    def test_market_read_raw(self, client: DNSEClient):
        payload = client.get_security_definition(symbol="HPG", raw=True)
        assert payload is not None

    def test_order_book_raw(self, client: DNSEClient, account_no: str):
        payload = client.get_orders(
            account_no=account_no,
            market_type=os.getenv("DNSE_MARKET_TYPE", "STOCK"),
            raw=True,
        )
        assert payload is not None
