# Changelog

All notable changes to this project will be documented in this file.

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
	- `News.health()` and `News.health_dataframe()`
- **Health log export**:
	- `News.log_health(file_path, fmt="jsonl|csv")`
	- utility `vnbroker/news/health.py`
- **Alerting and monitor helpers**:
	- `News.alerts(...)` and `News.monitor_health(...)`
	- utility `vnbroker/news/monitor.py`
- **Example monitor script**:
	- `tests/examples/news_health_monitor.py`
- **News integration and unit test coverage** for adapter failover, normalization, dedup, filtering, health logging, and alerts.

### Changed
- `AUTO` source router now includes a dedicated `news` module candidate pool and primary pool behavior.
- `vnbroker/__init__.py` and common exports now expose News-related functionality for direct developer usage.

### Docs
- Added `docs/STOCK_NEWS_USAGE_GUIDE.md` with end-to-end usage for retrieval, filtering, monitoring, logging, and alerts.
- Linked the News usage guide from both Vietnamese and English README documentation sections.

## [2026-04-04] — AUTO Source & VCI-first Routing

### Added
- **AUTO source routing** (`source='AUTO'`): vnbroker now ships a built-in source router that automatically selects VCI as the primary provider and fails over to KBS (then MSN where applicable) when VCI returns rate-limit errors, timeouts, or HTTP 4xx/5xx responses.
- `DataSource.AUTO = "auto"` enum value added to `vnbroker/core/types.py`.
- `vnbroker/core/source_router.py`: new routing engine with `build_source_order()`, `record_success/failure()`, exponential cooldown backoff (5 s → 90 s), `should_failover()`, and `annotate_result_source()`.
- All five public API adapters (`Quote`, `Listing`, `Trading`, `Company`, `Finance` in `vnbroker/api/`) now accept `source='AUTO'` (and `source='auto'`) without raising `ValueError`.
- `vnbroker.SUPPORTED_SOURCES` in `vnbroker/common/client.py` now includes `"AUTO"`.
- `PUBLIC_VN_SOURCES` constant in `vnbroker/common/data.py`; all facade `_load_data_source()` methods route through the adapter layer (instead of importing explorer modules directly) when `source in PUBLIC_VN_SOURCES`.
- `tests/unit/api/test_auto_source_router.py`: 4 unit tests covering initial source selection, failover on connection error, cooldown deprioritisation, and VCI-first ordering guarantee.
- `tests/examples/auto_source_benchmark.py`: CLI benchmark tool comparing AUTO vs explicit providers on large symbol sets; supports `--providers`, `--symbol-count`, `--concurrency`, `--profile`, `--output-csv/json`.
- `tests/unit/examples/test_auto_source_benchmark.py`: 5 unit tests for benchmark report helpers.
- `docs/AUTO_SOURCE_GUIDE.md`: comprehensive usage guide with priority table, code examples, failover flow diagram, benchmark results, and architecture overview.

### Changed
- `PRIMARY_SOURCE_POOLS["quote/company/financial/trading"]` set to `["vci"]` (single-element pool): hash-sharding now always selects VCI first; KBS activates only on confirmed failover, eliminating the previous 50/50 load-split that halved throughput.

### Changed
- `PRIMARY_SOURCE_POOLS["trading"]` switched to `["kbs"]` and `OPEN_SOURCE_CANDIDATES["trading"]` to `kbs -> vci` after sustained `price_board` benchmarks showed KBS materially outperformed VCI under online rate-limit conditions.
- `tests/unit/api/test_auto_source_router.py` now covers both KBS-first trading initialization and failover from KBS to VCI when KBS errors.
- `docs/AUTO_SOURCE_GUIDE.md` updated to document the per-module AUTO priority, including KBS-first routing for trading.

### Performance (measured 2026-04-04)
- `source='AUTO'` at concurrency 8: **100% success, 37.2 rps** (vs KBS 86.67% success, 11.1 rps).
- `source='AUTO'` at concurrency 12, 90 symbols: **100% success, 41.3 rps** (VCI handled 85/90; KBS absorbed 5 failovers).
- Pure `VCI` reference: 46.5 rps at concurrency 8 (upper bound with no overhead).

### Added
- Restored TCBS as an available current data source for quote, company, financial, trading, and screener flows.

### Removed
- Removed the legacy authentication flow and all public API key helpers from the runtime package and test setup.
- Removed the `vnai` dependency, related initialization hooks, and the API key verification workflow from CI.

### Changed
- Replaced explorer execution decorators with local no-op implementations to keep existing call sites stable without external auth/runtime coupling.
- Updated README, quickstart notebook, and test coverage to reflect the current KBS/VCI-first source model and auth-free usage flow.

## [2026-03-07]

### Added
- **Market events module**: Introduced `vnbroker/core/utils/market-events.py` containing a comprehensive list of Vietnam market holidays, suspensions and other notable events. The dataset is maintained in an open format so the community can contribute additional quant-focused events and reuse the list for analysis.

### Changed
- **Upgrade suggestions now more helpful**: When upgrading vnbroker, the system now properly detects your Python environment and shows you the exact command to use. If you have multiple Python versions installed, it will suggest the upgrade using the correct one.

### Removed
- **Screener functionality removed**: The built-in stock screener from TCBS is no longer available. If you were using this feature, you can find similar functionality in the vnbroker_data (sponsored version).

## [2026-03-05]

### Added
- Added pandas compatibility utilities and enhance frequency handling in data processing

### Fixed
- Add `pytz` to project dependencies (#217)

### Removed
- Removed TCBS data source and all its related dependencies and integrations across the library (`explorer/tcbs/`)
- Removed `api/screener.py` entirely as it was exclusively dependent on TCBS
- Removed TCBS references from core registry, constants, types, common data layer, and all API adapters (`Company`, `Finance`, `Quote`, `Trading`, `Listing`)

## [2025-02-01]

### Fixed
- Fixed `Listing` tests to correctly handle `pd.Series` return types from `all_future_indices` and related methods
- Fixed `Quote` integration tests to handle missing data and expired derivatives gracefully without failing the entire suite
- Fixed `KBS Quote` to correctly interpret bar-based lookback lengths (e.g., '500b') using `interpret_lookback_length` logic
- Enabled full integration test suite for `vnbroker.explorer` module

### Changed
- Consolidated test documentation into `tests/docs/` directory
- Updated `.gitignore` to include debug scripts
- Standardized KBS Quote price data to use decimal values (thousands unit) instead of VND in `history` and `intraday` methods

### Removed
- Removed `price_depth` method from `vnbroker.explorer.vci.quote`


## [3.4.2] - 2026-01-27

### Added

- **Derivatives Support**: Implemented `convert_derivative_symbol` and `get_derivative_maturity_date` to support the new KRX derivative symbol format (effective May 2025), automatically converting old symbols (e.g., VN30F2506) to the new standard.
- **KBS Index Support**: Added `_INDEX_MAPPING` and validation logic to fully support market indices in KBS Quote module, ensuring correct API endpoint routing.
- **VCI Listing**: Added `all_indices()` and `indices_by_group()` wrapper methods in `Listing` class to provide standardized access to market indices.

### Changed

- **KBS Financial**: Optimized `get_financial_report` to use `page_size=8` (fetching 2 years of quarterly data) and improved field normalization with `preserve_hierarchy=True`.
- **Quote Validation**: Added strict validation to prevent `intraday` data requests for Index symbols in both KBS and VCI sources (`ValueError` raised).
- **Refactoring**: Simplified `FieldHandler` initialization and removed file-based referencing in favor of built-in mappings for better performance.

## [2026-01-22]

### Added

- Overhauled Vietnamese text normalization with new character map and advanced options for robust snake_case conversion
- Advanced field handling system for financial reports with flexible standardization options
- Field display modes: standardized_only, all_fields, and auto_convert for flexible field handling
- Comprehensive field mapping and validation system for KBS financial data
- Language filtering support for financial reports (Vietnamese/English/Both)
- Field collision detection and handling with automatic ID generation
- Enhanced field utilities package with specialized financial data field handlers
- Comprehensive GitHub Actions CI/CD pipeline for automated testing and quality assurance
- Multi-platform test matrix: Ubuntu, macOS, Windows across Python 3.10-3.13
- Automated coverage reporting with Codecov integration
- Performance benchmarking and regression detection
- Code quality checks: flake8, black, isort, mypy
- Security scanning with Bandit and Safety
- Enhanced pytest fixtures and utilities for comprehensive testing
- Performance monitoring and quality metrics tracking
- AI-powered vibe coding section in README

### Changed

- Enhanced KBS trading module with code optimizations
- Improved README formatting and onboarding guidance
- Refactored KBS financial module with advanced field processing capabilities
- Updated all financial report methods (income_statement, balance_sheet, cash_flow, ratio) with language filtering support
- Enhanced field ID generation with collision detection and automatic resolution
- Integrated professional charting capabilities with pandas DataFrame extension
- Restructured test suite with comprehensive GitHub Actions CI/CD integration
- Enhanced pytest configuration with advanced fixtures and performance monitoring
- Implemented multi-platform and multi-version testing matrix for better compatibility assurance

### Fixed

- Optimized code performance in KBS trading module

## [2026-01-16]

### Added

- New KBS data source support as default source, replacing VCI as primary source
- Lazy loading mechanism to prevent circular import deadlocks across multiple modules

### Changed

- Updated version from 3.3.2 to 3.4.0
- Updated Listing class to use KBS as default data source instead of VCI
- Modified StockComponents to initialize listing with KBS source
- Updated error message to include KBS in valid source options

### Removed

- Removed outdated Vietnam stock notebook (1_vietnam_stock_vnbroker3.ipynb) containing 6497 lines of legacy content
- Cleaned up comprehensive examples covering Listing, Quote, Company, Finance, and Trading modules

## [2026-01-06]

### Fixed

- Fixed issue where VN100 derivative symbols (e.g., `VN100F1M`) were incorrectly identified as Covered Warrants due to length conflict.
- Refined `auto_count_back` logic in `Quote.history` to accurately reflect Vietnam market trading hours (5 hours/day, 255 mins/day).

### Added

- Feature "Smart Lookback" for `Quote.history` in `vnbroker/explorer/vci/quote.py` and `vnbroker/explorer/tcbs/quote.py`. Users can now use `length` parameter (e.g., `'3M'`, `'10W'`, `'100b'`, `150`) instead of specifying start/end dates.
- New utility `vnbroker/core/utils/lookback.py` for parsing flexible time periods and calculating start dates.
- Documentation for Smart Lookback feature at `docs/feature_lookback.md`.
- Enhanced header management mechanism in `vnbroker/core/utils/user_agent.py` supporting `Authorization`, `custom_headers`, and `override_headers` for dynamic and flexible request configuration.
- Enhanced `ProxyManager` with `get_fresh_proxies`, custom proxy support, and singleton instance.
- Updated `client.py` to support `AUTO` proxy mode and integrated with `ProxyManager`.
- Refactored `TCBS Quote` to use central `client.py` request wrapper, enabling proxy support.
- Refactored all VCI modules (`Quote`, `Company`, `Financial`, `Listing`, `Trading`) to support proxy configuration via `__init__` parameters (`proxy_mode`, `proxy_list`), addressing IP blocking issues on cloud platforms like Google Colab/Kaggle.
- Documentation for the new header system at `docs/header_management.md`.

### Changed

- `Quote.history`: `start` parameter is now optional if `length` or `count_back` is provided.
- Updated `get_asset_type` in `vnbroker/core/utils/parser.py` to dynamically recognize all indices from `vnbroker.constants.INDICES_INFO`, ensuring better support for sector and investment indices (e.g., `VNSI`, `VNFINLEAD`, `VNIND`).