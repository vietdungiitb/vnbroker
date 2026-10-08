# Health Store

| | |
|:--|:--|
| **Mã module** | `MOD-HS-01` |
| **Phiên bản** | 1.0 |
| **Files** | `core/health_store.py` |

---

## 1. Tổng quan

HealthStore lưu trữ trạng thái sức khoẻ provider (SQLite + in-memory).

## 2. Schema

```sql
CREATE TABLE health_state (
    module_source TEXT PRIMARY KEY,
    failures INTEGER DEFAULT 0,
    cooldown_until_wall REAL,
    last_success_wall REAL,
    last_failure_wall REAL
);
```

## 3. Features

| Feature | Description |
|:--|:--|
| Persist | SQLite (restart-safe) |
| Debounce | 1.0s / 10 events |
| Cooldown | `min(90, 5·2^(n-1))` |
| Half-open | Probe after cooldown expires |
