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

    # Auth provider configurations
    AUTH_PROVIDERS: Dict[str, Dict[str, Any]] = {
        "dnse": {
            "env_key": "DNSE_API_KEY",
            "env_secret": "DNSE_API_SECRET",
            "supports": ["quote", "listing", "trading"],
        },
        "ssi": {
            "env_key": "VNBROKER_BROKER_SSI_API_KEY",
            "env_secret": "VNBROKER_BROKER_SSI_API_SECRET",
            "supports": ["quote", "listing", "trading", "screener"],
        },
        "tcbs": {
            "env_key": "TCBS_API_KEY",
            "env_secret": "TCBS_API_SECRET",
            "supports": ["quote", "trading"],
        },
    }

    # No-auth providers always available
    NO_AUTH_PROVIDERS: List[str] = ["vci", "kbs"]

    def __init__(self) -> None:
        self._auth_providers: Dict[str, Dict[str, Any]] = {}
        self._detect_auth_providers()

    def _detect_auth_providers(self) -> None:
        """Auto-detect auth providers from environment variables."""
        for name, config in self.AUTH_PROVIDERS.items():
            key = os.getenv(config["env_key"])
            secret = os.getenv(config["env_secret"])
            if key and secret:
                self._auth_providers[name] = {
                    "key": key,
                    "secret": secret,
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

    def get_provider(self, name: str, module: str, symbol: Optional[str] = None) -> Optional[Any]:
        """Create a provider instance."""
        # This will be implemented in WP-5 (API integration)
        # For now, just return the provider class
        from vnbroker.core.registry import ProviderRegistry
        try:
            return ProviderRegistry.get(module, name)
        except ValueError:
            return None
