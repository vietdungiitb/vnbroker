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

# Sử dụng các lớp từ vnbroker tiêu chuẩn
from .api.quote import Quote
from .api.company import Company
from .api.financial import Finance
from .api.listing import Listing
from .api.trading import Trading
from .api.screener import Screener
from .api.news import News
from .api.snapshot import MarketSnapshot
from .explorer.fmarket import Fund

# Market constants
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

__all__ = [
    "Vnbroker",
    "Quote",
    "Listing",
    "Company",
    "Finance",
    "Trading",
    "Screener",
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
