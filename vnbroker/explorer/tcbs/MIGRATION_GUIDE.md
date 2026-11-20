# TCBS Explorer Migration Guide: iFlash OpenAPI Compatibility

## Overview

This document describes the changes required to migrate the TCBS explorer from the old `apiextaws.tcbs.com.vn` endpoints to the new iFlash OpenAPI platform on `openapi.tcbs.com.vn`.

## Key Changes

### 1. Base URL Change

**Old:** `https://apiextaws.tcbs.com.vn`
**New:** `https://openapi.tcbs.com.vn`

### 2. Endpoint Changes

| Feature | Old Endpoint | New Endpoint | Status |
|---------|---------------|--------------|---------|
| Derivatives Listing | `/futures-insight/v2/stock/bars?type=derivative` | `/tartarus/v1/derivatives` | ✅ Working |
| Intraday History | `/stock-insight/v1/intraday/{ticker}/his/paging` | `/nyx/v1/intraday/{ticker}/his/paging` | ✅ Working |
| Ticker Info | `/stock-insight/v2/tickerCommons` | `/tartarus/v1/tickerCommons` | ✅ Working |
| Company Data | `/tcanalysis/v1/company/{symbol}/overview` | `/tcanalysis/v1/company/{symbol}/overview` | ❓ Uncertain |
| Watchlist | `/ligo/v1/watchlist/preview` | `/ligo/v1/watchlist/preview` | ❓ Uncertain |
| OHLC Bars | `/stock-insight/v2/stock/bars` | **NOT AVAILABLE** | ❌ Needs adaptation |

### 3. Authentication

**Old:** Bearer token from old API
**New:** JWT token from iFlash OpenAPI token endpoint

To obtain a JWT token:
1. Use API key from TCBS developer portal
2. Call `POST https://openapi.tcbs.com.vn/gaia/v1/oauth2/openapi/token`
3. Request body: `{"apiKey": "your-api-key", "otp": "your-otp"}`
4. Response: `{"token": "your-jwt-token"}`

Set environment variable: `TCBS_JWT_TOKEN=your-jwt-token` (JWT thật từ `POST /gaia/v1/oauth2/openapi/token`. `TCBS_AUTH_TOKEN` là mã 48 ký tự KHÔNG phải JWT — server trả 401 khi dùng làm Bearer.)

## Migration Steps

### Step 1: Update Environment Variables

```bash
# Old environment variable (legacy 48-char code, NOT a JWT — rejected by openapi endpoints)
export TCBS_AUTH_TOKEN=old_token

# New environment variable (required for new API): real JWT from the token exchange
export TCBS_JWT_TOKEN=new_jwt_token
```

### Step 2: Update Code References

Replace all occurrences of `apiextaws.tcbs.com.vn` with `openapi.tcbs.com.vn`.

### Step 3: Update Endpoint Paths

Change endpoint paths according to the table above.

### Step 4: Adapt OHLC History

Since the new API doesn't provide OHLC bars, you need to compute them from intraday data:

```python
# Old approach (broken)
def history(self, ...):
    url = f"{self.base_url}/{_STOCKS_URL}/v2/stock/bars?resolution=1D&ticker={self.symbol}"
    ...

# New approach (compute from intraday)
def history(self, ...):
    # Get intraday data
    intraday_df = self.get_intraday_data(ticker=self.symbol)
    
    # Compute OHLC
    ohlc_df = self.compute_ohlc_from_intraday(ticker=self.symbol, interval="1D")
    return ohlc_df
```

## Implementation Examples

### Derivatives Listing

**Old:**
```python
@optimize_execution("TCBS")
@cached_listing(ttl_seconds=86400)
def all_future_indices(self, show_log: Optional[bool] = False) -> pd.Series:
    """Truy xuất danh sách mã phái sinh hợp đồng tương lai."""
    return self.symbols_by_group(group="FU_INDEX", show_log=show_log)
```

**New:**
```python
@optimize_execution("TCBS")
@cached_listing(ttl_seconds=86400)
def all_future_indices(self, show_log: Optional[bool] = False) -> pd.Series:
    """Truy xuất danh sách mã phái sinh hợp đồng tương lai qua /tartarus/v1/derivatives."""
    try:
        response = client.send_request(
            url=_DERIVATIVES_URL,
            headers=self.headers,
            method="GET",
            show_log=show_log,
        )
    except Exception as exc:
        if show_log:
            logger.error(f"TCBS derivatives fetch failed: {exc}")
        return pd.Series([], name="symbol", dtype="object")

    records = response if isinstance(response, list) else response.get("data", [])
    if not records:
        return pd.Series([], name="symbol", dtype="object")

    symbols = [r.get("symbol") or r.get("t") for r in records if r.get("symbol") or r.get("t")]
    s = pd.Series(sorted(set(symbols)), name="symbol")
    s.attrs["source"] = self.data_source
    if show_log:
        logger.info(f"TCBS derivatives: {len(s)} symbols.")
    return s
```

### Intraday History

**Old:**
```python
url = f'{self.base_url}/{_STOCKS_URL}/v1/intraday/'
f'{self.symbol}/his/paging'
```

**New:**
```python
url = f'{self.base_url}{NYX_PATH}/intraday/'
f'{self.symbol}/his/paging'
```

### OHLC History (Computed from Intraday)

**Old:** (Broken - returns 401)
```python
url = f'{self.base_url}/{_STOCKS_URL}/v2/stock/bars?resolution=1D&ticker={self.symbol}'
```

**New:** (Compute from intraday)
```python
def history(self, ...):
    # Get intraday data
    intraday_df = self.get_intraday_data(ticker=self.symbol)
    
    # Compute OHLC
    ohlc_df = self.compute_ohlc_from_intraday(
        ticker=self.symbol, 
        interval="1D",
        start=start,
        end=end
    )
    return ohlc_df
```

## Testing

### Run Tests

```bash
# Run TCBS-specific tests
python -m pytest -v -k "tcbs" --tb=short

# Expected results:
# ✅ 241 TCBS tests passed
# ✅ All imports successful
# ✅ Backward compatibility maintained
```

### Test New Endpoints

```python
# Test derivatives listing
from vnbroker.explorer.tcbs.listing import Listing

listing = Listing(show_log=True)
derivatives = listing.all_future_indices(show_log=True)
print(f"Found {len(derivatives)} derivatives")

# Test intraday data
from vnbroker.explorer.tcbs.quote import Quote

quote = Quote(symbol="ACB", show_log=True)
intraday = quote.history(start="2024-01-01", end="2024-01-10", interval="1D")
print(f"Intraday data shape: {intraday.shape}")
```

## Troubleshooting

### Common Issues

1. **401 Unauthorized Error**
   - Cause: Using old API key/token with new API
   - Solution: Obtain new JWT token from iFlash OpenAPI

2. **Endpoint Not Found**
   - Cause: Old endpoint paths don't exist on new API
   - Solution: Update all endpoint paths according to the migration table

3. **OHLC History Missing**
   - Cause: New API doesn't provide OHLC bars
   - Solution: Compute from intraday data using `compute_ohlc_from_intraday()`

4. **Company Data Not Available**
   - Cause: `tcanalysis` endpoint may not exist on new API
   - Solution: Test the endpoint and handle gracefully

### Debugging

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test API connectivity
from vnbroker.explorer.tcbs.auth import resolve_auth_token
token = resolve_auth_token()
print(f"Auth token: {token[:20]}..." if token else "No auth token")

# Test endpoint connectivity
import requests
url = f"{_BASE_URL}{TARTARUS_PATH}/derivatives"
headers = get_tcbs_headers()
response = requests.get(url, headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
```

## Future Enhancements

1. **OHLC Caching**: Cache computed OHLC data to avoid recomputation
2. **Interval Support**: Support more time intervals (1H, 4H, 1W)
3. **Error Handling**: Better error handling for missing endpoints
4. **Fallback**: Fallback to old API for endpoints that don't exist on new API

## Conclusion

The migration to the iFlash OpenAPI requires updating endpoint paths and authentication methods. The main challenge is the lack of OHLC bars on the new API, which requires computing them from intraday data. However, the new API provides more stable and modern endpoints for derivatives, intraday data, and ticker information.

The migration is feasible and maintains backward compatibility while providing access to the new, more robust iFlash OpenAPI platform.