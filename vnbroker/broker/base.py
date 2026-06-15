"""
BaseBrokerClient — Abstract base class cho mọi broker client.

Định nghĩa interface contract; không chứa implementation logic.
"""
from abc import ABC, abstractmethod


class BaseBrokerClient(ABC):
    """
    Abstract base class cho broker clients (TCBS, và các broker tương lai).

    Subclass phải implement authenticate() và revoke().
    Mọi logic nghiệp vụ nằm trong subclass, không ở đây.
    """

    @abstractmethod
    def authenticate(self, **kwargs) -> None:
        """Xác thực với broker. Sau khi gọi, session ở trạng thái READ."""
        ...

    @abstractmethod
    def revoke(self) -> None:
        """Huỷ session hiện tại."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Tên provider, ví dụ: 'tcbs'."""
        ...
