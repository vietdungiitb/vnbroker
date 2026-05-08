# Module Tree Full

Updated: 2026-05-08

## vnstock/
- `__init__.py` - lazy-load explorer modules including DNSE
- `api/quote.py` - public quote adapter, now accepts DNSE credentials
- `api/listing.py` - public listing adapter, now accepts DNSE credentials and source
- `common/client.py` - `Vnstock.stock()` now accepts DNSE source and `api_secret`
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
- `DNSE_EXPLORER_SPEC.md`
- `DNSE_CODING_GUIDE.md`
- `DNSE_TEST_SPEC_V2.md`
- `DNSE_AUDIT_CHECKLIST.md`
- `DNSE_INDEX.md`
