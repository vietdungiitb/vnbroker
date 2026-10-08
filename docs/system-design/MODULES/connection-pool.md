# Connection Pool

| | |
|:--|:--|
| **Mã module** | `MOD-CP-01` |
| **Phiên bản** | 1.0 |
| **Files** | `core/utils/connection_pool.py` |

---

## 1. Tổng quan

ConnectionPool cung cấp shared `requests.Session` với connection pool lớn, thay thế
thread-local sessions cũ gây mất 4-5× tốc độ.

## 2. Implementation

```python
class ConnectionPool:
    _instance: Optional["ConnectionPool"] = None
    _lock: threading.Lock = threading.Lock()
    
    @classmethod
    def get_instance(cls) -> "ConnectionPool":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def get_session(self) -> requests.Session:
        return self._session
```

## 3. Performance

| Metric | Before | After | Speedup |
|:--|---:|---:|---:|
| 100 symbols | 53.4s | 8.1s | **6.6×** |
| ms/sym | 534 | 81 | **6.6×** |

## 4. Tests

| Test | File |
|:--|:--|
| Singleton | `tests/unit/core/test_connection_pool.py` |
| Thread safety | `tests/unit/core/test_connection_pool.py` |
| Session reuse | `tests/unit/core/test_connection_pool.py` |
