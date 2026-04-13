import pytest

from vnstock.connector.dnse.trade import Trade


def test_trade_bridge_requires_openapi_credentials_for_new_methods():
    trade = Trade()
    with pytest.raises(ValueError):
        trade.get_accounts(dry_run=True, raw=True)


def test_trade_bridge_get_accounts_dry_run_works_with_credentials():
    trade = Trade(api_key="k", api_secret="s")
    payload = trade.get_accounts(dry_run=True, raw=True)
    assert payload["method"] == "GET"
    assert payload["url"].endswith("/accounts")
