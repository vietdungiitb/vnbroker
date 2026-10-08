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


if __name__ == "__main__":
    unittest.main()
