"""
vnbroker.api.broker — Public entrypoint cho broker lane.

Cách dùng:
    from vnbroker.api.broker import get_broker
    client = get_broker()          # TCBS mặc định
    client.authenticate(otp="...")
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from vnbroker.broker.base import BaseBrokerClient


def get_broker(
    provider: str = "tcbs",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    show_log: bool = False,
) -> "BaseBrokerClient":
    """
    Factory function trả về broker client đã khởi tạo.

    Client được trả về chưa authenticated — cần gọi .authenticate(otp=...) trước
    khi dùng bất kỳ method read/write nào.

    Args:
        provider: Tên broker provider. Hiện tại chỉ hỗ trợ "tcbs".
        api_key: API key (tùy chọn — đọc từ env VNBROKER_BROKER_TCBS_API_KEY nếu không truyền).
        base_url: Override base URL (tùy chọn).
        show_log: Không có tác dụng với broker lane (luôn False để bảo mật).

    Returns:
        BaseBrokerClient subclass tương ứng với provider.

    Raises:
        KeyError: Nếu provider chưa được hỗ trợ.
        ValueError: Nếu không tìm thấy API key.

    Example:
        client = get_broker()
        client.authenticate(otp="123456")
        balance = client.get_balance(account_no="0123456789")
    """
    _name = provider.lower()

    if _name == "tcbs":
        # Import lazy để tránh circular import khi broker/tcbs chưa đủ module
        from vnbroker.broker.tcbs.client import TCBSBrokerClient  # noqa: PLC0415
        return TCBSBrokerClient(api_key=api_key, base_url=base_url)

    # Fallback qua registry (cho provider tương lai)
    from vnbroker.broker.registry import BrokerRegistry  # noqa: PLC0415
    client_class = BrokerRegistry.get(_name)
    return client_class(api_key=api_key, base_url=base_url)
