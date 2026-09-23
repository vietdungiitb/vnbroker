# Đề xuất: đưa SSI thành source market-data tương thích KBS/VCI (source-agnostic)

- **Ngày:** 2026-09-23
- **Trạng thái:** Đề xuất chờ phê duyệt (chưa triển khai code)
- **Tài liệu liên quan:** `docs/SSI_INTEGRATION_PLAN.md` (broker lane), `docs/SSI_USAGE_GUIDE.md`, `docs/DNSE_EXPLORER_SPEC.md` (tiền lệ DNSE)
- **Phạm vi:** market-data lane (`Vnbroker.stock(..., source="SSI")`) — không thay đổi broker lane (`vnbroker/broker/ssi/`)

---

## 0. Kết luận trước (để quyết nhanh)

**Đề xuất phê duyệt Phương án B — Hybrid "SSI-native ở đâu có, fallback KBS/VCI ở đâu SSI không có":**

```python
vn = Vnbroker()
acb = vn.stock("ACB", source="SSI")   # user không quan tâm backend
acb.quote.history(start="2024-01-01", end="2024-12-31")  # SSI-native
acb.company.overview()    # tự fallback KBS/VCI, user không biết
acb.finance.ratio()       # tự fallback KBS/VCI, user không biết
```

Lý do: **SSI FastConnect Data chính thức chỉ có ~9 API market-data, KHÔNG có Company/Finance/News**.
Parity 100% native là bất khả thi về mặt kỹ thuật — bất kỳ ai hứa "viết lại Company/Finance bằng SSI"
đều là bịa dữ liệu. Phương án hybrid là cách duy nhất đạt `source="SSI"` chạy được toàn bộ
hàm KBS/VCI mà vẫn trung thực về nguồn.

---

## 1. Hiện trạng (đã kiểm chứng từ code + docs chính thức SSI)

### 1.1. SSI broker lane hiện có gì (`vnbroker/broker/ssi/`, 15 files)

| Nhóm | Methods | Nhận xét |
|---|---|---|
| Auth (`auth.py`) | `authenticate / request_otp / refresh / ensure_authenticated` | **Bắt buộc `consumerID + consumerSecret` ngay cả khi chỉ đọc market-data**. Không có anonymous/public như VCI/KBS |
| Market (`market.py`, FastConnect v3 `GET /api/v3/data/...`) | `get_ohlc`, `get_indexes`, `get_index_summary`, `get_board_summary`, `get_securities_info`, `get_securities_summary`, `get_master_data` (7 hàm) | Chỉ OHLC + metadata + summary. **Không có tick khớp lệnh REST, không có price-depth REST, không có Company/Finance/News** |
| Brokerage | balance, PPMMR, purchasing power, positions, orders, place/modify/cancel, 7 lệnh FCO, stream WS | Tốt cho trade lane, không liên quan market-data lane |
| Stream (`stream.py`, `wss://stream.ssi.com.vn/ws/v3`) | `TradeTick`, `QuoteUpdate`, `ForeignRoom`, ... qua WS | Có tick/depth realtime nhưng **stateful (connect/subscribe/disconnect)**, không khớp explorer sync hiện tại |

Chi tiết xem `docs/SSI_INTEGRATION_PLAN.md` §1 (wire-protocol) và `docs/SSI_USAGE_GUIDE.md`.

### 1.2. Docs chính thức SSI xác nhận giới hạn

`guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs` liệt kê toàn bộ Data API v2 — chỉ 9 endpoint:

> `AccessToken, Securities, SecuritiesDetails, IndexComponents, IndexList,`
> `DailyOhlc, IntradayOhlc, DailyIndex, DailyStockPrice`

**Không có:** profile công ty, cổ đông, BCTC, chỉ số tài chính, tin tức, sổ lệnh REST.
Đây là giới hạn của SSI server, không phải do ta chưa implement.

### 1.3. Ma trận KBS/VCI vs SSI-native (13 hàm P0 cần tương thích)

| Hàm chuẩn KBS/VCI | SSI-native đáp ứng? |
|---|---|
| `quote.history` | ✅ ~80% (`get_ohlc` map được, cần convert schema) |
| `listing.all_symbols / symbols_by_exchange / symbols_by_group` | ✅ một phần (`get_securities_info` + `master_data` + `get_indexes`) |
| `trading.price_board` | ⚠️ giả lập được bằng loop `securities_summary` (chậm, tốn quota 10 rps) |
| `quote.intraday` (tick khớp lệnh) | ❌ REST không có; chỉ có WS hoặc nến `1m` (không phải tick) |
| `quote.price_depth` | ❌ REST không có; chỉ có WS |
| `company.*` (8–12 hàm), `finance.*` (4 hàm), `news.*` (3 hàm) | ❌ hoàn toàn không có nguồn |

**Kết luận:** native tối đa đạt ~4/13 P0. 9/13 còn lại bắt buộc phải fallback hoặc `NotImplementedError`.

### 1.4. Tiền lệ DNSE trong repo đã giải quyết bài toán y hệt

`vnbroker/explorer/dnse/company.py:DNSECompany` — DNSE OpenAPI cũng không có company endpoints
→ implement "fallback provider": trả `DataFrame` rỗng đúng schema +
`Company.FALLBACK_MAP = {"DNSE": ["KBS", "VCI"]}` (`vnbroker/common/data.py:633`) +
`_call_with_fallback` tự bỏ qua DF rỗng và thử KBS/VCI (`vnbroker/common/data.py:250-289`).
SSI có thể tái dùng đúng pattern này — đã được chứng minh, không phát minh mới.

---

## 2. Định nghĩa "xong" (Definition of Done) — source-agnostic thật

1. `vn.stock("ACB", source="SSI")` chạy được **toàn bộ** hàm `quote/company/finance/listing/trading/news`
   mà KBS/VCI chạy được — không `AttributeError`, không vỡ schema.
2. Hàm nào SSI-native có → dùng SSI, gắn `df.attrs["source_used"] = "SSI"`.
   Hàm nào SSI không có → tự fallback KBS/VCI,
   gắn `source_requested="SSI", source_used="KBS"` (minh bạch, như DNSE làm với news ở `data.py:762-852`).
3. Schema/params tương thích: `history(start, end, interval)` với
   `interval ∈ {1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M}`, date `YYYY-MM-DD`,
   return `[time, open, high, low, close, volume]`, giá VND, `floating=2` —
   user đổi `source="SSI" ↔ "KBS"` không phải sửa code.
4. `SUPPORTED_SOURCES` của `Vnbroker` + `StockComponents/Quote/Company/Finance/Listing/Trading/News`
   thêm `"SSI"`. **Không** đưa SSI vào `OPEN_SOURCE_CANDIDATES` (pool AUTO) vì cần auth —
   AUTO vẫn chỉ VCI/KBS/RSS (`vnbroker/core/source_router.py:28`).

---

## 3. So sánh 3 phương án

| Tiêu chí | A. Native-only (viết `explorer/ssi/*` thuần SSI, thiếu thì `NotImplementedError`) | **B. Hybrid SSI-native + fallback KBS/VCI (đề xuất)** | C. Gom tất cả về một `SSIExplorerAdapter` ôm cả WS stateful |
|---|---|---|---|
| Đạt source-agnostic? | ❌ Không. `company/finance/news/intraday/depth` vỡ → user vẫn phải `if source == SSI` | ✅ Có. Chạy hết, minh bạch nguồn qua `attrs` | ✅ Có nhưng... |
| Trung thực dữ liệu | ✅ | ✅ (fallback ghi rõ nguồn) | ⚠️ rủi ro "chế" tick/depth từ WS buffer |
| Effort | S (~1 tuần) nhưng vô dụng | **M (~2–3 tuần, 4 phase)** | L (5–6 tuần, stateful WS trong explorer sync = đổi kiến trúc) |
| Rủi ro kỹ thuật | Thấp nhưng fail mục tiêu | Thấp (tái dùng pattern DNSE + `SSIMarketService`) | Cao (reconnect/subscribe/disconnect, thread-safety, leak session) |
| Vận hành | Thêm 1 source nửa vời | Thêm 1 source đầy đủ, fallback miễn phí thừa hưởng health của KBS/VCI | Phải nuôi WS lifecycle, khó test |
| Bảo mật | — | Credentials SSI qua env, lazy-auth + token cache, không log secret (kế thừa `SSIHttpClient`) | Như B + thêm rủi ro token trong thread WS |

**Loại A** vì không đạt mục tiêu source-agnostic.
**Loại C** vì biến explorer stateless thành stateful — lợi (tick/depth realtime) không xứng chi phí
và rủi ro; khi nào cần realtime thì user dùng `vn.broker(provider="ssi").stream` vốn đã có.
**Chọn B.**

---

## 4. Phương án B chi tiết

### 4.1. Kiến trúc: package mới `vnbroker/explorer/ssi/`, tái dùng broker lane

```
vnbroker/explorer/ssi/
  __init__.py        # register ProviderRegistry 6 modules
  _auth.py           # SSIExplorerSession: lazy authenticate(), cache token, refresh()
  quote.py           # SSIQuote    : history() native (get_ohlc); intraday/price_depth → NotImplementedError để fallback lo
  listing.py         # SSIListing  : all_symbols/symbols_by_exchange/symbols_by_group native (securities_info + master_data + indexes)
  trading.py         # SSITrading  : price_board native-dạng-loop (securities_summary) + cảnh báo quota
  company.py         # SSICompany  : theo mẫu DNSECompany — trả DF rỗng đúng schema → _call_with_fallback tự sang KBS/VCI
  financial.py       # SSIFinancial: tương tự (4 hàm trả rỗng đúng long-format)
  news.py            # SSINews     : tương tự
```

Nguyên tắc layering:

- `explorer/ssi/quote | listing | trading` là **wrapper mỏng** quanh `SSIMarketService`
  (không copy logic HTTP, không đụng `SSIHttpClient` trực tiếp).
  Auth tập trung một chỗ: `explorer/ssi/_auth.py`.
- `explorer/ssi/company | financial | news` **không gọi SSI server** (vì không có endpoint) —
  trả rỗng đúng schema như DNSE, để `_call_with_fallback` (`data.py:250`) tự chuyển sang KBS/VCI.
  Không bịa dữ liệu.
- Không sửa `broker/ssi/*`. Không sửa `core/source_router.py` (SSI đứng ngoài AUTO pool).

### 4.2. Mapping schema cụ thể (đã đối chiếu code hai đầu)

**Quote.history:** `SSIMarketService.get_ohlc(symbol, timeframe, from_date, to_date)` → chuẩn KBS/VCI:

- `interval`: `1D → 1d, 1H → 1h, 1W → 1w, 1M → 1M`; `30m` SSI v3 không có →
  map sang `15m` + resample (phase 2) hoặc `NotImplementedError` với message hướng dẫn (phase 1).
- date: `YYYY-MM-DD → YYYY/MM/DD`; default lookback 365 ngày
  (SSI default "hôm nay" gây bất ngờ → phải đổi).
- cột: `trading_date → time (datetime64)`, bỏ `value` (giữ khi `get_all=True`),
  ép `volume → int64`, giá VND giữ nguyên + `floating=2`, sort `time` asc,
  hỗ trợ `count_back / length / to_df / get_all`, set `attrs[symbol, source, interval, start, end]`.
- phân trang: SSI `page/size (max 1000)` → loop gom khi `get_all=True`.
  **Superseded bởi `SSI_EXPLORER_IMPLEMENTATION_PLAN.md` FR-Q1/NB-1:**
  `get_ohlc` không trả `pagesCount` nên không copy nguyên văn loop của `get_master_data`;
  áp dụng quy tắc dừng cứng (trang rỗng / row < size / trần page=10).

**Listing:** `get_securities_info(board/index)` + `get_master_data` + `get_indexes`:

- `all_symbols() → DF[symbol, organ_name]` (từ `symbol, symbol_name_vi`).
- `symbols_by_exchange(lang, get_all)` — filter `board HOSE/HNX/UPCOM`.
- `symbols_by_group(VN30/...)` — qua `get_securities_info(index=...)` → `pd.Series(name="symbol")`.
- `symbols_by_industries` — SSI có `icb_code/icb_name` trong `securities_info` →
  theo chuẩn ICB của VCI (khuyến nghị) thay vì mã riêng KBS.
- `all_covered_warrant / all_bonds / all_future_indices` — lọc `SecType CW/BO/FU` nếu có,
  thiếu thì `NotImplementedError` (chấp nhận được, KBS cũng thiếu `industries_icb`).

**Trading.price_board(symbols_list):** loop `get_securities_summary(symbol)` từng mã →
ráp DF phẳng theo chuẩn KBS `_PRICE_BOARD_STANDARD_COLUMNS` (~30 cột,
`explorer/kbs/trading.py:162`). Gắn warning khi `len(symbols_list) > 20` (quota 10 rps) +
hướng dẫn dùng KBS cho batch lớn. Đây là điểm yếu trung thực nhất của SSI —
phải nói rõ với user thay vì giấu.

**intraday / price_depth:** phase 1
`raise NotImplementedError("SSI REST không có tick/depth; dùng source KBS/VCI hoặc vn.broker(provider='ssi').stream")`.
`should_failover` (`core/source_router.py:293`) và `_call_with_fallback` đều bắt
`NotImplementedError` → khi thêm `FALLBACK_MAP["SSI"]`, fallback tự hoạt động.

### 4.3. Auth plumbing (điểm duy nhất làm SSI khác VCI/KBS)

VCI/KBS public; SSI/DNSE cần key. Đã có tiền lệ DNSE — copy y hệt:

1. `StockComponents.__init__` + từng facade (`Quote/Company/...`) đã có `api_key/api_secret` params —
   chỉ cần truyền tiếp xuống `SSIQuote(symbol, api_key, api_secret)` như `DNSEQuote` (`data.py:408-410`).
2. `Vnbroker.stock(symbol, source="SSI")` đọc env `VNBROKER_BROKER_SSI_API_KEY/_SECRET`
   (trùng env broker lane đã dùng — không thêm env mới) và truyền vào `StockComponents`.
3. `SSIQuote.__init__` thiếu key → `raise ValueError` message hướng dẫn đăng ký SSI + link docs
   (copy message DNSE ở `explorer/dnse/company.py:170-175`).
4. Token lifecycle: module-level `SSIExplorerSession`
   (lazy `authenticate()`, cache, thread-safe, `refresh()` trước khi hết hạn).
   Không log secret — kế thừa redaction của broker lane.
5. `SUPPORTED_SOURCES` thêm `"SSI"` ở 8 chỗ: `Vnbroker` (`common/client.py:47`),
   `StockComponents/Quote/Listing/Trading/Company/Finance/News` (`common/data.py`).
   `FALLBACK_MAP` thêm `"SSI": ["KBS", "VCI"]` ở `Trading/Company/Finance`
   (và `News` hard-fallback VCI đã có sẵn).

### 4.4. UX sau khi xong (cam kết)

```python
# Before: user phải rẽ nhánh
if source == "SSI":
    ssi = vn.broker(provider="ssi", api_key=..., api_secret=...)
    ssi.authenticate()
    df = ssi.get_ohlc("ACB", from_date="2024/01/01", ...)  # schema lạ, date lạ
else:
    df = vn.stock("ACB", source="KBS").quote.history(start="2024-01-01", ...)

# After (phương án B):
acb = vn.stock("ACB", source="SSI")  # key qua env, một lần
acb.quote.history(start="2024-01-01", end="2024-12-31")  # SSI-native
acb.company.overview()   # fallback KBS, attrs ghi rõ
acb.finance.ratio()      # fallback KBS, attrs ghi rõ
df.attrs  # {"source_requested": "SSI", "source_used": "KBS", ...}
```

### 4.5. Kế hoạch 4 phase (~2–3 tuần, TDD bắt buộc theo CLAUDE.md)

| Phase | Việc | Xong khi |
|---|---|---|
| 1. Khung + Quote (4–5 ngày) | `explorer/ssi/{__init__,_auth,quote}.py`, đăng ký `ProviderRegistry`, đấu nối `StockComponents/Vnbroker`, mapping `history` + test mock transport | `history` SSI-native pass unit + live gated 1 mã |
| 2. Listing + Trading (4–5 ngày) | `listing.py`, `trading.py` (loop + quota warning), `symbols_by_*` | batch 5 mã đúng schema KBS |
| 3. Company/Finance/News fallback (3–4 ngày) | 3 file kiểu DNSE + `FALLBACK_MAP["SSI"]`, kiểm `attrs[source_requested/source_used]` | mọi hàm company/finance/news chạy được qua fallback |
| 4. Hoàn thiện (3–4 ngày) | docs + docstring Google style, `mypy --strict`, `ruff`, `pytest tests/unit`, live test gated `vnbroker_RUN_LIVE_INTEGRATION=1` | CI xanh, không đụng `broker/ssi/*` |

Test: unit mock `SSIHttpClient` (không cần credentials) + integration live gated bằng key thật.
Không đưa SSI vào AUTO pool → không ảnh hưởng health/failover hiện tại.

### 4.6. Rủi ro & cách chặn (nói thẳng)

| Rủi ro | Mức | Chặn |
|---|---|---|
| User không có SSI credentials → `source="SSI"` lỗi | Cao (chắc chắn gặp) | `ValueError` message hướng dẫn rõ + docs; default source vẫn KBS, không ép ai |
| `price_board` loop chậm/dính 429 khi batch lớn | Trung | warning + giới hạn khuyến nghị 20 mã + hướng dẫn dùng KBS cho batch; SSI ngoài AUTO nên không ảnh hưởng router |
| SSI đổi spec v3 (đã từng đổi v2 → v3) | Trung | wrapper mỏng → chỉ sửa mapping một chỗ; pin `_paths.py` |
| Kỳ vọng "SSI cho tất cả" vượt thực tế | Cao | docs ghi rõ ma trận native-vs-fallback + `attrs` minh bạch từng response |
| Token hết hạn giữa phiên dài | Thấp | `ensure_authenticated()` trước mỗi batch + retry 401 một lần |

---

## 5. Xin phê duyệt 4 điểm

1. **Chốt Phương án B** (hybrid), loại A và C vì lý do ở §3.
2. **Cho phép SSI yêu cầu credentials** (`VNBROKER_BROKER_SSI_API_KEY/_SECRET`) —
   đồng nghĩa SSI không bao giờ vào AUTO pool public, chỉ dùng explicit `source="SSI"`.
3. **Cho phép fallback chéo SSI → KBS/VCI** cho Company/Finance/News (và intraday/depth phase 1)
   với `attrs` minh bạch nguồn — thay vì trả lỗi.
4. **Cho phép tạo package mới `vnbroker/explorer/ssi/` (~7 files, ≤400 dòng/file)**
   theo kế hoạch 4 phase trên, không sửa `broker/ssi/*`.

Nếu approve 4 điểm này, triển khai Phase 1 ngay
(TDD: test trước, implement sau, `pytest + mypy --strict + ruff` trước commit).
Nếu muốn điều chỉnh (ví dụ: không fallback mà trả lỗi rõ, hoặc muốn thêm WS-tick ở phase sau),
cập nhật tài liệu này trước khi code.
