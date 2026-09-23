# Lazy import vnbroker to avoid circular import deadlock
_vnbroker = None


def _get_vnbroker():
    """Lazy load vnbroker class."""
    global _vnbroker
    if _vnbroker is None:
        from vnbroker.common.client import Vnbroker as _VnbrokerClass
        _vnbroker = _VnbrokerClass
    return _vnbroker


class Vnbroker:
    """Lazy proxy for vnbroker.common.client.Vnbroker to avoid circular import."""
    def __new__(cls, *args, **kwargs):
        actual_class = _get_vnbroker()
        return actual_class(*args, **kwargs)


# Market constants
from .constants import (  # noqa: E402
    INDICES_INFO,
    INDICES_MAP,
    INDEX_GROUPS,
    SECTOR_IDS,
    EXCHANGES,
)

# Load connector modules to register providers
from . import connector  # noqa: E402
from . import analytics  # noqa: E402

# Load explorer modules to register providers (lazy to avoid deadlock)
_explorer_modules_loaded = False


def _ensure_explorer_modules_loaded():
    """Lazy load explorer modules to avoid circular import deadlock."""
    global _explorer_modules_loaded
    if _explorer_modules_loaded:
        return
    try:
        from .explorer import vci, tcbs, kbs, rss_cafef, rss_vneconomy  # noqa: F401
        from .explorer import dnse  # noqa: F401 - DNSE provider registration
        _explorer_modules_loaded = True
    except Exception as e:
        _explorer_modules_loaded = True
        import warnings
        warnings.warn(f"Failed to load explorer modules: {e}", stacklevel=2)


__all__ = [
    "Vnbroker",
    "connector",
    "analytics",
    "UnifiedRegistry",
    "INDICES_INFO",
    "INDICES_MAP",
    "INDEX_GROUPS",
    "SECTOR_IDS",
    "EXCHANGES",
]

# Unified Registry
from .core.unified_registry import UnifiedRegistry  # noqa: E402

# Check for updates only if explicitly enabled via environment variable
import os  # noqa: E402
if os.getenv("VNBROKER_CHECK_UPDATES") == "1" and not os.getenv("PYTEST_RUNNING"):
    try:
        from vnbroker.core.utils.upgrade import update_notice
        update_notice(verbose=False)
    except Exception:
        pass
