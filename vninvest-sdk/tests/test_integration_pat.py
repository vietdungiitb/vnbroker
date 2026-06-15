"""
Integration tests for PAT flow: create -> use -> revoke.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from vninvest.admin import LocalAdminClient
from vninvest.auth import APIKeyAuth
from vninvest.cache import CacheLayer, InMemoryCacheBackend
from vninvest.exceptions import AuthenticationError, ScopeDeniedError
from vninvest.models import PATScope
from vninvest.quota import QuotaContextManager, QuotaManager


class TestPATIntegration:
    """Integration tests for full PAT lifecycle."""

    @pytest.mark.asyncio
    async def test_pat_create_use_revoke_flow(self, pat_storage, sample_tenant_id, sample_user_id):
        """Test complete PAT lifecycle: create, authenticate, use, revoke."""
        # 1. Create PAT via storage (simulating admin)
        pat, plaintext = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="Integration Test PAT",
            scopes=[PATScope.QUOTE_READ, PATScope.COMPANY_READ],
            expires_in_days=30,
        )

        assert pat.is_active
        assert plaintext.startswith("vninvest_pat_")

        # 2. Authenticate with PAT
        auth = APIKeyAuth(mode="local", secret_key="test-secret", pat_storage=pat_storage)
        context = await auth.resolve_tenant(plaintext)

        assert context.tenant_id == sample_tenant_id
        assert context.pat_id == pat.pat_id
        assert context.user_id == sample_user_id
        assert context.has_scope(PATScope.QUOTE_READ)
        assert context.has_scope(PATScope.COMPANY_READ)
        assert not context.has_scope(PATScope.FINANCE_READ)

        # 3. Use PAT with quota manager (simulate API call)
        quota = QuotaManager(redis_client=pat_storage._redis_client)
        async with QuotaContextManager(quota, context, required_scope=PATScope.QUOTE_READ):
            # Quota check passed, scope validated
            pass

        # 4. Use PAT with cache layer (simulate cached API call)
        cache = CacheLayer(
            backend=InMemoryCacheBackend(),
            tenant_context=context,
        )

        async def fetch_data():
            return {"symbol": "ACB", "price": 25000}

        # First call - cache miss
        data, hit = await cache.get_or_fetch(
            data_type="quote_history",
            endpoint="history",
            params={"symbol": "ACB"},
            fetch_func=fetch_data,
            required_scope=PATScope.QUOTE_READ,
        )
        assert hit is False
        assert data["symbol"] == "ACB"

        # Second call - cache hit
        data, hit = await cache.get_or_fetch(
            data_type="quote_history",
            endpoint="history",
            params={"symbol": "ACB"},
            fetch_func=fetch_data,
            required_scope=PATScope.QUOTE_READ,
        )
        assert hit is True

        # 5. Try to access scope not granted - should fail
        with pytest.raises(ScopeDeniedError):
            await cache.get_or_fetch(
                data_type="finance_report",
                endpoint="report",
                params={"symbol": "ACB"},
                fetch_func=fetch_data,
                required_scope=PATScope.FINANCE_READ,
            )

        # 6. Revoke PAT
        result = await pat_storage.revoke_pat(pat.pat_id)
        assert result is True

        # Clear auth cache to ensure revoked PAT is not cached
        auth.clear_cache()

        # 7. Try to use revoked PAT - should fail
        with pytest.raises(AuthenticationError, match="revoked or expired"):
            await auth.resolve_tenant(plaintext)

    @pytest.mark.asyncio
    async def test_pat_scope_enforcement_across_components(
        self, pat_storage, sample_tenant_id, sample_user_id
    ):
        """Test that scope enforcement works consistently across quota, cache, streaming."""
        # Create PAT with limited scopes
        pat, plaintext = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="Limited Scope PAT",
            scopes=[PATScope.QUOTE_READ],  # Only quote read
        )

        auth = APIKeyAuth(mode="local", secret_key="test-secret", pat_storage=pat_storage)
        context = await auth.resolve_tenant(plaintext)

        # Quota manager should enforce scope
        quota = QuotaManager(redis_client=pat_storage._redis_client)

        # This should work (has QUOTE_READ)
        async with QuotaContextManager(quota, context, required_scope=PATScope.QUOTE_READ):
            pass

        # This should fail (no FINANCE_READ)
        with pytest.raises(ScopeDeniedError):
            async with QuotaContextManager(quota, context, required_scope=PATScope.FINANCE_READ):
                pass

        # Cache layer should enforce scope
        cache = CacheLayer(
            backend=InMemoryCacheBackend(),
            tenant_context=context,
        )

        async def fetch_data():
            return {"data": "test"}

        # This should work
        await cache.get_or_fetch(
            "quote_history", "history", {"symbol": "ACB"}, fetch_data,
            required_scope=PATScope.QUOTE_READ,
        )

        # This should fail
        with pytest.raises(ScopeDeniedError):
            await cache.get_or_fetch(
                "finance_report", "report", {"symbol": "ACB"}, fetch_data,
                required_scope=PATScope.FINANCE_READ,
            )

    @pytest.mark.asyncio
    async def test_pat_rotation_flow(self, pat_storage, sample_tenant_id, sample_user_id):
        """Test PAT rotation: old token works during overlap, then expires."""
        # Create initial PAT
        pat, plaintext = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="Rotatable PAT",
            scopes=[PATScope.QUOTE_READ],
            expires_in_days=30,
        )

        auth = APIKeyAuth(mode="local", secret_key="test-secret", pat_storage=pat_storage)

        # Original token works
        context = await auth.resolve_tenant(plaintext)
        assert context.pat_id == pat.pat_id

        # Rotate PAT
        new_pat, new_plaintext = await pat_storage.rotate_pat(pat.pat_id, overlap_hours=1)

        # New token works immediately
        new_context = await auth.resolve_tenant(new_plaintext)
        assert new_context.pat_id == new_pat.pat_id
        assert new_context.pat_id != pat.pat_id

        # Old token should still work during overlap (but will expire soon)
        old_context = await auth.resolve_tenant(plaintext)
        assert old_context.pat_id == pat.pat_id

        # Wait for overlap to expire (in real test, we'd mock time)
        # For now, verify old PAT has near-term expiry
        old_pat = await pat_storage.get_pat(pat.pat_id)
        assert old_pat.expires_at is not None
        assert (old_pat.expires_at - datetime.utcnow()).total_seconds() < 3600  # ~1 hour

    @pytest.mark.asyncio
    async def test_admin_client_pat_management(self, pat_storage, sample_tenant_id, sample_user_id):
        """Test LocalAdminClient PAT management methods."""
        admin = LocalAdminClient(pat_storage=pat_storage)

        # Create PAT via admin
        pat, plaintext = await admin.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="Admin Created PAT",
            scopes=[PATScope.QUOTE_READ, PATScope.STREAM_PRICE],
            expires_in_days=60,
        )

        assert pat.name == "Admin Created PAT"
        assert PATScope.QUOTE_READ in pat.scopes
        assert PATScope.STREAM_PRICE in pat.scopes
        assert plaintext.startswith("vninvest_pat_")

        # List PATs
        pats = await admin.list_pats(sample_tenant_id)
        assert len(pats) == 1
        assert pats[0].pat_id == pat.pat_id

        # Revoke via admin
        result = await admin.revoke_pat(pat.pat_id)
        assert result is True

        # Verify revoked
        revoked = await pat_storage.get_pat(pat.pat_id)
        assert revoked.revoked_at is not None

        # Rotate via admin
        pat2, plaintext2 = await admin.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="PAT to Rotate",
            scopes=[PATScope.QUOTE_READ],
        )

        new_pat, new_plaintext = await admin.rotate_pat(pat2.pat_id, overlap_hours=2)
        assert new_pat.pat_id != pat2.pat_id
        assert new_pat.name == "PAT to Rotate (rotated)"

        await admin.close()

    @pytest.mark.asyncio
    async def test_non_pat_token_rejected(self, pat_storage):
        """Test that non-PAT tokens (legacy format) are rejected."""
        auth = APIKeyAuth(mode="local", secret_key="test-secret", pat_storage=pat_storage)

        # Legacy key format should be rejected
        with pytest.raises(AuthenticationError, match="Only PAT tokens"):
            await auth.resolve_tenant("vninvest_abc123_1234567890_sig")
