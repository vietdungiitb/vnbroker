"""Tests for ProviderPool auth provider detection."""

import os
import unittest
from unittest.mock import patch

from vnbroker.core.provider_pool import ProviderPool


class TestProviderPool(unittest.TestCase):
    """Test suite for ProviderPool."""

    def test_no_auth_providers(self):
        """Without env vars, only vci/kbs available."""
        env = {
            "DNSE_API_KEY": "",
            "DNSE_API_SECRET": "",
            "VNBROKER_BROKER_SSI_API_KEY": "",
            "VNBROKER_BROKER_SSI_API_SECRET": "",
            "TCBS_API_KEY": "",
            "TCBS_API_SECRET": "",
        }
        with patch.dict(os.environ, env, clear=False):
            pool = ProviderPool()
            available = pool.get_available_providers("quote")
            self.assertIn("vci", available)
            self.assertIn("kbs", available)
            self.assertNotIn("dnse", available)
            self.assertNotIn("ssi", available)
            self.assertNotIn("tcbs", available)

    def test_dnse_detection(self):
        """With DNSE env vars, dnse is available."""
        env = {
            "DNSE_API_KEY": "test_dnse_key",
            "DNSE_API_SECRET": "test_dnse_secret",
            "VNBROKER_BROKER_SSI_API_KEY": "",
            "VNBROKER_BROKER_SSI_API_SECRET": "",
            "TCBS_API_KEY": "",
            "TCBS_API_SECRET": "",
        }
        with patch.dict(os.environ, env, clear=False):
            pool = ProviderPool()
            self.assertTrue(pool.has_auth_provider("dnse"))
            available = pool.get_available_providers("quote")
            self.assertIn("dnse", available)

    def test_ssi_detection(self):
        """With SSI env vars, ssi is available."""
        env = {
            "DNSE_API_KEY": "",
            "DNSE_API_SECRET": "",
            "VNBROKER_BROKER_SSI_API_KEY": "test_ssi_key",
            "VNBROKER_BROKER_SSI_API_SECRET": "test_ssi_secret",
            "TCBS_API_KEY": "",
            "TCBS_API_SECRET": "",
        }
        with patch.dict(os.environ, env, clear=False):
            pool = ProviderPool()
            self.assertTrue(pool.has_auth_provider("ssi"))
            available = pool.get_available_providers("quote")
            self.assertIn("ssi", available)

    def test_tcbs_detection(self):
        """With TCBS env vars, tcbs is available."""
        env = {
            "DNSE_API_KEY": "",
            "DNSE_API_SECRET": "",
            "VNBROKER_BROKER_SSI_API_KEY": "",
            "VNBROKER_BROKER_SSI_API_SECRET": "",
            "TCBS_API_KEY": "test_tcbs_key",
            "TCBS_API_SECRET": "test_tcbs_secret",
        }
        with patch.dict(os.environ, env, clear=False):
            pool = ProviderPool()
            self.assertTrue(pool.has_auth_provider("tcbs"))
            available = pool.get_available_providers("quote")
            self.assertIn("tcbs", available)

    def test_module_filter(self):
        """Providers filtered by module support."""
        env = {
            "DNSE_API_KEY": "test_dnse_key",
            "DNSE_API_SECRET": "test_dnse_secret",
            "VNBROKER_BROKER_SSI_API_KEY": "test_ssi_key",
            "VNBROKER_BROKER_SSI_API_SECRET": "test_ssi_secret",
            "TCBS_API_KEY": "test_tcbs_key",
            "TCBS_API_SECRET": "test_tcbs_secret",
        }
        with patch.dict(os.environ, env, clear=False):
            pool = ProviderPool()

            # screener: only ssi supports it
            screener_providers = pool.get_available_providers("screener")
            self.assertIn("ssi", screener_providers)
            self.assertNotIn("dnse", screener_providers)
            self.assertNotIn("tcbs", screener_providers)

            # trading: dnse, ssi, tcbs all support it
            trading_providers = pool.get_available_providers("trading")
            self.assertIn("dnse", trading_providers)
            self.assertIn("ssi", trading_providers)
            self.assertIn("tcbs", trading_providers)

            # quote: all three support it
            quote_providers = pool.get_available_providers("quote")
            self.assertIn("dnse", quote_providers)
            self.assertIn("ssi", quote_providers)
            self.assertIn("tcbs", quote_providers)

    def test_get_provider_config(self):
        """Auth config returned correctly."""
        env = {
            "DNSE_API_KEY": "my_dnse_key",
            "DNSE_API_SECRET": "my_dnse_secret",
            "VNBROKER_BROKER_SSI_API_KEY": "",
            "VNBROKER_BROKER_SSI_API_SECRET": "",
            "TCBS_API_KEY": "",
            "TCBS_API_SECRET": "",
        }
        with patch.dict(os.environ, env, clear=False):
            pool = ProviderPool()
            config = pool.get_provider_config("dnse")
            self.assertIsNotNone(config)
            self.assertEqual(config["key"], "my_dnse_key")
            self.assertEqual(config["secret"], "my_dnse_secret")
            self.assertIn("quote", config["supports"])
            self.assertIn("listing", config["supports"])
            self.assertIn("trading", config["supports"])

            # Non-existent provider returns None
            self.assertIsNone(pool.get_provider_config("nonexistent"))


class TestProviderPoolDeadCode(unittest.TestCase):
    """D3: decide whether ProviderPool is used, and drop its dead code.

    The class itself IS used for real: `vnbroker/api/bulk.py:37` builds one
    and `:64` asks it for providers, and `tests/unit/api/test_bulk_api.py:89`
    asserts it is not None. So the class stays.

    `ProviderPool.get_provider` was the dead code: zero callers anywhere in
    `vnbroker/` or `tests/` (the only `.get_provider(` receivers are
    `UnifiedRegistry.get_provider` in `core/unified_registry.py`), a
    "will be implemented in WP-5" placeholder, an unused `symbol` parameter,
    and it contradicted its own docstring — it claims to create a provider
    *instance* while returning whatever `ProviderRegistry.get` gives, which
    at e5d8133 is `None` 100% of the time because the registry is empty.
    """

    def test_dead_get_provider_is_gone(self):
        """The unused WP-5 placeholder must not come back."""
        self.assertFalse(
            hasattr(ProviderPool, "get_provider"),
            "ProviderPool.get_provider is dead code (0 callers) and was removed",
        )

    def test_pool_keeps_the_api_bulk_depends_on(self):
        """Positive case: the parts api/bulk.py uses must stay."""
        with patch.dict(os.environ, {}, clear=False):
            pool = ProviderPool()
            providers = pool.get_available_providers("quote")

        self.assertIn("vci", providers)
        self.assertIn("kbs", providers)

    def test_pool_still_reports_auth_providers(self):
        """Positive case: env detection is the pool's real job."""
        env = {
            "DNSE_API_KEY": "k",
            "DNSE_API_SECRET": "s",
            "VNBROKER_BROKER_SSI_API_KEY": "",
            "VNBROKER_BROKER_SSI_API_SECRET": "",
            "TCBS_API_KEY": "",
            "TCBS_API_SECRET": "",
        }
        with patch.dict(os.environ, env, clear=False):
            pool = ProviderPool()

            self.assertTrue(pool.has_auth_provider("dnse"))
            self.assertIsNotNone(pool.get_provider_config("dnse"))
            self.assertFalse(pool.has_auth_provider("ssi"))
            self.assertIsNone(pool.get_provider_config("ssi"))
            self.assertIn("dnse", pool.get_available_providers("quote"))


if __name__ == "__main__":
    unittest.main()
