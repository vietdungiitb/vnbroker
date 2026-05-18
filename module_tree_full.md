# Module Tree Full

Updated: 2026-05-19

## vnbroker/
- `__init__.py` - lazy-load explorer modules including DNSE
- `api/quote.py` - public quote adapter, now accepts DNSE credentials
- `api/listing.py` - public listing adapter, now accepts DNSE credentials and source
- `common/client.py` - `vnbroker.stock()` now accepts DNSE source and `api_secret`
- `common/data.py` - DNSE-aware `StockComponents`, `Quote`, and `Listing`
- `connector/dnse/client.py` - `_to_dataframe()` recognizes market-data payload keys
- `connector/dnse/trade.py` - logger refactor and OpenAPI bridge helpers
- `explorer/dnse/__init__.py` - provider registration
- `explorer/dnse/quote.py` - DNSE market data provider with live STOCK OHLC parsing support
- `explorer/dnse/listing.py` - DNSE listing provider with compatibility fallbacks and live limit=1000 default
- `explorer/dnse/financial.py` - DNSE financial stub (NotImplementedError, placeholder)

## VCI REST Migration (2026-05-19)
- `explorer/vci/const.py` — Added `_VCIQ_URL`, `_IQ_FINANCE_REPORT`, `_GROUP_CODE_MAPPING`, `_VCI_INDEX_MAPPING`, `RATIO_COLUMN_MAP_EN/VI/SNAKE`
- `explorer/vci/financial.py` — **Full rewrite**: migrated from GraphQL → REST (`iq.vietcap.com.vn/api/iq-insight-service`); KBS-compatible output (items-as-rows, periods-as-columns); `df.attrs` standardized; `display_mode` param; methods: `balance_sheet`, `income_statement`, `cash_flow`, `ratio`, `financial_ratios`
- `explorer/vci/listing.py` — `symbols_by_industries` → REST `/v2/company/search-bar`; `industries_icb` → REST `/v1/sectors/icb-codes`; `symbols_by_group` → uses `_VCI_INDEX_MAPPING` + `_GROUP_CODE_MAPPING` for validation and URL mapping
- `core/utils/parser.py` — `camel_to_snake()` improved: spaces/hyphens → underscores, no double underscores, strip leading/trailing underscores

## Output Standardization: VCI ↔ KBS
Both VCI and KBS `financial` providers now return identical column format:
- Columns: `[item, item_id]` (STD mode) or `[item, item_en, item_id]` (ALL mode) + period columns
- Period format: `"2024"` (annual) or `"2024-Q1"` (quarterly)
- `df.attrs`: `{symbol, source, report_type, period, periods}`

## tests/
- `unit/explorer/dnse/__init__.py`
- `unit/explorer/dnse/test_quote.py`
- `unit/explorer/dnse/test_listing.py`
- `unit/explorer/dnse/test_adapters.py`
- `unit/connector/dnse/test_trade_bridge.py`
- existing DNSE connector unit tests and integration smoke remain in place

## docs/
- `DNSE_INTEGRATION_PLAN_20260507.md`
- `DNSE_BROKER_PLATFORM_RFC.md`
- `DNSE_PROVIDER_COMPARISON_MATRIX.md`
- `DNSE_PROVIDER_DECISION_GUIDE.md`
- `DNSE_PROJECT_FINAL_RECOMMENDATION.md`

## vnbroker/
- `__init__.py` - lazy-load explorer modules including DNSE
- `api/quote.py` - public quote adapter, now accepts DNSE credentials
- `api/listing.py` - public listing adapter, now accepts DNSE credentials and source
- `common/client.py` - `vnbroker.stock()` now accepts DNSE source and `api_secret`
- `common/data.py` - DNSE-aware `StockComponents`, `Quote`, and `Listing`
- `connector/dnse/client.py` - `_to_dataframe()` recognizes market-data payload keys
- `connector/dnse/trade.py` - logger refactor and OpenAPI bridge helpers
- `explorer/dnse/__init__.py` - provider registration
- `explorer/dnse/quote.py` - DNSE market data provider with live STOCK OHLC parsing support
- `explorer/dnse/listing.py` - DNSE listing provider with compatibility fallbacks and live limit=1000 default

## tests/
- `unit/explorer/dnse/__init__.py`
- `unit/explorer/dnse/test_quote.py`
- `unit/explorer/dnse/test_listing.py`
- `unit/explorer/dnse/test_adapters.py`
- `unit/connector/dnse/test_trade_bridge.py`
- existing DNSE connector unit tests and integration smoke remain in place

## docs/
- `DNSE_INTEGRATION_PLAN_20260507.md`
- `DNSE_BROKER_PLATFORM_RFC.md`
- `DNSE_PROVIDER_COMPARISON_MATRIX.md`
- `DNSE_PROVIDER_DECISION_GUIDE.md`
- `DNSE_PROJECT_FINAL_RECOMMENDATION.md`
- `DNSE_EXECUTIVE_DECISION_BRIEF.md`
- `DNSE_IMPLEMENTATION_EXECUTION_PLAYBOOK.md`
- `DNSE_TEST_AND_AUDIT_EVIDENCE_PROTOCOL.md`
- `DNSE_SPRINT_TASK_BOARD.md`
- `DNSE_SLICE_DEFINITION_OF_DONE.md`
- `DNSE_AUDIT_CHECKLIST_V2.md`
- `DNSE_EXPLORER_SPEC.md`
- `DNSE_CODING_GUIDE.md`
- `DNSE_TEST_SPEC_V2.md`
- `DNSE_AUDIT_CHECKLIST.md`
- `DNSE_INDEX.md`
