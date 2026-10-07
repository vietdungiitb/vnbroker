# Version — nguồn duy nhất là `pyproject.toml`, đọc qua metadata của distribution.
#
# KHÔNG hardcode chuỗi version ở đây. Bản cài từ wheel luôn có metadata nên giá
# trị luôn khớp `pyproject.toml`; hardcode sẽ tạo nguồn sự thật thứ hai và lệch
# âm thầm ở lần bump đầu tiên (người dùng thấy `pip show` một đằng, `__version__`
# một nẻo). `scripts/check_version_sync.py` cũng cấm literal version trong tests/.
try:
    from importlib.metadata import version as _distribution_version

    __version__ = _distribution_version("vnbroker")
except Exception:  # pragma: no cover - chạy trực tiếp từ source chưa cài, hoặc metadata hỏng
    # Bắt rộng có chủ đích: đây chỉ là một chuỗi version, KHÔNG được làm
    # `import vnbroker` nổ. Giá trị dự phòng cố tình trông giả để không ai
    # nhầm nó là bản phát hành thật.
    __version__ = "0.0.0.dev0"

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
        from .explorer import ssi  # noqa: F401 - SSI provider registration
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
    "__version__",
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
