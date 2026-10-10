# Kế hoạch thực hiện: SSI Explorer (source market-data tương thích KBS/VCI)

<!-- TRẠNG THÁI ĐỐI CHIẾU — WP-PLAN-CLEANUP-01, 2026-10-07 -->

> ## ⚠️ Trạng thái đối chiếu (2026-10-07) — 7 ô `[ ]` bên dưới là tiêu chí nghiệm thu, đã đạt
>
> SSI Explorer **đã triển khai xong** (v3.3.0/v3.4.0). Các ô `[ ]` là danh mục
> nghiệm thu dạng "ghi mã test vào cột Minh chứng" — chưa tick vì không ai điền
> cột đó, **không phải** vì thiếu việc.
>
> **Đã xác minh bằng lệnh — XONG:**
> `tests/unit/explorer/ssi/` có 14 file test (có assert `attrs` — 26 dòng) ·
> `docs/SSI_USAGE_GUIDE.md` tồn tại, có mục ma trận native-vs-fallback ·
> `pytest tests/unit/explorer/test_provider_api_compatibility.py` pass ·
> `docs/VNBROKER_IMPROVEMENT_PLAN.md` là bảng theo dõi tiến độ của chính plan này.
>
> **CÒN LẠI:** điền cột "Minh chứng" trong §7.2 bằng mã test cụ thể (việc ghi
> chép, không phải code).


- **Ngày lập:** 2026-09-23
- **Sửa đổi sau audit:** 2026-09-23 (B1–B4 blocking + NB-1–NB-4, chi tiết §11 — mọi điểm đã kiểm chứng với code thật)
- **Trạng thái:** Sẵn sàng giao đội code (không cần hỏi lại)
- **Đề xuất gốc:** `docs/SSI_EXPLORER_PROPOSAL.md` (§0–§5 đã chốt Phương án B Hybrid)
- **Đối tượng đọc:** đội code thực hiện + người nghiệm thu
- **Nguyên tắc:** TDD bắt buộc (RED → GREEN → refactor), `mypy --strict`, `ruff check + ruff format`,
  mọi minh chứng phải là output lệnh/file thật, không mô tả miệng

---

## 1. Mục tiêu và phạm vi

### 1.1. Mục tiêu (1 câu)

Sau khi xong, `vn.stock(<mã>, source="SSI")` chạy được **toàn bộ** hàm public của
`quote / company / finance / listing / trading / news` mà KBS/VCI chạy được,
user không cần biết backend nào trả dữ liệu thật.

### 1.2. Trong phạm vi (IN)

| ID | Hạng mục | Chuẩn đạt |
|---|---|---|
| IN-1 | Package mới `vnbroker/explorer/ssi/` (7 files) | §4 |
| IN-2 | `SSIQuote.history()` native qua `SSIMarketService.get_ohlc()` | FR-Q1 |
| IN-3 | `SSIListing` native (all_symbols / symbols_by_exchange / symbols_by_group / symbols_by_industries tối thiểu) | FR-L1 |
| IN-4 | `SSITrading.price_board()` native-dạng-loop | FR-T1 |
| IN-5 | `SSICompany / SSIFinancial / SSINews` kiểu fallback (trả rỗng đúng schema như DNSE) | FR-C1, FR-F1, FR-N1 |
| IN-6 | Đấu nối `Vnbroker.stock(source="SSI")` + 7 facade trong `common/data.py` + `ProviderRegistry` (lane `api/`) | FR-W1 |
| IN-7 | Unit test mock + integration test live gated + docs sử dụng | §7, §8 |

### 1.3. Ngoài phạm vi (OUT — ai đề xuất thêm phải lập change request)

| ID | Hạng mục | Lý do loại |
|---|---|---|
| OUT-1 | `intraday` tick-by-tick / `price_depth` native qua WS | Explorer sync; WS là stateful. Phase này `raise NotImplementedError` + hướng dẫn dùng `vn.broker(provider="ssi").stream` |
| OUT-2 | Đưa SSI vào `OPEN_SOURCE_CANDIDATES` / pool AUTO | SSI cần auth → vi phạm quy tắc "Open providers only" (`source_router.py:27`) |
| OUT-3 | Sửa `vnbroker/broker/ssi/*` | Broker lane đã ổn định (522 tests); explorer chỉ được **dùng**, không được sửa |
| OUT-4 | Company/Finance/News "tự chế" từ nguồn không chính thức | Cấm bịa dữ liệu; chỉ fallback KBS/VCI minh bạch |
| OUT-5 | `fetch_multiple` / parallel batch cho SSI | P1, để phase sau; phase này single-symbol đúng là đủ |

---

## 2. Tiền điều kiện (phải xong trước khi code, owner: team lead)

| ID | Điều kiện | Cách xác minh |
|---|---|---|
| PRE-1 | Tài khoản SSI FastConnect có `consumerID (api_key)` + `consumerSecret (api_secret)` cho môi trường test | `POST https://api.ssi.com.vn/api/v3/auth/token` trả 200 (làm tay 1 lần, không commit secret) |
| PRE-2 | Baseline repo xanh: `pytest tests/unit -q` pass, `mypy vnbroker --strict` sạch với file hiện tại, `ruff check vnbroker` sạch | Lưu output vào `artifacts/ssi_baseline/` (xem §8.3) |
| PRE-3 | Đọc 3 file mẫu bắt buộc: `vnbroker/explorer/dnse/company.py` (mẫu fallback), `vnbroker/explorer/dnse/listing.py:50-75` (mẫu init + credential error), `vnbroker/common/data.py:250-289` (`_call_with_fallback`) | Mỗi dev xác nhận đã đọc trong biên bản kickoff |
| PRE-4 | Thống nhất env: dùng chung `VNBROKER_BROKER_SSI_API_KEY`, `VNBROKER_BROKER_SSI_API_SECRET` (đã dùng ở broker lane, `broker/ssi/client.py:83-86`). **Không tạo env mới** | Ghi vào `.env.example` 2 dòng (giữ nguyên tên) |

---

## 3. Kiến trúc và danh sách file

### 3.1. Sơ đồ đấu nối (không được đổi)

```
Vnbroker.stock(symbol, source="SSI")            # common/client.py (sửa: SUPPORTED_SOURCES + truyền key)
  → StockComponents(symbol, "SSI", api_key, api_secret)   # common/data.py (sửa: 7 facade)
      → Quote/Company/Finance/Listing/Trading/News._load_direct_provider()
          → vnbroker.explorer.ssi.{quote,listing,trading,company,financial,news}   # MỚI
              → quote/listing/trading: dùng SSIMarketService (broker lane, chỉ đọc)
              → company/financial/news: trả DataFrame rỗng đúng schema → _call_with_fallback sang KBS/VCI

Lane api/ (BaseAdapter + ProviderRegistry):
  api/quote.py::Quote(source="ssi", api_key, api_secret)  # (sửa: cho phép source SSI + truyền key)
      → ProviderRegistry.get("quote", "ssi") → SSIQuote   # đăng ký ở explorer/ssi/__init__.py
      → vnbroker/__init__.py::_ensure_explorer_modules_loaded() phải import thêm explorer.ssi
```

### 3.2. File MỚI (7 files, mỗi file ≤ 400 dòng)

| File | Class | Vai trò |
|---|---|---|
| `vnbroker/explorer/ssi/__init__.py` | — | Import 6 class + `ProviderRegistry.register()` cho 6 module (`quote/listing/company/financial/trading/news` ↔ `ssi`), copy mẫu `explorer/dnse/__init__.py` |
| `vnbroker/explorer/ssi/_auth.py` | `SSIExplorerSession` (module-level singleton, thread-safe) | Đọc key (param → env), `ensure_token()` (lazy `authenticate()` market-only + `refresh()` khi sắp hết hạn). Không log secret |
| `vnbroker/explorer/ssi/quote.py` | `SSIQuote` | FR-Q1 |
| `vnbroker/explorer/ssi/listing.py` | `SSIListing` | FR-L1 |
| `vnbroker/explorer/ssi/trading.py` | `SSITrading` | FR-T1 |
| `vnbroker/explorer/ssi/company.py` | `SSICompany` | FR-C1 (mẫu `DNSECompany`) |
| `vnbroker/explorer/ssi/financial.py` | `SSIFinancial` (đăng ký provider_type `"financial"`) | FR-F1 (mẫu `DNSEFinance`) |
| `vnbroker/explorer/ssi/news.py` | `SSINews` | FR-N1 (mẫu `DNSENews`) |

> Lưu ý đặt tên: DNSE dùng tiền tố `DNSE*` cho quote/listing/company/news nhưng finance là `DNSEFinance`
> (file `finance.py`, đăng ký `"financial"`). SSI làm tương tự để nhất quán.

### 3.3. File SỬA (chỉ sửa đúng dòng liệt kê, cấm refactor lan man)

| File | Dòng hiện tại | Sửa thành |
|---|---|---|
| `vnbroker/__init__.py:44-45` | `from .explorer import vci, tcbs, kbs, rss_cafef, rss_vneconomy` + `from .explorer import dnse` | Thêm `from .explorer import ssi` (để registry có `ssi`) |
| `vnbroker/common/client.py:47` | `SUPPORTED_SOURCES = ["KBS", "VCI", "TCBS", "DNSE"]` | Thêm `"SSI"`; docstring thêm ví dụ `source="SSI"` + yêu cầu key |
| `vnbroker/common/client.py:123-137` | `StockComponents(...)` chỉ truyền `api_key/api_secret` cho TCBS/DNSE | Truyền `api_key/api_secret` cho cả SSI (đọc env `VNBROKER_BROKER_SSI_*` khi `effective_source == "SSI"`) |
| `vnbroker/common/data.py` (7 facade) | `SUPPORTED_SOURCES = ["VCI", "KBS", "TCBS", "DNSE"]` ở `StockComponents:299`, `Quote:377`, `Listing:489`, `Trading:573`, `Company:632`, `Finance:917`, `News:730` | Thêm `"SSI"` cả 7 chỗ |
| `vnbroker/common/data.py` | `_load_direct_provider()` của Quote/Listing/Trading/Company/Finance/News | Thêm nhánh `ssi` (chi tiết ở từng FR tương ứng: FR-Q1/FR-L1/FR-T1/FR-C1/FR-F1/FR-N1) |
| `vnbroker/common/data.py` | `FALLBACK_MAP` ở Trading:574, Company:633, Finance:918 | Thêm `"SSI": ["KBS", "VCI"]` cả 3 chỗ |
| `vnbroker/common/data.py` | `Finance._load_direct_provider()` nhánh `dnse` hiện fallback cứng sang KBS (`:969-972`) | Giữ nguyên pattern: nhánh `ssi` cũng fallback cứng sang KBS (vì `SSIFinancial` trả rỗng; `_call_with_fallback` sẽ tự thử KBS rồi VCI) |
| `vnbroker/common/data.py` | `News._load_direct_provider()` nhánh `dnse` (`:762-768`, fallback VCI + gắn `_vnbroker_fallback_note`) + `_annotate_news_fallback` (`:842-852`, chỉ xử lý `source == "DNSE"`) | Nhánh `ssi`: copy nhánh `dnse` (fallback VCI, note `("SSI", "VCI")`); mở rộng `_annotate_news_fallback` cho cả `"SSI"` |
| `vnbroker/common/data.py:23` | `PUBLIC_VN_SOURCES = {"KBS", "VCI", "TCBS", "DNSE"}` (hiện không dùng ở đâu khác — đã grep toàn repo) | Thêm `"SSI"` cho nhất quán (zero behavior change, không sửa logic nào dùng nó) |
| `vnbroker/core/types.py:88-106` | `DataSource` enum = `{kbs, auto, vci, tcbs, dnse, binance, fmarket}` — **thiếu `ssi`** → `api/quote.py:71-76` (`DataSources.all_sources()`) sẽ `raise ValueError` với `source="ssi"` trước khi chạm registry | Thêm `SSI = "ssi"` vào enum (1 dòng). `core/constants.py:29` (`ALL_SOURCES = _DataSource.all_sources()`) tự kế thừa — không sửa logic; thêm `SSI = _DataSource.SSI.value` vào lớp deprecated `DataSources` cho nhất quán |
| `vnbroker/api/quote.py:37-80` | Validate qua `DataSources.all_sources()` (tự có `ssi` sau khi sửa `types.py`); `__init__` đã có `api_key/api_secret` và đã truyền xuống `super().__init__` | Không sửa logic — chỉ kiểm thử AC-W1.3 |
| `vnbroker/api/company.py:56`, `api/financial.py:52`, `api/listing.py:50` | `valid_sources` cứng `["kbs","vci","tcbs","dnse",...]` — **thiếu `"ssi"`**; cả 3 đã có `api_key/api_secret` + truyền xuống `super()` | Thêm `"ssi"` vào `valid_sources` (mỗi file 1 dòng). Không sửa gì khác |
| `vnbroker/api/trading.py:25-54` | `valid_sources = ["kbs","vci","tcbs",AUTO]` — **thiếu cả `"dnse"` lẫn `"ssi"`**; `__init__` **không có** `api_key/api_secret` (không truyền key xuống provider được) | Thêm `"ssi"` vào list + thêm 2 params `api_key/api_secret: Optional[str] = None` (copy mẫu `api/company.py:40-41,53-54,68-69`: lưu `self.api_key/api_secret` + truyền vào `super().__init__`). Không thêm param nào khác |
| `vnbroker/api/news.py:15-54` | `valid_sources` cứng 7 mục — **thiếu `"ssi"`**; `__init__` **không có** `api_key/api_secret` | Như `api/trading.py`: thêm `"ssi"` + 2 params `api_key/api_secret` + truyền vào `super().__init__`. Không thêm param nào khác |
| `.env.example` | — | Thêm 2 dòng `VNBROKER_BROKER_SSI_API_KEY=` / `VNBROKER_BROKER_SSI_API_SECRET=` (tên đã tồn tại, chỉ bổ sung tài liệu) |
| `docs/SSI_USAGE_GUIDE.md` | — | Thêm mục "Dùng SSI làm source market-data (`vn.stock(..., source='SSI')`)" + ma trận native-vs-fallback (§4 proposal) |

### 3.4. File TEST (mới + sửa)

| File test | Phủ cho | Mẫu copy |
|---|---|---|
| `tests/unit/explorer/ssi/__init__.py` (rỗng) + `conftest.py` (fixture key giả + mock `SSIMarketService`) | — | `tests/unit/explorer/dnse/` |
| `tests/unit/explorer/ssi/test_auth.py` | _auth: thiếu key raise; đọc env; cache token (gọi service 1 lần cho 2 `ensure_token`) | `tests/unit/broker/ssi/test_auth.py` (pattern) |
| `tests/unit/explorer/ssi/test_quote.py` | mapping interval/date/schema/dtype/attrs; `get_all` gom pages; lỗi thiếu key | `tests/unit/explorer/dnse/test_company.py` (pattern class Test*Init/Test*Methods) |
| `tests/unit/explorer/ssi/test_listing.py` | 4 hàm listing + Series/schema | như trên |
| `tests/unit/explorer/ssi/test_trading.py` | price_board ráp cột KBS + warning batch lớn | như trên |
| `tests/unit/explorer/ssi/test_company.py`, `test_financial.py`, `test_news.py` | rỗng đúng schema + vẫn raise khi thiếu key | copy `tests/unit/explorer/dnse/test_company.py`, `test_finance.py` |
| `tests/unit/explorer/ssi/test_registry.py` | 6 cặp `(module, ssi)` registered sau import `vnbroker.explorer.ssi` | `tests/unit/broker/ssi/test_registry_ssi.py` |
| `tests/unit/common/test_stock_ssi.py` (mới) | `Vnbroker().stock("ACB", source="SSI")` khởi tạo được; `SUPPORTED_SOURCES` chứa SSI ở 8 chỗ; fallback SSI→KBS với mock | — |
| `tests/integration/explorer/test_ssi_live.py` (mới, gated) | live 1 mã ACB + listing + price_board 3 mã, skip khi thiếu key hoặc không có flag | pattern integration hiện tại (`vnbroker_RUN_LIVE_INTEGRATION=1`) |

---

## 4. Yêu cầu chức năng chi tiết (FR) + tiêu chí nghiệm thu (AC)

Quy ước: mỗi FR có các AC đánh số; nghiệm thu = chạy lệnh §8 và đối chiếu output.
`attrs` = `df.attrs` (dict). Giá luôn VND. Date user-facing luôn `YYYY-MM-DD`.

### FR-Q1 — `SSIQuote.history()` native

**Signature bắt buộc** (copy KBS để tương thích `_filter_kwargs`):

```python
class SSIQuote:
    def __init__(self, symbol: str, api_key: str | None = None,
                 api_secret: str | None = None, show_log: bool = False, **kwargs): ...
    def history(self, start: str | None = None, end: str | None = None,
                interval: str = "1D", to_df: bool = True, count_back: int | None = None,
                floating: int = 2, length: str | int | None = None,
                get_all: bool = False, **kwargs) -> pd.DataFrame | str: ...
    def intraday(self, **kwargs): ...   # raise NotImplementedError (FR-Q2)
    def price_depth(self, **kwargs): ...  # raise NotImplementedError (FR-Q2)
```

**Mapping bắt buộc:**

| Đầu vào chuẩn | Chuyển sang SSI | Ghi chú |
|---|---|---|
| `interval` `1D/1W/1M/1H/1m/3m/5m/15m/30m/1d/1h...` (+ alias `d/day/daily/w/week/h/hour` như DNSE `_INTERVAL_ALIASES`) | `1d/1w/1M/1h/1m/3m/5m/15m` (đủ 8 giá trị `Timeframe` ở `broker/ssi/_enums.py:56-64` — gồm cả `3m`) | `30m` SSI v3 không có → phase này `raise NotImplementedError("SSI không hỗ trợ interval 30m; dùng 15m hoặc source KBS/VCI")`. Cấm im lặng resample. **Validate interval ở SSIQuote trước khi gọi service** — cấm để `BrokerValidationError` của broker lane bật ra ngoài (xem AC-Q1.2) |
| `start/end` `YYYY-MM-DD` (default: end=today, start=end−365 ngày; hoặc `length`/`count_back` theo `core/utils/lookback.py`) | `YYYY/MM/DD` (`broker/ssi/_utils.py:SSI_DATE_FMT`) | **Validate date ở SSIQuote trước khi gọi service** (strict `YYYY-MM-DD`, start ≤ end). Sai format → `ValueError` tiếng Việt, không để server trả 400 khó đọc |
| `get_ohlc(page, size=1000)` — 1 page/1 request, **không expose `pagesCount`** (khác `get_master_data`) | loop `page=1..N` khi `get_all=True` với **quy tắc dừng cứng**: dừng khi (a) trang trả về rỗng, hoặc (b) số row < `size`, hoặc (c) chạm `page=10` (trần an toàn). Không copy nguyên văn loop `pagesCount` của `get_master_data` (`broker/ssi/market.py:480-500`) vì `get_ohlc` không trả trường đó | Mỗi page = 1 request; `get_all=False` → đúng 1 request |

**Chuẩn hoá output (bắt buộc):** cột `[time, open, high, low, close, volume]`
(+ `value` chỉ khi `get_all=True`); `trading_date → time` (`datetime64`), sort asc;
`volume → int64`; giá làm tròn `floating` (default 2); `count_back` cắt `tail`;
`to_df=False → str` (json records, như KBS); rỗng → `DataFrame` rỗng **đúng 6 cột** (không raise);
`attrs = {symbol, source: "SSI", interval, start, end, source_used: "SSI"}`.

- **AC-Q1.1 (schema):** với mock `get_ohlc` trả 3 nến, `history(start="2024-01-01", end="2024-01-31")`
  trả DF đúng 6 cột, `time` là `datetime64`, `volume` là `int64`, sort asc, `attrs["source"] == "SSI"`.
- **AC-Q1.2 (interval + pre-validation):** `interval="1D"` gọi service với `timeframe="1d"`;
  `interval="3m"` gọi service với `timeframe="3m"` (SSI hỗ trợ thật — `broker/ssi/_enums.py:58`);
  `interval="30m"` raise `NotImplementedError` có chữ `30m`; `interval="X"` (không hợp lệ) raise
  `ValueError`. **Test pre-validation:** gọi với `interval="X"` mà KHÔNG mock service vẫn phải raise
  `ValueError` (chứng minh validate ở explorer, không ỷ lại service); assert `BrokerValidationError`
  không bao giờ bật ra khỏi `SSIQuote` (dùng `pytest.raises(ValueError)` strict, không catch base `Exception`).
- **AC-Q1.3 (date):** `start="01-01-2024"` raise `ValueError` (không mock service — pre-validation);
  thiếu `start` + thiếu `length`/`count_back` thì default 365 ngày
  (assert `from_date` truyền xuống service = today−365).
- **AC-Q1.4 (get_all + quy tắc dừng):** mock pages `[1000 rows, 400 rows]` → `get_all=True` dừng sau
  page 2 (quy tắc b) với đúng 2 requests; mock page 1 rỗng → dừng ngay với 1 request (quy tắc a);
  `get_all=False` → đúng 1 request. Assert số call service trên mock.
- **AC-Q1.5 (tương thích facade):** `Quote("ACB", source="SSI", api_key, api_secret).history(start=..., end=...)`
  qua `common/data.py` không bị `_filter_kwargs` nuốt param (vì signature có đủ tên).

### FR-Q2 — `intraday` / `price_depth` raise rõ

- Cả hai `raise NotImplementedError` với message固定:
  `"SSI REST không hỗ trợ <intraday|price_depth>; dùng source='KBS'/'VCI' hoặc vn.broker(provider='ssi').stream"`.
- **AC-Q2.1:** message chứa cả 3 chuỗi `KBS`, `VCI`, `stream`.

### FR-L1 — `SSIListing` native

**Signature:** `__init__(api_key=None, api_secret=None, show_log=False, **kwargs)`
(thiếu key → `ValueError("SSI cần api_key và api_secret...")`, copy câu DNSE
`explorer/dnse/listing.py:63-68` nhưng đổi prefix `DNSE → SSI` + env `VNBROKER_BROKER_SSI_*`).
Không nhận `symbol` (như `DNSEListing`).

| Method | Nguồn SSI | Chuẩn output |
|---|---|---|
| `all_symbols()` | Loop 3 boards `HOSE/HNX/UPCOM` gọi `get_securities_info(board=...)` từng board rồi concat + dedupe theo `symbol` (**bắt buộc loop** vì service raise `MISSING_FILTER` khi không có filter — `broker/ssi/market.py:367-372` — và không hỗ trợ phân trang). Thêm `DERIVATIVES` chỉ khi caller truyền `include_derivatives=True` (default `False`) | `DF[symbol, organ_name]` |
| `symbols_by_exchange(exchange="HOSE", lang="vi", get_all=False, ...)` | 1 request `get_securities_info(board=exchange)` | `DF[symbol, organ_name]` (tối thiểu; thêm cột khác được nhưng không được thiếu 2 cột này) |
| `symbols_by_group(group="VN30", ...)` | `get_securities_info(index=group)` | `pd.Series(name="symbol")` |
| `symbols_by_industries(...)` | `icb_code/icb_name` từ `securities_info` | Theo chuẩn ICB của VCI (ghi rõ trong docstring + docs) |
| `industries_icb()` | từ `icb_*` | Có thật (hơn KBS — KBS raise) |
| `all_covered_warrant/all_bonds/all_future_indices/all_government_bonds` | lọc `SecType` nếu có | Có thì tốt; không có → `NotImplementedError` rõ (không trả rỗng gây hiểu lầm là "không có mã nào") |

- **AC-L1.1:** mock `securities_info` 3 boards (mỗi board 2 mã, 1 mã trùng) → `all_symbols()`
  gọi service đúng 3 lần (assert mock counter) và trả DF dedupe đúng 2 cột. Test riêng:
  gọi `get_securities_info()` không filter phải raise (ghi nhận hành vi service, không phải test code ta).
- **AC-L1.2:** `symbols_by_group("VN30")` trả `Series` tên `symbol`.
- **AC-L1.3:** thiếu key raise `ValueError` có chữ `SSI cần api_key`.
- **AC-L1.4:** `@cached_listing` (TTL) được dùng như DNSE (`listing.py:15`) — gọi 2 lần chỉ chạm service 1 lần (assert bằng mock counter).

### FR-T1 — `SSITrading.price_board()` native-dạng-loop (1 master + N summary)

**Signature:** `__init__(symbol, api_key=None, api_secret=None, show_log=False, **kwargs)`;
`price_board(symbols_list: list, **kwargs)`.

**Vì sao phải 2 nguồn (bắt buộc hiểu trước khi code):**
`get_securities_summary` **không** có `ceiling/floor/reference/exchange`
(`_SEC_SUMMARY_COLUMNS`, `broker/ssi/market.py:95-121`); 4 trường này chỉ có ở
`get_master_data` (`_MASTER_COLUMNS: [board, symbol, trading_date, ceiling, floor, ref_price]`,
`broker/ssi/market.py:123-130`). Do đó mỗi `price_board` = **1 request `get_master_data`
(cache TTL 60s — cả phiên chỉ gọi 1 lần cho cùng ngày) + N requests `get_securities_summary`**
(`from_date=to_date=today`, lấy row mới nhất mỗi mã), join theo `symbol`.

**Mapping bắt buộc — output dùng đúng tên cột KBS `_PRICE_BOARD_STANDARD_COLUMNS`
(`explorer/kbs/const.py:343-374`), chỉ các cột điền được (không bid/ask — SSI REST không có):**

| Cột KBS (tên chuẩn) | Nguồn SSI |
|---|---|
| `symbol` | summary `symbol` (uppercase) |
| `time` | summary `trading_date` → `datetime64` |
| `exchange` | master `board` (fallback: info `board`) |
| `ceiling_price` / `floor_price` / `reference_price` | master `ceiling` / `floor` / `ref_price` |
| `open_price` / `high_price` / `low_price` / `close_price` | summary `open` / `high` / `low` / `close` |
| `average_price` | summary `average` |
| `volume_accumulated` | summary `total_match` |
| `total_value` | summary `total_match_value` |
| `price_change` / `percent_change` | summary `price_change` / `price_change_percent` |
| `foreign_buy_volume` / `foreign_sell_volume` | summary `total_foreign_buy` / `total_foreign_sell` |

Theo pattern KBS (`explorer/kbs/trading.py:208-212`): chỉ giữ cột nào có dữ liệu
(`available_cols`), mã nào thiếu master row thì 3 cột trần/sàn/TC để `NaN` (không drop row,
không raise). Mã nào summary rỗng → bỏ row đó.

- `symbols_list` rỗng → `ValueError` (như KBS `trading.py:195`).
- `len(symbols_list) > 20` → `logger.warning` 1 lần: khuyến nghị dùng KBS cho batch lớn (quota SSI 10 rps).
- `attrs = {symbols, source: "SSI", source_used: "SSI"}`.
- **AC-T1.1:** mock 3 mã (summary + master) → DF 3 rows, đúng 17 cột bảng trên theo đúng tên
  (`list(df.columns)` assert từng tên, đặc biệt `ceiling_price/floor_price/reference_price`
  chứ không phải `ceiling/floor/reference`); master service chỉ gọi 1 lần cho 2 lần `price_board`
  liên tiếp (cache TTL).
- **AC-T1.2:** batch 25 mã (mock) → có warning chứa `KBS`; assert số request summary = 25.
- **AC-T1.3:** `Trading("ACB", source="SSI", ...).price_board(["ACB","VNM"])` qua facade chạy được.

### FR-C1 / FR-F1 / FR-N1 — Company / Financial / News kiểu fallback

Copy nguyên mẫu DNSE (đổi prefix + env):

- `SSICompany`: `__init__(symbol, api_key=None, api_secret=None, show_log=False, **kwargs)`,
  methods `overview/profile/shareholders/officers/subsidiaries/affiliate/news/events/trading_stats/ratio_summary/dividends`
  → DF rỗng đúng schema DNSE (`_OVERVIEW_COLUMNS`... ở `explorer/dnse/company.py:22-128`).
  Thiếu key → `ValueError` (kể cả khi chỉ trả rỗng — để fail-sớm, giống DNSE).
- `SSIFinancial`: file `financial.py`, class `SSIFinancial`, đăng ký provider_type `"financial"`;
  methods `balance_sheet/income_statement/cash_flow/ratio` (+ alias `financial_ratios = ratio`)
  → DF rỗng đúng long-format (`[item, item_en, item_id]`, `explorer/dnse/finance.py:23-45`).
- `SSINews`: methods `latest/market_news/search/by_symbol` → DF rỗng đúng 9 cột DNSE
  (`explorer/dnse/news.py:22-32`). Lane `stock()` đấu nối News-SSI **trực tiếp sang VCI**
  (copy nhánh `dnse` ở `data.py:762-768`, note `("SSI","VCI")`), không qua `SSINews`
  (vì facade News đã hard-fallback; `SSINews` chỉ phục vụ lane `api/`).
- **AC-C1.1/F1.1/N1.1:** mỗi method trả `DataFrame.empty == True` và đủ cột chuẩn.
- **AC-CFN-2 (fallback đầu cuối):** với key SSI giả + mock `SSIFinancial.ratio` rỗng,
  `Finance("ACB", source="SSI", ...).ratio()` trả DF **không rỗng** từ KBS
  (chứng minh `_call_with_fallback` bỏ qua DF rỗng — `data.py:269-274`).
- **AC-N-2:** `News(source="SSI").latest("ACB")` trả tin tức thật (từ VCI) và
  `attrs["source_requested"] == "SSI"`, `attrs["source_used"] == "VCI"`.

### FR-W1 — Đấu nối `Vnbroker` + facade + registry

- **AC-W1.1:** `"SSI" in Vnbroker.SUPPORTED_SOURCES` và trong cả 7 `SUPPORTED_SOURCES` của facade;
  script kiểm tra: `python -c "from vnbroker.common.client import Vnbroker; ..."` (xem §8.2).
- **AC-W1.2:** `Vnbroker(source="SSI").stock("ACB")` khởi tạo được khi có env key
  (mock transport để không chạm mạng); thiếu key → `ValueError` hướng dẫn.
- **AC-W1.3 (lane api/ — 3 lớp kiểm tra, thiếu 1 là fail):**
  (a) Registry: sau `import vnbroker.explorer.ssi`,
  `ProviderRegistry.list_available(m)` chứa `"ssi"` với cả 6 `m ∈ {quote, listing, company, financial, trading, news}`.
  (b) Gate `DataSource`: `"ssi" in DataSource.all_sources()` (`core/types.py`).
  (c) Adapter: `Quote/Company/Financial/Listing(source="ssi", symbol="ACB", api_key=..., api_secret=...)`
  và `Trading/News(source="ssi", ...)` khởi tạo được (không `ValueError` valid_sources);
  `.history(...)` / `.price_board(...)` (mock service) chạy được — chứng minh
  `BaseAdapter._instantiate_provider` truyền được `api_key/api_secret` (inspect signature).
- **AC-W1.4 (không hồi quy):** `pytest tests/unit -q` vẫn xanh toàn bộ
  (đặc biệt `tests/unit/api/*`, `tests/unit/explorer/dnse/*`, `tests/unit/broker/ssi/*`).

### FR-W2 — `_auth.SSIExplorerSession`

- Key resolution: param → env `VNBROKER_BROKER_SSI_API_KEY/_SECRET` → thiếu thì `ValueError` (message §FR-L1).
- `ensure_token()` lazy: lần đầu gọi `SSIAuthService.authenticate()` (market-only, không OTP),
  cache `accessToken`; gọi lại khi còn hạn không chạm mạng (test bằng mock counter);
  hết hạn → `refresh()`, refresh hỏng → `authenticate()` lại.
- Thread-safe (`threading.Lock`). Không log secret (grep `api_key|api_secret|token` trong file chỉ xuất hiện ở code truyền biến, không ở `logger.*`).
- **AC-A1.1–A1.3:** thiếu key raise; 2 lần `ensure_token` → service gọi 1 lần; token hết hạn → gọi refresh.

---

## 5. Yêu cầu phi chức năng (NFR — bắt buộc, kiểm tra ở nghiệm thu)

| ID | Yêu cầu | Kiểm tra |
|---|---|---|
| NFR-1 | Type hints 100% public API, `mypy vnbroker --strict` sạch cho 7 file mới + dòng sửa | `mypy vnbroker/explorer/ssi vnbroker/common/data.py vnbroker/common/client.py vnbroker/__init__.py --strict` exit 0 |
| NFR-2 | `ruff check` + `ruff format --check` sạch | exit 0 (lệnh §8.2) |
| NFR-3 | snake_case hàm/biến, PascalCase class, Google-style docstring mọi public method, file ≤ 400 dòng | review checklist §8.4 |
| NFR-4 | Không `print`, dùng `get_logger(__name__)`; `show_log=False` → `logger.setLevel(CRITICAL)` (như KBS/DNSE) | grep `print(` trong 7 file = 0 kết quả |
| NFR-5 | Zero-secret: không log/ghi file/commit api_key/api_secret/token/OTP/private_key; test dùng key giả `test-ssi-key`; live test đọc env, output log phải redact | grep + kiểm `artifacts/` không chứa secret thật |
| NFR-6 | Không import `core/utils/client.py` (proxy/adaptive) trong explorer SSI; chỉ dùng `SSIHttpClient` của broker lane qua `SSIMarketService` | grep `core.utils.client` trong `explorer/ssi/` = 0 |
| NFR-7 | Hiệu năng: `history` 1 mã ≤ 3 page-requests nối tiếp khi không `get_all` (mặc định đúng 1 request); `price_board` batch N mã = **N+1 requests** (N summary + 1 master, master cache TTL 60s nên cả phiên thường chỉ 1 lần) — ghi rõ trong docstring + warning > 20 | assert số call trên mock ở AC-Q1.4/T1.1–T1.2 |
| NFR-8 | Không thay đổi hành vi VCI/KBS/TCBS/DNSE/AUTO (chỉ thêm nhánh, không sửa nhánh cũ) | diff review: mọi hunk sửa file cũ đều là `+` thêm `"ssi"`/params `api_key/api_secret`. Ngoại lệ cho phép (liệt kê đủ, ngoài ra cấm): `core/types.py` (+1 enum), `core/constants.py` (+1 attr deprecated class), `common/data.py:23` (`PUBLIC_VN_SOURCES` +`"SSI"`), `_annotate_news_fallback` (thêm `"SSI"` vào điều kiện), `valid_sources` ở 5 adapter `api/` |

---

## 6. Lộ trình 4 phase và phân việc

| Phase | Việc (theo thứ tự, TDD từng file) | Test đi kèm | Cửa ra (exit criteria) |
|---|---|---|---|
| P1 — Khung + Quote (4–5 ngày) | 1. `_auth.py` + `test_auth.py` 2. `quote.py` + `test_quote.py` 3. `__init__.py` (đăng ký trước 2 module) + `test_registry.py` 4. Đấu nối `Vnbroker` + `Quote` facade (FR-W1 phần quote) + `test_stock_ssi.py` | `pytest tests/unit/explorer/ssi/test_auth.py tests/unit/explorer/ssi/test_quote.py tests/unit/explorer/ssi/test_registry.py tests/unit/common/test_stock_ssi.py` xanh | AC-Q1.1–Q1.5, AC-Q2.1, AC-A1.1–A1.3, AC-W1.1 (quote), NFR-1/2 cho file phase 1 |
| P2 — Listing + Trading (4–5 ngày) | 1. `listing.py` + `test_listing.py` 2. `trading.py` + `test_trading.py` 3. Đấu nối `Listing`/`Trading` facade | test phase 2 xanh | AC-L1.1–L1.4, AC-T1.1–T1.3 |
| P3 — Company/Finance/News + fallback (3–4 ngày) | 1. `company.py`/`financial.py`/`news.py` + 3 test files 2. `FALLBACK_MAP["SSI"]` + nhánh `ssi` còn lại + News-VCI hard-fallback + `_annotate_news_fallback` | full `tests/unit/explorer/ssi/` + `test_stock_ssi.py` (fallback) xanh | AC-C1.1, AC-F1.1, AC-N1.1, AC-CFN-2, AC-N-2 |
| P4 — Hoàn thiện + live + docs (3–4 ngày) | 1. `test_ssi_live.py` + chạy live gated 2. `mypy/ruff` toàn bộ 3. docs (`SSI_USAGE_GUIDE.md` + docstring) 4. full `pytest tests/unit` | §8 toàn bộ xanh | Mọi AC + NFR, bộ minh chứng §8.3 đầy đủ |

Thứ tự trong phase: **test RED trước → implement GREEN → refactor**, mỗi file xong chạy `pytest` file đó + `mypy` + `ruff` ngay.

---

## 7. Chiến lược test (đội code làm đúng, không sáng tạo lại)

### 7.1. Unit (mock, không mạng, không key thật)

- Mock tại biên `SSIMarketService` (patch `vnbroker.explorer.ssi.quote.SSIMarketService.get_ohlc`
  hoặc inject fake service qua constructor param nội bộ `_service` — **bắt buộc** có param này để test được).
- Fixture key giả duy nhất: `api_key="test-ssi-key"`, `api_secret="test-ssi-secret"`
  (copy `tests/unit/explorer/dnse/test_company.py:16-19`).
- Mỗi test class theo mẫu DNSE: `TestSSIQuoteInit` (key/env/uppercase) + `TestSSIQuoteHistory` (schema/mapping).
- Live test **gated**: `pytest.mark.skipif(os.getenv("vnbroker_RUN_LIVE_INTEGRATION") != "1" or not keys, reason=...)`.

### 7.2. Ma trận test bắt buộc (traceability FR ↔ test)

| FR/AC | Test file :: class/test | Mock/Live |
|---|---|---|
| AC-Q1.1–Q1.5 | `test_quote.py::TestSSIQuoteHistory::*` | mock |
| AC-Q2.1 | `test_quote.py::TestSSIQuoteUnsupported::*` | mock |
| AC-L1.1–L1.4 | `test_listing.py::*` | mock |
| AC-T1.1–T1.3 | `test_trading.py::*` | mock |
| AC-C1.1/F1.1/N1.1 | `test_company.py/test_financial.py/test_news.py::*` | không cần mock |
| AC-A1.1–A1.3 | `test_auth.py::*` | mock `SSIAuthService` |
| AC-W1.1–W1.4 | `test_stock_ssi.py::*` + toàn bộ `tests/unit` | mock + regression |
| AC-CFN-2/N-2 | `test_stock_ssi.py::TestSSIFallback::*` | mock SSI rỗng + mock KBS/VCI thật (dùng provider KBS thật với monkeypatch transport nếu cần) |
| Live | `tests/integration/explorer/test_ssi_live.py` (ACB history + all_symbols + price_board 3 mã) | live, gated |

### 7.3. Ngưỡng chất lượng

- Coverage 7 file mới **≥ 90%** (`pytest --cov=vnbroker/explorer/ssi --cov-report=term-missing`).
- `pytest tests/unit -q`: **0 failed, 0 error** (so với baseline PRE-2, số test tăng, không test cũ nào đỏ).
- Thời gian unit mới < 60s (mock thuần, cấm `sleep` thật).

---

## 8. Nghiệm thu và minh chứng bàn giao

### 8.1. Nguyên tắc nghiệm thu

Nghiệm thu từng Phase theo cửa ra §6; nghiệm thu cuối = chạy lại **toàn bộ §8.2** từ đầu,
đối chiếu **từng AC**, thu **bộ minh chứng §8.3**. Thiếu 1 minh chứng = chưa nghiệm thu.

### 8.2. Lệnh nghiệm thu (chạy đúng thứ tự, copy-paste được)

```powershell
# 0. Baseline đã lưu ở artifacts/ssi_baseline/ (PRE-2)
# 1. Unit SSI mới
pytest tests/unit/explorer/ssi -v
# 2. Đấu nối stock() + không hồi quy lane api/dnse/ssi-broker
pytest tests/unit/common/test_stock_ssi.py tests/unit/api tests/unit/explorer/dnse tests/unit/broker/ssi -v
# 3. Toàn bộ unit (cửa cuối)
pytest tests/unit -q
# 4. Coverage package mới (>= 90%)
pytest tests/unit/explorer/ssi --cov=vnbroker/explorer/ssi --cov-report=term-missing -q
# 5. Type + lint (đủ file đã chạm §3.3 — types/api thiếu là fail NFR-1/2)
mypy vnbroker/explorer/ssi vnbroker/common/data.py vnbroker/common/client.py vnbroker/__init__.py vnbroker/core/types.py vnbroker/api --strict
ruff check vnbroker/explorer/ssi vnbroker/common/data.py vnbroker/common/client.py vnbroker/__init__.py vnbroker/core/types.py vnbroker/api
ruff format --check vnbroker/explorer/ssi vnbroker/common/data.py vnbroker/common/client.py vnbroker/__init__.py vnbroker/core/types.py vnbroker/api
# 6. Cấm secret/print/import sai (phải ra rỗng)
Select-String -Path vnbroker/explorer/ssi/*.py -Pattern 'logger\.(info|debug|warning|error).*api_key|logger\.(info|debug|warning|error).*token|print\('
Select-String -Path vnbroker/explorer/ssi/*.py -Pattern 'core\.utils\.client'
# 7. Kiểm tra registry + SUPPORTED_SOURCES + DataSource gate (không mạng)
python -c "import vnbroker.explorer.ssi; from vnbroker.core.registry import ProviderRegistry; print(ProviderRegistry.list_all())"
python -c "from vnbroker.common.client import Vnbroker; from vnbroker.common.data import StockComponents, Quote, Company, Finance, Listing, Trading, News; from vnbroker.core.types import DataSource; assert all('SSI' in c.SUPPORTED_SOURCES for c in [StockComponents, Quote, Company, Finance, Listing, Trading, News]); assert 'ssi' in DataSource.all_sources(); print('SSI wired OK:', Vnbroker.SUPPORTED_SOURCES)"
# 8. Live gated (chỉ khi có key thật; log phải redact secret)
$env:vnbroker_RUN_LIVE_INTEGRATION='1'; pytest tests/integration/explorer/test_ssi_live.py -v
```

### 8.3. Bộ minh chứng bàn giao (thư mục `artifacts/ssi_explorer/` đã xoá 2026-10; nội dung dưới đây là mô tả bàn giao lịch sử)

| # | File minh chứng | Lấy từ lệnh | Đạt khi |
|---|---|---|---|
| E-1 | `unit_ssi.log` | Lệnh 1 | tất cả pass, liệt kê đủ 8 test files `tests/unit/explorer/ssi/test_*.py` (auth/quote/listing/trading/company/financial/news/registry) + `tests/unit/common/test_stock_ssi.py` (lệnh 2) |
| E-2 | `unit_regression.log` | Lệnh 2–3 | `tests/unit` 0 failed/error; số test ≥ baseline |
| E-3 | `coverage_ssi.txt` | Lệnh 4 | `vnbroker/explorer/ssi` TOTAL ≥ 90%, file nào < 90% phải giải trình bằng văn bản |
| E-4 | `mypy_ruff.log` | Lệnh 5–6 | exit 0 hết; 2 grep ra rỗng |
| E-5 | `wiring.log` | Lệnh 7 | in đủ 6 module có `ssi` + dòng `SSI wired OK` |
| E-6 | `live_ssi.log` | Lệnh 8 (chạy bởi người có key) | 3 case live pass (history ACB / all_symbols / price_board 3 mã); log không chứa secret (kiểm bằng grep `SECRET|api_secret|accessToken` = rỗng) |
| E-7 | `sample_history.csv` + `sample_history.attrs.json` | script xuất DF mẫu từ live (ACB 2024-01-01→2024-01-31) | đúng 6 cột, `time` datetime, volume int, attrs đủ 6 key §FR-Q1 |
| E-8 | `sample_fallback.attrs.json` | `Finance(source="SSI").ratio()` live/mock | `source_requested=SSI`, `source_used ∈ {KBS,VCI}`, DF không rỗng |
| E-9 | `diff_stat.txt` (`git diff --stat` + `git status --short`) | — | chỉ chạm file §3.2–§3.3; không có file secret/`.env` trong diff |
| E-10 | `review_checklist.md` (đánh dấu từng ô §8.4) | — | đủ chữ ký reviewer |

### 8.4. Checklist review cuối (reviewer đánh từng ô, 1 ô fail = trả về)

- [ ] Mỗi FR ở §4 có ít nhất 1 test ở §7.2 trỏ tới (ghi mã test vào cột "Minh chứng").
- [ ] Message lỗi: thiếu key (`SSI cần api_key...`), sai date, interval `30m`/không hợp lệ, intraday/depth — đúng câu chữ §4 (so sánh chuỗi trong test, không review bằng mắt).
- [ ] Schema: 6 cột history / 2 cột listing / 17 cột price_board đúng tên KBS ở bảng FR-T1
  (`ceiling_price/floor_price/reference_price`, không phải `ceiling/floor/reference`) / Series `symbol` /
  DF rỗng đúng cột DNSE — assert bằng `list(df.columns)`.
- [ ] `attrs` đủ key ở history/price_board/news-fallback (test assert key, không chỉ "có attrs").
- [ ] NFR-1–NFR-8 đạt (dán output lệnh 5–6 vào E-4).
- [ ] Không sửa logic nhánh VCI/KBS/TCBS/DNSE (diff các hunk file cũ toàn dòng `+`; ngoại lệ `_annotate_news_fallback` đã liệt kê).
- [ ] Docs: `SSI_USAGE_GUIDE.md` có mục SSI-source + ma trận native-vs-fallback; mọi public method có Google docstring.

---

## 9. Rủi ro và xử lý (đội code gặp là làm theo, không cần hỏi)

| # | Dấu hiệu | Xử lý chuẩn |
|---|---|---|
| R-1 | SSI trả 401 giữa chừng | `_auth.ensure_token()` gọi `refresh()` 1 lần rồi retry request đúng 1 lần; vẫn 401 → raise `BrokerAuthError` nguyên bản, không wrap mất message |
| R-2 | SSI trả 429 (price_board batch lớn) | Không retry ồ ạt; raise nguyên lỗi + warning đã yêu cầu ở FR-T1; user chuyển sang KBS (ghi trong message) |
| R-3 | `get_ohlc` trả rỗng ngày nghỉ | Trả DF rỗng đúng 6 cột (không raise), attrs giữ nguyên start/end để caller phân biệt "nghỉ" với "lỗi" |
| R-4 | Symbol phái sinh (`VN30F*`) | Phase này không hỗ trợ: `history` raise `ValueError` hướng dẫn dùng KBS/VCI (ghi rõ trong docstring + test) |
| R-5 | SSI đổi response key | Mapping cột phải qua dict `_COLUMN_MAP` ở đầu file (như DNSE `_INSTRUMENT_COLUMN_MAP`) — sửa 1 chỗ, không rải `["TradingDate"]` khắp code |
| R-6 | Test live flaky (mạng/OTP) | Live chỉ assert schema + non-empty, không assert giá trị cụ thể; retry theo `@retry` có sẵn của facade |

---

## 10. Phụ lục tra cứu nhanh (không phải đọc thêm chỗ khác)

### A. Env và credentials

| Biến | Dùng ở | Lấy từ |
|---|---|---|
| `VNBROKER_BROKER_SSI_API_KEY` (= consumerID) | `_auth.py`, `Vnbroker.stock(source="SSI")` | Đăng ký SSI FastConnect |
| `VNBROKER_BROKER_SSI_API_SECRET` (= consumerSecret) | như trên | như trên |
| `vnbroker_RUN_LIVE_INTEGRATION=1` | gate live test | CI/người chạy live tự set |

### B. Mapping interval chuẩn (bắt buộc implement đúng bảng này)

`1D→1d`, `1W→1w`, `1M→1M`, `1H/1h→1h`, `1m→1m`, `3m→3m`, `5m→5m`, `15m→15m`,
alias `d/day/daily→1D`, `w/week/weekly→1W`, `h/hour→1h`;
`30m` → `NotImplementedError`; còn lại → `ValueError`.
(Đủ 8 giá trị `Timeframe` SSI — `broker/ssi/_enums.py:56-64`.)

### C. Schema cột chuẩn (copy tên y hệt)

- history: `[time, open, high, low, close, volume]` (+ `value` khi `get_all=True`)
- listing: `[symbol, organ_name]`; group: `Series(name="symbol")`
- price_board (17 cột, đúng tên KBS `_PRICE_BOARD_STANDARD_COLUMNS` —
  `explorer/kbs/const.py:343-374`): `[symbol, time, exchange, ceiling_price, floor_price,
  reference_price, open_price, high_price, low_price, close_price, average_price,
  volume_accumulated, total_value, price_change, percent_change,
  foreign_buy_volume, foreign_sell_volume]` —
  không có cột bid/ask (SSI REST không cung cấp); mã thiếu master row → 3 cột giá trần/sàn/TC là `NaN`
- company/finance/news rỗng: copy nguyên `_OVERVIEW_COLUMNS`… (`dnse/company.py:22-128`),
  `[item, item_en, item_id]` (`dnse/finance.py:23-45`), 9 cột (`dnse/news.py:22-32`)

### D. Điểm chốt chống hỏi lại

1. Thiếu Company/Finance/News native là **giới hạn của SSI server**, không phải việc chưa làm — cấm "tự chế" dữ liệu để lấp.
2. SSI **không** vào AUTO pool — mọi đề xuất "cho SSI vào AUTO" là change request riêng, không làm trong task này.
3. Mọi con số (6 cột history, 17 cột price_board đúng tên KBS, 20 mã warning, 365 ngày default,
   coverage 90%, file ≤ 400 dòng, cache master TTL 60s, trần get_all 10 pages) trong tài liệu này
   là **mệnh lệnh**, không phải gợi ý.

## 11. Lịch sử sửa đổi (audit 2026-09-23 — đã kiểm chứng với code thật)

| ID | Lỗi trong bản gốc | Sửa thành | Căn cứ code |
|---|---|---|---|
| B1 | FR-T1 đòi 12 cột `ceiling/floor/reference...` chỉ từ loop `securities_summary`; NFR-7 ghi N requests | FR-T1 = 1× `get_master_data` (cache TTL 60s) + N× `get_securities_summary`; 17 cột đúng tên KBS `*_price` (gồm foreign_buy/sell); NFR-7 = N+1 | `_SEC_SUMMARY_COLUMNS` thiếu 4 trường (`market.py:95-121`); `_MASTER_COLUMNS` có đủ (`market.py:123-130`); tên chuẩn KBS (`kbs/const.py:343-374`) |
| B2 | `all_symbols()` = 1 request `get_securities_info()` không tham số | Loop 3 boards HOSE/HNX/UPCOM + dedupe (AC-L1.1 assert 3 calls) | `MISSING_FILTER` khi thiếu filter + không có page params (`market.py:345-377`) |
| B3 | §3.3 bỏ sót gate lane `api/`; AC-W1.3 không thể pass | Thêm `SSI` vào `DataSource` enum (`types.py` — `constants.py` tự kế thừa), `valid_sources` 5 adapter `api/`, params `api_key/api_secret` cho `trading/news`; AC-W1.3 thành 3 lớp (registry/gate/adapter); NFR-8 liệt kê đủ ngoại lệ | `DataSource.all_sources()` (`types.py:88-106`); `api/quote.py:71-76`; hard lists (`company:56`, `financial:52`, `listing:50`, `trading:44`, `news:34-42`); `trading/news` thiếu key params |
| B4 | Bảng interval thiếu `3m` | Thêm `3m→3m` (FR-Q1 + §10.B) | `Timeframe.MINUTE_3` (`_enums.py:58`); service docstring (`market.py:162`) |
| NB-1 | `get_all` copy nguyên văn loop `pagesCount` của master data | Quy tắc dừng cứng 3 điều kiện (rỗng / row < size / page=10) + AC-Q1.4 assert số call | `get_ohlc` 1 page, không trả `pagesCount` (`market.py:148-212` vs `:480-500`) |
| NB-2 | AC assert `ValueError` nhưng service ném `BrokerValidationError` | Pre-validation ở SSIQuote (interval + date) + test không-mock chứng minh; cấm `BrokerValidationError` lọt ra | Service raise `BrokerValidationError` (`market.py:168,275,359,368,408`) |
| NB-3 | `PUBLIC_VN_SOURCES` không nhắc tới | §3.3 thêm `"SSI"` (đã grep: 1 match duy nhất, zero behavior change) | `common/data.py:23` |
| NB-4 | E-1 "đủ 8 test files §3.4" mơ hồ | Ghi rõ: 8 files `tests/unit/explorer/ssi/test_*.py` + `test_stock_ssi.py` | Đếm §3.4 |
