"""ISSUE-02: BrokerRegistry register-once + thread-safe lookup (mocked)."""

from __future__ import annotations

import threading

import pytest

from vnbroker import Vnbroker
from vnbroker.broker.base import BaseBrokerClient
from vnbroker.broker.registry import BrokerRegistry
from vnbroker.core.unified_registry import UnifiedRegistry


class _DummyBroker(BaseBrokerClient):
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.fixture(autouse=True)
def _restore_registry():
    import vnbroker.broker as broker_pkg  # noqa: F401 - re-register defaults

    yield
    # Re-register defaults after tests that clear the registry + drop dummy
    from vnbroker.broker.tcbs.client import TCBSBrokerClient
    from vnbroker.broker.ssi.client import SSIBrokerClient

    with BrokerRegistry._lock:
        BrokerRegistry._providers.pop("dummy", None)
    if not BrokerRegistry.is_registered("tcbs"):
        BrokerRegistry.register("tcbs", TCBSBrokerClient)
    if not BrokerRegistry.is_registered("ssi"):
        BrokerRegistry.register("ssi", SSIBrokerClient)


def test_register_once_at_import():
    assert BrokerRegistry.is_registered("tcbs")
    assert BrokerRegistry.is_registered("ssi")
    assert "tcbs" in UnifiedRegistry.list_brokers()
    assert "ssi" in UnifiedRegistry.list_brokers()


def test_vnbroker_broker_uses_unified_registry():
    vn = Vnbroker()
    first = vn.broker(provider="tcbs", api_key="K")
    second = vn.broker(provider="tcbs", api_key="K")
    assert type(first) is type(second)
    # No re-registration side effect: provider set unchanged
    assert set(BrokerRegistry.list_providers()) >= {"tcbs", "ssi"}


def test_concurrent_get_and_register_safe():
    errors: list = []

    def _reader():
        try:
            for _ in range(200):
                BrokerRegistry.get("tcbs")
                UnifiedRegistry.get_broker("ssi")
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    def _writer():
        try:
            for _ in range(50):
                BrokerRegistry.register("dummy", _DummyBroker)
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=_reader) for _ in range(4)]
    threads += [threading.Thread(target=_writer) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert BrokerRegistry.get("dummy") is _DummyBroker
