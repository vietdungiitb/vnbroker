"""
vnbroker/explorer/ssi/__init__.py

SSI explorer providers (market-data lane, source="SSI").
Registration into ProviderRegistry happens on import (see _ensure_explorer_modules_loaded).
"""

from vnbroker.explorer.ssi._auth import (
    SSIExplorerSession,
    get_shared_session,
    reset_shared_sessions,
    resolve_credentials,
)
from vnbroker.explorer.ssi.company import SSICompany
from vnbroker.explorer.ssi.financial import SSIFinancial
from vnbroker.explorer.ssi.listing import SSIListing
from vnbroker.explorer.ssi.news import SSINews
from vnbroker.explorer.ssi.quote import SSIQuote
from vnbroker.explorer.ssi.trading import SSITrading

__all__ = [
    "SSICompany",
    "SSIExplorerSession",
    "SSIFinancial",
    "SSIListing",
    "SSINews",
    "SSIQuote",
    "SSITrading",
    "get_shared_session",
    "reset_shared_sessions",
    "resolve_credentials",
]
