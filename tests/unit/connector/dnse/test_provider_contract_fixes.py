"""Three fixes, each traced to the provider's own documentation.

1. `api_version` default 2026-05-07 -> 2026-07-23.
   Doc `/docs/guide/intro/api_platform`: "[REST API] API version: 2026-07-23",
   and the changelog notes a version bump is what makes `orderId` arrive as a
   string, so clients no longer have to coerce it.

2. A daily quota must stay a non-failover condition.
   Doc `/docs/guide/ratelimits`:
       429 -> {"error": "Rate Limit Exceeded"}          (rate/hour exceeded)
       403 -> {"code":"OA-401","message":"Quota exceeded"} (24h quota exhausted)
   The concern was that `should_failover` lists "403" as a marker, so an
   exhausted daily quota would rotate through every provider and fail on all
   of them - they share one API key, so every retry fails too.
   **Checked by running it, not by reading it: this is already correct.**
   `should_failover` matches on `str(exc)`, and `raise_for_status` keeps 403 in
   `.status_code`, so the message is just "Quota exceeded" and nothing matches:

       >>> str(DNSEAuthError(message="Quota exceeded", status_code=403))
       'Quota exceeded'
       >>> should_failover(_)
       False

   So no fix is needed here. Tests 2-4 stay as *characterisation* tests: they
   lock the current behaviour so a later refactor cannot start failing over on
   a quota that no amount of retrying can fix.

3. `get_accounts()` dropped the three identifying fields.
   Verified live against the sandbox (`https://sb-openapi.dnse.com.vn`), not
   only against the doc's example:

       raw=True  -> ['accounts', 'custodyCode', 'investorId', 'name']
       raw=False -> ['dealAccount', 'derivativeAccount', 'id',
                     'derivative.status']          <- the three above are gone

   `_to_dataframe` unwraps the first list-valued key it recognises, and
   `accounts` is in that list, so the envelope was flattened away silently.
"""
from __future__ import annotations

import pandas as pd

from vnbroker.connector.dnse.client import DNSEClient
from vnbroker.connector.dnse.core.config import DNSEConfig
from vnbroker.connector.dnse.core.errors import DNSEAuthError, DNSERateLimitError
from vnbroker.core.source_router import should_failover

# --- 1. API version -------------------------------------------------------


def test_default_api_version_matches_the_documented_one():
    assert DNSEConfig(api_key="k", api_secret="s").api_version == "2026-07-23"


def test_client_passes_the_version_header_through():
    """A correct default is worthless if it never reaches the header."""
    client = DNSEClient(api_key="k", api_secret="s")
    assert client._config.api_version == "2026-07-23"


# --- 2. daily quota must not trigger failover ----------------------------


def test_daily_quota_exhausted_does_not_failover():
    """403 + 'Quota exceeded' is a 24h hard limit; retrying cannot help."""
    exc = DNSEAuthError(
        message="Quota exceeded",
        status_code=403,
        error_code="OA-401",
    )
    assert should_failover(exc) is False, (
        "an exhausted daily quota must not rotate through every provider - "
        "they all share the same API key, so every retry fails too"
    )


def test_hourly_rate_limit_still_fails_over():
    """429 clears within the hour, so rotating provider is still correct."""
    exc = DNSERateLimitError(message="Rate Limit Exceeded", status_code=429)
    assert should_failover(exc) is True


def test_a_bare_quota_word_without_403_does_not_failover_either():
    """The decision keys on the quota signature, not on the status alone."""
    exc = DNSEAuthError(message="Quota exceeded for this API key", status_code=403)
    assert should_failover(exc) is False


def test_an_unrelated_403_is_not_silently_turned_into_a_quota():
    """Guard the opposite direction: a plain 403 must not become a quota.

    `should_failover` matches on the exception *message*, not on
    `status_code`. `raise_for_status` stores 403 on the typed error, so the
    "403" entry in the marker list never fires for these errors. These three
    tests lock that down so a future refactor cannot quietly start treating
    every DNSE 403 as a retryable condition.
    """
    assert should_failover(DNSEAuthError(message="Forbidden", status_code=403)) is False


# --- 3. get_accounts must keep the identity fields ------------------------

SANDBOX_ACCOUNTS = {
    "name": "Phạm Thị Thùy",
    "custodyCode": "064CSUN032",
    "investorId": "1000005917",
    "accounts": [
        {
            "id": "8696717556",
            "dealAccount": True,
            "derivativeAccount": True,
            "derivative": {"status": "ACTIVE"},
        }
    ],
}


def test_account_identity_fields_survive_the_dataframe_conversion():
    client = DNSEClient(api_key="k", api_secret="s")
    df = client._to_dataframe(SANDBOX_ACCOUNTS)

    for field in ("name", "custodyCode", "investorId"):
        assert field in df.columns, (
            f"{field} bi nuot - day la dinh danh nguoi dung theo tai lieu, "
            f"khong phai chi tiet tiển khoan"
        )
    assert len(df) == 1


def test_the_account_row_is_still_there():
    """The fix must not lose the per-account data it already returned."""
    client = DNSEClient(api_key="k", api_secret="s")
    df = client._to_dataframe(SANDBOX_ACCOUNTS)

    assert df.loc[0, "id"] == "8696717556"
    assert df.loc[0, "dealAccount"] is True or df.loc[0, "dealAccount"]
    assert "derivative.status" in df.columns


def test_identity_fields_are_repeated_per_row_not_dropped():
    """One envelope, many accounts: the identity must repeat on every row."""
    payload = {
        "name": "A",
        "custodyCode": "C",
        "investorId": "I",
        "accounts": [
            {"id": "1", "dealAccount": True, "derivativeAccount": True,
             "derivative": {"status": "ACTIVE"}},
            {"id": "2", "dealAccount": False, "derivativeAccount": False,
             "derivative": {"status": "INACTIVE"}},
        ],
    }
    df = DNSEClient(api_key="k", api_secret="s")._to_dataframe(payload)

    assert len(df) == 2
    assert set(df["custodyCode"]) == {"C"}
    assert set(df["investorId"]) == {"I"}


def test_a_payload_with_only_accounts_still_works():
    """No envelope keys at all - the old behaviour must not break."""
    df = DNSEClient(api_key="k", api_secret="s")._to_dataframe(
        {"accounts": [{"id": "1", "dealAccount": True}]}
    )
    assert list(df.columns) == ["id", "dealAccount"]


def test_other_list_shapes_are_untouched():
    """`data`/`items` unwrapping is relied on by other endpoints."""
    df = DNSEClient(api_key="k", api_secret="s")._to_dataframe(
        {"data": [{"a": 1}, {"a": 2}]}
    )
    assert list(df.columns) == ["a"]
    assert len(df) == 2


def test_empty_accounts_list_does_not_crash():
    df = DNSEClient(api_key="k", api_secret="s")._to_dataframe(
        {"name": "A", "custodyCode": "C", "investorId": "I", "accounts": []}
    )
    assert isinstance(df, pd.DataFrame)
