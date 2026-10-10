# Cache

| | |
|:--|:--|
| **Mã module** | `MOD-CACHE-01` |
| **Phiên bản** | 1.0 |
| **Files** | `core/utils/cache.py` |

---

## 1. Tổng quan

TTLCache cung cấp bộ nhớ đệm TTL thread-safe.

## 2. Implementation

```python
class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int = 3600, max_size: int = 128):
        self._cache: Dict[str, CacheEntry[T]] = {}
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[T]:
        # Check expiration, return value or None
        ...
    
    def set(self, key: str, value: T, ttl_seconds: Optional[int] = None):
        # Set with TTL, evict if needed
        ...
```

## 3. Known Issue

**TD-001:** Cache key dùng `str(arg)` cho mọi arg — với `self` trong bound method,
key chứa **định chỉ bộ nhớ** → cache miss 100% nếu tạo object mới.

**Fix:** Key = `(provider, method, normalized_args)`, bỏ `self`.
