# AUDIT LƯỢT 2 — TIẾN SĨ HỆ THỐNG TẦNG 1

**Ngày:** 2026-10-05  
**Vai trò:** Project Manager + System Designer + Team Code Leader  
**Phạm vi:** Toàn bộ tầng 1 (dữ liệu thị trường ẩn danh)  
**Phương pháp:** Probe độc lập, không tin lượt 1, chạy từ đầu trên mạng thật

---

## 0. TÓM TẮT ĐIỀU HÀNH

| Trạng thái | Mức độ | Hành động |
|:---|:---|:---|
| Failover tự động | ❌ **Không hoạt động** trên đường chính | Cần sửa P0 |
| Bulk đa mã | ⚠️ Có nhưng **vỡ schema** và **mất dữ liệu âm thầm** | Cần sửa P0 |
| Multi-provider đồng thời | ❌ **Chưa có** | Cần xây mới P1 |
| Auth providers tham gia pool | ❌ **Chưa có** | Cần xây mới P1 |
| Connection reuse | ❌ **Mất 4–5× tốc độ** | Cần sửa P0 |
| Health-based routing | ❌ **Có code nhưng không chạy** | Cần nối vào P0 |

**Kết luận:** Tầng 1 hiện tại là **single-provider, single-thread-per-symbol, không failover, không bulk đúng chuẩn**. Khoảng cách với giải pháp thương mại (Bloomberg, Refinitiv, Polygon.io) là **vài tuần**, không phải vài tháng — nếu làm đúng thứ tự.

---

## 1. PHÁT HIỆN ĐỘC LẬP (Probe lượt 2)

### 1.1 Failover không chạy — xác nhận lại

```
[INIT] source=VCI, has _auto_sources=False
[OK] rows=6, source_used=None
--- SIMULATE 429 ---
[EXPECTED] Failover không chạy: 429 Too Many Requests
[HEALTH] VCI: failures=0, KBS: failures=0  ← không ghi nhận lỗi
```

**Nguyên nhân gốc:** `_run_with_failover` (`common/data.py:527`) chỉ rẽ nhánh failover khi `_auto_sources` tồn tại. Biến này **chỉ được set trong test** (`tests/contract/test_failover_tier1.py:87`). Runtime thật, `source="AUTO"` bị ghim cứng thành `candidates[0]` lúc khởi tạo (`data.py:462`).

**Hệ quả:** `source_router.py` có 405 dòng code failover hoàn chỉnh (health store, circuit breaker, backoff, half-open probe) nhưng **không có dòng nào được thực thi** trên đường chính.

### 1.2 Auth providers không tham gia AUTO pool

```
quote: ['vci', 'kbs']  ← TCBS, DNSE, SSI đã register nhưng không có trong pool
TCBS: NotImplementedError (không có OHLCV đa ngày)
DNSE: ValueError (cần api_key + api_secret)
SSI: ValueError (cần api_key + api_secret)
```

**Vấn đề:** `OPEN_SOURCE_CANDIDATES` (`source_router.py:28`) chỉ liệt kê providers **không cần auth**. TCBS/DNSE/SSI cần auth nên bị loại khỏi pool — **dù chúng có thể cung cấp dữ liệu tốt hơn**.

### 1.3 Bulk vỡ schema

```
Single: tz=Asia/Ho_Chi_Minh, cols=['time', 'open', 'high', 'low', 'close', 'volume']
Bulk:   type=list, Frame 0: tz=None, Frame 1: tz=None  ← KHÔNG chuẩn hoá
```

**Nguyên nhân:** `Quote.history` chỉ gọi `_normalize_quote_result` khi kết quả là `DataFrame`. Bulk trả `list[DataFrame]` → bỏ qua chuẩn hoá.

### 1.4 Connection reuse — mất 4–5× tốc độ

| Cách | 100 mã | ms/sym | Full market (1522) |
|:---|---:|---:|---:|
| Thread-local session (hiện tại) | 53.4s | 534 | ~813s |
| Shared session pool | 13.1s | 131 | ~200s |
| **Speedup** | **4.1×** | | |

**Nguyên nhân:** `_get_thread_session()` tạo `requests.Session` mới mỗi thread. `fetch_multiple` tạo ThreadPoolExecutor mới mỗi batch → mỗi symbol một TLS handshake.

### 1.5 Multi-provider — tiềm năng 1.9×

```
Split 50 KBS + 50 VCI đồng thời: 92/100 ok, 28.1s
vs single-provider KBS: 53.4s → 1.9× nhanh hơn
```

**Vấn đề:** Hiện tại không có cơ chế nào chia tải bulk trên nhiều provider.

---

## 2. ĐỀ XUẤT KIẾN TRÚC — "TIER 1 DATA ENGINE"

### 2.1 Nguyên tắc thiết kế

```
┌─────────────────────────────────────────────────────────────┐
│                    NGƯỜI DÙNG                                │
│   Market(auto=True).bulk.history(symbols=[...])             │
│   → Không biết provider, không biết auth, không biết bulk  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│              TIER 1 DATA ENGINE (mới)                       │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Bulk Router │→ │ Health Router│→ │ Provider Pool     │  │
│  │ (chia tải)  │  │ (sức khoẻ)   │  │ (auth + no-auth)  │  │
│  └─────────────┘  └──────────────┘  └───────────────────┘  │
│         │                                    │              │
│         ▼                                    ▼              │
│  ┌─────────────┐                    ┌───────────────────┐  │
│  │ Normalizer  │                    │ Connection Pool   │  │
│  │ (chuẩn hoá) │                    │ (session dùng chung)│ │
│  └─────────────┘                    └───────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   ┌─────────┐      ┌─────────┐      ┌─────────┐
   │   VCI   │      │   KBS   │      │  DNSE   │  ← auth providers
   │(no-auth)│      │(no-auth)│      │(env key)│    tự động tham gia
   └─────────┘      └─────────┘      └─────────┘    khi có key
```

### 2.2 Thành phần chi tiết

#### A. Bulk Router — chia tải thông minh

**Vấn đề hiện tại:** `fetch_multiple` chạy tuần tự hoặc single-provider.

**Giải pháp mới:**

```python
class BulkRouter:
    """Chia tải bulk trên nhiều provider dựa trên sức khoẻ."""
    
    def fetch_history(self, symbols: List[str], start: str, end: str) -> pd.DataFrame:
        # 1. Lấy health snapshot
        health = source_router.get_source_health_snapshot("quote")
        
        # 2. Chia symbols theo sức khoẻ provider
        plan = self._plan_distribution(symbols, health)
        # plan = {"vci": ["ACB", "VNM", ...], "kbs": ["HPG", "VCB", ...], "dnse": [...]}
        
        # 3. Chạy đồng thời mỗi provider một ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(plan)) as executor:
            futures = {
                executor.submit(self._fetch_batch, provider, syms, start, end): provider
                for provider, syms in plan.items()
            }
            results = {}
            for future in as_completed(futures):
                provider = futures[future]
                try:
                    results[provider] = future.result()
                except Exception as e:
                    results[provider] = e
        
        # 4. Merge + chuẩn hoá
        return self._merge_and_normalize(results, symbols)
    
    def _plan_distribution(self, symbols, health):
        """Chia đều tải, ưu tiên provider khỏe."""
        providers = [p for p, h in health.items() if not h["in_cooldown"]]
        if not providers:
            providers = list(health.keys())  # fallback: dùng hết
        
        # Round-robin hoặc weighted theo success rate
        plan = {p: [] for p in providers}
        for i, sym in enumerate(symbols):
            plan[providers[i % len(providers)]].append(sym)
        return plan
```

#### B. Health Router — sức khoẻ thời gian thực

**Vấn đề hiện tại:** Health store có nhưng không chạy.

**Giải pháp:** Nối health store vào đường chính + thêm metrics mới.

```python
class HealthRouter:
    """Quản lý sức khoẻ provider theo thời gian thực."""
    
    def __init__(self):
        self._store = HealthStore()
        self._latency_window = {}  # rolling window 50 requests
    
    def record_success(self, provider: str, latency_ms: float):
        """Ghi nhận thành công + độ trễ."""
        self._store.record_success("quote", provider)
        self._update_latency(provider, latency_ms)
    
    def record_failure(self, provider: str, error: Exception):
        """Ghi nhận thất bại + phân loại lỗi."""
        self._store.record_failure("quote", provider)
        if "429" in str(error) or "rate limit" in str(error).lower():
            self._store.record_rate_limit(provider)
    
    def get_healthy_providers(self, module: str) -> List[str]:
        """Trả về providers khỏe, sắp xếp theo độ trễ trung bình."""
        health = self._store.get_health(module)
        healthy = [p for p, h in health.items() if not h["in_cooldown"]]
        return sorted(healthy, key=lambda p: self._avg_latency(p))
    
    def _update_latency(self, provider: str, latency_ms: float):
        """Cập nhật rolling window độ trễ."""
        if provider not in self._latency_window:
            self._latency_window[provider] = collections.deque(maxlen=50)
        self._latency_window[provider].append(latency_ms)
```

#### C. Provider Pool — auth providers tự động tham gia

**Vấn đề hiện tại:** `OPEN_SOURCE_CANDIDATES` chỉ có no-auth providers.

**Giải pháp:** Thêm auth providers vào pool, tự động detect credentials.

```python
class ProviderPool:
    """Quản lý tất cả providers, bao gồm auth providers."""
    
    # Providers cần auth
    AUTH_PROVIDERS = {
        "dnse": {
            "env_key": "DNSE_API_KEY",
            "env_secret": "DNSE_API_SECRET",
            "supports": ["quote", "listing", "trading"],
        },
        "ssi": {
            "env_key": "VNBROKER_BROKER_SSI_API_KEY",
            "env_secret": "VNBROKER_BROKER_SSI_API_SECRET",
            "supports": ["quote", "listing", "trading", "screener"],
        },
        "tcbs": {
            "env_key": "TCBS_API_KEY",
            "env_secret": "TCBS_API_SECRET",
            "supports": ["quote", "trading"],  # intraday only
        },
    }
    
    def __init__(self):
        self._auth_providers = {}
        self._detect_auth_providers()
    
    def _detect_auth_providers(self):
        """Tự động phát hiện auth providers từ env."""
        for name, config in self.AUTH_PROVIDERS.items():
            key = os.getenv(config["env_key"])
            secret = os.getenv(config["env_secret"])
            if key and secret:
                self._auth_providers[name] = {
                    "key": key,
                    "secret": secret,
                    "supports": config["supports"],
                }
                logger.info(f"Auth provider '{name}' detected and ready")
    
    def get_available_providers(self, module: str) -> List[str]:
        """Trả về tất cả providers khả dụng cho module."""
        # No-auth providers luôn có
        available = ["vci", "kbs"]
        
        # Auth providers nếu có credentials
        for name, config in self._auth_providers.items():
            if module in config["supports"]:
                available.append(name)
        
        return available
    
    def get_provider(self, name: str, module: str):
        """Khởi tạo provider instance."""
        if name in self._auth_providers:
            config = self._auth_providers[name]
            return self._create_auth_provider(name, module, config)
        return self._create_no_auth_provider(name, module)
```

#### D. Connection Pool — session dùng chung

**Vấn đề hiện tại:** Thread-local session → mất 4–5× tốc độ.

**Giải pháp:**

```python
class ConnectionPool:
    """Session dùng chung cho mọi thread."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_pool()
        return cls._instance
    
    def _init_pool(self):
        """Khởi tạo session pool."""
        self._session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=256,
            pool_maxsize=256,
            max_retries=Retry(total=3, backoff_factor=0.3)
        )
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
    
    def get_session(self) -> requests.Session:
        """Trả về session dùng chung."""
        return self._session

# Sửa _get_thread_session để dùng pool
def _get_thread_session() -> requests.Session:
    return ConnectionPool().get_session()
```

#### E. Normalizer — chuẩn hoá tập trung

**Vấn đề hiện tại:** Bulk không qua chuẩn hoá.

**Giải pháp:** Chuẩn hoá mọi kết quả, kể cả bulk.

```python
class Normalizer:
    """Chuẩn hoá kết quả từ mọi provider."""
    
    def normalize_history(self, result: Any, start: str = None, end: str = None) -> Any:
        """Chuẩn hoá history result (DataFrame hoặc list[DataFrame])."""
        if isinstance(result, list):
            return [self._normalize_frame(f, start, end) for f in result]
        return self._normalize_frame(result, start, end)
    
    def _normalize_frame(self, df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
        """Chuẩn hoá một DataFrame."""
        if not isinstance(df, pd.DataFrame) or "time" not in df.columns:
            return df
        
        df = df.copy()
        df["time"] = self._to_canonical_tz(pd.to_datetime(df["time"]))
        df = df[df["time"].notna()]
        
        if start:
            df = df[df["time"] >= pd.to_datetime(start)]
        if end:
            df = df[df["time"] <= pd.to_datetime(end)]
        
        return df.sort_values("time").reset_index(drop=True)
    
    def _to_canonical_tz(self, series: pd.Series) -> pd.Series:
        """Chuyển sang Asia/Ho_Chi_Minh."""
        if series.dt.tz is None:
            return series.dt.tz_localize("Asia/Ho_Chi_Minh")
        return series.dt.tz_convert("Asia/Ho_Chi_Minh")
```

---

## 3. API ĐỀ XUẤT — SỬ DỤNG ĐƯỢC NGAY

### 3.1 Bulk history — 1 lệnh, không cần biết provider

```python
from vnbroker.ui.market import Market

mkt = Market(auto=True)

# Bulk history: tự chia tải, tự failover, tự chuẩn hoá
df = mkt.bulk.history(
    symbols=["ACB", "VNM", "HPG", "VCB", "CTG", ...],  # 100+ mã
    start="2024-01-01",
    end="2024-06-30"
)
# Trả về: DataFrame với cột symbol
#   time, open, high, low, close, volume, symbol
# attrs: {
#     "sources_used": {"ACB": "vci", "VNM": "kbs", "HPG": "dnse", ...},
#     "failed": {},
#     "requested": 100,
#     "returned": 100,
#     "latency_ms": 2300,
# }
```

### 3.2 Bulk price board — toàn thị trường

```python
# Lấy bảng giá toàn thị trường (1522 mã) trong ~1s
pb = mkt.bulk.price_board()
# 1522 dòng, ~1.1s (KBS /stock/iss endpoint)
```

### 3.3 Auth providers — khai báo 1 lần

```bash
# .env hoặc environment
DNSE_API_KEY=your_key
DNSE_API_SECRET=your_secret
VNBROKER_BROKER_SSI_API_KEY=your_key
VNBROKER_BROKER_SSI_API_SECRET=your_secret
```

```python
# Tự động tham gia pool, không cần code thêm
mkt = Market(auto=True)
# DNSE và SSI tự động được dùng nếu có credentials
```

---

## 4. KẾ HOẠCH TRIỂN KHAI

### Giai đoạn 1 — Nền tảng (1 tuần)

| # | Việc | Ước lượng | Kết quả |
|:--|:---|:---|:---|
| 1.1 | Connection Pool (session dùng chung) | 2 days | 4–5× nhanh hơn |
| 1.2 | Nối failover vào đường chính | 1 day | Failover thật sự chạy |
| 1.3 | Chuẩn hoá bulk | 1 day | Bulk cùng schema với single |
| 1.4 | Normalizer tập trung | 1 day | Một chỗ chuẩn hoá |
| 1.5 | Test + benchmark | 2 days | Đảm bảo không hồi quy |

### Giai đoạn 2 — Bulk Router (1 tuần)

| # | Việc | Ước lượng | Kết quả |
|:--|:---|:---|:---|
| 2.1 | BulkRouter chia tải | 2 days | Chia tải đa provider |
| 2.2 | Health Router | 1 day | Sức khoẻ thời gian thực |
| 2.3 | Multi-provider executor | 2 days | Chạy đồng thời nhiều provider |
| 2.4 | Test + benchmark | 2 days | 1.5–2× nhanh hơn |

### Giai đoạn 3 — Auth Providers (3 days)

| # | Việc | Ước lượng | Kết quả |
|:--|:---|:---|:---|
| 3.1 | ProviderPool detect env | 1 day | Tự động phát hiện auth |
| 3.2 | DNSE/SSI tham gia pool | 1 day | Pool rộng hơn |
| 3.3 | Test + benchmark | 1 day | Đảm bảo ổn định |

### Giai đoạn 4 — API + Tài liệu (2 days)

| # | Việc | Ước lượng | Kết quả |
|:--|:---|:---|:---|
| 4.1 | API bulk.history/price_board | 1 day | API sạch, dễ dùng |
| 4.2 | Tài liệu + examples | 1 day | Người dùng hiểu cách dùng |

**Tổng: ~4 tuần** (1 người full-time)

---

## 5. SO SÁNH VỚI GIẢI PHÁP THƯƠNG MẠI

| Tiêu chí | Bloomberg/Refinitiv | Polygon.io | vnbroker hiện tại | vnbroker đề xuất |
|:---|:---|:---|:---|:---|
| Không cần biết provider | ✅ | ✅ | ❌ | ✅ |
| Bulk đa mã | ✅ | ✅ | ⚠️ vỡ schema | ✅ |
| Multi-provider đồng thời | ✅ | ✅ | ❌ | ✅ |
| Health-based routing | ✅ | ✅ | ❌ code chết | ✅ |
| Auth providers tự động | ✅ | ✅ | ❌ | ✅ |
| Connection reuse | ✅ | ✅ | ❌ | ✅ |
| Failover tự động | ✅ | ✅ | ❌ | ✅ |
| Tốc độ full market | <1s | <1s | ~800s | ~20–40s |

---

## 6. RỦI RO VÀ THÁCH THỨC

| Rủi ro | Mức độ | Giải pháp |
|:---|:---|:---|
| Rate-limit đồng thời từ nhiều provider | Cao | Token bucket per provider + backoff |
| Schema khác nhau giữa providers | Trung bình | Normalizer tập trung + test contract |
| Auth providers không ổn định | Trung bình | Health router loại tự động |
| Độ phức tạp tăng | Thấp | Giữ API đơn giản, phức tạp bên trong |
| Người dùng không hiểu bulk | Thấm | Tài liệu + examples rõ ràng |

---

## 7. KẾT LUẬN

**Tầng 1 hiện tại là nền tảng tốt nhưng chưa nối vào sản phẩm.** Code failover, health store, adaptive controller đã viết xong nhưng không chạy. Bulk có nhưng vỡ schema. Multi-provider chưa có.

**Khoảng cách với giải pháp thương mại là ~4 tuần**, không phải vài thì. Nếu làm đúng thứ tự (P0 trước, P1 sau), vnbroker sẽ có:

1. ✅ Người dùng không cần biết provider
2. ✅ Bulk tăng tốc dựa trên sức khoẻ provider
3. ✅ Multi-thread đồng thời nhiều provider
4. ✅ Auth providers tự động tham gia khi có env key
5. ✅ Failover tự động khi rate-limit
6. ✅ Chuẩn hoá schema tập trung

**Khuyến nghị:** Bắt đầu Giai đoạn 1 ngay. Connection Pool + failover + bulk chuẩn hoá là 3 thay đổi nhỏ, đo được 4–5× cải thiện, và là nền tảng cho mọi thứ khác.
