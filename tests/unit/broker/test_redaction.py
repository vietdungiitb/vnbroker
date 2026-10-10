"""Credential-leak tests for the Redactor and the DNSE dry-run envelope.

Proven leaks at baseline (measured by calling the functions, not by reading):

  Redactor.redact_url('...?api_key=AKIA123&X-Signature=deadbeef&foo=1')
    -> '...api_key=REDACTED&X-Signature=deadbeef&foo=1'      X-Signature survived
  Redactor.redact_headers({'Trading-Token':'SECRET','X-Api-Key':'AKIA',
                           'smart-otp':'1234','authorization':'Bearer x'})
    -> only `authorization` was masked
  Redactor.redact_dict({'api-key':'SECRET', ...})
    -> `api-key` survived

  DNSE dry-run envelope: only `trading-token` was masked, so `X-Signature` and
  `x-api-key` - transmitted on every request - appeared verbatim.

Root cause was structural: the key set stored hyphenated entries while the
lookup normalised `-` to `_`, so those entries could never match, and
`redact_dict`/`redact_headers` bypassed the shared matcher entirely.
"""
from __future__ import annotations

import pytest

from vnbroker.broker.security.redaction import (
    SENSITIVE_KEYS,
    Redactor,
    _is_sensitive_key,
)


# ---------- the set itself must be self-consistent ----------
def test_every_declared_key_actually_matches():
    """Guards the original defect: an entry written in a form the lookup can
    never produce is silently dead forever."""
    dead = [k for k in SENSITIVE_KEYS if not _is_sensitive_key(k)]
    assert not dead, (
        f"these declared sensitive keys can never match: {dead}"
    )


def test_written_form_matches_lookup_form():
    """A key may be spelled with hyphens, spaces or caps; all must match."""
    for spelling in (
        "x-api-key", "X-API-KEY", "x_api_key", "X Api Key",
        "x-signature", "X-Signature", "trading-token", "Trading-Token",
        "smart-otp", "api-key", "api_key",
    ):
        assert _is_sensitive_key(spelling), f"{spelling!r} not treated as sensitive"


# ---------- the four measured leaks ----------
def test_signature_in_url_is_masked():
    url = Redactor.redact_url(
        "https://api.dnse.com.vn/ws?api_key=AKIA123&X-Signature=deadbeef&foo=1"
    )
    assert "deadbeef" not in url, f"X-Signature leaked: {url}"
    assert "AKIA123" not in url, f"api_key leaked: {url}"
    assert "foo=1" in url, "non-sensitive params must survive redaction"


def test_sensitive_headers_are_masked():
    out = Redactor.redact_headers(
        {
            "Trading-Token": "SECRET",
            "X-Api-Key": "AKIA",
            "X-Signature": "deadbeef",
            "smart-otp": "1234",
            "authorization": "Bearer x",
            "Content-Type": "application/json",
        }
    )
    for header in ("Trading-Token", "X-Api-Key", "X-Signature", "smart-otp",
                   "authorization"):
        assert out[header] == Redactor.REDACTED, f"{header} not masked: {out[header]}"
    assert out["Content-Type"] == "application/json", "harmless header was altered"


def test_dash_key_in_dict_is_masked():
    out = Redactor.redact_dict(
        {"api-key": "SECRET", "x-api-key": "AKIA", "api_key": "OK", "symbol": "ACB"}
    )
    assert out["api-key"] == Redactor.REDACTED
    assert out["x-api-key"] == Redactor.REDACTED
    assert out["api_key"] == Redactor.REDACTED
    assert out["symbol"] == "ACB", "business field must survive"


def test_dict_and_headers_agree_on_the_same_key():
    """The three entry points must not disagree with each other."""
    for key in ("x-api-key", "api-key", "api_key", "X-Signature", "otp"):
        in_dict = Redactor.redact_dict({key: "V"})[key]
        in_headers = Redactor.redact_headers({key: "V"})[key]
        in_url = "REDACTED" in Redactor.redact_url(f"https://h/p?{key}=V")
        assert in_dict == Redactor.REDACTED, key
        assert in_headers == Redactor.REDACTED, key
        assert in_url, key


def test_nested_and_listed_dicts_are_still_redacted():
    payload = {
        "outer": {"api-key": "S", "keep": 1},
        "items": [{"trading-token": "T", "n": 2}],
    }
    out = Redactor.redact_dict(payload)
    assert out["outer"]["api-key"] == Redactor.REDACTED
    assert out["outer"]["keep"] == 1
    assert out["items"][0]["trading-token"] == Redactor.REDACTED
    assert out["items"][0]["n"] == 2
    assert payload["outer"]["api-key"] == "S", "the original dict was mutated"


def test_caller_supplied_key_set_is_normalised():
    """A caller writing `{"X-Custom-Secret"}` must still work."""
    out = Redactor.redact_dict({"X-Custom-Secret": "v", "x_custom_secret": "v2"},
                               keys={"X-Custom-Secret"})
    assert out["X-Custom-Secret"] == Redactor.REDACTED
    assert out["x_custom_secret"] == Redactor.REDACTED


# ---------- the DNSE dry-run envelope ----------
@pytest.fixture
def dry_run_client():
    from vnbroker.connector.dnse.core.config import DNSEConfig
    from vnbroker.connector.dnse.core.http_client import DNSEHttpClient

    return DNSEHttpClient(
        DNSEConfig(
            api_key="REAL_API_KEY",
            api_secret="REAL_API_SECRET",
            base_url="https://blocked.invalid",
            show_log=False,
        )
    )


def test_dry_run_envelope_contains_no_transmitted_credential(dry_run_client):
    from vnbroker.connector.dnse.core.signature import build_signature_header

    date_value, signature = build_signature_header(
        api_key="REAL_API_KEY",
        api_secret="REAL_API_SECRET",
        method="POST",
        path="/accounts/orders",
    )
    # what the client would really transmit. The version is read from the
    # config rather than hardcoded: this test is about masking, and pinning the
    # string here only made it fail on every legitimate DNSE version bump.
    transmitted = {
        "X-Aux-Date": date_value,
        "X-Signature": signature,
        "x-api-key": "REAL_API_KEY",
        "version": dry_run_client._config.api_version,
        "trading-token": "REAL_TRADING_TOKEN",
    }

    _, envelope = dry_run_client.request(
        "POST",
        "/accounts/orders?apiKey=REAL_API_KEY&signature=" + signature,
        query={"marketType": "STOCK"},
        body={"accountNo": "0123456789", "symbol": "ACB"},
        headers={"trading-token": "REAL_TRADING_TOKEN"},
        dry_run=True,
    )

    # every transmitted header must survive into the envelope by name...
    for header in transmitted:
        assert header in envelope["headers"], f"{header} vanished from the envelope"

    # ...and every transmitted credential must be masked
    for header in ("X-Signature", "x-api-key", "trading-token"):
        assert envelope["headers"][header] == Redactor.REDACTED, (
            f"{header} passed through unmasked: {envelope['headers'][header]}"
        )

    # non-credential headers stay readable, otherwise the envelope is useless
    assert envelope["headers"]["version"] == transmitted["version"]
    assert envelope["headers"]["X-Aux-Date"] == transmitted["X-Aux-Date"]

    blob = repr(envelope)
    for secret in ("REAL_API_KEY", "REAL_API_SECRET", signature,
                   "REAL_TRADING_TOKEN", "0123456789"):
        assert secret not in blob, f"dry-run envelope leaked {secret!r}: {blob}"

    # but it must still be useful for verification
    assert envelope["method"] == "POST"
    assert "/accounts/orders" in envelope["url"]
    assert envelope["headers"]["x-api-key"] == "***REDACTED***"
    assert "X-Signature" in envelope["headers"], "header names must stay visible"
