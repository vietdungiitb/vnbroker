# Source Router

| | |
|:--|:--|
| **Mã module** | `MOD-SR-01` |
| **Phiên bản** | 1.0 |
| **Files** | `core/source_router.py` |

---

## 1. Tổng quan

Source Router quản lý failover dựa trên health store.

## 2. Implementation

```python
OPEN_SOURCE_CANDIDATES: Dict[str, List[str]] = {
    "quote": ["vci", "kbs"],
    "company": ["vci", "kbs"],
    "financial": ["vci", "kbs"],
    "listing": ["kbs", "vci"],
    "trading": ["kbs", "vci"],
    "news": ["vci", "kbs", "rss_cafef", "rss_vneconomy"],
}

def build_source_order(module_name: str, symbol: str | None = None) -> List[str]:
    # 1. Get candidates
    # 2. Filter out cooldown providers
    # 3. Hash-shard by symbol
    ...

def record_failure(module_name: str, source: str) -> None:
    # 1. Increment failures
    # 2. Set cooldown: min(90, 5·2^(n-1))
    ...
```

## 3. Rules

| Rule | Description |
|:--|:--|
| Cooldown | `min(90, 5·2^(n-1))` seconds |
| Half-open | Probe after cooldown expires |
| Hash-shard | Distribute by symbol hash |
