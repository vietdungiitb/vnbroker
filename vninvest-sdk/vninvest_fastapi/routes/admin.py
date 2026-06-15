"""
FastAPI routes for admin endpoints.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from vninvest import (
    AdminClient,
    LocalAdminClient,
    SystemHealthReport,
    TenantContext,
    TenantPlan,
    TenantTier,
    TenantUsageReport,
    get_tenant_context,
    require_admin_tenant,
)
from vninvest.models import PATScope as PATScopeModel

router = APIRouter(prefix="/admin", tags=["admin"])


# Request/Response Models

class CreateTenantRequest(BaseModel):
    name: str
    plan: TenantTier = TenantTier.FREE
    email: str | None = None
    custom_limits: dict | None = None
    metadata: dict | None = None


class UpdateTenantRequest(BaseModel):
    name: str | None = None
    plan: TenantTier | None = None
    status: str | None = None
    custom_limits: dict | None = None
    metadata: dict | None = None


class CreatePATRequest(BaseModel):
    tenant_id: UUID
    user_id: UUID
    name: str
    scopes: list[PATScopeModel]
    expires_in_days: int | None = 30


class RotatePATRequest(BaseModel):
    pat_id: UUID
    overlap_hours: int = 24


class TenantResponse(BaseModel):
    tenant_id: UUID
    api_key_hash: str
    plan: TenantPlan
    tier: TenantTier
    status: str
    metadata: dict


class PATResponse(BaseModel):
    pat_id: UUID
    tenant_id: UUID
    user_id: UUID
    name: str
    prefix: str
    scopes: list[PATScopeModel]
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    is_active: bool


# Dependency to get admin client
def get_admin_client(request: Request) -> AdminClient | LocalAdminClient:
    """Get admin client from app state."""
    if hasattr(request.app.state, "admin_client"):
        return request.app.state.admin_client
    if hasattr(request.app.state, "local_admin_client"):
        return request.app.state.local_admin_client
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Admin client not configured",
    )


# Tenant Management

@router.post(
    "/tenants",
    response_model=TenantResponse,
    summary="Create a new tenant",
    dependencies=[Depends(require_admin_tenant)],
)
async def create_tenant(
    request: CreateTenantRequest,
    http_request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> TenantResponse:
    """Create a new tenant."""
    admin = get_admin_client(http_request)
    try:
        tenant = await admin.create_tenant(
            name=request.name,
            plan=request.plan,
            email=request.email,
            custom_limits=request.custom_limits,
            metadata=request.metadata,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tenant: {str(e)}",
        )

    return TenantResponse(
        tenant_id=tenant.tenant_id,
        api_key_hash=tenant.api_key_hash,
        plan=tenant.plan,
        tier=tenant.tier,
        status=tenant.status,
        metadata=tenant.metadata,
    )


@router.get(
    "/tenants/{tenant_id}",
    response_model=TenantResponse,
    summary="Get tenant details",
    dependencies=[Depends(require_admin_tenant)],
)
async def get_tenant(
    tenant_id: UUID,
    http_request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> TenantResponse:
    """Get tenant details."""
    admin = get_admin_client(http_request)
    try:
        tenant = await admin.get_tenant(tenant_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant not found: {str(e)}",
        )

    return TenantResponse(
        tenant_id=tenant.tenant_id,
        api_key_hash=tenant.api_key_hash,
        plan=tenant.plan,
        tier=tenant.tier,
        status=tenant.status,
        metadata=tenant.metadata,
    )


@router.patch(
    "/tenants/{tenant_id}",
    response_model=TenantResponse,
    summary="Update tenant",
    dependencies=[Depends(require_admin_tenant)],
)
async def update_tenant(
    tenant_id: UUID,
    request: UpdateTenantRequest,
    http_request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> TenantResponse:
    """Update tenant configuration."""
    admin = get_admin_client(http_request)
    try:
        tenant = await admin.update_tenant(
            tenant_id=tenant_id,
            name=request.name,
            plan=request.plan,
            status=request.status,
            custom_limits=request.custom_limits,
            metadata=request.metadata,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tenant: {str(e)}",
        )

    return TenantResponse(
        tenant_id=tenant.tenant_id,
        api_key_hash=tenant.api_key_hash,
        plan=tenant.plan,
        tier=tenant.tier,
        status=tenant.status,
        metadata=tenant.metadata,
    )


@router.delete(
    "/tenants/{tenant_id}",
    summary="Delete tenant",
    dependencies=[Depends(require_admin_tenant)],
)
async def delete_tenant(
    tenant_id: UUID,
    http_request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    """Delete a tenant (soft delete)."""
    admin = get_admin_client(http_request)
    try:
        await admin.delete_tenant(tenant_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete tenant: {str(e)}",
        )

    return {"success": True, "tenant_id": str(tenant_id)}


@router.get(
    "/tenants",
    response_model=list[TenantResponse],
    summary="List tenants",
    dependencies=[Depends(require_admin_tenant)],
)
async def list_tenants(
    http_request: Request,
    status: str | None = Query(default=None),
    plan: TenantTier | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_tenant_context),
) -> list[TenantResponse]:
    """List tenants with filters."""
    admin = get_admin_client(http_request)
    try:
        tenants = await admin.list_tenants(
            status=status,
            plan=plan,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tenants: {str(e)}",
        )

    return [
        TenantResponse(
            tenant_id=t.tenant_id,
            api_key_hash=t.api_key_hash,
            plan=t.plan,
            tier=t.tier,
            status=t.status,
            metadata=t.metadata,
        )
        for t in tenants
    ]


@router.post(
    "/tenants/{tenant_id}/regenerate-key",
    summary="Regenerate API key for tenant",
    dependencies=[Depends(require_admin_tenant)],
)
async def regenerate_api_key(
    tenant_id: UUID,
    http_request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    """Regenerate API key for a tenant."""
    admin = get_admin_client(http_request)
    try:
        api_key = await admin.regenerate_api_key(tenant_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate API key: {str(e)}",
        )

    return {"api_key": api_key}


# PAT Management

@router.post(
    "/pats",
    response_model=PATResponse,
    summary="Create a new PAT",
    dependencies=[Depends(require_admin_tenant)],
)
async def create_pat(
    request: CreatePATRequest,
    http_request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> PATResponse:
    """Create a new Personal Access Token."""
    admin = get_admin_client(http_request)
    try:
        pat, plaintext = await admin.create_pat(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            name=request.name,
            scopes=request.scopes,
            expires_in_days=request.expires_in_days,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create PAT: {str(e)}",
        )

    return PATResponse(
        pat_id=pat.pat_id,
        tenant_id=pat.tenant_id,
        user_id=pat.user_id,
        name=pat.name,
        prefix=pat.prefix,
        scopes=pat.scopes,
        expires_at=pat.expires_at,
        last_used_at=pat.last_used_at,
        revoked_at=pat.revoked_at,
        created_at=pat.created_at,
        is_active=pat.is_active,
    )


@router.get(
    "/pats",
    response_model=list[PATResponse],
    summary="List PATs",
    dependencies=[Depends(require_admin_tenant)],
)
async def list_pats(
    http_request: Request,
    tenant_id: UUID = Query(...),
    user_id: UUID | None = Query(default=None),
    context: TenantContext = Depends(get_tenant_context),
) -> list[PATResponse]:
    """List PATs for a tenant."""
    admin = get_admin_client(http_request)
    try:
        pats = await admin.list_pats(tenant_id=tenant_id, user_id=user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list PATs: {str(e)}",
        )

    return [
        PATResponse(
            pat_id=pat.pat_id,
            tenant_id=pat.tenant_id,
            user_id=pat.user_id,
            name=pat.name,
            prefix=pat.prefix,
            scopes=pat.scopes,
            expires_at=pat.expires_at,
            last_used_at=pat.last_used_at,
            revoked_at=pat.revoked_at,
            created_at=pat.created_at,
            is_active=pat.is_active,
        )
        for pat in pats
    ]


@router.post(
    "/pats/{pat_id}/revoke",
    summary="Revoke a PAT",
    dependencies=[Depends(require_admin_tenant)],
)
async def revoke_pat(
    pat_id: UUID,
    http_request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    """Revoke a PAT."""
    admin = get_admin_client(http_request)
    try:
        result = await admin.revoke_pat(pat_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke PAT: {str(e)}",
        )

    return {"success": result, "pat_id": str(pat_id)}


@router.post(
    "/pats/{pat_id}/rotate",
    response_model=PATResponse,
    summary="Rotate a PAT",
    dependencies=[Depends(require_admin_tenant)],
)
async def rotate_pat(
    pat_id: UUID,
    request: RotatePATRequest,
    http_request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> PATResponse:
    """Rotate a PAT (create new one with overlap period)."""
    admin = get_admin_client(http_request)
    try:
        new_pat, plaintext = await admin.rotate_pat(pat_id, overlap_hours=request.overlap_hours)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rotate PAT: {str(e)}",
        )

    return PATResponse(
        pat_id=new_pat.pat_id,
        tenant_id=new_pat.tenant_id,
        user_id=new_pat.user_id,
        name=new_pat.name,
        prefix=new_pat.prefix,
        scopes=new_pat.scopes,
        expires_at=new_pat.expires_at,
        last_used_at=new_pat.last_used_at,
        revoked_at=new_pat.revoked_at,
        created_at=new_pat.created_at,
        is_active=new_pat.is_active,
    )


# Usage Reporting

@router.get(
    "/tenants/{tenant_id}/usage",
    response_model=TenantUsageReport,
    summary="Get tenant usage report",
    dependencies=[Depends(require_admin_tenant)],
)
async def get_tenant_usage(
    tenant_id: UUID,
    http_request: Request,
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    context: TenantContext = Depends(get_tenant_context),
) -> TenantUsageReport:
    """Get usage report for a tenant."""
    admin = get_admin_client(http_request)
    try:
        report = await admin.get_tenant_usage(tenant_id, start_date, end_date)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get usage report: {str(e)}",
        )

    return report


@router.get(
    "/system/health",
    response_model=SystemHealthReport,
    summary="Get system health",
    dependencies=[Depends(require_admin_tenant)],
)
async def get_system_health(
    http_request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> SystemHealthReport:
    """Get system health report."""
    admin = get_admin_client(http_request)
    try:
        health = await admin.get_system_health()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system health: {str(e)}",
        )

    return health


@router.get(
    "/export/usage",
    summary="Export usage as CSV",
    dependencies=[Depends(require_admin_tenant)],
)
async def export_usage_csv(
    http_request: Request,
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    tenant_ids: list[UUID] | None = Query(default=None),
    context: TenantContext = Depends(get_tenant_context),
):
    """Export usage data as CSV."""
    admin = get_admin_client(http_request)
    try:
        csv_data = await admin.export_usage_csv(start_date, end_date, tenant_ids)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export usage: {str(e)}",
        )

    from fastapi.responses import Response

    filename = f"usage_{start_date.date()}_{end_date.date()}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# Quota Management

@router.post(
    "/tenants/{tenant_id}/quota/reset",
    summary="Reset tenant quota",
    dependencies=[Depends(require_admin_tenant)],
)
async def reset_tenant_quota(
    tenant_id: UUID,
    http_request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    """Reset quota for a tenant."""
    admin = get_admin_client(http_request)
    try:
        result = await admin.reset_tenant_quota(tenant_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset quota: {str(e)}",
        )

    return result
