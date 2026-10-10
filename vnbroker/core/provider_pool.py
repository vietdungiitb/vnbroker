"""
Provider Pool with automatic auth provider detection.

Manages all providers (no-auth and auth-based) for the bulk router.
Auth providers (DNSE, SSI, TCBS) are auto-detected from environment variables.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


class ProviderPool:
    """Manages all providers, including auth providers with env detection."""

    # Auth provider configurations.
    #
    # `env_any` is checked in order; a provider counts as available when the
    # first is set and every entry of `env_all` is set too.
    #
    # This replaced the old `env_key` + `env_secret` pair, which was
    # unsatisfiable for TCBS: it demanded `TCBS_API_SECRET`, a variable that
    # exists in no production `.env` and no code path, so a working TCBS JWT
    # was invisible and TCBS could never enter AUTO. Measured 2026-10-10: the
    # repo `.env` held a valid `TCBS_JWT_TOKEN` (1290 chars, HTTP 200 on
    # `/tartarus/*`) and no `TCBS_API_SECRET` at all, yet
    # `has_auth_provider('tcbs')` returned False.
    #
    # DNSE keeps both halves because its HMAC signature genuinely needs key and
    # secret. TCBS read-only market data needs only a bearer token.
    AUTH_PROVIDERS: Dict[str, Dict[str, Any]] = {
        "dnse": {
            "env_any": ("DNSE_API_KEY",),
            "env_all": ("DNSE_API_SECRET",),
            "supports": ["quote", "listing", "trading"],
        },
        "ssi": {
            "env_any": ("VNBROKER_BROKER_SSI_API_KEY",),
            "env_all": ("VNBROKER_BROKER_SSI_API_SECRET",),
            "supports": ["quote", "listing", "trading", "screener"],
        },
        "tcbs": {
            "env_any": ("vnbroker_TCBS_JWT_TOKEN", "TCBS_JWT_TOKEN"),
            "env_all": (),
            "supports": ["quote", "trading", "listing", "financial", "company"],
        },
    }

    # Providers that need no credential. `rss_cafef` / `rss_vneconomy` là
    # nguồn RSS công khai — chúng có trong `OPEN_SOURCE_CANDIDATES['news']`
    # nhưng thiếu ở đây, tức ba danh sách đã lệch nhau trước khi có cổng
    # kiểm tra (đo 2026-10-10).
    NO_AUTH_PROVIDERS: List[str] = ["vci", "kbs", "rss_cafef", "rss_vneconomy"]

    def __init__(self) -> None:
        self._auth_providers: Dict[str, Dict[str, Any]] = {}
        self._detect_auth_providers()

    @staticmethod
    def _first_env(names: "tuple[str, ...]") -> str:
        """Giá trị đầu tiên tồn tại và khác rỗng sau ``strip``.

        Khoảng trắng thuần bị coi là không có: một dòng ``KEY=`` sốt trong
        ``.env`` tạo ra chuỗi rỗng, và coi đó là "có credential" thì pool
        đưa provider vào AUTO rồi mọi request đều 401.
        """
        for name in names:
            value = os.getenv(name)
            if value and value.strip():
                return value.strip()
        return ""

    def _detect_auth_providers(self) -> None:
        """Auto-detect auth providers from environment variables.

        ``env_any`` và ``env_all`` đều là **tuple tên biến**. Phải truyền cả
        tuple vào ``_first_env``, không truyền từng chuỗi: ``_first_env`` duyệt
        theo phần tử, nên đưa vào một chuỗi đơn sẽ duyệt từng **ký tự**
        (``"DNSE_API_SECRET"`` → ``'D'``, ``'N'``, ...), không tìm thấy biến
        nào, và provider biến mất khỏi pool mà không có bất kỳ cảnh báo nào.
        Gate ``check_provider_consistency.py`` bắt được đúng lỗi này.

        Never logs the credential itself.
        """
        for name, config in self.AUTH_PROVIDERS.items():
            key = self._first_env(tuple(config["env_any"]))
            secrets = [
                self._first_env(tuple([name_])) for name_ in config["env_all"]
            ]
            if key and all(secrets):
                self._auth_providers[name] = {
                    "key": key,
                    "secret": secrets[0] if secrets else "",
                    "supports": config["supports"],
                }

    def get_available_providers(self, module: str) -> List[str]:
        """Return all available providers for a module."""
        # No-auth providers always available
        available = list(self.NO_AUTH_PROVIDERS)
        # Add auth providers if credentials exist
        for name, config in self._auth_providers.items():
            if module in config["supports"]:
                available.append(name)
        return available

    def has_auth_provider(self, name: str) -> bool:
        """Check if an auth provider is configured."""
        return name in self._auth_providers

    def get_provider_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Get auth config for a provider."""
        return self._auth_providers.get(name)
