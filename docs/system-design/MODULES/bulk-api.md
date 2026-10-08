# Bulk API

| | |
|:--|:--|
| **Mã module** | `MOD-BULK-01` |
| **Phiên bản** | 1.0 |
| **Files** | `api/bulk.py` |

---

## 1. Tổng quan

BulkAPI cung cấp API cho bulk operations (nhiều mã, nhiều provider).

## 2. Implementation

```python
class BulkAPI:
    def __init__(self, source: str = "AUTO", show_log: bool = False):
        self._health_router = HealthRouter()
        self._bulk_router = BulkRouter(self._health_router)
        self._provider_pool = ProviderPool()
    
    def history(self, symbols: List[str], start: str = None, end: str = None) -> pd.DataFrame:
        # 1. Get available providers
        # 2. Use BulkRouter to fetch concurrently
        # 3. Merge results into single DataFrame
        # 4. Add metadata (sources_used, failed, requested, returned)
        ...
    
    def price_board(self, symbols: List[str] = None) -> pd.DataFrame:
        # Use KBS price_board endpoint (supports bulk)
        ...
```

## 3. Usage

```python
from vnbroker.ui.market import Market

mkt = Market(auto=True)
df = mkt.bulk.history(symbols=["ACB", "VNM", "HPG"], start="2024-01-01", end="2024-06-30")
# → DataFrame with columns: time, open, high, low, close, volume, symbol
# → attrs: sources_used, failed, requested, returned
```

## 4. Tests

| Test | File |
|:--|:--|
| Init | `tests/unit/api/test_bulk_api.py` |
| History | `tests/unit/api/test_bulk_api.py` |
| Price board | `tests/unit/api/test_bulk_api.py` |
| Market integration | `tests/unit/api/test_bulk_api.py` |
