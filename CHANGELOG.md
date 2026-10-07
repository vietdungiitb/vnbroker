# Changelog

All notable changes to this project will be documented in this file.

## [3.5.0] — Kiến trúc hai tầng + an toàn đường giao dịch

**Breaking changes — đọc trước khi nâng cấp:**

1. `quote.history()` qua `Vnbroker` trả cột `time` **tz-aware** (`Asia/Ho_Chi_Minh`)
   thay vì tz-naive, và được **lọc theo `start`/`end`**.
   - Lý do: provider trả tz khác nhau (VCI tz-aware, KBS/DNSE/SSI tz-naive) khiến
     `pd.concat` sinh dtype `object`; VCI còn trả nến ngoài khoảng yêu cầu **không báo lỗi**.
   - Nếu code bạn so `df["time"]` với timestamp naive: dùng `.dt.tz_localize(None)`.
   - Gọi provider trực tiếp (`VCIQuote(...).history()`) **không đổi**.
2. `connector/dnse`: `place_order` / `cancel_order` / `deposit_derivative_margin` /
   `withdraw_derivative_margin` nay cần `trade.enable_write()` trước khi gửi thật.
   Mặc định `dry_run=True` (an toàn). Trước đây lệnh gửi ngay, không có hàng rào.
3. SSI **không còn retry tự động** trên POST đặt lệnh (chống double-submit).
   Đã tái hiện được: trước đây 1 lời gọi → **5 POST thật** khi response mất.
   - Hãy truyền `clientRequestId` khi định thử lại; key được gắn vào exception.

**Tính năng mới:**

- **Tầng 1 — dữ liệu ẩn danh, không cần biết provider.** `Market/Reference/Fundamental(auto=True)`
  và `Vnbroker(source="AUTO")`: hệ thống tự chọn provider ổn định và xoay vòng khi
  rate-limit / mất kết nối. Failover áp cho `history`, `intraday`, `price_depth`.
  **Mặc định vẫn là `"KBS"`** — không đổi hành vi cho người dùng hiện tại.
- Chuẩn hoá dữ liệu ở **một điểm duy nhất** (`_normalize_quote_result`): tz-aware,
  lọc biên, sort. Provider mới thêm vào tự động tuân thủ.
- `match_type` chuẩn hoá về `Buy`/`Sell`/`unknown` cho mọi provider (trước đó
  DNSE/SSI giữ nguyên giá trị provider → sai âm thầm).
- `Redactor.redact_url()` — chặn rò `api_key`/signature trong query string
  (`connector/dnse/websocket.py` trước đây log nguyên văn ở level INFO).

**Sửa lỗi hạ tầng:**

- **CI không chạy cho PR vào `dev`**: cả 4 workflow trigger `[main, develop]` nhưng
  repo không có branch `develop`. Đã đổi thành `[main, dev]`.
- `pytest tests/contract/` + `ruff` nay **chặn thật** (trước mọi bước đều advisory).
- `[tool.ruff]`: 2888 → 0 lỗi với rule set có chủ đích.
- `check_version_sync.py` quét cả `tests/` (trước gate xanh trong khi test đỏ).
- Reset baseline `mypy --strict` (ghi 556 dòng nhưng thực tế 1266 lỗi → gate luôn đỏ),
  hạn **2026-11-01** và hạn **được thực thi thật** (`baseline_is_expired`).
- Xoá `vnbroker/core/base/` — 164 câu lệnh code chết (registry thứ hai bị thay thế
  từ `dbcd81a`, 0 import). Bằng chứng ở `f5de70d`; gate ngăn tái sinh.

**Số liệu:** pytest **1001 passed** / 5 skipped · ruff 0 · version-sync 0 ·
mypy-baseline 0 · coverage **55%**.

### Sửa lỗi phát hiện bởi CI ngay sau khi đóng gói (v3.5.0 follow-up)

Ba lỗi này **chỉ lộ ra trên CI**, không thấy ở máy dev — và là nguyên nhân release
v3.5.0 bị đánh dấu đỏ. Đã tái hiện và sửa, không reset baseline.

1. **`fillna(None)` — phụ thuộc phiên bản pandas.** `common/data.py:83` gọi
   `.fillna(symbol)` với `symbol=None`. pandas **2.x** ném
   `ValueError: Must specify a fill 'value' or 'method'.`; pandas **3.x** bỏ qua.
   Máy dev dùng pandas 3.0.2 nên xanh, CI dùng 2.x nên đỏ trên cả 3 OS.
   → Sửa bằng `if symbol is not None:` + `test_pandas_version_compat.py` chặn
   tái phát ở mức AST (vì test runtime ở máy pandas 3 không bắt được).
   **Đã verify bằng pandas 2.2.3 thật: trước sửa đỏ, sau sửa xanh.**
2. **Thiếu stub `types-requests` trong `[lint]`.** Không có nó, số lỗi mypy phụ
   thuộc môi trường: CI (Python 3.11) báo 14 lỗi "mới" cho cùng một commit mà máy
   dev báo 0. → Bổ sung stub vào `lint` extra, và sửa 3 lỗi thật phát lộ ra:
   `dict` không annotate → `Dict[str, Any]` ở `dnse/trade.py` và `proxy_manager.py`;
   `_telegram_photo` khai báo `-> requests.Response` nhưng trả `response.json()`
   (bug annotation thật) → `Dict[str, Any]` + `cast`.
   **Kết quả: 33 lỗi strict được sửa thật, không phải nới baseline.**
3. **`import file mismatch` — 7 basename trùng giữa các thư mục test.**
   Thiếu `__init__.py` nên `test_quote.py` ở `tests/unit/explorer` và
   `tests/integration/explorer` đụng nhau, làm **toàn bộ** collection fail.
   → Thêm 16 `__init__.py`. `pytest tests/` giờ thu thập 1090 test, exit 0.
4. **2 test integration lỗi thời** — `tests/integration/test_vnstock_client.py` assert
   `SUPPORTED_SOURCES == ['KBS','VCI','TCBS','DNSE']` (thiếu SSI từ 3.4.0 và AUTO
   từ 3.5.0), và kỳ vọng `crypto()` ném `NotImplementedError` trong khi nay là
   `ValueError` (crypto đã có provider BINANCE thật từ 3.4.0). File đã bị xoá
   cùng đợt dọn tham chiếu `vnstock`; bất biến `SUPPORTED_SOURCES` nay được giữ ở
   `tests/unit/common/test_stock_ssi.py::test_supported_sources`.
   → Chuyển sang bất biến + kiểm đúng hành vi.

**Số liệu sau sửa:** pytest **1064 passed** / 29 skipped (toàn bộ `tests/`) ·
1006 passed trên pandas 2.2.3 · ruff 0 · version-sync 0 · mypy-baseline 0.

---

## [Unreleased]

### Added
- **Hợp đồng tầng 1 (contract test)** — `tests/contract/` khoá bảo đảm mọi provider ẩn danh
  (VCI, KBS) trả về cùng schema: đủ cột chuẩn, `time` tz-aware, không có dòng ngoài khoảng
  `[start, end]`, thứ tự thời gian tăng dần.
- `tests/contract/test_layer_normalization.py` — 12 test khoá hợp đồng chuẩn hoá ở tầng `data.py`.
- **Failover tầng 1** — `Quote._run_with_failover()`: hệ thống tự chọn provider ổn định và
  tự xoay vòng khi gặp rate-limit / mất kết nối, dùng cơ chế `core.source_router`
  (`build_source_order`, `should_failover`, health store có cooldown). Kết quả được gắn
  vào `df.attrs["source_used"]` để debug.
- **Tuỳ chọn `auto=True`** trên `Market` / `Reference` / `Fundamental`, và `source="AUTO"`
  trên `Vnbroker`. **Mặc định giữ nguyên `"KBS"`** — không thay đổi hành vi cho người
  dùng hiện tại.
- `tests/contract/test_failover_tier1.py` — 8 test khoá hành vi failover.
- **Gate CI thực sự chặn (GĐ4):** `pytest tests/contract/` và `ruff check` chạy **không**
  `continue-on-error`. Trước đó mọi bước lint/type/security đều advisory.
- `[tool.ruff]` trong `pyproject.toml` — rule set nhỏ, có chủ đích (syntax error, undefined
  name, unused import/biến, mutable default). Baseline: **2888 → 0 lỗi**.
- `check_version_sync.py` quét cả `tests/` — trước đó gate xanh trong khi 3 test đỏ vì
  test hardcode version cũ.
- Sửa `params: Dict = {...}` dùng chung giữ các lần gọi ở 3 `explorer/*/screener.py` (B006).

### Security — đường tiền thật (P0, sau kiến trúc hai tầng)

- **SSI không còn retry mù trên POST đặt lệnh.** `SSIHttpClient.request` trước đây bọc
  mọi method trong `tenacity.Retrying` không phân biệt idempotent; `ConnectionError`
  xảy ra cả khi server **đã nhận lệnh** nhưng response mất → gửi lại lệnh trùng.
  **Đã tái hiện: 1 lời gọi → 5 POST thật.** Nay chỉ retry method idempotent
  (`GET`/`HEAD`/`PUT`/`DELETE`/`OPTIONS`); POST ném `BrokerNetworkError` với code
  `NETWORK_ERROR_NON_IDEMPOTENT` kèm hướng dẫn tra cứu `clientRequestId`.
- **`clientRequestId` được gắn vào exception** khi lỗi mạng xảy ra (`broker/ssi/equity.py`)
  — không có nó thì lần thử lại sinh key mới và dedupe phía server vô hiệu, tức vẫn
  là double-submit do người dùng bấm.
- **`connector/dnse/trade.py` có hàng rào ghi.** Trước đây `place_order`,
  `cancel_order`, `deposit_derivative_margin`, `withdraw_derivative_margin`
  **không có** `dry_run`, **không có** `write_gate` → tiền đi thật ngay.
  Nay: `dry_run: bool = True` (an toàn) + `Trade.enable_write()` tắt mặc định;
  `dry_run=False` mà chưa bật quyền thì ném `BrokerPermissionError`.
- Thứ tự trong `place_order`: **validate → guard → network.** Để guard trước validate
  sẽ khiến dry-run trả "OK" cho một lệnh mà lúc gửi thật chắc chắn raise — dry-run nói dối.

### Fixed — dữ liệu âm thầm & rò credential (P2)

- **`match_type` chuẩn hoá về một tập giá trị.** `process_match_types` trước đây là
  if/elif theo `source`, mỗi provider một cách viết (VCI `'b'`, TCBS `'BU'`, KBS `'B'`),
  và **DNSE/SSI không có nhánh nào** nên giữ nguyên giá trị provider. Hệ quả:
  `df[df.match_type == "Buy"]` cho kết quả khác nhau tuỳ provider, sai mà không ném lỗi.
  Nay dùng bảng mapping chung + chuẩn hoá hoa/thường → chỉ còn `Buy`/`Sell`/`unknown`,
  không NaN, provider mới tự động tuân thủ.
- **`Redactor.redact_url()`** cho URL có credential trong query string (client HMAC DNSE/KBS
  truyền `?api_key=...&signature=...`). `connector/dnse/websocket.py` trước đây log URL
  nguyên văn ở level **INFO** → rò `api_key` + HMAC signature. Đã bổ sung `signature`,
  `sig`, `trading_token`, `smart_otp`, `x-api-key` vào danh sách nhạy cảm.
- **Xoá `vnbroker/core/base/` — 164 câu lệnh code chết.** Đây là registry đầu
  tiên của dự án, đã bị `core/registry.py` thay thế ở commit `dbcd81a` ("registry merge")
  nhưng quên dọn. 0% coverage và **không module nào import** (đã quét toàn repo).
  Hai registry cùng tên khác API là bẫy cho người đọc mới. Bằng chứng hoạt động được
  lưu ở commit `f5de70d` trước khi xoá; `tests/unit/core/test_legacy_base_module.py`
  nay là gate ngăn tái sinh (đã kiểm chứng đỏ khi thư mục tồn tại).
- **Failover mở rộng sang `intraday` và `price_depth`.** Trước đó chỉ `history` xoay vòng
  provider — khi provider chính hết hạn, toàn bộ người dùng mất dữ liệu trong phiên dù
  hệ thống còn provider dự phòng.
- `_normalize_quote_result()` trong `vnbroker/common/data.py` — điểm kiểm soát **duy nhất**
  cho chuẩn hoá kết quả provider. Provider mới thêm vào sau này tự động tuân thủ.

### Fixed
- **Baseline `mypy --strict` bị lệch ngay từ đầu:** file ghi 556 dòng nhưng thực tế có
  **1266** lỗi strict, nên `check_mypy_baseline.py` luôn đỏ và gate không bảo vệ được gì.
  Đã reset về trạng thái thật kèm **hạn 30 ngày (2026-11-01)**, và hạn giờ **được thực thi
  thật**: quá hạn thì gate đỏ, buộc thu hẹp baseline hoặc xin gia hạn có lý do.
  Ưu tiên giảm dần: `common/data.py` (142), `broker/tcbs/account.py` (66),
  `explorer/vci/company.py` (56), `brokerage/tcbs/client.py` (36).
- **CI không chạy cho PR vào `dev`:** cả 4 workflow trigger `branches: [main, develop]` nhưng
  repo **không có branch `develop`** (`git rev-parse --verify develop` → `fatal`). Đã đổi
  thành `[main, dev]`.

### Changed
- **Retry policy rõ ràng hơn:** đường không-auto retry cả lời gọi provider (`DEFAULT_RETRIES=3`,
  như trước). Đường `AUTO` retry **từng provider** rồi mới xoay vòng — tránh việc hết pool
  bị thử lại N lần.
- Khi mọi provider đều lỗi, hệ thống **ném lỗi gốc** thay vì trả DataFrame rỗng (frame rỗng
  khiến người dùng tưởng "không có giao dịch" thay vì "đã lỗi mạng").
- Lỗi lập trình (`TypeError`…) **không** bị failover che giấu: ném thẳng ra.
- ⚠️ **BREAKING (giới hạn ở đường `Vnbroker`)**: `quote.history()` qua facade giờ trả
  `time` **tz-aware** `Asia/Ho_Chi_Minh` thay vì tz-naive, và lọc cắt theo `start`/`end`.
  - Lý do: provider khác nhau trả tz khác nhau (VCI tz-aware, KBS/DNSE/SSI tz-naive) khiến
    `pd.concat` sinh dtype `object`; VCI còn trả nến ngoài khoảng yêu cầu mà không báo lỗi.
  - Đây là tiền quyết cho failover tự động (GĐ3): xoay vòng provider giờ trả đúng schema.
  - Gọi provider trực tiếp (`VCIQuote(...).history()`) **không đổi hành vi**.
  - Code so sánh `df["time"]` với timestamp naive cần `.dt.tz_localize(None)`.

## [2026-09-23] — Release 3.4.0: SSI Swap Parity (P0–P4)

### Added
- **SSI swap parity**: `source="SSI"` dùng qua lại với KBS/VCI cho
  `quote.history` (mở `30m`, cửa sổ `HH:MM:SS`, `fetch_multiple` batch),
  `listing`, `trading.price_board` (`trading_date` + concurrent).
- **SSI T2 mới**: `explorer/ssi/{indices,securities,screener}.py`
  (index list/members/summary/history, securities summary/master/foreign-room,
  screener lọc local) + TTL phân tầng (symbols 6h, indexSummary 5m, master 60s).
- **SSI T3 realtime**: `explorer/ssi/live.py` (`intraday_ticks`,
  `depth_snapshot`, `session_snapshot`, `session_flags`) + `market.*`
  subscribe trong `SSIStreamManager`.
- **AUTO credential-aware**: SSI vào candidates quote/listing/trading khi có key
  (failover cuối), opt-in primary `vnbroker_SSI_AUTO_PRIMARY=1`;
  persist debounce (10 events/1s) + `flush_router_state()`.

### Fixed
- **Deadlock cold-start** `build_source_order` (`Lock` → `RLock`,
  `core/source_router.py`) — treo vĩnh viễn trên process tươi.
- `Trading.FALLBACK_MAP` trùng dòng làm mất SSI fallback; bổ sung map cho
  Quote/Listing (1 chiều SSI→KBS,VCI); `_call_with_fallback` bắt thêm
  `UnsupportedMethodError`; lazy-auth cho SSI company/finance/news.

### Testing
- 40 tests mới (parity 16 + indices/securities 8 + screener 6 + live 10 +
  router SSI/debounce 8 + fetch_multiple 3 + live-gated 7, mock-only);
  full `tests/unit`: 909 passed, 5 skipped (live-gated).

## [2026-09-22] — Release 3.3.0: Retail + Unified UI

### Added
- **Retail facade** (`vnbroker/common/retail.py` + `Vnbroker.retail()`):
  giá vàng SJC/BTMC, tỷ giá Vietcombank — validate fail-sớm, DataFrame đúng
  schema + `source`, RuntimeError prefix nguồn khi lỗi mạng, chặn print legacy.
- **Unified UI** (`vnbroker/ui/`): `Market/Reference/Fundamental/Retail`
  delegate mỏng về `common.data`, `show_api()/show_doc()` + snapshot test.
- **InstrumentType** (`str`-Enum lowercase) + dedup `get_asset_type`
  (`core/utils/parser.py` còn 1 định nghĩa; khóa bug ETF-8-ký-tự bằng test).
- **kwargs-filtering** ở `Quote.history/intraday/price_depth` theo signature
  provider (passthrough khi có `**kwargs`, luôn giữ `show_log`).
- Docs: `docs/RETAIL_USAGE.md`, `docs/ROADMAP_V33_PLAN.md`.

### Testing
- 53 tests mới (retail 19 + ui 11 + asset-type 16 + quote-kwargs 3 + snippets 4),
  Retail coverage 96%, UI 100%, mypy/ruff sạch scope mới.

## [2026-09-22] — Release 3.2.0: SSI broker lane (native FastConnect v3)

### Added
- **SSI broker lane đầy đủ, native, không dependency `ssi-sdk`**:
  `vnbroker/broker/ssi/` (auth, account, money, equity, market, portfolio,
  fco, stream, client + `_paths/_enums/_utils/_signing/_transport`).
  - Auth: market-only (không OTP), OTP, Smart OTP push (poll 202/401114), refresh.
  - Market data: OHLC 8 timeframe, index/board summary, securities info/summary,
    master data trần/sàn/TC (tự gom pages).
  - Brokerage: balance/positions equity + phái sinh, PPMMR full-columns,
    maxBuySell, sổ lệnh, portfolio snapshot (map tường minh sang engine).
  - Write ký RSA-SHA256 stdlib (nanoid idempotency), `dry_run=True` mặc định.
  - 7 lệnh điều kiện FCO (GTD/Stop/Stop-Limit/Trailing/Trailing-Limit/OCO/BullBear)
    + query vòng đời + order book.
  - Streaming WebSocket native (`websockets>=12.0`): trade/quote/room/put/oddlot/
    OHLCV + order/portfolio events, alias `subscribe_fco_order_status`.
- `SSIBrokerClient` đăng ký `BrokerRegistry` (`vn.broker(provider="ssi")`).
- `SSICredentialConfig` (`VNBROKER_BROKER_SSI_*`), mở rộng `Redactor` key SSI.
- Docs: `docs/SSI_USAGE_GUIDE.md`, `docs/SSI_INTEGRATION_PLAN.md`, `.env.example`.

### Changed
- `websockets>=11.0` → `>=12.0` (sync client chỉ có từ 12.0).
- `write_gate` ParamSpec-typed (giữ nguyên behavior, verified bởi suite TCBS).
- `camel_to_snake` có type hints; `from_dict` credentials typed `dict[str, Any]`.

### Testing
- 171 SSI unit tests mới (mocked), SSI coverage 93%, mypy --strict + ruff sạch.
- Live integration gated `vnbroker_RUN_LIVE_INTEGRATION=1` (manual, OTP người thật).

## [2026-06-22] — Release 3.1.1: Cleanup — Remove SSI/VNDirect brokerage scaffolds

### Breaking Changes
- **Xóa hoàn toàn SSI brokerage scaffold**: `vnbroker/broker/ssi/` (auth, account, equity, market, money, portfolio, client) — chưa triển khai thực tế.
- **Xóa hoàn toàn VNDirect brokerage scaffold**: `vnbroker/broker/vndirect/` (auth, account, equity, market, money, portfolio, client) — chưa triển khai thực tế.
- **BrokerRegistry**: Chỉ còn `TCBS` provider. SSI, VNDirect đã bị loại khỏi registry.

### Removed
- Toàn bộ thư mục `vnbroker/broker/ssi/` và `vnbroker/broker/vndirect/`.
- References SSI/VNDirect trong `README.md`, `CLAUDE.md`, `broker/__init__.py`.

### Changed
- `README.md`: Cập nhật bảng broker providers, xóa SSI.
- `CLAUDE.md`: Cập nhật cấu trúc thư mục broker, xóa SSI/VNDirect khỏi roadmap.
- `broker/__init__.py`: Chỉ export TCBS broker client.

## [2026-06-18] — Release 3.1.0: Cleanup — Remove MSN/FMP, restructure core

### Breaking Changes
- **Xóa hoàn toàn MSN explorer**: `vnbroker/explorer/msn/` (quote, listing, company, finance, news, trading, helper, const) — không có dữ liệu thật.
- **Xóa hoàn toàn FMP connector**: `vnbroker/connector/fmp/` (quote, config, const) — không có API key, không có module khác.
- **SUPPORTED_SOURCES thu hẹp**: Chỉ còn `KBS`, `VCI`, `TCBS`, `DNSE`. MSN, FMP, GATEWAY, AUTO đã bị loại.
- **Xóa `fx()`/`crypto()`/`world_index()` tests**: Các phương thức này chỉ hoạt động với MSN/FMP — đã bị xóa.
- **Xóa `msn_symbol_map`**: `Vnbroker` không còn property này.

### Removed
- Toàn bộ file rác: test scratch, benchmark artifacts, planning docs, caches, vninvest-sdk.
- Toàn bộ planning/audit docs: `ARCHITECTURE_REVIEW.md`, `BENCHMARK_COMPARISON_REPORT.md`, ...
- `_load_msn_const()` và `_CURRENCY_ID_MAP`/`_GLOBAL_INDICES`/`_CRYPTO_ID_MAP` khỏi `data.py`.
- `GATEWAY`, `MSN`, `FMP` khỏi `DataSource` enum, `DataSources` compat class, `core/settings.py`, `dispatch.py`, `source_router.py`, `user_agent.py`.
- 4 orphan test fixtures gây ERROR (`mock_vci_send_request`, `mock_response_factory`, `diverse_test_symbols`).
- `GatewayHttpClient`, `launcher.py`.

### Changed
- `TODO.md` được thay thế bằng phiên bản cập nhật, không còn tham chiếu vninvest-sdk.
- `README.md` cập nhật bảng nguồn dữ liệu, env vars không còn FMP.

### Testing
- **522 passed**, 9 skipped, 8 warnings — **0 failures, 0 errors** sau cleanup.

## [2026-06-18] — Release 3.0.0: Direct Provider Architecture (Loại bỏ PAT/Gateway)

### Breaking Changes
- **Loại bỏ hoàn toàn vninvest-sdk/PAT/Gateway**: `vnbroker` giờ đây hoạt động độc lập, không phụ thuộc vào PAT hay Gateway SaaS.
- **Xóa `GatewayHttpClient`**: File `vnbroker/core/utils/gateway_client.py` đã bị xóa.
- **Xóa Gateway adapters**: `GatewayQuoteAdapter`, `GatewayListingAdapter`, `GatewayTradingAdapter`, `GatewayCompanyAdapter`, `GatewayFinanceAdapter`, `GatewayNewsAdapter` đã bị xóa khỏi `vnbroker/common/data.py`.
- **Xóa PAT exceptions**: `AuthenticationError`, `AuthorizationError`, `QuotaExceededError`, `InvalidPATFormatError`, `GatewayUnavailableError`, `EmergencyQuotaExceededError` đã bị xóa khỏi `vnbroker/core/exceptions.py`.
- **Xóa deprecated wrappers**: Các lớp `_DeprecatedQuote`, `_DeprecatedCompany`, `_DeprecatedFinance`, `_DeprecatedListing`, `_DeprecatedTrading`, `_DeprecatedNews`, `_DeprecatedMarketSnapshot`, `_DeprecatedFund`, `_DeprecatedStream` đã bị xóa khỏi `vnbroker/__init__.py`.
- **SUPPORTED_SOURCES không còn `GATEWAY` và `AUTO`**: Tất cả component chỉ hỗ trợ các provider trực tiếp (`VCI`, `KBS`, `TCBS`, `DNSE`, `MSN`, `FMP`).

### Architecture Changes
- `Vnbroker.__init__()`: Bỏ `pat_key`, `gateway_url` parameters. Chỉ còn `symbol`, `source`, `show_log`.
- `source` mặc định từ `"AUTO"` → `"KBS"`.
- Không cần PAT key để sử dụng thư viện.

### Removed
- Xóa thư mục `Projects/vnbrokder/vninvest-sdk/` (stub empty).
- Xóa thư mục `.agents/`, `tmp/`, các file test root liên quan PAT/Gateway.
- Xóa `create_pat.py`, `create_valid_pat.py`.

### Documentation
- Cập nhật `README.md` phản ánh kiến trúc Direct Provider.
- Cập nhật `CHANGELOG.md`.
- Cập nhật `TODO_MIGRATION.md` → đánh dấu hoàn thành.

## [2026-06-17] — Release 2.0.0: Multi-Source Architecture & Private Brokerage Lane

### Architecture
- **Multi-Source Support**: Market data accessible via multiple providers (VCI, KBS, TCBS, DNSE, MSN, FMP) with automatic failover
- **Direct Provider Access**: Each provider (VCI, KBS, TCBS, DNSE, MSN, FMP) has own credentials and direct API access
- **Supported Sources**: `GATEWAY`, `AUTO`, `VCI`, `KBS`, `TCBS`, `DNSE`, `MSN`, `FMP` for market data components
- **Source Router**: AUTO source with VCI-first for quote/company/finance, KBS-first for trading, exponential backoff failover

### Private Brokerage Lane
- **TCBS Broker Client**: Full trading operations via direct TCBS iFlash OpenAPI v1.0.0:
  - Read: Profile, Balance, Purchasing Power, Cash, Margin, Holdings, Orders, Executions, Derivatives Positions/Orders/Cash
  - Write: Place/Modify/Cancel orders (dry_run=True default, idempotency via request_id)
  - Market Data: Ticker info, snaps, BSA, intraday, derivatives info (public endpoints)
  - Portfolio Engine: Snapshot, PnL, reconciliation (pure compute)
- **DNSE Broker Client**: Scaffolded (coming soon)
- **Security Model**: Zero-Knowledge — OTP, API Key/Secret, PIN never transit Gateway. Direct client → Broker API for minimal latency and maximum security.

### API Changes
- `Vnbroker.__init__()`: Added `pat_key`, `gateway_url` for Gateway mode; direct provider credentials via env vars
- `Vnbroker.stock()`: Supports `source` parameter for direct provider access (VCI, KBS, TCBS, DNSE, MSN, FMP)
- `Vnbroker.fx()`, `crypto()`, `world_index()`: Support MSN and FMP sources
- `Vnbroker.broker()`: New method returning `TCBSBrokerClient` for private brokerage
- `Quote.history()`: Removed MSN symbol mapping logic
- `Finance` class: Removed duplicate methods (`industry_peers`, `industry_benchmark`, `industry_rank`, `_extract_latest_metric_values`)
- `Screener`: Removed (was TCBS-direct only)

### Testing
- All 560 unit tests pass (12 skipped — pre-existing live API/env issues)

### Migration Guide
```python
# Gateway mode (requires PAT)
vn = Vnbroker(pat_key="vninvest_pat_your_token")
acb = vn.stock("ACB")  # Uses Gateway

# Direct provider mode (no PAT needed)
vn = Vnbroker()
acb = vn.stock("ACB", source="VCI")  # Direct VCI access
acb = vn.stock("ACB", source="DNSE")  # Direct DNSE access (requires DNSE_API_KEY + DNSE_API_SECRET)

# Broker Lane (direct API)
client = vn.broker(provider="tcbs", api_key="tcbs_openapi_key")
client.authenticate(otp="123456")
balance = client.get_balance("0123456789")
```

## [2026-04-18] — Release 1.0.2: Core API standardization and production hardening

### Added
- Standardized insider API surface and normalization path with `insider_deals` compatibility across providers.
- New financial snapshot API: `fundamental_snapshot` in the finance facade.
- New industry comparison APIs: `industry_peers`, `industry_benchmark`, `industry_rank`.
- Onboarding dry-run coverage for mock provider registration without core rewrite.
- New usage guide for the three core analytics groups:
  - `docs/FINANCE_INSIDER_INDUSTRY_USAGE_GUIDE.md`

### Changed
- Stabilized unit test behavior by gating live integration suites behind `vnbroker_RUN_LIVE_INTEGRATION=1` to avoid false negatives from upstream rate limits.
- Updated implementation and signoff documentation for production-ready handoff.

### Validation
- Full unit regression after release changes: **195 passed, 6 skipped**.

## [2026-04-13] — Upgrade Notice: GitHub-only Version Comparison Fix

### Fixed
- **Perpetual false upgrade notices**: `_check_version_updates()` previously compared package metadata version (`1.0.x`) against GitHub release tags (`3.x`), causing the upgrade notice to fire on every import.
- **Root cause**: `importlib.metadata.version("vnbroker")` returns the editable-install packaging version (`1.0.0`) which is unrelated to the upstream release line (`3.x`).
- **Solution**: Added `_get_current_github_channel_version()` which reads the highest version key from `VERSION_REQUIREMENTS`, `VERSION_NOTICES`, and `PYTHON_VERSION_SUPPORT` in `vnbroker/config.py` (currently `"3.4.0"`) as the source-of-truth for the installed codebase version. GitHub-only comparison is preserved (no PyPI fallback added).
- **Message cleanup**: Removed noisy `package metadata: 1.0.0` text from notice output. Display now shows `Current: 3.4.0 (Python 3.x (venv))`.

### Added
- `_get_current_github_channel_version()` — internal helper in `vnbroker/core/utils/upgrade.py`.
- `get_github_version_diagnostics()` — public debug helper returning a dict with `package`, `github_repo`, `package_metadata_version`, `current_github_channel_version`, `latest_github_release`.
- `tests/unit/core/test_upgrade_notice.py` — 4 regression tests locking the GitHub-only update notice behavior.

### Tagged
- Branch `core` tagged as `v3.4.0-core`.

## [2026-04-11] - Stock News API, Filtering, and Health Monitoring

### Added
- **Unified News facade** in `StockComponents`: `stock.news` now provides normalized multi-source news access for stock symbols.
- **New News adapter and providers**:
	- `vnbroker/api/news.py`
	- provider wrappers for `VCI`, `KBS`, `TCBS`
	- RSS providers for `RSS_CAFEF` and `RSS_VNECONOMY`
- **Normalization and dedup pipeline**:
	- `vnbroker/news/normalize.py` for canonical schema mapping
	- `vnbroker/news/dedup.py` for duplicate reduction
- **Criteria-based filtering API**:
	- `News.filter(...)` supports symbol, query text, source list, and time-range filters
	- `News.query(...)` convenience alias for text search
	- utility `vnbroker/news/filtering.py`
- **Source health observability for News**:
	- `vnbroker/core/source_router.get_source_health_snapshot("news")`

[Rest of changelog preserved...]