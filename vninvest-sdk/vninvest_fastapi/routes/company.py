"""
FastAPI routes for company data endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from vninvest import (
    CompanyRequest,
    TenantContext,
    VninvestClient,
    get_tenant_context,
    require_company_read,
)

router = APIRouter(prefix="/company", tags=["company"])


class CompanyRequestModel(BaseModel):
    """Request model for company endpoint."""
    symbol: str = Field(..., description="Stock symbol")
    source: str = Field(default="AUTO", description="Data source (AUTO, VCI, KBS, MSN, TCBS, DNSE)")
    include_overview: bool = Field(default=True, description="Include company overview")
    include_profile: bool = Field(default=True, description="Include company profile")
    include_shareholders: bool = Field(default=False, description="Include shareholders")
    include_insiders: bool = Field(default=False, description="Include insiders")
    include_subsidiaries: bool = Field(default=False, description="Include subsidiaries")
    include_officers: bool = Field(default=False, description="Include officers")
    include_events: bool = Field(default=False, description="Include events")


@router.post(
    "",
    summary="Get company data",
    description=(
        "Retrieve company data (overview, profile, shareholders, etc.). "
        "Requires company:read scope."
    ),
    dependencies=[Depends(require_company_read)],
)
async def get_company(
    request: CompanyRequestModel,
    http_request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    """
    Get company data for a symbol.

    - **symbol**: Stock symbol (e.g., "ACB")
    - **source**: Data source (AUTO, VCI, KBS, MSN, TCBS, DNSE)
    - **include_overview**: Include company overview
    - **include_profile**: Include company profile
    - **include_shareholders**: Include shareholders
    - **include_insiders**: Include insiders
    - **include_subsidiaries**: Include subsidiaries
    - **include_officers**: Include officers
    - **include_events**: Include events
    """
    client: VninvestClient = http_request.app.state.vninvest_client

    sdk_request = CompanyRequest(
        symbol=request.symbol.upper(),
        source=request.source,
        include_overview=request.include_overview,
        include_profile=request.include_profile,
        include_shareholders=request.include_shareholders,
        include_insiders=request.include_insiders,
        include_subsidiaries=request.include_subsidiaries,
        include_officers=request.include_officers,
        include_events=request.include_events,
    )

    try:
        result = await client.company(sdk_request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch company data: {str(e)}",
        )

    # Store metadata for metering middleware
    http_request.state.provider_used = "unknown"  # Would be set by client
    http_request.state.symbols_accessed = [request.symbol.upper()]

    return result


@router.get(
    "/{symbol}",
    summary="Get company overview",
    description="Convenience endpoint for company overview. Requires company:read scope.",
    dependencies=[Depends(require_company_read)],
)
async def get_company_overview(
    symbol: str,
    http_request: Request,
    source: str = Query(default="AUTO", description="Data source"),
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    """Get company overview for a symbol."""
    request = CompanyRequestModel(
        symbol=symbol.upper(),
        source=source,
        include_overview=True,
        include_profile=False,
        include_shareholders=False,
        include_insiders=False,
        include_subsidiaries=False,
        include_officers=False,
        include_events=False,
    )
    return await get_company(request, http_request, context)
