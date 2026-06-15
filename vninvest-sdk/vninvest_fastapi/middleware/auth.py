"""
FastAPI authentication middleware for Vninvest SDK.

Extracts and validates API keys, resolves tenant context, and attaches to request state.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware

from vninvest import APIKeyAuth, TenantContext, get_settings
from vninvest.auth import APIKeyAuth as AuthClass
from vninvest.config import Settings
from vninvest.exceptions import AuthenticationError, TenantNotFoundError, TenantSuspendedError
from vninvest.observability import trace_span

# API Key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
authorization_header = APIKeyHeader(name="Authorization", auto_error=False)


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware for FastAPI."""

    def __init__(self, app, auth: AuthClass | None = None, settings: Settings | None = None):
        super().__init__(app)
        self._auth = auth
        self._settings = settings or get_settings()

    def get_auth(self, request: Request) -> AuthClass:
        """Get auth instance from app state or create default."""
        if hasattr(request.app.state, "auth") and request.app.state.auth:
            return request.app.state.auth
        if self._auth is not None:
            return self._auth
        # Fallback: create default
        return APIKeyAuth(
            mode=self._settings.auth.mode,
            secret_key=self._settings.auth.secret_key,
            auth_service_url=self._settings.auth.service_url,
            redis_url=self._settings.redis.url,
            cache_ttl_seconds=self._settings.auth.cache_ttl_seconds,
        )

    async def dispatch(self, request: Request, call_next):
        """Process request through authentication."""
        # Skip auth for health checks and docs
        if request.url.path in ("/health", "/healthz", "/ready", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        # Extract API key
        api_key = self._extract_api_key(request)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing PAT token. Provide via X-API-Key header or Authorization: Bearer <vninvest_pat_...>",
            )

        # Resolve tenant context
        try:
            with trace_span("auth.resolve_tenant", {"api_key_prefix": api_key[:20]}):
                auth = self.get_auth(request)
                context = await auth.resolve_tenant(api_key)
        except AuthenticationError as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
        except TenantNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except TenantSuspendedError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        # Attach context to request state
        request.state.tenant_context = context
        request.state.api_key = api_key

        # Process request
        response = await call_next(request)
        return response

    def _extract_api_key(self, request: Request) -> str | None:
        """Extract API key from request headers."""
        # Try X-API-Key header first
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key.strip()

        # Try Authorization: Bearer <token>
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:].strip()

        return None


# Dependency for getting tenant context in route handlers
async def get_tenant_context(request: Request) -> TenantContext:
    """Get tenant context from request state (set by AuthMiddleware)."""
    if not hasattr(request.state, "tenant_context"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tenant context not found. AuthMiddleware may not be installed.",
        )
    return request.state.tenant_context


# Dependency for getting API key
async def get_api_key(request: Request) -> str:
    """Get API key from request state."""
    if not hasattr(request.state, "api_key"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key not found in request state.",
        )
    return request.state.api_key


# Scope-based authorization dependencies
def require_scope(scope: str):
    """Create a dependency that requires a specific PAT scope."""
    async def scope_checker(context: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        from vninvest.models import PATScope
        try:
            required_scope = PATScope(scope)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid scope: {scope}",
            )

        if not context.has_scope(required_scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Token missing required scope: {scope}",
            )
        return context

    return scope_checker


# Common scope dependencies
require_quote_read = require_scope("quote:read")
require_company_read = require_scope("company:read")
require_finance_read = require_scope("finance:read")
require_news_read = require_scope("news:read")
require_stream_price = require_scope("stream:price")
require_stream_depth = require_scope("stream:depth")
require_stream_trade = require_scope("stream:trade")
require_admin_tenant = require_scope("admin:tenant")
