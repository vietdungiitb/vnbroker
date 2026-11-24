"""CafeF must stay OUT of the anonymous tier-1 provider pool."""

from __future__ import annotations

import pytest

from vnbroker import Vnbroker
from vnbroker.base import get_auto_candidates
from vnbroker.common.client import Vnbroker as ConcreteVnbroker
from vnbroker.core.registry import ProviderRegistry
from vnbroker.reference import CafefReference


def test_cafef_not_in_supported_sources() -> None:
    assert "CAFEF" not in ConcreteVnbroker.SUPPORTED_SOURCES
    assert "cafef" not in ConcreteVnbroker.SUPPORTED_SOURCES


def test_cafef_not_in_auto_candidates() -> None:
    candidates = {str(item).lower() for item in get_auto_candidates("quote")}
    assert "cafef" not in candidates


def test_cafef_not_registered_as_quote_provider() -> None:
    available = {str(item).lower() for item in ProviderRegistry.list_available("quote")}
    assert "cafef" not in available


def test_reference_facade_is_explicit_only() -> None:
    assert isinstance(Vnbroker().reference("cafef"), CafefReference)
    with pytest.raises(ValueError):
        Vnbroker().reference("nope")
