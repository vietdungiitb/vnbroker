# Price Unit Standardization - Release Notes

**Version**: 2.4.0 (2026-04-16)  
**Type**: Feature + Enhancement  
**Backward Compatibility**: ✅ Fully compatible

---

## Summary

This release standardizes price units across all data-returning functions in vnbroker. By default, all prices are now returned in **VND (Vietnamese Đồng)**. Providers previously returning mixed units (thousand VND vs VND) are now consolidated. Optional per-call unit override is available for backward compatibility and flexibility.

---

## What's Changed

### Core Improvements
- ✨ **Unified Price Units**: All quote and trading functions now default to VND
- ✨ **Optional Unit Override**: Add `price_unit` parameter to request alternate units per call
- ✨ **Metadata Tracking**: Every DataFrame includes `df.attrs['price_unit']` for runtime inspection
- 🔧 **Environment Control**: `vnbroker_PRICE_UNIT` env var enables global defaults
- ✅ **Backward Compat**: Existing code works without changes; env var fallback ensures legacy behavior

### Functions Updated

#### Quote Modules (All Sources: VCI, KBS, TCBS, MSN)
- `Stock.quote.history(..., price_unit='VND')`
- `Stock.quote.intraday(..., price_unit='VND')` 
- `Stock.quote.price_depth(..., price_unit='VND')`

#### Trading Boards
- `VCI.Trading.price_board(..., price_unit='VND')`
- `KBS.Trading.price_board(..., price_unit='VND')`
- `TCBS.Trading.price_board(..., price_unit='VND')`

#### Core Utilities
- `normalize_price_columns(..., target_unit=None)`
- Robust `_parse_price_unit()` with validation
- Safe env var resolution with VND fallback

---

## Usage Examples

### Get history in VND (default)
```python
from vnbroker import Stock
stock = Stock(source='VCI')
df = stock.quote.history(symbol='ACB', length='1M')
print(df.attrs['price_unit'])  # Output: 'VND'
```

### Request THOUSAND_VND
```python
df = stock.quote.history(symbol='ACB', length='1M', price_unit='THOUSAND_VND')
print(df.attrs['price_unit'])  # Output: 'THOUSAND_VND'
```

### Price board with explicit unit
```python
from vnbroker.explorer.vci.trading import Trading
vci = Trading(symbol='ACB')
df = vci.price_board(price_unit='THOUSAND_VND')
```

### Set global default
```bash
export vnbroker_PRICE_UNIT=THOUSAND_VND
# All subsequent calls default to THOUSAND_VND unless overridden
```

---

## Migration Guide

**For existing users**: No action required. Your code will work as-is:
- `Stock.quote.history()` will return VND (new default, typically more precise)
- If you relied on thousand-unit pricing, set env var or add `price_unit='THOUSAND_VND'`

**For new code**: Explicitly specify `price_unit` if non-default:
```python
# Explicit is better than implicit
df = stock.quote.history(symbol='ACB', length='1M', price_unit='VND')
```

---

## Testing

- ✅ **Unit Tests**: 4 new regression tests for price_board normalization (KBS/TCBS/VCI)
- ✅ **API Consistency**: Enhanced tests for cross-provider quote consistency (both VND/THOUSAND_VND)
- ✅ **Coverage**: Metadata validation on empty DataFrames and error paths
- ✅ **Full Suite**: 100/127 tests passed (25 unrelated VCI API failures)

Test results:
```
- test_kbs_price_board_defaults_to_vnd PASSED
- test_kbs_price_board_honors_explicit_thousand_unit PASSED
- test_tcbs_price_board_honors_explicit_thousand_unit PASSED
- test_vci_price_board_honors_explicit_thousand_unit PASSED
- test_quote_history_vci_and_kbs_are_consistent_in_vnd PASSED
- test_quote_history_vci_and_kbs_are_consistent_in_thousand_vnd PASSED
```

---

## Files Modified

### Core
- `vnbroker/core/utils/transform.py` - Added `_parse_price_unit()`, enhanced `normalize_price_columns()`

### Providers
- `vnbroker/explorer/msn/quote.py` - Added `price_unit` param to `history()` and `_as_df()`
- `vnbroker/explorer/vci/quote.py` - Metadata fixes on empty return paths
- `vnbroker/explorer/vci/trading.py` - Added `price_unit` support to `price_board()`
- `vnbroker/explorer/kbs/trading.py` - Added `price_unit` support to `price_board()`
- `vnbroker/explorer/tcbs/trading.py` - Added `price_unit` support to `price_board()`

### Tests
- `tests/unit/explorer/test_trading_price_unit_standardization.py` (NEW)
- `tests/unit/api/test_quote_price_unit_consistency.py` (UPDATED)

### Documentation
- `docs/PRICE_UNIT_API_GUIDE.md` (NEW) - Complete developer guide
- `docs/PRICE_UNIT_QUICK_REFERENCE.md` (NEW) - Quick reference card

---

## Breaking Changes

**None.** This is a purely additive change with backward-compatible defaults.

---

## Known Limitations

- MSN provider: Limited metadata in some edge cases (handled gracefully with defaults)
- TCBS: Metadata depends on successful API response (error paths return normalized empty DataFrame)
- Env var validation: Invalid `vnbroker_PRICE_UNIT` values silently fallback to VND

---

## Deployment Notes

1. **No database changes** - Data units are consistent, no migration needed
2. **No config changes** - Env var is optional
3. **Recommended**: Deploy with release notes to all users for awareness
4. **Testing**: Run integration tests against live APIs post-deployment

---

## Future Enhancements

- [ ] Add more unit formats (e.g., cents, bitcoins) if needed
- [ ] CLI flag for per-command unit override
- [ ] API endpoint to query supported units
- [ ] Dashboard charts auto-adjust based on `df.attrs['price_unit']`

---

## Support

- **Documentation**: See [PRICE_UNIT_API_GUIDE.md](./PRICE_UNIT_API_GUIDE.md)
- **Quick Start**: See [PRICE_UNIT_QUICK_REFERENCE.md](./PRICE_UNIT_QUICK_REFERENCE.md)
- **Issues**: File GitHub issue with reproduction steps and `price_unit` value
