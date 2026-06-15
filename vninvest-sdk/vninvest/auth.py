"""
Authentication and tenant resolution for Vninvest SDK.

Supports PAT (Personal Access Token) authentication only.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from uuid import UUID

import httpx

from .exceptions import (
    AuthenticationError,
    ConfigurationError,
    TenantNotFoundError,
    TenantSuspendedError,
)
from .models import PATScope, TenantContext, TenantPlan, TenantTier
from .pat import PATStorage


class APIKeyAuth:
    """
    API Key authentication handler.

    Supports PAT (Personal Access Token) authentication:
    - vninvest_pat_<random> - user-created, scoped tokens
    - Remote validation (HTTP call to auth service) - for SaaS
    """

    def __init__(
        self,
        mode: str = "local",
        secret_key: str | None = None,
        auth_service_url: str | None = None,
        auth_service_timeout: float = 5.0,
        cache_ttl_seconds: int = 300,
        pat_storage: PATStorage | None = None,
        redis_url: str | None = None,
    ):
        """
        Initialize API key auth.

        Args:
            mode: "local" or "remote"
            secret_key: HMAC secret for local validation (required for local mode)
            auth_service_url: Base URL for remote auth service (required for remote mode)
            auth_service_timeout: Timeout for remote auth calls
            cache_ttl_seconds: Cache TTL for resolved tenant contexts
            pat_storage: PATStorage instance for PAT validation (required for PAT support)
            redis_url: Redis URL for creating default PATStorage if not provided
        """
        self.mode = mode
        self.secret_key = secret_key or os.getenv("VNINVEST_AUTH_SECRET")
        self.auth_service_url = auth_service_url or os.getenv("VNINVEST_AUTH_SERVICE_URL")
        self.auth_service_timeout = auth_service_timeout
        self.cache_ttl_seconds = cache_ttl_seconds

        self._tenant_cache: dict[str, tuple[TenantContext, float]] = {}
        self._client: httpx.AsyncClient | None = None

        # PAT support
        self._pat_storage = pat_storage
        if self._pat_storage is None and redis_url:
            self._pat_storage = PATStorage(redis_url=redis_url)

        if mode == "local" and not self.secret_key:
            raise ConfigurationError("Local auth mode requires secret_key or VNINVEST_AUTH_SECRET env var")
        if mode == "remote" and not self.auth_service_url:
            raise ConfigurationError("Remote auth mode requires auth_service_url or VNINVEST_AUTH_SERVICE_URL env var")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.auth_service_timeout)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def resolve_tenant(self, credential: str) -> TenantContext:
        """
        Resolve tenant context from PAT credential.

        Returns TenantContext with plan limits, metadata, and effective scopes.
        Raises AuthenticationError if credential is invalid.
        Raises TenantSuspendedError if tenant is suspended.
        """
        if not credential or not credential.startswith("vninvest_pat_"):
            raise AuthenticationError("Invalid credential format. Only PAT tokens (vninvest_pat_...) are supported.")

        # Check cache
        cached = self._tenant_cache.get(credential)
        if cached:
            context, cached_at = cached
            if time.time() - cached_at < self.cache_ttl_seconds:
                return context

        # Resolve PAT token
        context = await self._resolve_pat(credential)

        # Cache result
        self._tenant_cache[credential] = (context, time.time())

        return context

    async def _resolve_pat(self, pat_token: str) -> TenantContext:
        """Resolve tenant context from a Personal Access Token."""
        if not self._pat_storage:
            raise AuthenticationError("PAT authentication not configured (missing PATStorage)")

        # Look up PAT by token
        pat = await self._pat_storage.get_pat_by_token(pat_token)
        if not pat:
            raise AuthenticationError("Invalid or expired PAT")

        if not pat.is_active:
            raise AuthenticationError("PAT has been revoked or expired")

        # Fetch tenant details
        tenant_data = await self._fetch_tenant_details(pat.tenant_id)
        if not tenant_data:
            raise TenantNotFoundError(f"Tenant {pat.tenant_id} not found")

        if tenant_data.get("status") != "active":
            raise TenantSuspendedError(f"Tenant {pat.tenant_id} is {tenant_data.get('status')}")

        # Build plan
        tier = TenantTier(tenant_data.get("plan", "free"))
        plan = TenantPlan.from_tier(tier)

        # Apply custom limits if any
        custom_limits = tenant_data.get("custom_limits", {})
        if custom_limits:
            plan = plan.model_copy(update=custom_limits)

        # Build context with PAT info and scopes
        context = TenantContext(
            tenant_id=pat.tenant_id,
            api_key_hash=self._hash_key(pat_token),
            plan=plan,
            tier=tier,
            status=tenant_data.get("status", "active"),
            metadata=tenant_data.get("metadata", {}),
            pat_id=pat.pat_id,
            user_id=pat.user_id,
            effective_scopes=pat.scopes,
        )

        # Fire-and-forget update last_used_at
        asyncio.create_task(self._pat_storage.update_last_used(pat.pat_id))

        return context

    async def _fetch_tenant_details(self, tenant_id: UUID) -> dict | None:
        """Fetch tenant details from remote service or local DB."""
        if self.mode == "remote":
            client = await self._get_client()
            try:
                response = await client.get(f"{self.auth_service_url}/api/v1/tenants/{tenant_id}")
                if response.status_code == 200:
                    return response.json()
            except Exception:
                pass
        # Local mode: would query local DB here
        # For now, return mock data for development
        return {
            "id": str(tenant_id),
            "name": f"Tenant {str(tenant_id)[:8]}",
            "plan": "pro",
            "status": "active",
            "metadata": {},
        }

    def _hash_key(self, api_key: str) -> str:
        """Create a hash of the API key for logging (never log full key)."""
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]

    def clear_cache(self) -> None:
        """Clear tenant resolution cache."""
        self._tenant_cache.clear()


# Global auth instance (initialized by SDK client)
_auth_instance: APIKeyAuth | None = None


def get_auth() -> APIKeyAuth:
    """Get global auth instance."""
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = APIKeyAuth()
    return _auth_instance


def set_auth(auth: APIKeyAuth) -> None:
    """Set global auth instance."""
    global _auth_instance
    _auth_instance = auth


# FastAPI dependency functions
from fastapi import Depends, HTTPException, Request, status


async def get_tenant_context(request: Request) -> TenantContext:
    """FastAPI dependency to get tenant context from request."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    api_key = auth_header[7:]  # Remove "Bearer "
    auth = get_auth()
    try:
        context = await auth.resolve_tenant(api_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    return context


def require_scope(scope: PATScope):
    """Create a dependency that requires a specific scope."""

    async def _require_scope(context: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if not context.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Token missing required scope: {scope.value}",
            )
        return context

    return _require_scope


require_quote_read = require_scope(PATScope.QUOTE_READ)
require_company_read = require_scope(PATScope.COMPANY_READ)
require_finance_read = require_scope(PATScope.FINANCE_READ)
require_news_read = require_scope(PATScope.NEWS_READ)
require_admin_tenant = require_scope(PATScope.ADMIN_TENANT)


async def resolve_tenant(api_key: str) -> TenantContext:
    """Convenience function to resolve tenant from API key."""
    return await get_auth().resolve_tenant(api_key)