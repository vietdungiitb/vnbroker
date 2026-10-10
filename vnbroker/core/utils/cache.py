"""
TTL-based in-memory cache for vnbroker.

Provides thread-safe caching with time-to-live expiration for
listing data, industry mappings, and other static/reference data.
"""

import datetime
import hashlib
import re
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

#: Types that are terminal in :func:`_encode_value` — they never contain
#: another value to recurse into, and they are safe to read ``__dict__`` of.
_TERMINAL_TYPES = PRIMITIVES + (
    bytes,
    bytearray,
    datetime.datetime,
    datetime.date,
    datetime.time,
    datetime.timedelta,
)

#: Recursion ceiling. A self-referential container (``x = []; x.append(x)``)
#: would otherwise blow the stack while a key is being built.
_MAX_DEPTH = 6

#: Object tokens longer than this are replaced by a BLAKE2b-128 digest so a
#: wide DataFrame cannot turn into a multi-megabyte dictionary key. The digest
#: is stable across processes (``hash()`` is not: str hashing is salted).
_MAX_TOKEN_CHARS = 4096

#: Memory addresses inside a ``repr()``. The class is **case-insensitive**:
#: CPython prints ``<Cls object at 0x000001E65D248D70>`` with *uppercase* hex
#: digits, and ``0x[0-9a-f]+`` would stop at the first ``E`` and leave
#: ``E65D248D70`` behind — so every such object would still look unique. The
#: replacement is ``<addr>``, not ``0x?``: no key should still contain the
#: string ``0x`` at all, which is what the address-free contract promises.
_ADDR_MASK = re.compile(r"0[xX][0-9a-fA-F]+")


def _is_terminal(value: Any, depth: int = 0) -> bool:
    """True when ``value`` can be encoded without touching any internals.

    Used to decide whether an object's own state is safe to fold into its
    key. A DataFrame's ``__dict__`` holds a ``BlockManager``; recursing into
    that would drag in buffers and addresses, so such objects are encoded
    from their ``repr()`` alone.
    """
    if isinstance(value, _TERMINAL_TYPES):
        return True
    if depth >= _MAX_DEPTH:
        return False
    if isinstance(value, (list, tuple, set, frozenset)):
        return all(_is_terminal(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return all(
            _is_terminal(k, depth + 1) and _is_terminal(v, depth + 1)
            for k, v in value.items()
        )
    return False


def _instance_state(value: Any) -> Optional[str]:
    """Encode an instance's own attributes, or ``None`` if that is unsafe.

    A plain domain object's ``repr()`` is ``<Cls object at 0x...>``: masked,
    it is identical for *every* instance, so ``Obj('a')`` and ``Obj('b')``
    would share a key. Folding in the attribute values separates them while
    two instances holding equal state still produce the same token.
    """
    state = getattr(value, "__dict__", None)
    if (
        isinstance(state, dict)
        and state
        and all(isinstance(name, str) for name in state)
        and all(_is_terminal(item) for item in state.values())
    ):
        return _encode_value(state)

    slots = getattr(type(value), "__slots__", None)
    if slots:
        names = [slots] if isinstance(slots, str) else list(slots)
        values = {name: getattr(value, name) for name in names if hasattr(value, name)}
        if values and all(_is_terminal(item) for item in values.values()):
            return _encode_value(values)
    return None


def _encode_object(value: Any) -> str:
    """Token for an object no specialised branch claims.

    The class name alone is not enough — ``Decimal('1')``/``Decimal('2')`` and
    two different DataFrames all reduced to it — so the masked ``repr()`` is
    included, which is exactly as discriminating as the object's own repr.
    """
    try:
        shown = _ADDR_MASK.sub("<addr>", repr(value))
    except Exception as exc:  # a broken __repr__ must not break the cache
        logger.debug(f"cache key: repr() failed for {type(value).__name__}: {exc}")
        shown = "<unrepresentable>"

    body = f"{type(value).__module__}.{type(value).__qualname__}|{shown}"
    state = _instance_state(value)
    if state is not None:
        body = f"{body}|state={state}"
    if len(body) > _MAX_TOKEN_CHARS:
        digest = hashlib.blake2b(
            body.encode("utf-8", "surrogatepass"), digest_size=16
        ).hexdigest()
        body = f"{body[:_MAX_TOKEN_CHARS]}|blake2b128={digest}"
    return f"obj:{body}"


def _encode_value(value: Any, _depth: int = 0) -> str:
    """Encode one argument into a deterministic, address-free token.

    Invariant actually implemented (the docstring used to claim a stronger
    one that the code did not provide):

    *Two arguments share a token only when they are indistinguishable.*  Every
    branch tags the token with its type, so ``None``/``"None"``, ``0``/``"0"``
    and ``1``/``True``/``1.0`` — which are all ``==`` in Python — cannot
    collapse. The object branch keeps the masked ``repr()`` and, when safe,
    the instance state, so ``Decimal('1')``, two DataFrames and two
    differently-configured domain objects stay apart.

    *Equal arguments always share a token*, so the cache still hits. Nothing
    in a token comes from a memory address or from ``hash()``: the address
    mask is applied to every ``repr()`` and oversized tokens are digested
    with BLAKE2b, which is stable across processes (``hash()`` on ``str`` is
    salted by ``PYTHONHASHSEED``).

    Known residual limit: an object's own ``__repr__`` is the ceiling. pandas
    truncates a frame past ``display.max_rows``, so two frames differing only
    below that row can share a token. Nothing in this repo caches DataFrames
    through ``_make_key``, so this is a bound on the contract, not a live bug.
    """
    if _depth >= _MAX_DEPTH:
        return f"depth>{_MAX_DEPTH}"

    # NOTE: `bool` is a subclass of `int` and `1 == True == 1.0`, so these
    # branches must be tested in this order and must each carry a type label.
    if value is None:
        return "none"
    if isinstance(value, bool):
        return f"bool:{value}"
    if isinstance(value, str):
        return f"str:{value}"
    if isinstance(value, int):
        return f"int:{value}"
    if isinstance(value, float):
        return f"float:{value!r}"
    if isinstance(value, (bytes, bytearray)):
        return f"{type(value).__name__}:{bytes(value).hex()}"
    if isinstance(value, (list, tuple)):
        inner = ",".join(_encode_value(item, _depth + 1) for item in value)
        return f"{type(value).__name__}:{len(value)}:[{inner}]"
    if isinstance(value, (set, frozenset)):
        inner = ",".join(sorted(_encode_value(item, _depth + 1) for item in value))
        return f"{type(value).__name__}:{len(value)}:{{{inner}}}"
    if isinstance(value, dict):
        # Sort the ENCODED pairs, not the raw items: sorting the items by
        # encoded key alone left `{1: 'x', '1': 'y'}` order-dependent, because
        # both keys encoded to the same token and the stable sort then kept
        # insertion order. Sorting the pair is order-independent even there.
        pairs = sorted(
            (_encode_value(k, _depth + 1), _encode_value(v, _depth + 1))
            for k, v in value.items()
        )
        inner = ",".join(f"{k}={v}" for k, v in pairs)
        return f"dict:{len(value)}:{{{inner}}}"
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return f"{type(value).__name__}:{value.isoformat()}"
    if isinstance(value, datetime.timedelta):
        return f"timedelta:{value.total_seconds()}"
    return _encode_object(value)


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

        Each field is written as ``p<len>:<token>`` or
        ``k<namelen>:<name>=<len>:<token>``, so a token that itself contains
        ``|``, ``=`` or ``:`` cannot be mistaken for a field boundary. Before
        this, ``_make_key('x', 1)`` and ``_make_key(x=1)`` produced ``'x|1'``
        and ``'x=1'`` — separated only by the accident that one argument
        happened to contain no ``=``. Length prefixes make the split
        structural rather than lucky.
        """
        parts = []
        for arg in args:
            token = _encode_value(arg)
            parts.append(f"p{len(token)}:{token}")
        for name in sorted(kwargs):
            token = _encode_value(kwargs[name])
            parts.append(f"k{len(name)}:{name}={len(token)}:{token}")
        return "|".join(parts)
    
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


def _cache_namespace(func: Callable[..., Any], args: tuple[Any, ...]) -> str:
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