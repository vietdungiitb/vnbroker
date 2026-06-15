"""
FastAPI routes package for Vninvest SDK.
"""

from .admin import router as admin_router
from .company import router as company_router
from .finance import router as finance_router
from .news import router as news_router
from .quote import router as quote_router
from .stream import router as stream_router

__all__ = [
    "quote_router",
    "company_router",
    "finance_router",
    "news_router",
    "stream_router",
    "admin_router",
]
