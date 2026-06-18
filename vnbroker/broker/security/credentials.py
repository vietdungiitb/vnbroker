"""
vnbroker.broker.security.credentials — Credential configs for broker lanes.

TCBS Env priority (theo TCBS_BROKER_SPEC.md §2.1):
  1. Tham số trực tiếp
  2. VNBROKER_BROKER_TCBS_API_KEY
  3. vnbroker_TCBS_OPENAPI_API_KEY
  4. TCBS_OPENAPI_API_KEY
  5. TCBS_API_KEY

SSI Env priority:
  1. Tham số trực tiếp
  2. VNBROKER_BROKER_SSI_CONSUMER_ID / VNBROKER_BROKER_SSI_CONSUMER_SECRET
  3. SSI_CONSUMER_ID / SSI_CONSUMER_SECRET

KHÔNG LOG credentials ở bất kỳ nơi nào trong module này.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

# TCBS
_TCBS_ENV_PRIORITY: tuple[str, ...] = (
    "VNBROKER_BROKER_TCBS_API_KEY",
    "vnbroker_TCBS_OPENAPI_API_KEY",
    "TCBS_OPENAPI_API_KEY",
    "TCBS_API_KEY",
)

_TCBS_DEFAULT_BASE_URL = "https://openapi.tcbs.com.vn"

# Backward compatibility
_ENV_PRIORITY = _TCBS_ENV_PRIORITY
_DEFAULT_BASE_URL = _TCBS_DEFAULT_BASE_URL

# SSI
_SSI_ENV_PRIORITY_ID: tuple[str, ...] = (
    "VNBROKER_BROKER_SSI_CONSUMER_ID",
    "SSI_CONSUMER_ID",
)

_SSI_ENV_PRIORITY_SECRET: tuple[str, ...] = (
    "VNBROKER_BROKER_SSI_CONSUMER_SECRET",
    "SSI_CONSUMER_SECRET",
)

_SSI_DEFAULT_BASE_URL = "https://iboard.ssi.com.vn"

# VNDirect
_VNDIRECT_ENV_PRIORITY: tuple[str, ...] = (
    "VNBROKER_BROKER_VNDIRECT_API_KEY",
    "VNDIRECT_API_KEY",
)

_VNDIRECT_DEFAULT_BASE_URL = "https://openapi.vndirect.com.vn"


@dataclass
class TCBSCredentialConfig:
    """
    Cấu hình kết nối cho TCBS OpenAPI broker lane.

    WARNING: KHÔNG truyền instance này vào logger — chứa api_key dạng plain text.
    """
    api_key: str                              # Bắt buộc — KHÔNG log
    base_url: str = _TCBS_DEFAULT_BASE_URL
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


@dataclass
class SSICredentialConfig:
    """
    Cấu hình kết nối cho SSI FastConnect broker lane.

    WARNING: KHÔNG truyền instance này vào logger — chứa consumer_secret dạng plain text.
    """
    consumer_id: str                          # Bắt buộc — KHÔNG log
    consumer_secret: str                      # Bắt buộc — KHÔNG log
    base_url: str = _SSI_DEFAULT_BASE_URL
    timeout_seconds: float = 30.0
    auth_token: Optional[str] = field(default=None, repr=False)  # OAuth2 access token

    def __repr__(self) -> str:
        """Override repr để che credentials trong log/debug."""
        return (
            f"SSICredentialConfig("
            f"consumer_id=***REDACTED***, "
            f"consumer_secret=***REDACTED***, "
            f"base_url={self.base_url!r}, "
            f"timeout_seconds={self.timeout_seconds}"
            f")"
        )


@dataclass
class VNDirectCredentialConfig:
    """
    Cấu hình kết nối cho VNDirect OpenAPI broker lane.

    WARNING: KHÔNG truyền instance này vào logger — chứa api_key dạng plain text.
    """
    api_key: str                              # Bắt buộc — KHÔNG log
    base_url: str = _VNDIRECT_DEFAULT_BASE_URL
    timeout_seconds: float = 30.0
    auth_token: Optional[str] = field(default=None, repr=False)

    def __repr__(self) -> str:
        """Override repr để che api_key trong log/debug."""
        return (
            f"VNDirectCredentialConfig("
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
      2. Env vars theo _TCBS_ENV_PRIORITY

    Raises:
        ValueError: Nếu không tìm thấy api_key ở bất kỳ nguồn nào.

    Security: Không log api_key ở đây hay bất kỳ caller nào.
    """
    resolved_key = api_key or _resolve_tcbs_from_env()

    if not resolved_key:
        raise ValueError(
            "Không tìm thấy TCBS API key. "
            "Truyền trực tiếp qua get_broker(api_key=...) hoặc set env var "
            f"{_TCBS_ENV_PRIORITY[0]}."
        )

    return TCBSCredentialConfig(
        api_key=resolved_key,
        base_url=base_url or _TCBS_DEFAULT_BASE_URL,
        auth_token=auth_token,
    )


def resolve_ssi_credentials(
    consumer_id: Optional[str] = None,
    consumer_secret: Optional[str] = None,
    base_url: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> SSICredentialConfig:
    """
    Tạo SSICredentialConfig theo thứ tự ưu tiên:
      1. Tham số trực tiếp (consumer_id, consumer_secret)
      2. Env vars

    Raises:
        ValueError: Nếu không tìm thấy credentials ở bất kỳ nguồn nào.

    Security: Không log credentials ở đây hay bất kỳ caller nào.
    """
    resolved_id = consumer_id or _resolve_ssi_from_env(_SSI_ENV_PRIORITY_ID)
    resolved_secret = consumer_secret or _resolve_ssi_from_env(_SSI_ENV_PRIORITY_SECRET)

    if not resolved_id or not resolved_secret:
        raise ValueError(
            "Không tìm thấy SSI credentials. "
            "Truyền trực tiếp qua get_broker(consumer_id=..., consumer_secret=...) "
            f"hoặc set env vars {_SSI_ENV_PRIORITY_ID[0]} và {_SSI_ENV_PRIORITY_SECRET[0]}."
        )

    return SSICredentialConfig(
        consumer_id=resolved_id,
        consumer_secret=resolved_secret,
        base_url=base_url or _SSI_DEFAULT_BASE_URL,
        auth_token=auth_token,
    )


def _resolve_tcbs_from_env() -> Optional[str]:
    """Thử lần lượt các env var TCBS theo thứ tự ưu tiên. Trả về None nếu không tìm thấy."""
    for var in _TCBS_ENV_PRIORITY:
        value = os.environ.get(var)
        if value and value.strip():
            return value.strip()
    return None


def _resolve_ssi_from_env(priority_vars: tuple[str, ...]) -> Optional[str]:
    """Thử lần lượt các env var SSI theo thứ tự ưu tiên. Trả về None nếu không tìm thấy."""
    for var in priority_vars:
        value = os.environ.get(var)
        if value and value.strip():
            return value.strip()
    return None


def _resolve_vndirect_from_env() -> Optional[str]:
    """Thử lần lượt các env var VNDirect theo thứ tự ưu tiên. Trả về None nếu không tìm thấy."""
    for var in _VNDIRECT_ENV_PRIORITY:
        value = os.environ.get(var)
        if value and value.strip():
            return value.strip()
    return None


def resolve_vndirect_credentials(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> VNDirectCredentialConfig:
    """
    Tạo VNDirectCredentialConfig theo thứ tự ưu tiên:
      1. Tham số trực tiếp (api_key)
      2. Env vars

    Raises:
        ValueError: Nếu không tìm thấy api_key ở bất kỳ nguồn nào.

    Security: Không log api_key ở đây hay bất kỳ caller nào.
    """
    resolved_key = api_key or _resolve_vndirect_from_env()

    if not resolved_key:
        raise ValueError(
            "Không tìm thấy VNDirect API key. "
            "Truyền trực tiếp qua get_broker(api_key=...) hoặc set env var "
            f"{_VNDIRECT_ENV_PRIORITY[0]}."
        )

    return VNDirectCredentialConfig(
        api_key=resolved_key,
        base_url=base_url or _VNDIRECT_DEFAULT_BASE_URL,
        auth_token=auth_token,
    )
