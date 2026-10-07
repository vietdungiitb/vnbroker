# AUDIT TẦNG 1 — DỮ LIỆU THỊ TRƯỜNG ẨN DANH

**Ngày:** 2026-10-05 · **Phạm vi:** `explorer/`, `common/data.py`, `api/`, `base.py`,
`core/source_router.py`, `core/utils/{client,cache}.py`, `ui/`
**Cơ sở:** đọc code + probe runtime thật (`.venv/Scripts/python.exe`, mạng thật tới
KBS/VCI/TCBS). Số liệu hiệu năng dưới đây là **đo**, không ước lượng.

---

## 0. TÓM TẮT

| Câu hỏi của chủ | Trả lời |
|:---|:---|
| Đang dùng provider nào? | Registered: **VCI, KBS, TCBS, DNSE, SSI** (+ RSS cafef/vneconomy cho news, FMARKET cho fund) |
| Đã có xoay vòng khi rate-limit? | **Có về mặt code, KHÔNG có trên đường chính.** Failover chỉ chạy khi `_auto_sources` tồn tại — biến này chỉ được set trong test. Runtime thật: `source="AUTO"` → ghim VCI, không bao giờ xoay |
| Đã có bulk/multi-provider chưa? | Bulk **có**, nhưng **chỉ 1 provider** và **vỡ khi failover**. Multi-provider cùng tải **chưa có** — router chỉ failover tuần tự |
| Có thể tăng tốc? | **Có, rất nhiều và rất rẻ.** Đo được 5–9× chỉ bằng cách dùng chung connection pool |

Kết luận một dòng: **kỹ thuật xoay vòng đã viết xong nhưng chưa nối vào sản phẩm; nút
thắt hiệu năng nằm ở connection pool chứ không ở provider.**

---

## 1. BẢN ĐỒ PROVIDER (đo từ `ProviderRegistry.list_all()`)

```
company    : dnse, kbs, ssi, tcbs, vci
financial  : dnse, kbs, ssi, tcbs, vci
listing    : dnse, kbs, ssi, tcbs, vci
quote      : dnse, kbs, ssi, tcbs, vci
trading    : dnse, kbs, ssi, tcbs, vci
news       : dnse, kbs, rss_cafef, rss_vneconomy, ssi, tcbs, vci
screener   : kbs, ssi, vci
indices/live/securities : ssi
```

**Pool AUTO thực sự dùng** (`core/source_router.py:28`):

| module | pool | primary |
|:---|:---|:---|
| quote, company, financial | `vci, kbs` | `vci` |
| listing, trading | `kbs, vci` | `kbs` |
| news | `vci, kbs, rss_cafef, rss_vneconomy` | `vci, kbs` |

**TCBS và DNSE không có trong pool AUTO** — dù đã registered.

### 1.1 Pool ẩn danh thực tế chỉ rộng 2

Probe live:

- `TCBS.history(1D)` → `NotImplementedError` (iFlash OpenAPI không có OHLCV đa ngày)
- `TCBS.intraday()` → `ConnectionError: requires valid JWT token`
- `TCBS.price_board([...])` → 0 dòng
- `DNSEQuote.__init__` → `ValueError: DNSE cần api_key và api_secret`

→ **TCBS và DNSE không phải provider ẩn danh dù đã register.** SSI cần key.
Pool tầng 1 = **KBS + VCI = 2 provider**. Hệ quả: failover đúng 1 lần; KBS và VCI
chết đồng thời là hard fail, không có lưới an toàn.

---

## 2. PHÁT HIỆN LỚN — FAILOVER KHÔNG CHẠY TRÊN ĐƯỜNG CHÍNH

`common/data.py:527` — `_run_with_failover` rẽ nhánh failover **chỉ khi**
`getattr(self, "_auto_sources", None)` khác `None`.

`_auto_sources` được set ở **đúng một chỗ**: `tests/contract/test_failover_tier1.py:87`.
Không có dòng nào trong `vnbroker/` set nó.

Trong khi đó `Quote._load_direct_provider` (`data.py:462`) làm:

```python
if source == "auto":
    source = candidates[0]        # "vci"
    self.source = source.upper()  # -> "VCI", ghim cứng
```

Probe thật:

```
>>> acb = Vnbroker(source="AUTO").stock("ACB")
quote.source: VCI
has _auto_sources: False
rows 20  source_used: None          <- annotate_result_source không chạy
NO FAILOVER -> ConnectionError 429 Too Many Requests
```

Cùng kịch bản trên `vnbroker/api/quote.py` (BaseAdapter) thì failover **chạy đúng**:
VCI lỗi → KBS phục vụ, `source_used="KBS"`, health store ghi
`VCI.failures=1, in_cooldown=True`.

**Vấn đề kiến trúc:** có **hai stack adapter song song**.

| Stack | Failover | Ai dùng |
|:---|:---|:---|
| `vnbroker/api/*.py` (`BaseAdapter`) | ✅ đúng | chỉ test + benchmark |
| `vnbroker/common/data.py` (`BaseComponent`) | ❌ chết | **toàn bộ public API** |

`common/client.py` và `ui/market.py` đều import từ `common.data`. `vnbroker.api.*`
không có import nào từ trong package (grep xác nhận) — **stack này bị cô lập khỏi sản phẩm**.

→ **README dòng 260 ("Failover áp cho history, intraday, price_depth") không đúng
với đường chạy thật.**

### 2.1 Các module không phải quote: không failover, chỉ ghim

`Company / Finance / Listing / Trading` dùng `_call_with_fallback` với
`FALLBACK_MAP = {"DNSE": ["KBS","VCI"], "SSI": ["KBS","VCI"]}` — **không có key
"VCI"/"KBS"**. `AUTO` ở các module này bị `_resolve_auto_source` ghim cứng thành
`candidates[0]` lúc khởi tạo, không bao giờ xoay.

Probe (`source="VCI"`, nhân bản lỗi 429 vào provider):

```
company -> RAISED ConnectionError 429 rate limit
listing -> RAISED ConnectionError 429 rate limit
news    -> trả 50 dòng
```

### 2.2 News không có fallback và tự tái tạo provider mỗi lần gọi

- `News.FALLBACK_MAP = {}`
- `News.latest()` gọi `_update_data_source(symbol)` → **`self.data_source` là object
  mới mỗi lần** (probe: `id()` đổi). Hệ quả kép:
  1. không có đường fallback nào;
  2. phá cache (mục 5.3).

---

## 3. BULK CÓ, NHƯNG VỞ KHI FAILOVER

Bulk hiện có ở tầng provider: `KBS.Quote.fetch_multiple` (ThreadPoolExecutor +
`AdaptiveController` + `GlobalPressure`), `VCI.Quote.fetch_multiple` (asyncio +
httpx), `TCBS.fetch_multiple`, `SSIQuote.fetch_multiple`.

**Ba lỗi khiến bulk chưa dùng được như một tính năng tầng 1:**

### 3.1 `symbols=` bị bỏ âm thầm → mất dữ liệu không báo lỗi

`_filter_kwargs` (`data.py:751`) lọc kwarg theo signature provider:

```
provider có `symbols`   -> nhận đủ, trả N frame
provider không có       -> 'Quote: bỏ kwarg không hỗ trợ symbols' (chỉ log DEBUG)
provider có **kwargs    -> nhận `symbols` rồi BỎ QUA, trả 1 frame, KHÔNG lỗi
```

DNSE đúng loại thứ ba (`history(self, symbol, start, end, interval, **kwargs)`).
Probe mô phỏng failover KBS → provider loại `**kwargs`:

```
type: DataFrame  rows: 2
>>> USER ASKED 3 SYMBOLS, GOT 1 FRAME  -> SILENT DATA LOSS
```

### 3.2 Bulk **không** qua chuẩn hoá

`Quote.history` chỉ gọi `_normalize_quote_result` khi `isinstance(result, pd.DataFrame)`.
Bulk trả `list[DataFrame]` → **bỏ qua**. Probe:

```
single  tz: Asia/Ho_Chi_Minh
bulk    tz per frame: [None, None]
```

→ Hợp đồng "mọi provider trả cùng schema" **giữ ở đường đơn, vỡ ở đường bulk** —
đúng đường dữ liệu lớn mà câu hỏi này nhắm tới.

### 3.3 Bulk nuốt lỗi, không manifest

`fetch_multiple` (`kbs/quote.py:_run_one`) `except Exception: return None`.
Đo 120 mã: nhận **105 frame, mất 15, không cảnh báo**. Người dùng phải tự map bằng
`df.attrs["symbol"]` và **tự phát hiện thiếu**. Danh sách mã của KBS gồm cả mã
không có dữ liệu OHLCV (`SAL, VPW, PTM, VCE, VNI, MES, NDW, EGL, GTX, CH5, UXC, HCI, CCS`)
→ lỗi `"Dữ liệu trống cho mã ..."` bị coi là lỗi provider.

---

## 4. NÚT THẮT HIỆU NĂNG: SESSION THEO THREAD

`core/utils/client.py:73` — `_get_thread_session()` tạo `requests.Session` **mới cho
mỗi thread**. `fetch_multiple` lại tạo **ThreadPoolExecutor mới cho mỗi batch**
(`kbs/quote.py:249`). Hệ quả: **mỗi symbol một thread mới → một TLS handshake
mới**.

Đo thật, 120 mã, cùng khoảng thời gian, cùng `max_concurrency`:

| Cách | Kết quả | ms/sym | Ước lượng full market (1522 mã) |
|:---|---:|---:|---:|
| **A. code hiện tại** (thread-local session) | 13.93s | 116 | ~172s |
| **B. session dùng chung** (pool 256) | 2.61s | 22 | ~33s |
| **C. session dùng chung, đã warm** | 1.51s | 13 | ~20s |

→ **5.3× đến 8.9×** chỉ bằng một thay đổi. Nguyên nhân đã xác nhận bằng probe
đơn lẻ: request trong cùng thread 5 lần = 0.59s (118ms/req); thread mới mỗi lần
= ~445ms/req (đúng bằng chi phí handshake).

Cùng bệnh ở `explorer/kbs/trading.py:130` — `price_board` gọi `requests.post` trần,
không qua client:

| | ms/call |
|:---|---:|
| `requests.post` trần (hiện tại) | 643 |
| session dùng chung | **31** |

**Đây là đòn bẩy lớn nhất và rẻ nhất trong toàn bộ đề xuất.**

---

## 5. NHỮNG GÌ ĐÃ LÀM TỐT (giữ nguyên)

- **5.1 Chuẩn hoá tập trung.** `_normalize_quote_result` (`data.py:705`) là một
  điểm kiểm soát duy nhất: tz → `Asia/Ho_Chi_Minh`, lọc biên `[start, end]`, sort,
  không mutate input. Thiết kế đúng — provider mới tự tuân thủ.
- **5.2 Không bao giờ trả DataFrame rồng khi hết provider.** `_run_with_failover`
  ném lỗi gốc (`data.py:589`). Đúng tinh thần "lỗi thấy được hơn sai âm thầm" —
  dù nhánh đó hiện không chạy (mục 2).
- **5.3 Health store bền vững.** `HealthStore` sqlite + in-memory, backoff
  `min(90, 5·2^(n-1))`, half-open probe, debounce ghi 1.0s/10 event. Có thể dùng
  lại nguyên vẹn.
- **5.4 `AdaptiveController` + `GlobalPressure`** có thật và dùng chung cho
  KBS/TCBS. Đo: mc 1→16 giảm 737→122 ms/sym.
- **5.5 Test contract có thật.** `tests/contract` — 58 test pass; full
  `tests/unit + tests/contract` = **1006 passed, 5 skipped**.
- **5.6 Endpoint bulk thật đã có.** KBS `/stock/iss` nhận **1522 mã trong 1
  request, 1.14s**. Đây là nền tảng để xây `bulk()`.

**Lỗi cache cần biết:** `TTLCache._make_key` (`cache.py:58`) dùng
`str(arg)` cho mọi arg — với `self` trong bound method, key chứa **địa chỉ bộ nhớ**:

```
all_symbols|<vnbroker.explorer.kbs.listing.Listing object at 0x000002113ED43770>
all_symbols|<vnbroker.explorer.kbs.listing.Listing object at 0x000002113ED1E210>
```

→ **TTL 86400s nhưng cache hit 0%** nếu tạo object mới (mà `News` tạo object mới
mỗi lần gọi). Cache chỉ hữu ích khi tái dùng đúng instance đó.

---

## 6. ĐỀ XUẤT CẢI TIẾN

### P0 — Sửa sai lệch (chặn promise "không cần biết provider")

**P0.1 — Nối failover thật vào `common/data.py`.**
Trong `Quote.__init__`, khi `source == "AUTO"`, dựng sẵn dict provider cho toàn bộ
pool và gán `self._auto_sources`. Đây là fix 1 chỗ; nhánh failover + health store +
circuit breaker đã viết sẵn sẽ chạy ngay, không cần viết lại.
→ Đồng thời: cân nhắc **xoá một trong hai stack** để không còn adapter nào bị cô lập.
`BaseAdapter` có logic failover đúng; `BaseComponent` đang là bản chết. Hợp nhất về
một, bỏ `common/data.py` khỏi đường chính.

**P0.2 — `FALLBACK_MAP` hai chiều cho module không phải quote.**
Thêm `"VCI": ["KBS"], "KBS": ["VCI"]` cho `Company/Finance/Listing/Trading/News`;
bỏ `_resolve_auto_source` ghim cứng, thay bằng `build_source_order` mỗi lần gọi.

**P0.3 — `News` không tái tạo provider mỗi lần gọi.**
Chỉ tạo lại khi `symbol` thực sự đổi. Sửa luôn cache key.

**P0.4 — Bulk phải chuẩn hoá và phải có manifest.**
- Áp `_normalize_quote_result` cho **từng frame** khi kết quả là `list`.
- Trước khi gọi provider, kiểm tra provider có nhận `symbols` không. Nếu không →
  **fan-out ở tầng data** (N lần gọi đơn, song song) thay vì bỏ kwarg.
  Cấm `**kwargs` nuốt `symbols`.
- Trả về kèm manifest: `{requested, returned, failed: {symbol: lỗi},
  source_per_symbol}`. Không bao giờ trả list ngắn hơn mà không nói.

**P0.5 — Phân biệt "rỗng" và "lỗi".**
VCI trả DataFrame rồng cho mã không tồn tại → router ghi `record_success`, không
bao giờ xoay. Ngưỡng: frame rỗng + symbol hợp lệ = coi như thất bại, thử provider
kế; vẫn rỗng ở mọi provider thì mới trả về kèm cảnh báo.

---

### P1 — Hiệu năng (đo được, thay đổi nhỏ)

**P1.1 — Session dùng chung thay thread-local.** *(đòn bẩy lớn nhất: 5–9×)*
Một module-level `requests.Session` + `HTTPAdapter(pool_connections=256,
pool_maxsize=256)` chia sẻ giữa các thread (Session của `requests` an toàn với
nhiều thread ở mức connection pool). Giữ `threading.local` chỉ cho session của
luồng nếu thực sự cần.

**P1.2 — `kbs/trading.py` đi qua client chung.** 643ms → 31ms/call.

**P1.3 — Một ThreadPoolExecutor cho cả lệnh bulk,** không tạo lại theo batch
(`kbs/quote.py:249`). Cắt cả overhead tạo thread lẫn TLS handshake.

**P1.4 — Ưu tiên endpoint bulk trước fan-out.** `bulk()` thử, theo thứ tự:
1. KBS `/stock/iss` — **1522 mã / 1 request / 1.14s** (bảng giá realtime)
2. TCBS `second-tc-price?tickers=a,b,c` (cần kiểm auth)
3. SSI `securitiesSummary` (khi có key)
4. Chỉ fan-out từng mã cho **OHLCV lịch sử** — không provider nào có endpoint
   bulk cho loại này.

**P1.5 — Cache theo giá trị, không theo `id()`.** Key = `(provider, method,
normalized_args)`, bỏ `self`. TTL cho listing/industry **thực sự có hiệu lực**;
thêm cache daily-bar ngắn hạn (vd 5 phút trong phiên) để chặn 10 lệnh giống nhau.

---

### P2 — Multi-provider cùng tải + chiều sâu pool

**P2.1 — Chia tải bulk trên nhiều provider (thứ chủ đang hỏi).**
Với lệnh bulk N mã: phân vùng `N` mã theo **sức khoẻ provider** (`health()` +
`last_success_age_sec`), chạy **đồng thời** mỗi provider một ThreadPoolExecutor,
failover **theo từng mã** chứ không theo cả lệnh. Kết quả: một provider chết
giữa chừng chỉ mất phần của nó, phần còn lại vẫn về; và tải được chia giữa 2
provider nên không đâm vào rate-limit của một chỗ.

**P2.2 — `PRIMARY_SOURCE_POOLS["quote"] = ["vci"]` là pool 1 phần tử → hash-shard
vô nghĩa.** Comment trong file cũng thừa nhận. Đặt `["vci","kbs"]` sẽ khiến hash-shard
thật sự rải tải, thay vì ghim 100% vào VCI rồi đổi 100% sang KBS khi VCI rate-limit
(thundering herd, không phải chia tải).

**P2.3 — Rate-limit theo provider, không phải cooldown chung.**
`record_failure` hiện gộp 429 với mất mạng: cùng backoff 5/10/20/40/90s. Cần:
- Token bucket per provider (`Config.RATE_LIMIT_RPM` đã khai báo ở `config.py:26`
  nhưng **chỉ `async_client.py` dùng** — `send_request` đồng bộ không giới hạn tốc độ).
- 429 → đọc `Retry-After`, khoá đúng thời hạn provider đó; **giảm `max_concurrency`
  của provider đó** thay vì đổi hẳn sang provider khác.

**P2.4 — Nói thẳng giới hạn pool 2.** Nếu không thêm provider ẩn danh, AUTO có
độ sâu 2 và phải tài liệu hoá: *"KBS và VCI cùng gián đoạn → `history()` ném lỗi;
`price_board` vẫn chạy được."* Nguồn ẩn danh đáng thử thêm: endpoint công khai
của DNSE (bỏ HMAC), KBS SAS, và các RSS cho news (đã có).

---

## 7. API ĐỀ XUẤT — BULK LONG-FORMAT

Hiện `history(symbols=[...])` trả `list[DataFrame]` không có cột `symbol` — bất tiện
cho phân tích. Thay bằng một entry point duy nhất:

```python
from vnbroker.ui.market import Market

mkt = Market(auto=True)                       # không biết provider

# 1 lệnh, không cần biết provider, trả 1 DataFrame long-format
df = mkt.bulk.history(symbols=["ACB","VNM","HPG"], start="2024-01-01", end="2024-06-30")
#   columns: time, open, high, low, close, volume, symbol
#   attrs:   {"sources_used": {"ACB": "KBS", "VNM": "VCI", ...},
#             "failed": {}, "requested": 3, "returned": 3}

pb = mkt.bulk.price_board()                   # toàn thị trường, 1 request
#   1522 dòng ~ 1.1s
```

Ràng buộc bắt buộc của API này: **cùng schema với đường đơn** (tz-aware, cùng cột,
đã sort), và **luôn có manifest** trong `attrs` — không bao giờ im lặng thiếu mã.

---

## 8. THỨ TỰ LÀM

| # | Việc | Nỗ lực | Kết quả |
|:--|:---|:---|:---|
| 1 | P1.1 session dùng chung | S | **5–9×** nhanh hơn, toàn bộ bulk |
| 2 | P1.2 `kbs/trading` qua client | XS | 643→31ms/call |
| 3 | P0.1 nối `_auto_sources` | S | failover thật trên đường chính |
| 4 | P0.4 bulk chuẩn hoá + manifest | M | hợp đồng tầng 1 đúng ở đường bulk |
| 5 | P0.2 + P0.3 fallback map, News | S-M | company/listing/trading/news có xoay vòng |
| 6 | P1.5 cache theo giá trị | S | TTL có hiệu lực |
| 7 | P2.1 chia tải multi-provider | M | bulk dùng song song 2 provider |
| 8 | P2.2 pool `["vci","kbs"]` | XS | hash-shard thật |
| 9 | P2.3 token bucket per provider | M | không đâm rate-limit |

---

## 9. GHI CHÚ PHƯƠNG PHÁP

- Số hiệu năng đo bằng `.venv/Scripts/python.exe` (Python 3.13, Windows 11), mạng
  thật, cùng khoảng thời gian cho mọi phép so sánh. Bảng mục 4 chạy 3 phép trong
  **cùng một process** để loại nhiễu mạng.
- Các probe chạm rate-limit thật của KBS — chạy lại benchmark nên giữ khoảng
  nghỉ giữa các lượt.
- `pytest tests/unit tests/contract` → 1006 passed, 5 skipped (contract: 58 passed).
  Cần `--basetemp` trỏ khỏi `%TEMP%` (pytest cleanup đụng `WinError 5`).
- Không sửa file nào trong repo trong lúc audit này.
