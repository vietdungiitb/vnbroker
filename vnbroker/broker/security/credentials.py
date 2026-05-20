"""
vnbroker.broker.security.credentials — TCBSCredentialConfig và resolver.

Env priority (theo TCBS_BROKER_SPEC.md §2.1):
  1. Tham số trực tiếp
  2. VNBROKER_BROKER_TCBS_API_KEY
  3. vnbroker_TCBS_OPENAPI_API_KEY
  4. TCBS_OPENAPI_API_KEY
  5. TCBS_API_KEY

KHÔNG LOG api_key ở bất kỳ nơi nào trong module này.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

_ENV_PRIORITY: tuple[str, ...] = (
    "VNBROKER_BROKER_TCBS_API_KEY",
    "vnbroker_TCBS_OPENAPI_API_KEY",
    "TCBS_OPENAPI_API_KEY",
    "TCBS_API_KEY",
)

_DEFAULT_BASE_URL = "https://openapi.tcbs.com.vn"


@dataclass
class TCBSCredentialConfig:
    """
    Cấu hình kết nối cho TCBS OpenAPI broker lane.

    WARNING: KHÔNG truyền instance này vào logger — chứa api_key dạng plain text.
    """
    api_key: str                              # Bắt buộc — KHÔNG log
    base_url: str = _DEFAULT_BASE_URL
    timeout_seconds: float = 30.0
    auth_token: Optional[str] = field(default=None, repr=False)  # JWT nếu inject sẵn
    custody_code: Optional[str] = None       # 105C format, dùng cho get_profile + derivatives

    def __repr__(self) -> str:
        """Override repr để che api_key trong log/debug."""
        return (
            f"TCBSCredentialConfig("
            f"api_key=***REDACTED***, "
            f"base_url={self.base_url!r}, "
            f"timeout_seconds={self.timeout_seconds}"
            f")"
        )


def resolve_tcbs_credentials(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> TCBSCredentialConfig:
    """
    Tạo TCBSCredentialConfig theo thứ tự ưu tiên:
      1. Tham số trực tiếp (api_key)
      2. Env vars theo _ENV_PRIORITY

    Raises:
        ValueError: Nếu không tìm thấy api_key ở bất kỳ nguồn nào.

    Security: Không log api_key ở đây hay bất kỳ caller nào.
    """
    resolved_key = api_key or _resolve_from_env()

    if not resolved_key:
        raise ValueError(
            "Không tìm thấy TCBS API key. "
            "Truyền trực tiếp qua get_broker(api_key=...) hoặc set env var "
            f"{_ENV_PRIORITY[0]}."
        )

    return TCBSCredentialConfig(
        api_key=resolved_key,
        base_url=base_url or _DEFAULT_BASE_URL,
        auth_token=auth_token,
    )


def _resolve_from_env() -> Optional[str]:
    """Thử lần lượt các env var theo thứ tự ưu tiên. Trả về None nếu không tìm thấy."""
    for var in _ENV_PRIORITY:
        value = os.environ.get(var)
        if value and value.strip():
            return value.strip()
    return None
