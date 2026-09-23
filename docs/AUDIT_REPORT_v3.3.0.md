# Báo cáo Audit toàn diện vnbroker v3.3.0

> Ngày audit: 2026-09-22
> Ngày fix DoD: 2026-09-23
> Phạm vi: toàn bộ dự án `vnbroker/` — kiến trúc Direct Provider, market data, brokerage/broker lanes, analytics, news, retail, core utils
> Phương pháp: đọc code trực tiếp + `pytest tests/unit -q` + `ruff check vnbroker` + `mypy vnbroker --ignore-missing-imports` + security audit

## Tóm tắt điều hành

| Hạng mục | Trước fix | Sau fix DoD (2026-09-23) |
|---|---|---|
| Unit tests | **753 passed, 5 skipped** | **753 passed, 5 skipped** — giữ xanh sau mọi fix (3 test version đã cập nhật 3.1.0→3.3.0) |
| Ruff | **118 errors** | **All checks passed (0 errors)** — 118→0 |
| Mypy | **Blocked bởi constants.py:23** | **Hết blocked, chạy full** — còn lỗi strict có sẵn (ngoài scope DoD, cần epic riêng) |
| Security audit cơ bản | Pass 2/2, gap thực tế | BTMC key ra env, timeout + logger cho retail, md5 cho news hash |

**Kết luận nhanh:** Kiến trúc Direct Provider + `ProviderRegistry` + `Source Router` là đúng hướng, test mock phủ tốt. Nhưng dự án đang bị chặn bởi lỗi syntax/import cơ bản và nhiều pattern `except: pass / return empty` che giấu lỗi, khiến failover, cache, chuẩn đơn vị giá và broker lane không đáng tin. Sửa hết P0+P1 dưới đây sẽ nâng hiệu quả thực tế nhiều hơn bất kỳ tính năng mới nào.

**Quy ước mức độ:**

* **P0 — Critical:** crash runtime tái hiện được / sai logic / chặn CI, phải sửa ngay (<1 ngày).
* **P1 — Major:** latent lint/type, dead code, hiệu năng kém, bảo mật, cần sửa trong 1–2 tuần.
* **P2 — Roadmap:** gap kiến trúc / tính năng cho v3.4+.

> **Đính chính phản biện 2026-09-22 (đối chiếu code + chạy thử):**
> - Báo cáo này là **repo-wide audit**, không phải regression của v3.3. Toàn bộ P0 đều là nợ có sẵn ở HEAD, v3.3 không làm vỡ thêm.
> - **P0#3 rút xuống P1:** `brokerage/tcbs/client.py:82` dùng annotation `asyncio.Queue` trong method-body — theo PEP 526 không eval ở runtime. Đã chạy thử `TCBSClient(api_key='x',...)` → `instantiate OK`. Lỗi thực chỉ còn là `F821` lint/type, không phải crash.
> - Giữ **P0 thật chỉ còn #2, #5** (+ #1 ở mức P0-cho-CI vì chặn `mypy --strict` full, nhưng không crash runtime vì chưa ai import `core/constants`).
> - `#4 dead code unreachable`, `#6 duplicate ghi đè ổn định (753 test pass)`, `#7 đã nằm roadmap v3.2+` → chuyển về P1.
> - `mypy full --strict` bị chặn, nhưng scoped `mypy` với `--follow-imports=silent` (cách DoD từng dùng) vẫn chạy được — không thể kết luận "mypy vô dụng" toàn cục.

---

## I. Bug P0 — Crash / Sai logic nghiêm trọng

### 1. `vnbroker/core/constants.py:23` — syntax error chặn toàn bộ mypy/type-check

```python
"KBS" = _DataSource.KBS.value  # literal không thể gán
```

`mypy` báo `Cannot assign to literal here` và dừng, không check được bất kỳ file nào khác. File này được import bởi nhiều nơi nên CI type-check hiện vô dụng.

**Giải pháp:**

* Sửa thành `KBS = _DataSource.KBS.value`.
* Xóa class deprecated `DataSources`, chuyển code mới sang `vnbroker/core/types.py:DataSource`.
* Bật lại `mypy --strict` trong CI sau khi sửa.

### 2. `vnbroker/broker/tcbs/money.py:194,240,285` — `BrokerValidationError` không tồn tại

File chỉ import ở `vnbroker/broker/tcbs/money.py:19-24`:

```python
from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerNetworkError,
    BrokerPermissionError,
    BrokerSessionExpiredError,
)
```

nhưng lại `raise BrokerValidationError(...)` tại 3 chỗ (`get_ppse`, `get_purchasing_power_by_symbol_price`, `get_customer_accounts`). Runtime sẽ `NameError` khi gọi 3 API này.

**Giải pháp:** thêm `BrokerValidationError` vào import (nếu đã có trong `vnbroker/broker/exceptions.py`) hoặc dùng `BrokerError` hiện có. Thêm unit test gọi 3 nhánh validation rỗng.

### 3. `vnbroker/brokerage/tcbs/client.py:82,168` — `asyncio` thiếu import [ĐÍNH CHÍNH: P1, không phải crash P0]

```python
self._ws_subscriptions: Dict[str, asyncio.Queue] = {}
self._tasks: List[asyncio.Task] = []
```

trong khi file không `import asyncio` top-level. Chỉ có `import asyncio` cục bộ trong `_message_loop` ở `vnbroker/brokerage/tcbs/client.py:193`. **Đính chính:** annotation dạng `self.x: T = ...` trong method-body theo PEP 526 không eval ở runtime — đã chạy thử `from vnbroker.brokerage.tcbs.client import TCBSClient; TCBSClient(api_key='x',...)` → `instantiate OK`. Vì vậy không phải crash P0, chỉ còn `F821` + `mypy undefined-name` ở mức P1. File còn thừa `import uuid`, `TimeInForce` (`ruff F401`).

**Giải pháp:** `import asyncio` top-level (dọn F821/mypy), xóa `uuid` và `TimeInForce` thừa.

### 4. `vnbroker/explorer/tcbs/quote.py:377-381` — dead code `df` chưa từng định nghĩa

```python
if interval_key in ["1D"...]: return ...
elif ...: return ...
else: raise ...
df.attrs['symbol']=...  # unreachable, df undefined -> F821 x4
return df
```

Mọi nhánh trên đều `return/raise`, đoạn cuối không bao giờ chạy. `ruff` báo 4 lỗi `F821 Undefined name df`. Nếu refactor trong tương lai mà lọt xuống đây sẽ `NameError`.

**Giải pháp:** xóa 5 dòng cuối hoặc gán `df` trước return. Xóa biến thừa `end_stamp` ở `vnbroker/explorer/tcbs/quote.py:359-361`, biến `dt` ở `:473`.

### 5. `vnbroker/explorer/tcbs/websocket.py:238` — `websockets` chưa import

```python
except websockets.exceptions.ConnectionClosed:
```

nhưng file không `import websockets`. Sẽ `NameError` đúng lúc mất kết nối — ca cần reconnect nhất lại crash.

**Giải pháp:** `import websockets` top-level. Xóa import thừa `typing.Callable` (`ruff F401`).

### 6. Trùng định nghĩa hàm trong `vnbroker/core/utils/parser.py:287` vs `:583`

`normalize_vietnamese_text_to_snake_case` định nghĩa 2 lần, `ruff F811 Redefinition`. Định nghĩa thứ 2 (có `preserve_hierarchy`) ghi đè cái đầu, làm docstring/test cũ sai lệch. Dễ gây bug chuẩn hóa tên cột tài chính tiếng Việt.

**Giải pháp:** giữ 1 bản duy nhất (bản dòng 583 đầy đủ hơn), xóa bản dòng 287, thêm test collision và test `preserve_hierarchy=True/False`.

### 7. Mâu thuẫn DNSE Finance: 2 file song song, 2 hành vi khác nhau

* `vnbroker/explorer/dnse/financial.py:29-30` — `__init__ raise NotImplementedError`.
* `vnbroker/explorer/dnse/finance.py:49-` — `DNSEFinance` trả `DataFrame` rỗng.
* `vnbroker/explorer/dnse/__init__.py:11,25` đăng ký `finance.DNSEFinance` cho `"financial/dnse"`, file `financial.py` thành dead code.
* Nhưng `vnbroker/common/data.py:954-957` khi `source="DNSE"` lại fallback cứng về `KBSFinancial`, bỏ qua provider đã đăng ký.

Hậu quả: `Finance("ACB", source="DNSE").ratio()` đi đường vòng, `attrs["source_used"]` sai, không nhất quán với `Company`/`Trading` (vốn có `FALLBACK_MAP` + `_call_with_fallback`).

**Giải pháp (chọn 1 chuẩn duy nhất):**

* Option A (khuyến nghị): DNSE Company/Finance/News đều `raise NotImplementedError` để `source_router.should_failover()` bắt được và failover sang VCI/KBS.
* Option B: đều trả empty DF + ghi `attrs["source_used"]` rõ ràng.
* Hiện tại Company trả rỗng, Finance có 2 kiểu, News trả rỗng → router không failover được vì empty DF không phải exception. Xóa file dead, sửa `common/data.py` dùng registry thay vì fallback cứng.

---

## II. Bug P1 — Logic / Hiệu năng / Bảo mật

### 8. `lru_cache` trên instance method gây leak + stale cache

`vnbroker/common/data.py:671-724,991-1012,841-853`: `@lru_cache` trên `Company.overview/profile/...`, `Finance.balance_sheet/...`, `News.latest/search/by_symbol`, `Listing.all_symbols/...`. `self` nằm trong key cache → giữ reference instance mãi, không bao giờ giải phóng; đổi `symbol` via `update_symbol()` vẫn trả data cũ.

**Giải pháp:** thay bằng `TTLCache` đã có ở `vnbroker/core/utils/cache.py`, key = `(symbol, source, params)`, hoặc dùng decorator `cached_listing` / `cached_industry`. Bắt buộc trước khi bật cache listing 24h.

### 9. Retry 2 lớp chồng nhau

`vnbroker/base.py:183-195` (`BaseAdapter.history` retry 3 lần) + `vnbroker/common/data.py:414-424` (`Quote.history` retry 3 lần) = 9 lần request khi lỗi mạng. Chưa kể `source_router` failover loop. Tổng latency worst-case >90s.

**Giải pháp:** chỉ retry ở 1 tầng (giữ ở `BaseAdapter`), `Quote` chỉ failover, không retry. Ghi rõ chính sách retry trong docstring.

### 10. `TTLCache.stats()` báo `hit_rate` sai mãi mãi

`vnbroker/core/utils/cache.py:137`: `_hit_count/_total_count` chưa bao giờ được set ở `get()/set()`. `hit_rate` luôn 0. Không thể tuning cache. File còn import thừa `dataclasses.field`.

**Giải pháp:** thêm counter trong `get()` (hit/miss) và `set()`, expose qua `stats()`.

### 11. Thuật toán `cci()` chậm O(n*w)

`vnbroker/analytics/indicators.py:259-261` dùng `.rolling(...).apply(lambda x: mean(abs(...)), raw=True)` — chậm gấp 10–50x so với vector hóa. `compute_all_indicators()` còn tính đủ 16 cột dù user chỉ cần 1. Thiếu validate `window>0`, `high>=low`.

**Giải pháp:**

```python
mean_dev = (typical_price - sma_tp).abs().rolling(window).mean()
```

Thêm param `indicators=["rsi","macd",...]` cho `compute_all_indicators`, validate đầu vào, thêm benchmark test.

### 12. `fetch_multiple` tạo `ThreadPoolExecutor` mỗi batch

`vnbroker/explorer/tcbs/quote.py:660` (và tương tự VCI/KBS): `while cursor: with ThreadPoolExecutor(...)`. Tạo/hủy pool liên tục, không reuse session, nuốt exception (`except: return None` ở dòng 656).

**Giải pháp:** 1 pool duy nhất cho toàn bộ symbols, dùng `httpx.AsyncClient` + `core/utils/async_client.py` đã có, trả về `dict[symbol->df]` thay vì `list` mất nhãn khi 1 symbol fail. Log exception thay vì nuốt.

### 13. Retail lane: hardcoded secret + thiếu timeout + `print`

* `vnbroker/explorer/misc/gold_price.py:82-83`: `key=3kd8ub1llcg9t45hnoh8hmn7t5kc2v` hardcode trong default arg.
* `sjc_gold_price():49`, `btmc_goldprice():93`, `vcb_exchange_rate():33` dùng `requests.post/get` không `timeout`, `vcb_exchange_rate():30` chỉ `print` khi sai date rồi vẫn chạy tiếp.
* `btmc` sort bằng string `sell_price` ở dòng 119 → sort lexicographic sai.
* `vnbroker/common/retail.py` đã phải `_suppress_print()` để vá — là code smell.
* `vnbroker/explorer/misc/exchange_rate.py:13` import không ở top (`E402`).

**Giải pháp:** đưa key ra env `BTMC_API_KEY`, thêm `timeout=Config.REQUEST_TIMEOUT` cho mọi request, raise `ValueError` thay vì print, cast `buy_price/sell_price` sang float trước sort, chuyển `print` sang `logger`.

### 14. DNSE Quote: timezone + error swallowing

`vnbroker/explorer/dnse/quote.py:177-180,211-214`: `.dt.tz_localize(None)` xóa timezone sau khi convert UTC → mất thông tin, so sánh với VCI/KBS (giữ `Asia/Ho_Chi_Minh`) lệch 7h. `history/intraday/price_depth` ở dòng 319–321, 414, 470 dùng `except Exception: return empty DF` — nuốt lỗi auth/network, `source_router.should_failover()` không bao giờ thấy để failover.

**Giải pháp:** giữ `tz_convert('Asia/Ho_Chi_Minh')`, chỉ trả DF rỗng khi API trả rỗng thật, còn lại raise `DataFetchError`/`NetworkError` để router failover.

### 15. `News` DNSE fallback cứng về VCI

`vnbroker/common/data.py:764-767`: `source="DNSE"` tự ý dùng `VCINews` mà không ghi `attrs["source_used"]`. User tưởng lấy tin DNSE. Mâu thuẫn với bảng `SUPPORTED_SOURCES` quảng cáo DNSE có News.

**Giải pháp:** raise `NotImplementedError` + để router failover, hoặc annotate `source_used="VCI"` rõ ràng.

### 16. `normalize_news_dataframe` dùng `hash()` builtin

`vnbroker/news/normalize.py:116`: `abs(hash(x))` — Python `hash()` random mỗi process (`PYTHONHASHSEED`), không ổn định để dedup cross-run. `dedup.py:21-24` chỉ dedup exact URL/title, không bắt tin trùng nội dung khác nguồn.

**Giải pháp:** dùng `hashlib.md5(title|url|published_at).hexdigest()` cho `raw_hash`, thêm fuzzy dedup (TF-IDF/cosine hoặc `rapidfuzz`) cho `dedup_group_id`.

### 17. Các lỗi `ruff` còn lại cần dọn

* `E722 bare except`: `vnbroker/core/utils/env.py:130`, `vnbroker/core/utils/transform.py:723`, `vnbroker/explorer/tcbs/company.py:147,156`, `vnbroker/explorer/vci/trading.py:105` — thay bằng `except Exception`.
* `F841 unused variable`: `vnbroker/core/utils/market.py:32` (`valid_markets`), `vnbroker/explorer/kbs/financial.py:140` (`unit_list`), `vnbroker/explorer/tcbs/quote.py:361,473`.
* `E741 ambiguous `l``: `vnbroker/broker/tcbs/portfolio.py:246` — đổi thành `local_df`.
* `F403 import *`: `vnbroker/core/__init__.py`, `vnbroker/explorer/tcbs/__init__.py`, `vnbroker/explorer/vci/__init__.py`, `vnbroker/explorer/misc/__init__.py` — thay bằng import显式 + `__all__`.
* `E402 import không ở top`: `vnbroker/__init__.py`, `vnbroker/broker/session.py:25`, `vnbroker/explorer/vci/company.py:352`, `vnbroker/explorer/tcbs/listing.py:372` — chuyển lên top hoặc thêm `# noqa: E402` có lý do.

---

## III. Gap kiến trúc / tính năng (P2 — roadmap v3.4)

1. **`fx/crypto/world_index` chết hoàn toàn** (`vnbroker/common/client.py:139-194` raise `NotImplementedError`). `connector/binance/__init__.py` tồn tại nhưng không wiring. Mất 3 mảng user cần nhất.
   → Wiring Binance cho `crypto()`, TwelveData/Yahoo cho `fx()/world_index()`, hoặc xóa hẳn khỏi facade nếu không làm.

2. **Không có circuit-breaker thật sự:** `source_router.py:142` cooldown `5*2^(n-1)` max 90s trong memory, mất khi restart, không có half-open probe, không metric Prometheus. Chỉ là exponential backoff đơn giản.
   → Circuit-breaker persistent (disk/redis) + half-open probe + expose health metric.

3. **Giá đơn vị chưa chuẩn:** đã có `_resolve_target_price_unit` nhưng `DNSEQuote` trả raw VND, `TCBSQuote._compute_ohlc_from_intraday` tự normalize, VCI/KBS normalize chỗ khác — thiếu test cross-provider đầy đủ (`test_quote_price_unit_consistency` chỉ cover 1 phần).
   → Chuẩn hóa 1 điểm duy nhất trong `transform.normalize_price_columns`, thêm test matrix 4 providers x stock/index/derivative.

4. **Broker lane 2 đầu không统一:** `vnbroker/broker/tcbs` (iFlash OTP) + `vnbroker/brokerage/tcbs` (HMAC+WS) + `connector/dnse` (HMAC+JWT) — 3 auth flow, 2 registry (`BrokerRegistry` vs `ProviderRegistry`), không có `UnifiedRegistry` wiring cho brokerage write. `Vnbroker.broker()` ở `vnbroker/common/client.py:256-259` tự register mỗi lần gọi, không thread-safe.
   → Thống nhất brokerage auth qua `BrokerSession`, gộp `BrokerRegistry` vào `UnifiedRegistry`, register 1 lần ở import.

5. **Config phân mảnh:** `vnbroker/config.py:26` default `RATE_LIMIT_RPM=300` nhưng `CLAUDE.md` ghi 500; `Config` trong `common/data.py:183-189` là class khác hoàn toàn cùng tên; `VERSION_REQUIREMENTS` vẫn `3.1.0` dù version `3.3.0`; `LOG_LEVEL=DEBUG` mặc định gây spam log.
   → Gộp 2 `Config`, đồng bộ `RATE_LIMIT_RPM`, chuyển `LOG_LEVEL` default về `INFO`, cập nhật `VERSION_REQUIREMENTS` lên `3.3.0`.

6. **Thiếu tài liệu API + type stub:** chưa có `.pyi`, chưa có API reference. `ui/registry.py` là cây tĩnh tốt nhưng chưa cover broker/brokerage lanes.

---

## IV. Kế hoạch sửa chữa đề xuất

### P0 (làm ngay, <1 ngày)

* [ ] Sửa `core/constants.py:23` (`"KBS"` → `KBS`).
* [ ] Sửa `broker/tcbs/money.py` import `BrokerValidationError`.
* [ ] Thêm `import asyncio` ở `brokerage/tcbs/client.py`, `import websockets` ở `explorer/tcbs/websocket.py`.
* [ ] Xóa dead `df` block ở `explorer/tcbs/quote.py:377-381`.
* [ ] Gộp duplicate `normalize_vietnamese_text_to_snake_case` trong `core/utils/parser.py`.
* [ ] Xóa `explorer/dnse/financial.py` dead hoặc sửa `common/data.py` dùng registry.
* [ ] Chạy `ruff check --fix`, bật lại `mypy --strict` trong CI.

### P1 (1–2 tuần)

* [ ] Thay `lru_cache` trên method bằng `TTLCache`, fix `hit_rate`.
* [ ] Bỏ retry 2 lớp, giữ retry ở `BaseAdapter` duy nhất.
* [ ] Fix retail timeout/secret/sort/print → logger.
* [ ] Fix DNSE timezone + failover đúng, news `md5` + `source_used`.
* [ ] Vector hóa `cci`, thêm `indicators` filter, refactor `fetch_multiple` sang 1 pool/async.
* [ ] Dọn toàn bộ `E722`, `F841`, `F403`, `E402`.

### P2 (roadmap v3.4)

* [ ] Wiring Binance / TwelveData cho FX-Crypto-WorldIndex.
* [ ] Circuit-breaker persistent + half-open + metric.
* [ ] Chuẩn hóa price-unit 1 điểm + test matrix 4 providers.
* [ ] Thống nhất brokerage auth + registry.
* [ ] Gộp `Config`, sửa `RATE_LIMIT_RPM`, `LOG_LEVEL`, `VERSION_REQUIREMENTS`.
* [ ] Bổ sung `.pyi` stub + API reference docs.

---

## V. Phụ lục — Lệnh tái hiện

```bash
# Unit tests
python -m pytest tests/unit -q

# Lint
python -m ruff check vnbroker

# Type-check (hiện bị chặn bởi core/constants.py:23)
python -m mypy vnbroker --ignore-missing-imports

# Coverage (cần chạy với pytest-cov trước)
python -m pytest tests/unit -q --cov=vnbroker --cov-report=term-missing
```
