"""
Admin API client for Vninvest platform operations.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from .exceptions import AuthenticationError, VninvestError
from .models import (
    PATScope,
    PersonalAccessToken,
    SystemHealthReport,
    TenantContext,
    TenantPlan,
    TenantTier,
    TenantUsageReport,
)


class AdminClient:
    """
    Admin client for platform operations.

    Provides:
    - Tenant management (create, update, suspend, delete)
    - Usage reporting and analytics
    - System health monitoring
    - Quota management
    - Billing integration
    """

    def __init__(
        self,
        base_url: str,
        admin_api_key: str,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.admin_api_key = admin_api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.admin_api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        json_data: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        client = await self._get_client()
        for attempt in range(self.max_retries):
            try:
                response = await client.request(method, path, json=json_data, params=params)
                if response.status_code == 401:
                    raise AuthenticationError("Invalid admin API key")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500 or attempt == self.max_retries - 1:
                    raise VninvestError(f"Admin API error: {e.response.text}", status_code=e.response.status_code)
                await asyncio.sleep(2**attempt)
            except Exception:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)
        raise VninvestError("Max retries exceeded")

    # Tenant Management

    async def create_tenant(
        self,
        name: str,
        plan: TenantTier = TenantTier.FREE,
        email: str | None = None,
        custom_limits: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TenantContext:
        """Create a new tenant."""
        data = {
            "name": name,
            "plan": plan.value,
            "email": email,
            "custom_limits": custom_limits or {},
            "metadata": metadata or {},
        }
        result = await self._request("POST", "/api/v1/admin/tenants", json_data=data)
        return TenantContext(
            tenant_id=UUID(result["id"]),
            api_key_hash=result["api_key_hash"],
            plan=TenantPlan.from_tier(TenantTier(result["plan"])),
            tier=TenantTier(result["plan"]),
            status=result["status"],
            metadata=result.get("metadata", {}),
        )

    async def get_tenant(self, tenant_id: UUID) -> TenantContext:
        """Get tenant details."""
        result = await self._request("GET", f"/api/v1/admin/tenants/{tenant_id}")
        return TenantContext(
            tenant_id=UUID(result["id"]),
            api_key_hash=result["api_key_hash"],
            plan=TenantPlan.from_tier(TenantTier(result["plan"])),
            tier=TenantTier(result["plan"]),
            status=result["status"],
            metadata=result.get("metadata", {}),
        )

    async def update_tenant(
        self,
        tenant_id: UUID,
        name: str | None = None,
        plan: TenantTier | None = None,
        status: str | None = None,
        custom_limits: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TenantContext:
        """Update tenant configuration."""
        data = {}
        if name is not None:
            data["name"] = name
        if plan is not None:
            data["plan"] = plan.value
        if status is not None:
            data["status"] = status
        if custom_limits is not None:
            data["custom_limits"] = custom_limits
        if metadata is not None:
            data["metadata"] = metadata

        result = await self._request("PATCH", f"/api/v1/admin/tenants/{tenant_id}", json_data=data)
        return TenantContext(
            tenant_id=UUID(result["id"]),
            api_key_hash=result["api_key_hash"],
            plan=TenantPlan.from_tier(TenantTier(result["plan"])),
            tier=TenantTier(result["plan"]),
            status=result["status"],
            metadata=result.get("metadata", {}),
        )

    async def delete_tenant(self, tenant_id: UUID) -> bool:
        """Delete a tenant (soft delete)."""
        await self._request("DELETE", f"/api/v1/admin/tenants/{tenant_id}")
        return True

    async def list_tenants(
        self,
        status: str | None = None,
        plan: TenantTier | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TenantContext]:
        """List tenants with filters."""
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if plan:
            params["plan"] = plan.value

        result = await self._request("GET", "/api/v1/admin/tenants", params=params)
        return [
            TenantContext(
                tenant_id=UUID(t["id"]),
                api_key_hash=t["api_key_hash"],
                plan=TenantPlan.from_tier(TenantTier(t["plan"])),
                tier=TenantTier(t["plan"]),
                status=t["status"],
                metadata=t.get("metadata", {}),
            )
            for t in result.get("tenants", [])
        ]

    async def regenerate_api_key(self, tenant_id: UUID) -> str:
        """Regenerate API key for a tenant."""
        result = await self._request("POST", f"/api/v1/admin/tenants/{tenant_id}/regenerate-key")
        return result["api_key"]

    # PAT Management

    async def create_pat(
        self,
        tenant_id: UUID,
        user_id: UUID,
        name: str,
        scopes: list[PATScope],
        expires_in_days: int | None = 30,
    ) -> tuple[PersonalAccessToken, str]:
        """
        Create a new Personal Access Token for a tenant.

        Returns:
            Tuple of (PAT model, plaintext_token) - plaintext shown ONCE
        """
        data = {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "name": name,
            "scopes": [s.value for s in scopes],
            "expires_in_days": expires_in_days,
        }
        result = await self._request("POST", "/api/v1/admin/pats", json_data=data)
        pat = PersonalAccessToken(
            pat_id=UUID(result["pat_id"]),
            tenant_id=UUID(result["tenant_id"]),
            user_id=UUID(result["user_id"]),
            name=result["name"],
            token_hash=result["token_hash"],
            prefix=result["prefix"],
            scopes=[PATScope(s) for s in result["scopes"]],
            expires_at=datetime.fromisoformat(result["expires_at"]) if result.get("expires_at") else None,
            created_at=datetime.fromisoformat(result["created_at"]),
        )
        return pat, result["plaintext_token"]

    async def list_pats(
        self,
        tenant_id: UUID,
        user_id: UUID | None = None,
    ) -> list[PersonalAccessToken]:
        """List PATs for a tenant, optionally filtered by user."""
        params = {}
        if user_id:
            params["user_id"] = str(user_id)
        result = await self._request("GET", f"/api/v1/admin/tenants/{tenant_id}/pats", params=params)
        return [
            PersonalAccessToken(
                pat_id=UUID(p["pat_id"]),
                tenant_id=UUID(p["tenant_id"]),
                user_id=UUID(p["user_id"]),
                name=p["name"],
                token_hash=p["token_hash"],
                prefix=p["prefix"],
                scopes=[PATScope(s) for s in p["scopes"]],
                expires_at=datetime.fromisoformat(p["expires_at"]) if p.get("expires_at") else None,
                last_used_at=datetime.fromisoformat(p["last_used_at"]) if p.get("last_used_at") else None,
                revoked_at=datetime.fromisoformat(p["revoked_at"]) if p.get("revoked_at") else None,
                created_at=datetime.fromisoformat(p["created_at"]),
            )
            for p in result.get("pats", [])
        ]

    async def revoke_pat(self, pat_id: UUID) -> bool:
        """Revoke a PAT."""
        await self._request("DELETE", f"/api/v1/admin/pats/{pat_id}")
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
        data = {"overlap_hours": overlap_hours}
        result = await self._request("POST", f"/api/v1/admin/pats/{pat_id}/rotate", json_data=data)
        pat = PersonalAccessToken(
            pat_id=UUID(result["pat_id"]),
            tenant_id=UUID(result["tenant_id"]),
            user_id=UUID(result["user_id"]),
            name=result["name"],
            token_hash=result["token_hash"],
            prefix=result["prefix"],
            scopes=[PATScope(s) for s in result["scopes"]],
            expires_at=datetime.fromisoformat(result["expires_at"]) if result.get("expires_at") else None,
            created_at=datetime.fromisoformat(result["created_at"]),
        )
        return pat, result["plaintext_token"]

    # Usage Reporting

    async def get_tenant_usage(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> TenantUsageReport:
        """Get usage report for a tenant."""
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        result = await self._request("GET", f"/api/v1/admin/tenants/{tenant_id}/usage", params=params)
        return TenantUsageReport(**result)

    async def get_all_tenants_usage(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100,
    ) -> list[TenantUsageReport]:
        """Get usage report for all tenants."""
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "limit": limit,
        }
        result = await self._request("GET", "/api/v1/admin/usage", params=params)
        return [TenantUsageReport(**r) for r in result.get("reports", [])]

    async def get_top_symbols(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get most accessed symbols across all tenants."""
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "limit": limit,
        }
        result = await self._request("GET", "/api/v1/admin/analytics/top-symbols", params=params)
        return result.get("symbols", [])

    async def get_endpoint_usage(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, int]:
        """Get API endpoint usage distribution."""
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        result = await self._request("GET", "/api/v1/admin/analytics/endpoints", params=params)
        return result.get("endpoints", {})

    # System Health

    async def get_system_health(self) -> SystemHealthReport:
        """Get system-wide health report."""
        result = await self._request("GET", "/api/v1/admin/health")
        return SystemHealthReport(**result)

    async def get_provider_health(self) -> dict[str, dict[str, Any]]:
        """Get health status for all data providers."""
        result = await self._request("GET", "/api/v1/admin/health/providers")
        return result.get("providers", {})

    async def get_cache_stats(self) -> dict[str, Any]:
        """Get cache performance statistics."""
        result = await self._request("GET", "/api/v1/admin/health/cache")
        return result

    async def get_streaming_stats(self) -> dict[str, Any]:
        """Get WebSocket streaming statistics."""
        result = await self._request("GET", "/api/v1/admin/health/streaming")
        return result

    # Quota Management

    async def reset_tenant_quota(self, tenant_id: UUID) -> dict[str, Any]:
        """Reset quota counters for a tenant."""
        result = await self._request("POST", f"/api/v1/admin/tenants/{tenant_id}/quota/reset")
        return result

    async def set_tenant_quota_override(
        self,
        tenant_id: UUID,
        daily_calls: int | None = None,
        concurrent_requests: int | None = None,
    ) -> dict[str, Any]:
        """Set custom quota overrides for a tenant."""
        data = {}
        if daily_calls is not None:
            data["daily_calls"] = daily_calls
        if concurrent_requests is not None:
            data["concurrent_requests"] = concurrent_requests
        result = await self._request("POST", f"/api/v1/admin/tenants/{tenant_id}/quota/override", json_data=data)
        return result

    # Billing

    async def get_tenant_billing(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get billing details for a tenant."""
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        result = await self._request("GET", f"/api/v1/admin/tenants/{tenant_id}/billing", params=params)
        return result

    async def export_usage_csv(
        self,
        start_date: datetime,
        end_date: datetime,
        tenant_ids: list[UUID] | None = None,
    ) -> bytes:
        """Export usage data as CSV."""
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        if tenant_ids:
            params["tenant_ids"] = ",".join(str(t) for t in tenant_ids)

        client = await self._get_client()
        response = await client.get("/api/v1/admin/export/usage", params=params)
        response.raise_for_status()
        return response.content

    # Alerts & Monitoring

    async def get_active_alerts(self) -> list[dict[str, Any]]:
        """Get active system alerts."""
        result = await self._request("GET", "/api/v1/admin/alerts")
        return result.get("alerts", [])

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        await self._request("POST", f"/api/v1/admin/alerts/{alert_id}/acknowledge")
        return True

    async def create_alert_rule(
        self,
        name: str,
        condition: str,
        threshold: float,
        severity: str = "warning",
        notification_channels: list[str] = None,
    ) -> dict[str, Any]:
        """Create a new alert rule."""
        data = {
            "name": name,
            "condition": condition,
            "threshold": threshold,
            "severity": severity,
            "notification_channels": notification_channels or ["email"],
        }
        result = await self._request("POST", "/api/v1/admin/alerts/rules", json_data=data)
        return result


class LocalAdminClient:
    """
    Local admin client for self-hosted deployments.

    Operates directly on local Redis/DB without HTTP calls.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        quota_manager: Any = None,
        metering_backend: Any = None,
        cache_backend: Any = None,
        stream_manager: Any = None,
        pat_storage: Any = None,
    ):
        self.redis_url = redis_url
        self.quota_manager = quota_manager
        self.metering_backend = metering_backend
        self.cache_backend = cache_backend
        self.stream_manager = stream_manager
        self.pat_storage = pat_storage
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def get_system_health(self) -> SystemHealthReport:
        """Get local system health."""
        r = await self._get_redis()

        # Collect metrics from various components
        total_keys = await r.dbsize()
        info = await r.info("memory")
        used_memory = info.get("used_memory_human", "unknown")

        # Get tenant count from quota keys
        tenant_keys = await r.keys("vninvest:quota:daily:*")
        tenant_ids = set()
        for key in tenant_keys:
            parts = key.split(":")
            if len(parts) >= 4:
                tenant_ids.add(parts[3])

        return SystemHealthReport(
            timestamp=datetime.utcnow(),
            total_tenants=len(tenant_ids),
            active_tenants=len(tenant_ids),  # Simplified
            total_calls_24h=0,  # Would need metering backend
            avg_latency_ms=0.0,
            error_rate_pct=0.0,
            provider_health={},
            cache_hit_rate_pct=0.0,
            active_streams=0,
            alerts=[],
        )

    async def get_tenant_usage(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> TenantUsageReport:
        """Get usage from local metering backend."""
        if self.metering_backend:
            metrics = await self.metering_backend.aggregate_usage(tenant_id, start_date, end_date)
            return TenantUsageReport(
                tenant_id=tenant_id,
                tenant_name=f"Tenant {str(tenant_id)[:8]}",
                tier=TenantTier.PRO,  # Would fetch from tenant store
                period_start=start_date,
                period_end=end_date,
                metrics=metrics,
                quota_utilization_pct=0.0,
            )
        return TenantUsageReport(
            tenant_id=tenant_id,
            tenant_name="Unknown",
            tier=TenantTier.FREE,
            period_start=start_date,
            period_end=end_date,
            metrics=UsageMetrics(tenant_id=tenant_id, period_start=start_date, period_end=end_date),
            quota_utilization_pct=0.0,
        )

    async def reset_tenant_quota(self, tenant_id: UUID) -> dict[str, Any]:
        """Reset local quota."""
        if self.quota_manager:
            self.quota_manager.reset_tenant_quota(tenant_id)
        return {"success": True, "tenant_id": str(tenant_id)}

    # PAT Management (Local)

    async def create_pat(
        self,
        tenant_id: UUID,
        user_id: UUID,
        name: str,
        scopes: list[PATScope],
        expires_in_days: int | None = 30,
    ) -> tuple[PersonalAccessToken, str]:
        """Create a new PAT locally."""
        if not self.pat_storage:
            raise RuntimeError("PATStorage not configured for LocalAdminClient")
        return await self.pat_storage.create_pat(
            tenant_id=tenant_id,
            user_id=user_id,
            name=name,
            scopes=scopes,
            expires_in_days=expires_in_days,
        )

    async def list_pats(
        self,
        tenant_id: UUID,
        user_id: UUID | None = None,
    ) -> list[PersonalAccessToken]:
        """List PATs locally."""
        if not self.pat_storage:
            raise RuntimeError("PATStorage not configured for LocalAdminClient")
        return await self.pat_storage.list_pats(tenant_id=tenant_id, user_id=user_id)

    async def revoke_pat(self, pat_id: UUID) -> bool:
        """Revoke a PAT locally."""
        if not self.pat_storage:
            raise RuntimeError("PATStorage not configured for LocalAdminClient")
        return await self.pat_storage.revoke_pat(pat_id)

    async def rotate_pat(
        self,
        pat_id: UUID,
        overlap_hours: int = 24,
    ) -> tuple[PersonalAccessToken, str]:
        """Rotate a PAT locally."""
        if not self.pat_storage:
            raise RuntimeError("PATStorage not configured for LocalAdminClient")
        return await self.pat_storage.rotate_pat(pat_id, overlap_hours)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
