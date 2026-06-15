"""
PAT (Personal Access Token) storage backend for Vninvest SDK.

Provides Redis-backed CRUD operations for PAT management.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import bcrypt
import redis.asyncio as redis

from .models import PATScope, PersonalAccessToken


class PATStorage:
    """
    Redis-backed storage for Personal Access Tokens.

    Key schema:
    - vninvest:pat:{pat_id} -> PAT JSON (TTL: max(90d, expiry))
    - vninvest:pat:index:{prefix} -> pat_id (TTL: max(90d, expiry))
    - vninvest:pat:tenant:{tenant_id} -> Set[pat_id]
    - vninvest:pat:user:{user_id} -> Set[pat_id]
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        redis_client: redis.Redis | None = None,
        key_prefix: str = "vninvest:pat",
        default_ttl_days: int = 90,
    ):
        self.redis_url = redis_url
        self._redis_client = redis_client
        self._owns_client = redis_client is None
        self.key_prefix = key_prefix
        self.default_ttl_days = default_ttl_days
        self._redis: redis.Redis | None = None

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None and self._redis_client is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
            await self._redis.ping()
        return self._redis or self._redis_client

    async def close(self) -> None:
        if self._owns_client and self._redis:
            await self._redis.aclose()
            self._redis = None

    def _pat_key(self, pat_id: UUID) -> str:
        return f"{self.key_prefix}:{pat_id}"

    def _index_key(self, prefix: str) -> str:
        return f"{self.key_prefix}:index:{prefix}"

    def _tenant_set_key(self, tenant_id: UUID) -> str:
        return f"{self.key_prefix}:tenant:{tenant_id}"

    def _user_set_key(self, user_id: UUID) -> str:
        return f"{self.key_prefix}:user:{user_id}"

    def _calculate_ttl(self, expires_at: datetime | None) -> int:
        """Calculate TTL in seconds based on expiry or default."""
        if expires_at:
            ttl_seconds = int((expires_at - datetime.utcnow()).total_seconds())
            return max(ttl_seconds, 1)
        return self.default_ttl_days * 86400

    @staticmethod
    def generate_token() -> tuple[str, str, str]:
        """
        Generate a new PAT token.

        Returns:
            Tuple of (plaintext_token, token_hash, prefix)
            - plaintext_token: Full token shown to user ONCE (e.g., "vninvest_pat_abcdefghijklmnopqrstuvwx")
            - token_hash: bcrypt hash for storage
            - prefix: First 22 chars for index lookup (e.g., "vninvest_pat_abcdefgh")
        """
        # Generate 32 random bytes -> 43 base64url chars, but we use hex for simplicity
        random_part = secrets.token_hex(16)  # 32 hex chars
        plaintext = f"vninvest_pat_{random_part}"
        prefix = plaintext[:22]  # "vninvest_pat_" (13) + 9 chars = 22
        token_hash = bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(12)).decode()
        return plaintext, token_hash, prefix

    @staticmethod
    def verify_token(plaintext: str, token_hash: str) -> bool:
        """Verify a plaintext token against its bcrypt hash."""
        try:
            return bcrypt.checkpw(plaintext.encode(), token_hash.encode())
        except Exception:
            return False

    async def create_pat(
        self,
        tenant_id: UUID,
        user_id: UUID,
        name: str,
        scopes: list[PATScope],
        expires_in_days: int | None = 30,
    ) -> tuple[PersonalAccessToken, str]:
        """
        Create a new PAT.

        Returns:
            Tuple of (PAT model, plaintext_token) - plaintext shown ONCE
        """
        r = await self._get_redis()
        pat_id = uuid4()
        plaintext, token_hash, prefix = self.generate_token()

        expires_at = None
        if expires_in_days is not None:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        pat = PersonalAccessToken(
            pat_id=pat_id,
            tenant_id=tenant_id,
            user_id=user_id,
            name=name,
            token_hash=token_hash,
            prefix=prefix,
            scopes=scopes,
            expires_at=expires_at,
        )

        ttl = self._calculate_ttl(expires_at)
        pat_json = pat.model_dump_json()

        # Use pipeline for atomic writes
        pipe = r.pipeline()
        pipe.set(self._pat_key(pat_id), pat_json, ex=ttl)
        pipe.set(self._index_key(prefix), str(pat_id), ex=ttl)
        pipe.sadd(self._tenant_set_key(tenant_id), str(pat_id))
        pipe.sadd(self._user_set_key(user_id), str(pat_id))
        await pipe.execute()

        return pat, plaintext

    async def get_pat(self, pat_id: UUID) -> PersonalAccessToken | None:
        """Get PAT by ID."""
        r = await self._get_redis()
        data = await r.get(self._pat_key(pat_id))
        if not data:
            return None
        return PersonalAccessToken.model_validate_json(data)

    async def get_pat_by_token(self, token: str) -> PersonalAccessToken | None:
        """Look up PAT by full token string (uses prefix index)."""
        if not token.startswith("vninvest_pat_"):
            return None
        prefix = token[:22]
        r = await self._get_redis()
        pat_id_str = await r.get(self._index_key(prefix))
        if not pat_id_str:
            return None
        pat_id = UUID(pat_id_str)
        pat = await self.get_pat(pat_id)
        if pat and self.verify_token(token, pat.token_hash):
            return pat
        return None

    async def list_pats(
        self,
        tenant_id: UUID,
        user_id: UUID | None = None,
    ) -> list[PersonalAccessToken]:
        """List PATs for a tenant, optionally filtered by user."""
        r = await self._get_redis()
        if user_id:
            # Intersect tenant and user sets
            pat_ids = await r.sinter(
                self._tenant_set_key(tenant_id),
                self._user_set_key(user_id),
            )
        else:
            pat_ids = await r.smembers(self._tenant_set_key(tenant_id))

        pats = []
        for pat_id_str in pat_ids:
            pat = await self.get_pat(UUID(pat_id_str))
            if pat:
                pats.append(pat)
        return pats

    async def revoke_pat(self, pat_id: UUID) -> bool:
        """Revoke a PAT (soft delete - marks revoked_at)."""
        r = await self._get_redis()
        pat = await self.get_pat(pat_id)
        if not pat:
            return False

        pat.revoked_at = datetime.utcnow()
        ttl = self._calculate_ttl(pat.expires_at)
        await r.set(self._pat_key(pat_id), pat.model_dump_json(), ex=ttl)
        return True

    async def rotate_pat(
        self,
        pat_id: UUID,
        overlap_hours: int = 24,
    ) -> tuple[PersonalAccessToken, str]:
        """
        Rotate a PAT: create new one with same scopes, mark old for expiry after overlap.

        Returns:
            Tuple of (new PAT model, new plaintext_token)
        """
        old_pat = await self.get_pat(pat_id)
        if not old_pat:
            raise ValueError(f"PAT {pat_id} not found")

        # Create new PAT with same scopes
        new_pat, plaintext = await self.create_pat(
            tenant_id=old_pat.tenant_id,
            user_id=old_pat.user_id,
            name=f"{old_pat.name} (rotated)",
            scopes=old_pat.scopes,
            expires_in_days=None,  # Will set custom expiry below
        )

        # Set new PAT expiry to overlap_hours from now
        new_expires = datetime.utcnow() + timedelta(hours=overlap_hours)
        new_pat.expires_at = new_expires
        ttl = self._calculate_ttl(new_expires)
        r = await self._get_redis()
        await r.set(self._pat_key(new_pat.pat_id), new_pat.model_dump_json(), ex=ttl)
        await r.expire(self._index_key(new_pat.prefix), ttl)

        # Update old PAT to expire after overlap
        old_pat.expires_at = new_expires
        old_ttl = self._calculate_ttl(old_pat.expires_at)
        await r.set(self._pat_key(pat_id), old_pat.model_dump_json(), ex=old_ttl)
        await r.expire(self._index_key(old_pat.prefix), old_ttl)

        return new_pat, plaintext

    async def update_last_used(self, pat_id: UUID) -> None:
        """Update last_used_at timestamp (fire-and-forget)."""
        try:
            pat = await self.get_pat(pat_id)
            if pat:
                pat.last_used_at = datetime.utcnow()
                ttl = self._calculate_ttl(pat.expires_at)
                r = await self._get_redis()
                await r.set(self._pat_key(pat_id), pat.model_dump_json(), ex=ttl)
        except Exception:
            # Silently ignore - last_used is best-effort
            pass
