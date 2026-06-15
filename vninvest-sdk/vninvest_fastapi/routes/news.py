"""
FastAPI routes for news data endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from vninvest import (
    NewsRequest,
    TenantContext,
    VninvestClient,
    get_tenant_context,
    require_news_read,
)

router = APIRouter(prefix="/news", tags=["news"])


class NewsRequestModel(BaseModel):
    """Request model for news endpoint."""
    symbol: str | None = Field(default=None, description="Stock symbol filter")
    query: str | None = Field(default=None, description="Search query")
    sources: list[str] | None = Field(default=None, description="News sources filter")
    from_time: str | None = Field(default=None, description="From time (ISO format)")
    to_time: str | None = Field(default=None, description="To time (ISO format)")
    limit: int = Field(default=20, ge=1, le=100, description="Limit number of results")
    source: str = Field(default="AUTO", description="Data source (AUTO, VCI, KBS, MSN, TCBS, DNSE)")


@router.post(
    "",
    summary="Get news data",
    description="Retrieve news data. Requires news:read scope.",
    dependencies=[Depends(require_news_read)],
)
async def get_news(
    request: NewsRequestModel,
    http_request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> list[dict]:
    """
    Get news data.

    - **symbol**: Stock symbol filter (e.g., "ACB")
    - **query**: Search query
    - **sources**: News sources filter
    - **from_time**: From time in ISO format
    - **to_time**: To time in ISO format
    - **limit**: Limit number of results (1-100)
    - **source**: Data source (AUTO, VCI, KBS, MSN, TCBS, DNSE)
    """
    client: VninvestClient = http_request.app.state.vninvest_client

    sdk_request = NewsRequest(
        symbol=request.symbol.upper() if request.symbol else None,
        query=request.query,
        sources=request.sources,
        from_time=request.from_time,
        to_time=request.to_time,
        limit=request.limit,
        source=request.source,
    )

    try:
        result = await client.news(sdk_request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch news data: {str(e)}",
        )

    # Store metadata for metering middleware
    http_request.state.provider_used = "unknown"
    http_request.state.symbols_accessed = [request.symbol.upper()] if request.symbol else []

    return result


@router.get(
    "",
    summary="Get latest news",
    description="Convenience endpoint for latest news. Requires news:read scope.",
    dependencies=[Depends(require_news_read)],
)
async def get_latest_news(
    http_request: Request,
    symbol: str | None = Query(default=None, description="Stock symbol filter"),
    limit: int = Query(default=20, ge=1, le=100, description="Limit number of results"),
    source: str = Query(default="AUTO", description="Data source"),
    context: TenantContext = Depends(get_tenant_context),
) -> list[dict]:
    """Get latest news."""
    request = NewsRequestModel(
        symbol=symbol.upper() if symbol else None,
        limit=limit,
        source=source,
    )
    return await get_news(request, http_request, context)
