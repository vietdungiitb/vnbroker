"""
Unit tests for PAT storage and authentication.
"""

from uuid import uuid4

import pytest

from vninvest.auth import APIKeyAuth
from vninvest.exceptions import AuthenticationError
from vninvest.models import PATScope


class TestPATStorage:
    """Tests for PATStorage CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_pat(self, pat_storage, sample_tenant_id, sample_user_id):
        """Test creating a new PAT."""
        pat, plaintext = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="Test PAT",
            scopes=[PATScope.QUOTE_READ, PATScope.COMPANY_READ],
            expires_in_days=30,
        )

        assert pat.tenant_id == sample_tenant_id
        assert pat.user_id == sample_user_id
        assert pat.name == "Test PAT"
        assert PATScope.QUOTE_READ in pat.scopes
        assert PATScope.COMPANY_READ in pat.scopes
        assert pat.expires_at is not None
        assert pat.revoked_at is None
        assert pat.is_active
        assert plaintext.startswith("vninvest_pat_")
        assert len(plaintext) == 13 + 32  # "vninvest_pat_" (13) + 32 hex chars

    @pytest.mark.asyncio
    async def test_get_pat_by_id(self, pat_storage, sample_tenant_id, sample_user_id):
        """Test retrieving PAT by ID."""
        pat, _ = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="Test PAT",
            scopes=[PATScope.QUOTE_READ],
        )

        retrieved = await pat_storage.get_pat(pat.pat_id)
        assert retrieved is not None
        assert retrieved.pat_id == pat.pat_id
        assert retrieved.name == "Test PAT"

    @pytest.mark.asyncio
    async def test_get_pat_by_token(self, pat_storage, sample_tenant_id, sample_user_id):
        """Test looking up PAT by full token."""
        pat, plaintext = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="Test PAT",
            scopes=[PATScope.QUOTE_READ],
        )

        retrieved = await pat_storage.get_pat_by_token(plaintext)
        assert retrieved is not None
        assert retrieved.pat_id == pat.pat_id

        # Wrong token should return None
        wrong = await pat_storage.get_pat_by_token("vninvest_pat_wrongtoken123456789012")
        assert wrong is None

    @pytest.mark.asyncio
    async def test_list_pats_by_tenant(self, pat_storage, sample_tenant_id, sample_user_id):
        """Test listing PATs for a tenant."""
        await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="PAT 1",
            scopes=[PATScope.QUOTE_READ],
        )
        await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="PAT 2",
            scopes=[PATScope.COMPANY_READ],
        )

        pats = await pat_storage.list_pats(sample_tenant_id)
        assert len(pats) == 2
        names = {p.name for p in pats}
        assert names == {"PAT 1", "PAT 2"}

    @pytest.mark.asyncio
    async def test_list_pats_by_user(self, pat_storage, sample_tenant_id, sample_user_id):
        """Test listing PATs filtered by user."""
        user2 = uuid4()
        await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="User 1 PAT",
            scopes=[PATScope.QUOTE_READ],
        )
        await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=user2,
            name="User 2 PAT",
            scopes=[PATScope.COMPANY_READ],
        )

        pats = await pat_storage.list_pats(sample_tenant_id, user_id=sample_user_id)
        assert len(pats) == 1
        assert pats[0].name == "User 1 PAT"

    @pytest.mark.asyncio
    async def test_revoke_pat(self, pat_storage, sample_tenant_id, sample_user_id):
        """Test revoking a PAT."""
        pat, _ = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="Test PAT",
            scopes=[PATScope.QUOTE_READ],
        )

        result = await pat_storage.revoke_pat(pat.pat_id)
        assert result is True

        # Verify revoked
        revoked = await pat_storage.get_pat(pat.pat_id)
        assert revoked is not None
        assert revoked.revoked_at is not None
        assert not revoked.is_active

        # Revoking non-existent should return False
        result = await pat_storage.revoke_pat(uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_rotate_pat(self, pat_storage, sample_tenant_id, sample_user_id):
        """Test rotating a PAT."""
        pat, _ = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="Original PAT",
            scopes=[PATScope.QUOTE_READ, PATScope.COMPANY_READ],
        )

        new_pat, new_plaintext = await pat_storage.rotate_pat(pat.pat_id, overlap_hours=24)

        assert new_pat.pat_id != pat.pat_id
        assert new_pat.name == "Original PAT (rotated)"
        assert new_pat.scopes == pat.scopes
        assert new_pat.expires_at is not None
        assert new_plaintext.startswith("vninvest_pat_")

        # Old PAT should have updated expiry (still active during overlap)
        old_pat = await pat_storage.get_pat(pat.pat_id)
        assert old_pat.expires_at is not None
        assert old_pat.is_active  # Should be active during overlap period

    @pytest.mark.asyncio
    async def test_pat_is_active_property(self, sample_pat, expired_pat, revoked_pat):
        """Test PAT is_active property."""
        assert sample_pat.is_active is True
        assert expired_pat.is_active is False
        assert revoked_pat.is_active is False


class TestPATAuth:
    """Tests for PAT authentication via APIKeyAuth."""

    @pytest.mark.asyncio
    async def test_resolve_pat_success(self, pat_storage, sample_tenant_id, sample_user_id):
        """Test successful PAT resolution."""
        pat, plaintext = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="Test PAT",
            scopes=[PATScope.QUOTE_READ, PATScope.COMPANY_READ],
        )

        auth = APIKeyAuth(mode="local", secret_key="test-secret", pat_storage=pat_storage)
        context = await auth.resolve_tenant(plaintext)

        assert context.tenant_id == sample_tenant_id
        assert context.pat_id == pat.pat_id
        assert context.user_id == sample_user_id
        assert PATScope.QUOTE_READ in context.effective_scopes
        assert PATScope.COMPANY_READ in context.effective_scopes
        assert context.has_scope(PATScope.QUOTE_READ)
        assert not context.has_scope(PATScope.FINANCE_READ)

    @pytest.mark.asyncio
    async def test_resolve_pat_invalid_token(self, pat_storage):
        """Test PAT resolution with invalid token."""
        auth = APIKeyAuth(mode="local", secret_key="test-secret", pat_storage=pat_storage)

        with pytest.raises(AuthenticationError, match="Invalid or expired PAT"):
            await auth.resolve_tenant("vninvest_pat_invalidtoken123456789012")

    @pytest.mark.asyncio
    async def test_resolve_pat_revoked(self, pat_storage, revoked_pat):
        """Test PAT resolution with revoked token."""
        # Manually store revoked PAT
        r = pat_storage._redis_client or await pat_storage._get_redis()
        await r.set(pat_storage._pat_key(revoked_pat.pat_id), revoked_pat.model_dump_json())
        await r.set(pat_storage._index_key(revoked_pat.prefix), str(revoked_pat.pat_id))

        auth = APIKeyAuth(mode="local", secret_key="test-secret", pat_storage=pat_storage)

        with pytest.raises(AuthenticationError, match="revoked or expired"):
            await auth.resolve_tenant("vninvest_pat_revokedtoken1234567")

    @pytest.mark.asyncio
    async def test_resolve_pat_expired(self, pat_storage, expired_pat):
        """Test PAT resolution with expired token."""
        r = pat_storage._redis_client or await pat_storage._get_redis()
        await r.set(pat_storage._pat_key(expired_pat.pat_id), expired_pat.model_dump_json())
        await r.set(pat_storage._index_key(expired_pat.prefix), str(expired_pat.pat_id))

        auth = APIKeyAuth(mode="local", secret_key="test-secret", pat_storage=pat_storage)

        with pytest.raises(AuthenticationError, match="revoked or expired"):
            await auth.resolve_tenant("vninvest_pat_expiredtoken1234567")

    @pytest.mark.asyncio
    async def test_resolve_pat_missing_storage(self):
        """Test PAT resolution without PATStorage configured."""
        auth = APIKeyAuth(mode="local", secret_key="test-secret")

        with pytest.raises(AuthenticationError, match="PAT authentication not configured"):
            await auth.resolve_tenant("vninvest_pat_sometoken123456789012")

    @pytest.mark.asyncio
    async def test_resolve_invalid_format(self, pat_storage):
        """Test resolution with invalid credential format."""
        auth = APIKeyAuth(mode="local", secret_key="test-secret", pat_storage=pat_storage)

        # Test non-PAT format
        with pytest.raises(AuthenticationError, match="Invalid credential format"):
            await auth.resolve_tenant("invalid_format")

        # Test legacy key format (should be rejected)
        with pytest.raises(AuthenticationError, match="Invalid credential format"):
            await auth.resolve_tenant("vninvest_" + str(uuid4()) + "_1234567890_invalidsig")

        # Test empty string
        with pytest.raises(AuthenticationError, match="Invalid credential format"):
            await auth.resolve_tenant("")

    @pytest.mark.asyncio
    async def test_resolve_non_pat_token_rejected(self, pat_storage):
        """Test that non-PAT tokens (legacy format) are rejected."""
        auth = APIKeyAuth(mode="local", secret_key="test-secret", pat_storage=pat_storage)

        # Legacy key format should be rejected
        with pytest.raises(AuthenticationError, match="Only PAT tokens"):
            await auth.resolve_tenant("vninvest_abc123_1234567890_sig")
