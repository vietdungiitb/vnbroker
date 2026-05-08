from vnbroker.connector.dnse.client import DNSEClient


def _make_client() -> DNSEClient:
    return DNSEClient(api_key="k", api_secret="s")


def test_get_accounts_dry_run_raw_returns_debug_payload():
    client = _make_client()
    payload = client.get_accounts(dry_run=True, raw=True)

    assert payload["method"] == "GET"
    assert payload["url"].endswith("/accounts")
    assert payload["query"] == {}


def test_get_accounts_dry_run_dataframe_mode_returns_dataframe():
    client = _make_client()
    df = client.get_accounts(dry_run=True, raw=False)

    assert "method" in df.columns
    assert df.iloc[0]["method"] == "GET"
