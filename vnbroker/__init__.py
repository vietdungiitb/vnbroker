# Lazy import vnbroker to avoid circular import deadlock
_vnbroker = None

def _get_vnbroker():
    """Lazy load vnbroker class."""
    global _vnbroker
    if _vnbroker is None:
        from vnbroker.common.client import Vnbroker as _VnbrokerClass
        _vnbroker = _VnbrokerClass
    return _vnbroker

# Create a lazy proxy for vnbroker
class Vnbroker:
    """Lazy proxy for vnbroker.common.client.vnbroker to avoid circular import."""
    def __new__(cls, *args, **kwargs):
        actual_class = _get_vnbroker()
        return actual_class(*args, **kwargs)

# Market constants (read-only, no PAT needed)
from .constants import (
    INDICES_INFO,
    INDICES_MAP,
    INDEX_GROUPS,
    SECTOR_IDS,
    EXCHANGES,
)

# Load connector modules to register providers
# Tải các module connector để đăng ký các provider
from . import connector

# Load explorer modules to register providers (lazy to avoid deadlock)
# Tải các module explorer để đăng ký các provider (lazy để tránh deadlock)
_explorer_modules_loaded = False

def _ensure_explorer_modules_loaded():
    """Lazy load explorer modules to avoid circular import deadlock."""
    global _explorer_modules_loaded
    if _explorer_modules_loaded:
        return
    try:
        from .explorer import vci, tcbs, msn, kbs, rss_cafef, rss_vneconomy  # noqa: F401
        from .explorer import dnse  # noqa: F401  – DNSE provider registration
        _explorer_modules_loaded = True
    except Exception as e:
        _explorer_modules_loaded = True  # Mark as loaded to avoid retry loops
        import warnings
        warnings.warn(f"Failed to load explorer modules: {e}", stacklevel=2)

# ============================================================
# PAT-Only Architecture: Direct API access is DEPRECATED
# All data access MUST go through Vnbroker with valid PAT
# ============================================================

import warnings as _warnings

def _deprecated_direct_access(class_name: str):
    """Raise deprecation warning for direct low-level API access."""
    _warnings.warn(
        f"Direct access to '{class_name}' is DEPRECATED and will be removed in v2.0. "
        f"All data access must go through Vnbroker with a valid PAT key. "
        f"Use: Vnbroker(pat_key='vninvest_pat_...').stock('SYMBOL').{class_name.lower()}()",
        DeprecationWarning,
        stacklevel=3
    )

# Lazy deprecated proxies for backward compatibility (will be removed in v2.0)
class _DeprecatedQuote:
    def __new__(cls, *args, **kwargs):
        _deprecated_direct_access("Quote")
        from .api.quote import Quote as _Quote
        return _Quote(*args, **kwargs)

class _DeprecatedCompany:
    def __new__(cls, *args, **kwargs):
        _deprecated_direct_access("Company")
        from .api.company import Company as _Company
        return _Company(*args, **kwargs)

class _DeprecatedFinance:
    def __new__(cls, *args, **kwargs):
        _deprecated_direct_access("Finance")
        from .api.financial import Finance as _Finance
        return _Finance(*args, **kwargs)

class _DeprecatedListing:
    def __new__(cls, *args, **kwargs):
        _deprecated_direct_access("Listing")
        from .api.listing import Listing as _Listing
        return _Listing(*args, **kwargs)

class _DeprecatedTrading:
    def __new__(cls, *args, **kwargs):
        _deprecated_direct_access("Trading")
        from .api.trading import Trading as _Trading
        return _Trading(*args, **kwargs)



class _DeprecatedNews:
    def __new__(cls, *args, **kwargs):
        _deprecated_direct_access("News")
        from .api.news import News as _News
        return _News(*args, **kwargs)

class _DeprecatedMarketSnapshot:
    def __new__(cls, *args, **kwargs):
        _deprecated_direct_access("MarketSnapshot")
        from .api.snapshot import MarketSnapshot as _MarketSnapshot
        return _MarketSnapshot(*args, **kwargs)

class _DeprecatedFund:
    def __new__(cls, *args, **kwargs):
        _deprecated_direct_access("Fund")
        from .explorer.fmarket import Fund as _Fund
        return _Fund(*args, **kwargs)

# Export deprecated classes with warning
Quote = _DeprecatedQuote
Company = _DeprecatedCompany
Finance = _DeprecatedFinance
Listing = _DeprecatedListing
Trading = _DeprecatedTrading

News = _DeprecatedNews
MarketSnapshot = _DeprecatedMarketSnapshot
Fund = _DeprecatedFund

__all__ = [
    "Vnbroker",  # ONLY supported entry point
    # Deprecated (will be removed in v2.0):
    "Quote",
    "Listing",
    "Company",
    "Finance",
    "Trading",
    "News",
    "MarketSnapshot",
    "Fund",
    "connector",
    "INDICES_INFO",
    "INDICES_MAP",
    "INDEX_GROUPS",
    "SECTOR_IDS",
    "EXCHANGES",
]

# Lazy check for dependency compatibility (non-blocking, compact output)
try:
    from vnbroker.core.utils.upgrade import update_notice
    update_notice(verbose=False)
except Exception:
    # Silently fail if notice check has any issues
    pass
