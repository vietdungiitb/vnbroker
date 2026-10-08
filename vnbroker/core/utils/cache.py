"""
TTL-based in-memory cache for vnbroker.

Provides thread-safe caching with time-to-live expiration for
listing data, industry mappings, and other static/reference data.
"""

import datetime
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, TypeVar, Generic, Callable
from functools import wraps

from vnbroker.config import Config
from vnbroker.core.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')

#: Types whose ``str()`` is a stable, address-free representation.
PRIMITIVES = (str, int, float, bool, type(None))


def _encode_value(value: Any) -> str:
    """Encode one argument into a deterministic, address-free token.

    Every branch keeps the value's information, so different arguments cannot
    share a token. The same value always yields the same token, so equal
    arguments still share a key and the cache still hits.

    Domain objects with a custom ``__str__`` collapse to their *type name*
    on purpose: their ``str()`` usually embeds a memory address, which would
    make every call look like a different argument and empty the cache.
    """
    if isinstance(value, PRIMITIVES):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return f"{type(value).__name__}:{bytes(value).hex()}"
    if isinstance(value, (list, tuple)):
        inner = ",".join(_encode_value(item) for item in value)
        return f"{type(value).__name__}:{len(value)}:[{inner}]"
    if isinstance(value, (set, frozenset)):
        inner = ",".join(sorted(_encode_value(item) for item in value))
        return f"{type(value).__name__}:{len(value)}:{{{inner}}}"
    if isinstance(value, dict):
        # Sorted by encoded key so insertion order cannot change the key.
        items = sorted(value.items(), key=lambda item: _encode_value(item[0]))
        inner = ",".join(f"{_encode_value(k)}={_encode_value(v)}" for k, v in items)
        return f"{type(value).__name__}:{len(value)}:{{{inner}}}"
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return f"{type(value).__name__}:{value.isoformat()}"
    if isinstance(value, datetime.timedelta):
        return f"timedelta:{value.total_seconds()}"
    return type(value).__name__


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with value and expiration timestamp."""
    value: T
    expires_at: float
    
    def is_expired(self) -> bool:
        return time.monotonic() > self.expires_at


class TTLCache(Generic[T]):
    """
    Thread-safe TTL cache with automatic expiration.
    
    Features:
    - Time-to-live expiration
    - Thread-safe operations
    - Automatic cleanup of expired entries
    - Configurable max size with LRU eviction
    """
    
    def __init__(
        self,
        ttl_seconds: int = 3600,
        max_size: int = 128,
        name: str = "cache"
    ):
        self._ttl_seconds = ttl_seconds
        self._max_size = max_size
        self._name = name
        self._cache: Dict[str, CacheEntry[T]] = {}
        self._lock = threading.RLock()
        self._access_times: Dict[str, float] = {}
        self._hit_count = 0
        self._total_count = 0
    
    def _make_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments.

        Every argument contributes to the key. Dropping the non-primitive ones
        made calls with different ``date``/``list``/``dict`` arguments share a
        single entry, so the cache silently served one call's payload for
        another call's arguments.
        """
        key_parts = [_encode_value(arg) for arg in args]
        key_parts.extend(
            f"{name}={_encode_value(value)}"
            for name, value in sorted(kwargs.items())
        )
        return "|".join(key_parts)
    
    def get(self, key: str) -> Optional[T]:
        """Get value from cache if not expired."""
        with self._lock:
            self._total_count += 1
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._cache[key]
                self._access_times.pop(key, None)
                return None
            self._access_times[key] = time.monotonic()
            self._hit_count += 1
            return entry.value
    
    def set(self, key: str, value: T, ttl_seconds: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        with self._lock:
            ttl = ttl_seconds if ttl_seconds is not None else self._ttl_seconds
            expires_at = time.monotonic() + ttl
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
            self._access_times[key] = time.monotonic()
            self._evict_if_needed()
    
    def delete(self, key: str) -> bool:
        """Delete key from cache. Returns True if key existed."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._access_times.pop(key, None)
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
    
    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache exceeds max size."""
        while len(self._cache) > self._max_size:
            # Find least recently used entry
            if not self._access_times:
                break
            lru_key = min(self._access_times, key=self._access_times.get)
            del self._cache[lru_key]
            del self._access_times[lru_key]
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
                self._access_times.pop(key, None)
            return len(expired_keys)
    
    @property
    def size(self) -> int:
        """Return current cache size (excluding expired)."""
        with self._lock:
            self.cleanup_expired()
            return len(self._cache)
    
    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        with self._lock:
            self.cleanup_expired()
            total = self._total_count
            hits = self._hit_count
            return {
                "name": self._name,
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl_seconds,
                "hit_count": hits,
                "total_count": total,
                "hit_rate": (hits / total) if total else 0.0,
            }


# Global cache instances
_listing_cache: Optional[TTLCache] = None
_industry_cache: Optional[TTLCache] = None
_cache_lock = threading.Lock()


def get_listing_cache() -> TTLCache:
    """Get or create the global listing cache."""
    global _listing_cache
    with _cache_lock:
        if _listing_cache is None:
            _listing_cache = TTLCache(
                ttl_seconds=Config.LISTING_CACHE_TTL,
                max_size=Config.CACHE_SIZE,
                name="listing"
            )
        return _listing_cache


def get_industry_cache() -> TTLCache:
    """Get or create the global industry/sector cache."""
    global _industry_cache
    with _cache_lock:
        if _industry_cache is None:
            _industry_cache = TTLCache(
                ttl_seconds=Config.INDUSTRY_CACHE_TTL,
                max_size=Config.CACHE_SIZE,
                name="industry"
            )
        return _industry_cache


def _cache_namespace(func: Callable, args: tuple) -> str:
    """Namespace that keeps same-named methods of different owners apart.

    The listing cache and the industry cache are single process-wide objects
    shared by every provider, and providers reuse the same method names
    (``kbs.Listing.all_symbols`` vs ``vci.Listing.all_symbols``). Keying on
    ``func.__name__`` alone therefore let one provider's result be served to
    another. The namespace is built from the defining module/qualname and,
    when the call is a method, from the instance's own class.
    """
    owner = ""
    if args and not isinstance(args[0], PRIMITIVES) and hasattr(args[0], "__class__"):
        owner_cls = type(args[0])
        owner = f"{owner_cls.__module__}.{owner_cls.__qualname__}."
    return f"{owner}{func.__module__}.{func.__qualname__}"


def cached_listing(ttl_seconds: Optional[int] = None):
    """
    Decorator for caching listing functions.
    
    Args:
        ttl_seconds: Optional custom TTL (uses Config.LISTING_CACHE_TTL by default)
    """
    def decorator(func: Callable) -> Callable:
        cache = get_listing_cache()
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = cache._make_key(_cache_namespace(func, args), *args, **kwargs)
            result = cache.get(key)
            if result is not None:
                logger.debug(f"Cache HIT for {func.__name__}: {key}")
                return result
            
            logger.debug(f"Cache MISS for {func.__name__}: {key}")
            result = func(*args, **kwargs)
            cache.set(key, result, ttl_seconds)
            return result
        
        return wrapper
    return decorator


def cached_industry(ttl_seconds: Optional[int] = None):
    """
    Decorator for caching industry/sector mapping functions.
    
    Args:
        ttl_seconds: Optional custom TTL (uses Config.INDUSTRY_CACHE_TTL by default)
    """
    def decorator(func: Callable) -> Callable:
        cache = get_industry_cache()
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = cache._make_key(_cache_namespace(func, args), *args, **kwargs)
            result = cache.get(key)
            if result is not None:
                logger.debug(f"Cache HIT for {func.__name__}: {key}")
                return result
            
            logger.debug(f"Cache MISS for {func.__name__}: {key}")
            result = func(*args, **kwargs)
            cache.set(key, result, ttl_seconds)
            return result
        
        return wrapper
    return decorator


def invalidate_listing_cache(pattern: Optional[str] = None) -> int:
    """
    Invalidate listing cache entries.
    
    Args:
        pattern: Optional substring to match keys (None = clear all)
        
    Returns:
        Number of entries invalidated
    """
    cache = get_listing_cache()
    with cache._lock:
        if pattern is None:
            count = len(cache._cache)
            cache.clear()
            return count
        
        keys_to_delete = [k for k in cache._cache.keys() if pattern in k]
        for key in keys_to_delete:
            cache.delete(key)
        return len(keys_to_delete)


def invalidate_industry_cache(pattern: Optional[str] = None) -> int:
    """
    Invalidate industry cache entries.
    
    Args:
        pattern: Optional substring to match keys (None = clear all)
        
    Returns:
        Number of entries invalidated
    """
    cache = get_industry_cache()
    with cache._lock:
        if pattern is None:
            count = len(cache._cache)
            cache.clear()
            return count
        
        keys_to_delete = [k for k in cache._cache.keys() if pattern in k]
        for key in keys_to_delete:
            cache.delete(key)
        return len(keys_to_delete)


def get_cache_stats() -> Dict[str, Any]:
    """Get statistics for all caches."""
    return {
        "listing": get_listing_cache().stats(),
        "industry": get_industry_cache().stats(),
    }


__all__ = [
    "TTLCache",
    "CacheEntry",
    "get_listing_cache",
    "get_industry_cache",
    "cached_listing",
    "cached_industry",
    "invalidate_listing_cache",
    "invalidate_industry_cache",
    "get_cache_stats",
]