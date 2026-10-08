# Provider Registry

| | |
|:--|:--|
| **Mã module** | `MOD-PR-01` |
| **Phiên bản** | 1.0 |
| **Files** | `core/registry.py` |

---

## 1. Tổng quan

ProviderRegistry đăng ký và tra cứu providers.

## 2. Implementation

```python
class ProviderRegistry:
    _registry: Dict[Tuple[str, str], Type] = {}
    
    @classmethod
    def register(cls, provider_type: str, source_name: str, provider_class: Type):
        cls._registry[(provider_type, source_name.lower())] = provider_class
    
    @classmethod
    def get(cls, provider_type: str, source_name: str) -> Type:
        return cls._registry[(provider_type, source_name.lower())]
```

## 3. Registered Providers

| Module | Providers |
|:--|:--|
| quote | vci, kbs, tcbs, dnse, ssi |
| company | vci, kbs, tcbs, dnse, ssi |
| financial | vci, kbs, tcbs, dnse, ssi |
| listing | vci, kbs, tcbs, dnse, ssi |
| trading | vci, kbs, tcbs, dnse, ssi |
| news | vci, kbs, tcbs, dnse, ssi, rss_cafef, rss_vneconomy |
