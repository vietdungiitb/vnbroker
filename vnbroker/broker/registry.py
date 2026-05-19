"""
BrokerRegistry — Singleton registry ánh xạ provider name → client class.

Tách hoàn toàn khỏi ProviderRegistry của explorer lane.
"""
from __future__ import annotations

from typing import Type, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from vnbroker.broker.base import BaseBrokerClient


class BrokerRegistry:
    """
    Registry singleton cho broker clients.

    Cách dùng:
        BrokerRegistry.register("tcbs", TCBSBrokerClient)
        cls = BrokerRegistry.get("tcbs")
    """

    _registry: Dict[str, Type["BaseBrokerClient"]] = {}

    @classmethod
    def register(cls, name: str, client_class: Type["BaseBrokerClient"]) -> None:
        """Đăng ký broker client class theo tên (lowercase)."""
        cls._registry[name.lower()] = client_class

    @classmethod
    def get(cls, name: str) -> Type["BaseBrokerClient"]:
        """
        Lấy broker client class theo tên.

        Raises:
            KeyError: Nếu provider chưa được đăng ký.
        """
        key = name.lower()
        if key not in cls._registry:
            available = list(cls._registry.keys())
            raise KeyError(
                f"Broker provider '{name}' chưa được đăng ký. "
                f"Hiện có: {available}"
            )
        return cls._registry[key]

    @classmethod
    def list_providers(cls) -> list[str]:
        """Trả về danh sách tên provider đã đăng ký."""
        return list(cls._registry.keys())
