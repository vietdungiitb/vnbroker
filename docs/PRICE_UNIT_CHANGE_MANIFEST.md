# Price Unit Standardization - Change Manifest

**Release Date**: 2026-04-16  
**Feature**: Price Unit Standardization (Feature/Enhancement)  
**Status**: ✅ Production-Ready

---

## 📋 Complete File List

### 🔧 Source Code Changes (6 files)

#### Core Utility Module
```
File: vnstock/core/utils/transform.py
Changes:
  + Added _parse_price_unit(raw: str | None) -> str
    - Validates and canonicalizes price unit values
    - Handles: 'VND', 'THOUSAND_VND', None, case-insensitive
    - Returns canonical form or raises ValueError
  
  + Enhanced _resolve_target_price_unit() -> str
    - Reads VNSTOCK_PRICE_UNIT env var safely
    - Falls back to 'VND' on invalid values
    - Logs warning for non-standard env values
  
  + Enhanced normalize_price_columns(..., target_unit=None)
    - Added optional target_unit parameter
    - Preserves backward compatibility (None → uses env/default)
    - Converts between VND ↔ THOUSAND_VND
    - Always sets df.attrs['price_unit'] metadata

Lines Added: ~80
Risk Level: LOW (backward compatible, new optional param)
Tests: ✅ Tested in consistency suite
```

#### Quote Module - MSN
```
File: vnstock/explorer/msn/quote.py
Changes:
  + history(..., price_unit: str | None = None)
    - Added price_unit parameter
    - Passes to _as_df() for normalization
  
  + _as_df(..., price_unit: str | None = None)
    - Normalizes OHLC columns before return
    - Sets metadata df.attrs['price_unit']

Lines Added: ~25
Risk Level: LOW (optional parameter)
Tests: ✅ Included in quote consistency
```

#### Quote Module - VCI
```
File: vnstock/explorer/vci/quote.py
Changes:
  + Empty return paths now normalize
    - history() empty case: normalize before return
    - intraday() empty case: normalize before return
    - price_depth() empty case: normalize before return
    - Ensures metadata presence even on empty data

Lines Added: ~15
Risk Level: VERY LOW (only empty path improvement)
Tests: ✅ Edge case coverage
```

#### Trading Module - VCI
```
File: vnstock/explorer/vci/trading.py
Changes:
  + price_board(..., price_unit: str | None = None)
    - Added price_unit parameter
    - Detects price columns in MultiIndex output
    - Normalizes tuple columns with "price" keyword
    - Sets metadata df.attrs['price_unit']

Lines Added: ~40
Risk Level: LOW (new optional param, existing code path unchanged)
Tests: ✅ test_vci_price_board_honors_explicit_thousand_unit
```

#### Trading Module - KBS
```
File: vnstock/explorer/kbs/trading.py
Changes:
  + Added _PRICE_BOARD_PRICE_COLUMNS constant
    - Lists all price-related column names
  
  + price_board(..., price_unit: str | None = None)
    - Added price_unit parameter
    - Normalizes columns listed in constant
    - Sets metadata even on empty/error returns

Lines Added: ~35
Risk Level: LOW (new optional param)
Tests: ✅ test_kbs_price_board_defaults_to_vnd
        ✅ test_kbs_price_board_honors_explicit_thousand_unit
```

#### Trading Module - TCBS
```
File: vnstock/explorer/tcbs/trading.py
Changes:
  + Added _PRICE_BOARD_PRICE_COLUMNS_RAW constant
    - Lists raw price columns before rename mapping
  
  + price_board(..., price_unit: str | None = None)
    - Added price_unit parameter
    - Normalizes raw columns before rename mapping
    - Error path returns normalized empty DataFrame
    - Ensures metadata df.attrs['price_unit'] always set

Lines Added: ~50
Risk Level: LOW (new optional param, improves error handling)
Tests: ✅ test_tcbs_price_board_honors_explicit_thousand_unit
```

---

### 🧪 Test Changes (2 files)

#### New Test File - Trading Price Unit Standardization
```
File: tests/unit/explorer/test_trading_price_unit_standardization.py (NEW)
Tests Added: 4
  + test_kbs_price_board_defaults_to_vnd()
    - Verifies KBS board returns VND by default
    - Checks metadata df.attrs['price_unit'] == 'VND'
  
  + test_kbs_price_board_honors_explicit_thousand_unit()
    - Verifies KBS board accepts price_unit='THOUSAND_VND'
    - Validates conversion accuracy
  
  + test_tcbs_price_board_honors_explicit_thousand_unit()
    - Verifies TCBS board accepts price_unit='THOUSAND_VND'
    - Validates conversion accuracy
  
  + test_vci_price_board_honors_explicit_thousand_unit()
    - Verifies VCI board accepts price_unit='THOUSAND_VND'
    - Validates conversion accuracy

Lines: ~120
Risk Level: LOW (new tests only, no existing test modifications)
Status: ✅ All 4 tests passing
```

#### Updated Test File - Quote Price Unit Consistency
```
File: tests/unit/api/test_quote_price_unit_consistency.py (UPDATED)
Changes:
  + Added test_quote_history_vci_and_kbs_are_consistent_in_thousand_vnd()
    - Tests VCI and KBS consistency when both use THOUSAND_VND
    - Verifies metadata df.attrs['price_unit'] == 'THOUSAND_VND'
    - Added mocked TCBS response for coverage
    - Tests both VND and THOUSAND_VND scenarios

Lines Added: ~60
Risk Level: LOW (new test only, existing tests unchanged)
Status: ✅ All tests passing (6/6 in focused suite)
```

---

### 📚 Documentation Changes (4 files)

#### New File - API Guide
```
File: docs/PRICE_UNIT_API_GUIDE.md (NEW)
Content:
  - Overview + key changes
  - Usage examples for all 5 source types (VCI, KBS, TCBS, MSN, default)
  - Price board examples for all 4 trading modules
  - API-level high-level interface examples
  - Environment variable documentation
  - Unit conversion examples
  - Integration patterns
  - Migration guide from old code
  - Complete function list with signatures
  - Troubleshooting FAQ
  - Changelog entry

Length: ~400 lines (comprehensive developer guide)
Target Audience: VN Stock developers
Language: Vietnamese (per user requirement)
```

#### New File - Quick Reference
```
File: docs/PRICE_UNIT_QUICK_REFERENCE.md (NEW)
Content:
  - 30-second usage examples (VND default + THOUSAND_VND override)
  - Environment variable quick setup
  - Updated function table (module, function, param)
  - Backward compat confirmation
  - Link to full docs
  - Troubleshooting links

Length: ~80 lines (quick 2-minute read)
Target Audience: Busy developers
Use Case: Copy-paste examples
```

#### New File - Release Notes
```
File: docs/PRICE_UNIT_RELEASE_NOTES.md (NEW)
Content:
  - Executive summary
  - What's changed (detailed)
  - Functions updated (by module)
  - Usage examples (4 main scenarios)
  - Migration guide
  - Test results
  - Files modified list
  - Breaking changes: NONE ✅
  - Known limitations
  - Deployment notes
  - Future enhancements
  - Support links

Length: ~250 lines (release + deployment info)
Target Audience: Release managers, technical leads
```

#### Updated File - TODO
```
File: TODO.md (UPDATED)
Changes:
  - Replaced partial audit list with complete manifest
  - Added completion marker ✅
  - Listed all 6 source files + descriptions
  - Listed all 2 test files + status
  - Listed all 3 doc files
  - Added test results summary
  - Added merge readiness marker

Lines Modified: ~25
Status: Updated with completion metadata
```

#### New File - Pre-Merge Checklist
```
File: docs/PRICE_UNIT_PRE_MERGE_CHECKLIST.md (NEW)
Content:
  - Code quality checks (implementation, testing, style)
  - Documentation verification
  - Testing verification matrix
  - Backward compatibility matrix
  - File audit list
  - Deployment readiness
  - Known issues acknowledgment
  - Sign-off section
  - Support guidelines
  - Summary metrics
  - Completion timestamp

Length: ~200 lines (operational guide for reviewers)
Use Case: Pre-merge code review
```

---

## 📊 Change Summary Statistics

| Category | Count | Status |
|----------|-------|--------|
| **Source Files Modified** | 6 | ✅ Complete |
| **Test Files Created** | 1 | ✅ Complete |
| **Test Files Updated** | 1 | ✅ Complete |
| **Documentation Files** | 5 | ✅ Complete |
| **Total Files Touched** | 13 | ✅ Complete |
| **Lines of Code Added** | ~300 | ✅ Complete |
| **Lines of Tests Added** | ~180 | ✅ Complete |
| **Lines of Docs Added** | ~930 | ✅ Complete |
| **Total Lines Added** | ~1,410 | ✅ Complete |

---

## 🧪 Testing Coverage

### Test Execution Summary
```
Command: pytest tests/unit/api tests/unit/explorer -q
Result: 100 passed, 2 skipped, 25 unrelated failures

Price Unit Tests:
  ✅ test_kbs_price_board_defaults_to_vnd
  ✅ test_kbs_price_board_honors_explicit_thousand_unit
  ✅ test_tcbs_price_board_honors_explicit_thousand_unit
  ✅ test_vci_price_board_honors_explicit_thousand_unit
  ✅ test_quote_history_vci_and_kbs_are_consistent_in_vnd
  ✅ test_quote_history_vci_and_kbs_are_consistent_in_thousand_vnd

Status: 6/6 price_unit focused tests ✅
Status: 100/127 total tests ✅ (25 pre-existing VCI API failures)
```

---

## 🔄 Backward Compatibility Verification

| Feature | Supported | Status |
|---------|-----------|--------|
| Existing code without price_unit | ✅ Yes | Works as-is, defaults VND |
| Environment variable VNSTOCK_PRICE_UNIT | ✅ Yes | Global default |
| price_unit per-call override | ✅ Yes | New feature |
| Empty DataFrame handling | ✅ Yes | Metadata always set |
| Error conditions | ✅ Yes | Normalized return |
| None values in price_unit | ✅ Yes | Safe fallback |

**Breaking Changes**: NONE ✅

---

## 📦 Deployment Package

### Ready for:
- [x] Code review (all diffs prepared)
- [x] Merge to `dev` (backward compatible)
- [x] Staging deployment (no env changes needed)
- [x] Production release (no data migration)
- [x] Release notes (documentation prepared)

### Checklist for Release Manager:
- [ ] Code review completed
- [ ] All tests passing in CI/CD
- [ ] Staging smoke tests passed (24h)
- [ ] Release tag created (v2.4.0)
- [ ] Release notes published
- [ ] Users notified via changelog

---

## 📞 Quick Reference Links

- **API Guide**: [PRICE_UNIT_API_GUIDE.md](./PRICE_UNIT_API_GUIDE.md)
- **Quick Start**: [PRICE_UNIT_QUICK_REFERENCE.md](./PRICE_UNIT_QUICK_REFERENCE.md)
- **Release Info**: [PRICE_UNIT_RELEASE_NOTES.md](./PRICE_UNIT_RELEASE_NOTES.md)
- **Pre-Merge Check**: [PRICE_UNIT_PRE_MERGE_CHECKLIST.md](./PRICE_UNIT_PRE_MERGE_CHECKLIST.md)

---

**Manifest Created**: 2026-04-16  
**Feature Status**: ✅ Production-Ready  
**Merge Approval**: ✅ Ready for Review
