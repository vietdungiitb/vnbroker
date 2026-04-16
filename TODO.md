# 8X API Calls + 5X Speed Optimization TODO
## Current Progress: Phase 1 ⏳

## Audit File List (Price Unit Standardization - 2026-04-16) ✅ COMPLETED

### Core Implementation Files
- vnstock/core/utils/transform.py (enhanced normalization logic + env var handling)
- vnstock/explorer/msn/quote.py (added price_unit parameter)
- vnstock/explorer/vci/quote.py (metadata fixes on empty paths)
- vnstock/explorer/vci/trading.py (added price_unit parameter)
- vnstock/explorer/kbs/trading.py (added price_unit parameter)
- vnstock/explorer/tcbs/trading.py (added price_unit parameter)

### Test Files
- tests/unit/explorer/test_trading_price_unit_standardization.py (NEW - 4 tests)
- tests/unit/api/test_quote_price_unit_consistency.py (UPDATED - TCBS coverage)

### Documentation Files (NEW)
- docs/PRICE_UNIT_API_GUIDE.md (comprehensive developer guide)
- docs/PRICE_UNIT_QUICK_REFERENCE.md (quick reference card)
- docs/PRICE_UNIT_RELEASE_NOTES.md (release notes + migration guide)

**Test Results**: 100/127 passed, 4 price_unit tests ✅, 2 consistency tests ✅
**Status**: Production-ready ✅ | Ready for merge to dev ✅

## Phase 1 COMPLETE ✓
- [x] `async_client.py` created (httpx.AsyncClient + RateLimiter 500/min)
- [x] `__init__.py` exports (async_send_request, fetch_multiple_requests)
- [x] `proxy_manager.py` enhanced (get_proxy_pool(16))
- [x] requirements.txt + deps installed

**Ready for Phase 2: Quote parallelization** (user priority)

## Phase 2: Quote (vci/kbs → async + parallel)

## Phase 2: Quote Parallelization (Priority: quote/listing first)
- [ ] `vnstock/explorer/vci/quote.py`: Add async history(), fetch_multiple(symbols)
- [ ] `vnstock/explorer/kbs/quote.py`: Add async history(), fetch_multiple()
- [ ] `vnstock/api/quote.py`: Add quote_multiple(symbols, parallel=True)

## Phase 3: Listing + Financial
- [ ] `vnstock/explorer/vci/listing.py`: symbols_parallel(groups)
- [ ] `vnstock/explorer/kbs/listing.py`: Similar  
- [ ] `vnstock/api/listing.py`: listing_parallel()

## Phase 4: Productionize
- [ ] **DEPS**: httpx[http2], asyncio-throttle → requirements.txt
- [ ] Tests: pytest-asyncio + httpx-mock
- [ ] Benchmark script
- [ ] Docs + examples

## Phase 5: Advanced
- [ ] Caching (LRU)
- [ ] Metrics dashboard

**Metrics Target**: 500 req/min safe, 8X calls, 5X processing speed
**User Priority**: quote/listing first ✓

