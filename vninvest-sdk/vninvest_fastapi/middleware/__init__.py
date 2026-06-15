"""
FastAPI middleware package for Vninvest SDK.
"""

from .auth import (
    AuthMiddleware,
    get_api_key,
    get_tenant_context,
    require_admin_tenant,
    require_company_read,
    require_finance_read,
    require_news_read,
    require_quote_read,
    require_scope,
    require_stream_depth,
    require_stream_price,
    require_stream_trade,
)
from .metering import MeteringMiddleware, record_metering
from .quota import QuotaMiddleware, check_quota

__all__ = [
    # Auth
    "AuthMiddleware",
    "get_tenant_context",
    "get_api_key",
    "require_scope",
    "require_quote_read",
    "require_company_read",
    "require_finance_read",
    "require_news_read",
    "require_stream_price",
    "require_stream_depth",
    "require_stream_trade",
    "require_admin_tenant",
    # Quota
    "QuotaMiddleware",
    "check_quota",
    # Metering
    "MeteringMiddleware",
    "record_metering",
]
