"""
FastAPI routes for quote data endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from vninvest import (
    QuoteRequest,
    TenantContext,
    VninvestClient,
    get_tenant_context,
    require_quote_read,
)

router = APIRouter(prefix="/quote", tags=["quote"])


class QuoteRequestModel(BaseModel):
    """Request model for quote endpoint."""
    symbols: list[str] = Field(..., min_length=1, description="List of stock symbols")
    interval: str = Field(default="1D", description="Time interval (1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M)")
    start_date: str | None = Field(default=None, description="Start date (YYYY-MM-DD)")
    end_date: str | None = Field(default=None, description="End date (YYYY-MM-DD)")
    count_back: int | None = Field(default=None, ge=1, description="Number of bars to look back")
    length: str | int | None = Field(default=None, description="Flexible lookback (e.g., '3M', '100b')")
    source: str = Field(default="AUTO", description="Data source (AUTO, VCI, KBS, MSN, TCBS, DNSE)")
    adjust_price: bool = Field(default=True, description="Adjust for splits/dividends")
    to_df: bool = Field(default=True, description="Return as DataFrame (True) or JSON (False)")


class QuoteResponseModel(BaseModel):
    """Response model for quote endpoint."""
    symbol: str
    data: list[dict] | dict  # JSON-serializable
    source_used: str
    fetched_at: str
    cache_hit: bool
    latency_ms: int
    row_count: int
    price_unit: str = "VND"


@router.post(
    "",
    response_model=list[QuoteResponseModel],
    summary="Get historical/intraday quote data",
    description="Retrieve quote data for one or more symbols. Requires quote:read scope.",
    dependencies=[Depends(require_quote_read)],
)
async def get_quote(
    request: QuoteRequestModel,
    http_request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> list[QuoteResponseModel]:
    """
    Get quote data for symbols.

    - **symbols**: List of stock symbols (e.g., ["ACB", "VCB"])
    - **interval**: Time interval (1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M)
    - **start_date**: Start date in YYYY-MM-DD format
    - **end_date**: End date in YYYY-MM-DD format
    - **count_back**: Number of bars to look back
    - **length**: Flexible lookback (e.g., "3M", "100b")
    - **source**: Data source (AUTO, VCI, KBS, MSN, TCBS, DNSE)
    - **adjust_price**: Adjust for splits/dividends
    - **to_df**: Return format (ignored in API, always returns JSON)
    """
    # Get or create VninvestClient from app state
    client: VninvestClient = http_request.app.state.vninvest_client

    # Convert to SDK request model
    sdk_request = QuoteRequest(
        symbols=request.symbols,
        interval=request.interval,
        start_date=request.start_date,
        end_date=request.end_date,
        count_back=request.count_back,
        length=request.length,
        source=request.source,
        adjust_price=request.adjust_price,
        to_df=request.to_df,
    )

    try:
        results = await client.quote(sdk_request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch quote data: {str(e)}",
        )

    # Convert to response models
    response_models = []
    for result in results:
        # Convert DataFrame to JSON-serializable format
        if hasattr(result.data, "to_dict"):
            data = result.data.to_dict(orient="records")
        else:
            data = result.data

        response_models.append(QuoteResponseModel(
            symbol=result.symbol,
            data=data,
            source_used=result.source_used,
            fetched_at=(
        result.fetched_at.isoformat()
        if hasattr(result.fetched_at, "isoformat")
        else str(result.fetched_at)
    ),
            cache_hit=result.cache_hit,
            latency_ms=result.latency_ms,
            row_count=result.row_count,
            price_unit=result.price_unit,
        ))

    # Store metadata for metering middleware
    http_request.state.provider_used = results[0].source_used if results else "unknown"
    http_request.state.symbols_accessed = request.symbols
    http_request.state.cache_hit = any(r.cache_hit for r in results)

    return response_models


@router.get(
    "/{symbol}",
    response_model=QuoteResponseModel,
    summary="Get quote data for a single symbol",
    description="Convenience endpoint for single symbol quote data. Requires quote:read scope.",
    dependencies=[Depends(require_quote_read)],
)
async def get_quote_single(
    symbol: str,
    http_request: Request,
    interval: str = Query(default="1D", description="Time interval"),
    start_date: str | None = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(default=None, description="End date (YYYY-MM-DD)"),
    count_back: int | None = Query(default=None, ge=1, description="Number of bars to look back"),
    length: str | int | None = Query(default=None, description="Flexible lookback"),
    source: str = Query(default="AUTO", description="Data source"),
    adjust_price: bool = Query(default=True, description="Adjust for splits/dividends"),
    context: TenantContext = Depends(get_tenant_context),
) -> QuoteResponseModel:
    """Get quote data for a single symbol."""
    request = QuoteRequestModel(
        symbols=[symbol.upper()],
        interval=interval,
        start_date=start_date,
        end_date=end_date,
        count_back=count_back,
        length=length,
        source=source,
        adjust_price=adjust_price,
    )
    results = await get_quote(request, http_request, context)
    return results[0]
