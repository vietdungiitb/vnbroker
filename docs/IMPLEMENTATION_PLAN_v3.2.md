# vnbroker v3.2 - Implementation Plan

This plan implements the technical improvements scheduled for version 3.2.0, addressing the findings from the v3.1.1 audit report.

## Proposed Changes

---

### 1. Version Update
- **Target File:** `pyproject.toml`
  - Update version to `"3.2.0"`.
- **Target File:** `vnbroker/config.py`
  - Update notices, support matrix, and compatibility checklist to target version `"3.2.0"`.
- **Target File:** `CHANGELOG.md`
  - Ensure version `"3.2.0"` is documented.

---

### 2. Implement DNSE Brokerage Client
- **Target File:** `[NEW] vnbroker/brokerage/dnse/__init__.py`
  - Export `DNSEBrokerageClient`.
- **Target File:** `[NEW] vnbroker/brokerage/dnse/client.py`
  - Extend `BrokerageBase`.
  - Implement dynamic HMAC signature generation using `build_signature_header` from the DNSE connector.
  - Implement JWT trading token flow/OTP handling.
  - Implement sync and async methods: `get_balance`, `get_positions`, `get_orders`, `get_margin_info`, `place_order`, `cancel_order`, `modify_order`, `place_order_async`, `cancel_order_async`, `modify_order_async`.
  - Implement `authenticate(otp_type, passcode)` to fetch and store the trading token.

---

### 3. Add Async Brokerage Write Operations for TCBS & Base
- **Target File:** `vnbroker/brokerage/base.py`
  - Add abstract async methods: `place_order_async`, `cancel_order_async`, `modify_order_async`.
- **Target File:** `vnbroker/brokerage/tcbs/client.py`
  - Implement `place_order_async`, `cancel_order_async`, `modify_order_async` using `_async_request`.

---

### 4. Implement Circuit Breaker Pattern in Source Router
- **Target File:** `vnbroker/core/source_router.py`
  - Introduce states: `CLOSED`, `OPEN`, `HALF_OPEN`.
  - Implement transition logic in `record_failure`, `record_success`, and `build_source_order`.
  - Deprioritize or fast-reject candidates in `OPEN` state.
  - Allow limited test calls in `HALF_OPEN` state.
  - Update `get_source_health_snapshot` to include states and active call counts.

---

### 5. Optimize Provider Registry Lazy Loading
- **Target File:** `vnbroker/core/registry.py`
  - Implement `_auto_discover_provider` to dynamically import `vnbroker.explorer.<source>` or `vnbroker.connector.<source>` on-demand.
  - Call it inside `get()` if the provider is not already registered.
- **Target File:** `vnbroker/__init__.py`
  - Remove the eager imports of all explorer/connector modules at package load time. Keep the loader function for compatibility but do not call it dynamically.

---

### 6. HTTP/2 and Connection Pooling Optimization
- **Target File:** `vnbroker/connector/dnse/core/http_client.py`
  - Replace `requests.request` with a pooled `httpx.Client(http2=True)`.
- **Target File:** `vnbroker/brokerage/base.py`
  - Add `http2=True` to the default `httpx.Client` configuration in `BrokerageBase`.
- **Target File:** `vnbroker/core/utils/async_client.py`
  - Implement Request Deduplication (In-Flight Request Coalescing) in `async_send_request` by caching in-flight futures under a unique key.

---

### 7. Standardize DNSE Company/Finance
- **Target File:** `vnbroker/explorer/dnse/company.py`
  - Raise `NotImplementedError` for all public company methods.
- **Target File:** `vnbroker/explorer/dnse/finance.py`
  - Raise `NotImplementedError` for all public finance methods.
- **Target File:** `[DELETE] vnbroker/explorer/dnse/financial.py`
  - Remove duplicate file.

---

### 8. Archive Outdated Documentation
- Move outdated planning, delivery, and RFC documents under `docs/` to `docs/archive/`.
- Retain only current reference plans and user guides.

---

### 9. Add Unit Tests for Technical Indicators
- **Target File:** `tests/unit/analytics/test_indicators.py`
  - Write comprehensive tests for `sma`, `ema`, `rsi`, `macd`, `bollinger_bands`, `atr`, `stochastic`, `williams_r`, `cci`, and `compute_all_indicators`.

---

### 10. Add Type Stubs (.pyi)
- Add `.pyi` type stubs for the main public entrypoints:
  - `vnbroker/common/client.pyi`
  - `vnbroker/common/data.pyi`
  - `vnbroker/broker/tcbs/client.pyi`

---

## Verification Plan

### Automated Tests
- Run full unit test suite:
  ```powershell
  .venv\Scripts\python -m pytest tests/unit -v
  ```
- Run new tests specifically:
  ```powershell
  .venv\Scripts\python -m pytest tests/unit/analytics/test_indicators.py -v
  ```
- Ensure type checking passes:
  ```powershell
  .venv\Scripts\python -m mypy vnbroker --strict
  ```
- Ensure linting passes:
  ```powershell
  .venv\Scripts\python -m ruff check vnbroker
  ```
