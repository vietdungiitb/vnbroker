"""
FastAPI routes for financial data endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from vninvest import (
    FinanceRequest,
    TenantContext,
    VninvestClient,
    get_tenant_context,
    require_finance_read,
)

router = APIRouter(prefix="/finance", tags=["finance"])


class FinanceRequestModel(BaseModel):
    """Request model for finance endpoint."""
    symbol: str = Field(..., description="Stock symbol")
    source: str = Field(default="AUTO", description="Data source (AUTO, VCI, KBS, MSN, TCBS, DNSE)")
    report_type: str = Field(default="all", description="Report type: income_statement, balance_sheet, cash_flow, ratio, or all")
    period: str = Field(default="quarterly", description="Period: quarterly or yearly")
    language: str = Field(default="vi", description="Language: vi or en")
    limit: int | None = Field(default=None, ge=1, description="Limit number of reports")


@router.post(
    "",
    summary="Get financial data",
    description=(
        "Retrieve financial data (income statement, balance sheet, "
        "cash flow, ratios). Requires finance:read scope."
    ),
    dependencies=[Depends(require_finance_read)],
)
async def get_finance(
    request: FinanceRequestModel,
    http_request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    """
    Get financial data for a symbol.

    - **symbol**: Stock symbol (e.g., "ACB")
    - **source**: Data source (AUTO, VCI, KBS, MSN, TCBS, DNSE)
    - **report_type**: income_statement, balance_sheet, cash_flow, ratio, or all
    - **period**: quarterly or yearly
    - **language**: vi or en
    - **limit**: Limit number of reports
    """
    client: VninvestClient = http_request.app.state.vninvest_client

    sdk_request = FinanceRequest(
        symbol=request.symbol.upper(),
        source=request.source,
        report_type=request.report_type,
        period=request.period,
        language=request.language,
        limit=request.limit,
    )

    try:
        result = await client.finance(sdk_request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch financial data: {str(e)}",
        )

    # Store metadata for metering middleware
    http_request.state.provider_used = "unknown"
    http_request.state.symbols_accessed = [request.symbol.upper()]

    return result


@router.get(
    "/{symbol}",
    summary="Get financial reports",
    description="Convenience endpoint for financial reports. Requires finance:read scope.",
    dependencies=[Depends(require_finance_read)],
)
async def get_finance_reports(
    symbol: str,
    http_request: Request,
    report_type: str = Query(default="all", description="Report type"),
    period: str = Query(default="quarterly", description="Period: quarterly or yearly"),
    language: str = Query(default="vi", description="Language: vi or en"),
    limit: int | None = Query(default=None, ge=1, description="Limit number of reports"),
    source: str = Query(default="AUTO", description="Data source"),
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    """Get financial reports for a symbol."""
    request = FinanceRequestModel(
        symbol=symbol.upper(),
        source=source,
        report_type=report_type,
        period=period,
        language=language,
        limit=limit,
    )
    return await get_finance(request, http_request, context)
