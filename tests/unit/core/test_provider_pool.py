"""Tests for ProviderPool auth provider detection.

LƯU Ý (đợt Tier-1 Wave 1, 2026-10-10): danh sách biến dưới đây phải khớp với
`ProviderPool.AUTH_PROVIDERS`. Trước đây cấu hình pool đòi `TCBS_API_KEY` +
`TCBS_API_SECRET` — **không tồn tại** trong bất kỳ `.env` nào của production, nên
một `TCBS_JWT_TOKEN` hợp lệ bị bỏ qua và TCBS không bao giờ vào AUTO.

`patch.dict(..., clear=False)` **GỘP** chứ không xoá, nên test "không có env var"
phải xoá **mọi** tên biến mà pool đọc — kể cả tên mới. Bỏ sót một tên thì test
xanh vì credential thật của máy, không phải vì hành vi đúng: đây là dạng gate
xanh vì lý do sai, cùng họ với "grep-derived count".
"""

import os
import unittest
from unittest.mock import patch

from vnbroker.core.provider_pool import ProviderPool

#: Mọi biến mà `ProviderPool` đọc, gộp từ `AUTH_PROVIDERS`. Test dùng danh sách
#: này nên tự bám theo cấu hình thay vì liệt kê thủ công — liệt kê thủ công
#: chính là cách bản vá này sinh ra lỗi lần trước.
AUTH_ENV_VARS: tuple = tuple(
    name
    for config in ProviderPool.AUTH_PROVIDERS.values()
    for name in tuple(config["env_any"]) + tuple(config["env_all"])
)


def blank_env(**overrides: str) -> dict:
    """Env trong đó **mọi** biến của pool đều rỗng, trừ `overrides`."""
    env = {name: "" for name in AUTH_ENV_VARS}
    env.update(overrides)
    return env


class TestProviderPool(unittest.TestCase):
    """Test suite for ProviderPool."""

    def test_auth_env_vars_are_tuples_not_strings(self):
        """`env_any`/`env_all` phải là tuple.

        `_first_env` duyệt **phần tử**. Nếu cấu hình truyền một chuỗi, nó duyệt
        từng ký tự, không tìm thấy biến nào, và provider biến mất khỏi pool mà
        không có cảnh báo. Lỗi này đã xảy ra thật khi viết lại cấu hình pool
        ngày 2026-10-10, và chỉ bị phát hiện nhờ
        `scripts/check_provider_consistency.py`.
        """
        for name, config in ProviderPool.AUTH_PROVIDERS.items():
            with self.subTest(provider=name):
                self.assertIsInstance(
                    config["env_any"], tuple, f"{name}.env_any phai la tuple"
                )
                self.assertIsInstance(
                    config["env_all"], tuple, f"{name}.env_all phai la tuple"
                )

    def test_no_auth_providers(self):
        """Without env vars, only vci/kbs available."""
        with patch.dict(os.environ, blank_env(), clear=False):
            pool = ProviderPool()
            available = pool.get_available_providers("quote")
            self.assertIn("vci", available)
            self.assertIn("kbs", available)
            self.assertNotIn("dnse", available)
            self.assertNotIn("ssi", available)
            self.assertNotIn("tcbs", available)

    def test_dnse_detection(self):
        """With DNSE env vars, dnse is available."""
        env = blank_env(DNSE_API_KEY="test_dnse_key", DNSE_API_SECRET="test_dnse_secret")
        with patch.dict(os.environ, env, clear=False):
            pool = ProviderPool()
            self.assertTrue(pool.has_auth_provider("dnse"))
            available = pool.get_available_providers("quote")
            self.assertIn("dnse", available)

    def test_ssi_detection(self):
        """With SSI env vars, ssi is available."""
        env = blank_env(
            VNBROKER_BROKER_SSI_API_KEY="test_ssi_key",
            VNBROKER_BROKER_SSI_API_SECRET="test_ssi_secret",
        )
        with patch.dict(os.environ, env, clear=False):
            pool = ProviderPool()
            self.assertTrue(pool.has_auth_provider("ssi"))
            available = pool.get_available_providers("quote")
            self.assertIn("ssi", available)

    def test_tcbs_detected_from_jwt_token(self):
        """TCBS phải được nhận diện từ `TCBS_JWT_TOKEN`.

        Đây là biến thật trong `.env`: JWT 1290 ký tự, gọi
        `/tartarus/v1/tickerCommons` → HTTP 200. Bản vá cũ đòi
        `TCBS_API_KEY`/`TCBS_API_SECRET`, cả hai đều không tồn tại ⇒ pool không
        thấy TCBS dù có token chạy được.
        """
        with patch.dict(os.environ, blank_env(TCBS_JWT_TOKEN="a.b.c"), clear=False):
            pool = ProviderPool()
            self.assertTrue(pool.has_auth_provider("tcbs"))
            self.assertIn("tcbs", pool.get_available_providers("quote"))

    def test_tcbs_not_detected_without_any_credential(self):
        """Không có biến TCBS nào thì pool không được tự chế ra TCBS."""
        with patch.dict(os.environ, blank_env(), clear=False):
            pool = ProviderPool()
            self.assertFalse(pool.has_auth_provider("tcbs"))

    def test_whitespace_only_credential_is_not_a_credential(self):
        """`KEY=` sốt trong `.env` tạo chuỗi rỗng — không được coi là có key.

        Coi là có thì pool đưa provider vào AUTO rồi mọi request đều 401.
        """
        with patch.dict(os.environ, blank_env(TCBS_JWT_TOKEN="   "), clear=False):
            pool = ProviderPool()
            self.assertFalse(pool.has_auth_provider("tcbs"))

    def test_module_filter(self):
        """Providers filtered by module support."""
        env = blank_env(
            DNSE_API_KEY="test_dnse_key",
            DNSE_API_SECRET="test_dnse_secret",
            VNBROKER_BROKER_SSI_API_KEY="test_ssi_key",
            VNBROKER_BROKER_SSI_API_SECRET="test_ssi_secret",
            TCBS_JWT_TOKEN="a.b.c",
        )
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
        env = blank_env(DNSE_API_KEY="my_dnse_key", DNSE_API_SECRET="my_dnse_secret")
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
        env = blank_env(DNSE_API_KEY="k", DNSE_API_SECRET="s")
        with patch.dict(os.environ, env, clear=False):
            pool = ProviderPool()

            self.assertTrue(pool.has_auth_provider("dnse"))
            self.assertIsNotNone(pool.get_provider_config("dnse"))
            self.assertFalse(pool.has_auth_provider("ssi"))
            self.assertIsNone(pool.get_provider_config("ssi"))
            self.assertIn("dnse", pool.get_available_providers("quote"))


if __name__ == "__main__":
    unittest.main()
