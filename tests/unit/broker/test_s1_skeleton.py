"""
Unit tests cho S1: BrokerRegistry và BaseBrokerClient skeleton.
"""
import pytest
from vnbroker.broker.base import BaseBrokerClient
from vnbroker.broker.registry import BrokerRegistry


# ─── Fixtures ────────────────────────────────────────────────────────────────

class ConcreteBroker(BaseBrokerClient):
    """Concrete subclass dùng để test ABC."""

    @property
    def provider_name(self) -> str:
        return "fake"

    def authenticate(self, **kwargs) -> None:
        pass

    def revoke(self) -> None:
        pass


# ─── BaseBrokerClient ─────────────────────────────────────────────────────────

class TestBaseBrokerClientABC:
    def test_cannot_instantiate_abstract_class_directly(self):
        with pytest.raises(TypeError):
            BaseBrokerClient()  # type: ignore

    def test_concrete_subclass_instantiable(self):
        broker = ConcreteBroker()
        assert isinstance(broker, BaseBrokerClient)

    def test_provider_name_returns_expected_value(self):
        broker = ConcreteBroker()
        assert broker.provider_name == "fake"

    def test_authenticate_callable(self):
        broker = ConcreteBroker()
        broker.authenticate()  # Không raise

    def test_revoke_callable(self):
        broker = ConcreteBroker()
        broker.revoke()  # Không raise

    def test_subclass_missing_provider_name_raises(self):
        with pytest.raises(TypeError):
            class Incomplete(BaseBrokerClient):
                def authenticate(self, **kwargs): pass
                def revoke(self): pass
            Incomplete()  # Missing provider_name abstract property


# ─── BrokerRegistry ──────────────────────────────────────────────────────────

class TestBrokerRegistry:
    def setup_method(self):
        """Dọn registry trước mỗi test để tránh pollution."""
        BrokerRegistry._registry.clear()

    def test_register_and_get_provider(self):
        BrokerRegistry.register("fake", ConcreteBroker)
        retrieved = BrokerRegistry.get("fake")
        assert retrieved is ConcreteBroker

    def test_get_is_case_insensitive(self):
        BrokerRegistry.register("FAKE", ConcreteBroker)
        assert BrokerRegistry.get("fake") is ConcreteBroker
        assert BrokerRegistry.get("FAKE") is ConcreteBroker

    def test_get_unregistered_provider_raises_key_error(self):
        with pytest.raises(KeyError, match="chưa được đăng ký"):
            BrokerRegistry.get("nonexistent")

    def test_list_providers_returns_registered_names(self):
        BrokerRegistry.register("a", ConcreteBroker)
        BrokerRegistry.register("b", ConcreteBroker)
        providers = BrokerRegistry.list_providers()
        assert "a" in providers
        assert "b" in providers

    def test_list_providers_empty_when_no_registrations(self):
        assert BrokerRegistry.list_providers() == []

    def test_error_message_includes_available_providers(self):
        BrokerRegistry.register("tcbs", ConcreteBroker)
        with pytest.raises(KeyError) as exc:
            BrokerRegistry.get("dnse")
        assert "tcbs" in str(exc.value)

    def test_register_overwrite_updates_class(self):
        class AnotherBroker(BaseBrokerClient):
            @property
            def provider_name(self): return "another"
            def authenticate(self, **kwargs): pass
            def revoke(self): pass

        BrokerRegistry.register("fake", ConcreteBroker)
        BrokerRegistry.register("fake", AnotherBroker)
        assert BrokerRegistry.get("fake") is AnotherBroker
