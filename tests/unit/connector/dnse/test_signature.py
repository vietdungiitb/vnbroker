from datetime import datetime, timezone

from vnbroker.connector.dnse.core.signature import build_signature, format_date_header


def test_format_date_header_uses_rfc_style_utc_offset():
    value = format_date_header(datetime(2026, 1, 19, 7, 45, 23, tzinfo=timezone.utc))
    assert value == "Mon, 19 Jan 2026 07:45:23 +0000"


def test_build_signature_returns_encoded_signature():
    headers, signature = build_signature(
        secret="secret",
        method="GET",
        path="/accounts",
        date_value="Mon, 19 Jan 2026 07:45:23 +0000",
        algorithm="hmac-sha256",
        nonce="abc123",
        header_name="Date",
    )

    assert headers == "(request-target) date"
    assert isinstance(signature, str)
    assert "%" in signature
