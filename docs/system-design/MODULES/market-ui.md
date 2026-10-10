# Market UI

| | |
|:--|:--|
| **Mã module** | `MOD-UI-01` |
| **Phiên bản** | 1.0 |
| **Files** | `ui/market.py` |

---

## 1. Tổng quan

Market là facade cho dữ liệu thị trường (giá, bảng giá).

## 2. Implementation

```python
class Market:
    def __init__(self, source: str = "KBS", show_log: bool = True, auto: bool = False):
        self.source = "AUTO" if auto else source
        self.auto = auto
        self.show_log = show_log
    
    def equity(self, symbol: str) -> Quote:
        return Quote(symbol, self.source, show_log=self.show_log)
    
    @property
    def bulk(self) -> BulkAPI:
        from vnbroker.api.bulk import BulkAPI
        return BulkAPI(source=self.source, show_log=self.show_log)
```

## 3. Usage

```python
from vnbroker.ui.market import Market

mkt = Market(auto=True)
hist = mkt.equity("ACB").history(start="2024-01-01", end="2024-06-30")
bulk = mkt.bulk.history(symbols=["ACB", "VNM"], start="2024-01-01", end="2024-06-30")
```
