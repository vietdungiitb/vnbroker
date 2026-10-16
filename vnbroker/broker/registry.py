"""
Broker registry for provider lookup.

Singleton registry to manage broker provider implementations.
"""

import threading

from typing import Any, Dict, Type, Optional
from vnbroker.broker.base import BaseBrokerClient


class BrokerRegistry:
    """
    Registry for broker providers.

    Provides lookup and instantiation of broker clients by provider name.

    Registration happens once at import (see ``vnbroker.broker.__init__``);
    all methods are guarded by a lock so concurrent lookup/register
    from multiple threads cannot race.
    """

    _instance: Optional["BrokerRegistry"] = None
    _providers: Dict[str, Type[BaseBrokerClient]] = {}
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "BrokerRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, name: str, client_class: Type[BaseBrokerClient]) -> None:
        """
        Register a broker provider.

        Args:
            name: Provider name (e.g., 'TCBS')
            client_class: Broker client class implementing BaseBrokerClient
        """
        with cls._lock:
            cls._providers[name.lower()] = client_class

    @classmethod
    def get(cls, name: str) -> Type[BaseBrokerClient]:
        """
        Get broker client class by name.

        Args:
            name: Provider name

        Returns:
            Broker client class

        Raises:
            KeyError: If provider not registered
        """
        with cls._lock:
            provider = cls._providers.get(name.lower())
            available = ", ".join(sorted(cls._providers.keys()))
        if provider is None:
            raise KeyError(
                f"Broker provider '{name}' chưa được đăng ký. "
                f"Danh sách khả dụng: {available}"
            )
        return provider

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> BaseBrokerClient:
        """
        Create broker client instance.

        Args:
            name: Provider name
            **kwargs: Arguments passed to client constructor

        Returns:
            Broker client instance
        """
        client_class = cls.get(name)
        return client_class(**kwargs)

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names."""
        with cls._lock:
            return list(cls._providers.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if provider is registered."""
        with cls._lock:
            return name.lower() in cls._providers

    @classmethod
    def clear(cls) -> None:
        """Clear all registered providers (for testing)."""
        with cls._lock:
            cls._providers.clear()

    @classmethod
    def capabilities(cls, provider: str) -> Dict[str, Any]:
        """Describe a broker lane's usable surface, without credentials.

        VNBROKER-REQ-001. Exists so a consumer can ask "is this method real,
        or was it removed?" instead of discovering it by calling and catching
        ``NotImplementedError`` — which is fail-open: it tells you nothing
        until something breaks.

        Covers **three** lanes, not just the registered ones: ``dnse`` is not
        a :class:`BaseBrokerClient` and is therefore absent from this
        registry, but it is a lane a consumer needs to reason about. The
        implementation and its reasoning live in
        ``vnbroker/broker/capabilities.py``.

        Args:
            provider: ``"tcbs"``, ``"ssi"`` or ``"dnse"`` (case-insensitive).

        Returns:
            ``{version, provider, registered, methods, features}``. See
            ``vnbroker.broker.capabilities.capabilities()``.

        Raises:
            KeyError: unknown provider; the message lists the known lanes.
        """
        from vnbroker.broker.capabilities import capabilities as _capabilities

        return _capabilities(provider)