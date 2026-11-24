"""AC-6: raw-price error must be a terminal answer, never a failover trigger."""

from __future__ import annotations

from vnbroker.core.exceptions import ProviderBadRequestError
from vnbroker.core.source_router import should_failover


def test_raw_price_error_is_not_failover() -> None:
    exc = ProviderBadRequestError("KBS không có giá thô", http_status=400)

    assert should_failover(exc) is False


def test_not_implemented_error_would_have_been_failover() -> None:
    """Ratchet: explains why the implementation must NOT use NotImplementedError."""
    assert should_failover(NotImplementedError("not implemented")) is True
