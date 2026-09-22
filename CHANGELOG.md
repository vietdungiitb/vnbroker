# Changelog

All notable changes to this project will be documented in this file.

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