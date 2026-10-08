"""
Provider Registry System for vnbroker.

Hệ thống đăng ký cho phép các provider (VCI, TCBS, DNSE, ...)
tự đăng ký để trở thành available data source.

Module này cho phép:
- Đăng ký provider từ bất kỳ thư mục (explorer/, connector/, ...)
- Tìm kiếm provider theo provider_type và source name
- Liệt kê tất cả available providers
"""

from typing import Dict, Tuple, Type, List, Optional
from logging import getLogger

logger = getLogger(__name__)

# --------------------------------------------------------------------------
# Lazy discovery (T1)
#
# Providers self-register as an *import side effect* of their module
# (``vnbroker/explorer/<source>/<module>.py`` bottom line). Nothing reachable
# from ``import vnbroker`` imports those modules, so the registry stayed
# empty until some unrelated code happened to touch ``explorer/*`` first.
# ``get()`` then raised ``ValueError`` for perfectly valid providers, which is
# what silently emptied the bulk path.
#
# ``_auto_loaded`` memoises what the loader discovered so a later ``clear()``
# (tests) is repaired on the next lookup instead of staying broken forever —
# re-running the loader would not help, ``sys.modules`` caches the modules and
# their bottom-line ``register()`` calls would not execute a second time.
# --------------------------------------------------------------------------
_auto_loaded: Dict[Tuple[str, str], Type] = {}
_load_attempted = False
_loading = False


def _ensure_providers_loaded() -> None:
    """Import the provider packages so their ``register()`` calls run.

    Uses the same lazy loader ``vnbroker.api.quote.Quote.__init__`` already
    uses, so the explorer module list stays owned by ``vnbroker/__init__.py``.
    """
    global _load_attempted, _loading
    if _loading:
        # Re-entrant call while the loader is running: the registry is being
        # filled right now, a nested lookup must not recurse.
        return

    if _auto_loaded:
        # Heal a ``clear()`` without clobbering deliberate overrides.
        for key, provider_class in _auto_loaded.items():
            ProviderRegistry._registry.setdefault(key, provider_class)
        return

    if _load_attempted:
        return

    import vnbroker as _vnbroker

    loader = getattr(_vnbroker, "_ensure_explorer_modules_loaded", None)
    if loader is None:
        # ``vnbroker`` is still executing its own ``__init__`` (this lookup
        # came from a module it imports). Leave ``_load_attempted`` False so
        # the next call retries once the loader exists.
        return

    _load_attempted = True
    _loading = True
    try:
        loader()
    except Exception as exc:  # pragma: no cover - loader swallows its own
        logger.debug("Lazy provider discovery failed: %s", exc)
    finally:
        _loading = False

    _auto_loaded.update(ProviderRegistry._registry)


class ProviderRegistry:
    """
    Registry for vnbroker data providers.
    
    Cho phép registration của các provider class từ các nguồn khác nhau:
    - vnbroker.explorer.* (VCI, TCBS, ...) - Web scraping
    - vnbroker.connector.* (DNSE, Binance, ...) - REST API
    """
    
    # Registry structure: {(provider_type, source_name_lower): provider_class}
    _registry: Dict[Tuple[str, str], Type] = {}
    
    @classmethod
    def register(
        cls,
        provider_type: str,
        source_name: str,
        provider_class: Type
    ) -> None:
        """
        Register a provider class.

        Tham số:
            provider_type (str): Type của provider
                                 (quote, company, financial, etc.)
            source_name (str): Tên nguồn dữ liệu
                              (vci, fmp, tcbs, msn, kbs, etc.)
            provider_class (Type): Class của provider
            
        Ví dụ:
            ProviderRegistry.register('quote', 'fmp', FMPQuote)
            ProviderRegistry.register('quote', 'vci', VCIQuote)
            ProviderRegistry.register('quote', 'kbs', KBSQuote)
        """
        key = (provider_type, source_name.lower())
        cls._registry[key] = provider_class
        logger.debug(
            f"✓ Provider registered: {provider_type}/{source_name} "
            f"-> {provider_class.__module__}.{provider_class.__name__}"
        )
    
    @classmethod
    def get(
        cls,
        provider_type: str,
        source_name: str
    ) -> Optional[Type]:
        """
        Get a provider class by type and source name.
        
        Tham số:
            provider_type (str): Type của provider (quote, company, etc.)
            source_name (str): Tên nguồn dữ liệu
            
        Returns:
            Type: Provider class nếu được tìm thấy
            
        Raises:
            ValueError: Nếu provider không được tìm thấy
        """
        key = (provider_type, source_name.lower())
        
        if key not in cls._registry:
            _ensure_providers_loaded()
        if key not in cls._registry:
            available = cls.list_available(provider_type)
            raise ValueError(
                f"Provider '{provider_type}/{source_name}' not found. "
                f"Available: {available}"
            )
        
        return cls._registry[key]
    
    @classmethod
    def list_available(cls, provider_type: str) -> List[str]:
        """
        List all available source names cho một provider type.
        
        Tham số:
            provider_type (str): Type của provider
            
        Returns:
            List[str]: Danh sách source names (sắp xếp)
        """
        _ensure_providers_loaded()
        names = sorted({
            source for ptype, source in cls._registry
            if ptype == provider_type
        })
        return names
    
    @classmethod
    def list_all(cls) -> Dict[str, List[str]]:
        """
        List tất cả registered providers, grouped by type.
        
        Returns:
            Dict[str, List[str]]: {provider_type: [source_names]}
        """
        _ensure_providers_loaded()
        result: Dict[str, List[str]] = {}
        for ptype, source in cls._registry:
            if ptype not in result:
                result[ptype] = []
            result[ptype].append(source)
        
        # Sort sources trong mỗi type
        for ptype in result:
            result[ptype].sort()
        
        return result
    
    @classmethod
    def is_registered(cls, provider_type: str, source_name: str) -> bool:
        """
        Check xem provider có được register không.
        
        Tham số:
            provider_type (str): Type của provider
            source_name (str): Tên nguồn dữ liệu
            
        Returns:
            bool: True nếu provider được register
        """
        key = (provider_type, source_name.lower())
        if key not in cls._registry:
            _ensure_providers_loaded()
        return key in cls._registry
    
    @classmethod
    def clear(cls) -> None:
        """
        Clear tất cả registered providers. Chủ yếu dùng cho testing.

        Lookup sau ``clear()`` vẫn tự nạp lại các provider đã auto-discover
        (xem ``_ensure_providers_loaded``).
        """
        cls._registry.clear()
        logger.debug("Registry cleared")
    
    @classmethod
    def debug_info(cls) -> str:
        """
        Get debug info về registry state.
        
        Returns:
            str: Debug info
        """
        info = []
        info.append("=" * 60)
        info.append("PROVIDER REGISTRY DEBUG INFO")
        info.append("=" * 60)
        
        all_providers = cls.list_all()
        if not all_providers:
            info.append("(Registry empty)")
        else:
            for provider_type in sorted(all_providers.keys()):
                sources = all_providers[provider_type]
                info.append(f"\n[{provider_type}]")
                for source in sources:
                    provider_class = cls.get(provider_type, source)
                    info.append(
                        f"  • {source:12} -> "
                        f"{provider_class.__module__}.{provider_class.__name__}"
                    )
        
        info.append("\n" + "=" * 60)
        return "\n".join(info)
