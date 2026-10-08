# Normalizer

| | |
|:--|:--|
| **Mã module** | `MOD-NORM-01` |
| **Phiên bản** | 1.0 |
| **Files** | `core/utils/normalizer.py` |

---

## 1. Tổng quan

Normalizer chuẩn hoá kết quả từ mọi provider, đảm bảo schema nhất quán.

## 2. Implementation

```python
class Normalizer:
    @staticmethod
    def normalize_history(result: Any, start: Any = None, end: Any = None) -> Any:
        if isinstance(result, list):
            return [Normalizer._normalize_frame(f, start, end) for f in result]
        return Normalizer._normalize_frame(result, start, end)
    
    @staticmethod
    def _normalize_frame(df: pd.DataFrame, start: Any, end: Any) -> pd.DataFrame:
        # Copy, tz-aware, boundary filter, sort, reset index
        ...
```

## 3. Rules

| Rule | Description |
|:--|:--|
| tz-aware | Convert to `Asia/Ho_Chi_Minh` |
| Boundary | Filter by `[start, end]` |
| Sort | Sort by time |
| Reset | Reset index |

## 4. Tests

| Test | File |
|:--|:--|
| Single DataFrame | `tests/unit/common/test_bulk_normalizer.py` |
| List DataFrame | `tests/unit/common/test_bulk_normalizer.py` |
| Boundary filter | `tests/unit/common/test_bulk_normalizer.py` |
