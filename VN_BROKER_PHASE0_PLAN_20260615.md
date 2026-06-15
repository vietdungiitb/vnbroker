# Kế Hoạch Triển Khai - Phase 0: Sửa Lỗi và Đồng Bộ Hóa Screener

**Ngày:** 15/06/2026  
**Dự án:** VNBroker (c:\Mujoco Projects\vnbrokder)  
**Trạng thái:** **ĐÃ PHÊ DUYỆT - SẴN SÀNG IMPLEMENT**  
**Quyết định:**
1. Screener: **Option B - Xóa hoàn toàn** `vnbroker/api/screener.py`
2. TCBS payload: **Theo spec TCBS website** (camelCase: `pinCode`, `requestId`)
3. Backward compatibility: **KHÔNG** - Breaking change chấp nhận

---

## 1. Tóm Tắt Vấn Đề P0 (83 Failures)

| Bug | File | Failures | Root Cause |
|-----|------|----------|------------|
| 1. TCBS Equity Write API Signature | `vnbroker/broker/tcbs/equity.py` | 81 | Thiếu `pin_code`, `request_id` params |
| 2. Mock Token Expiry | `tests/unit/broker/tcbs/test_session_auth.py` | 2 | Hardcoded `2026-05-20` đã quá hạn |
| 3. DNSE Source Override | `vnbroker/common/client.py` line 257 | 1+ | Gateway logic ghi đè `source="DNSE"` |
| 4. Screener Inconsistency | `CHANGELOG.md` + `vnbroker/api/screener.py` | 0 (consistency) | CHANGELOG ghi xóa nhưng file còn |

---

## 2. Chi Tiết Thay Đổi Mã Nguồn (Approved Changes)

### 2.1 Sửa TCBS Equity Write API (`vnbroker/broker/tcbs/equity.py`)

**Breaking change:** Thay đổi signature 6 methods (3 public + 3 private `_gated_*`). Không có default values.

#### A. `place_order` (Public) - Line ~270
```python
def place_order(
    self,
    account_no: str,
    symbol: str,
    side: str,
    order_type: str,
    quantity: int,
    price: float,
    pin_code: str,
    request_id: str,
    *,
    dry_run: bool = True,
) -> dict:
```

#### B. `_gated_place_order` (Private) - Line ~310
```python
def _gated_place_order(
    self,
    account_no: str,
    symbol: str,
    side: str,
    order_type: str,
    quantity: int,
    price: float,
    pin_code: str,
    request_id: str,
    *,
    dry_run: bool = True,
) -> dict:
    # Payload cho TCBS API (camelCase theo spec):
    payload = {
        "symbol": symbol,
        "side": side.upper(),
        "orderType": order_type.upper(),
        "quantity": quantity,
        "price": price,
        "pinCode": pin_code,
        "requestId": request_id,
    }
```

#### C. `modify_order` (Public) - Line ~330
```python
def modify_order(
    self,
    account_no: str,
    order_id: str,
    quantity: int,
    price: float,
    request_id: str,
    *,
    dry_run: bool = True,
) -> dict:
```

#### D. `_gated_modify_order` (Private) - Line ~340
```python
def _gated_modify_order(
    self,
    account_no: str,
    order_id: str,
    quantity: int,
    price: float,
    request_id: str,
    *,
    dry_run: bool = True,
) -> dict:
    payload = {
        "orderId": order_id,
        "quantity": quantity,
        "price": price,
        "requestId": request_id,
    }
```

#### E. `cancel_order` (Public) - Line ~350
```python
def cancel_order(
    self,
    account_no: str,
    order_id: str,
    request_id: str,
    *,
    dry_run: bool = True,
) -> dict:
```

#### F. `_gated_cancel_order` (Private) - Line ~360
```python
def _gated_cancel_order(
    self,
    account_no: str,
    order_id: str,
    request_id: str,
    *,
    dry_run: bool = True,
) -> dict:
    payload = {
        "orderIds": [order_id],
        "requestId": request_id,
    }
```

#### G. Update `_validate_order_input` - Line ~480
```python
def _validate_order_input(
    symbol: str,
    side: str,
    order_type: str,
    quantity: int,
    price: float,
    request_id: str,
) -> None:
    # ... existing validations ...
    if not request_id or not request_id.strip():
        raise BrokerValidationError(
            message="request_id là bắt buộc cho write methods (idempotency key).",
            code="MISSING_REQUEST_ID",
        )
```

---

### 2.2 Động Hóa Mock Token (`tests/unit/broker/tcbs/test_session_auth.py`)

**Line 158:** Thay thế hardcoded expiredTime.

```python
# Thêm import ở đầu file:
from datetime import datetime, timezone, timedelta

# Line 158:
future_date = (datetime.now(tz=timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
mock_resp.json.return_value = {
    "token": "jwt.real-token",
    "expiredTime": future_date,
}
```

---

### 2.3 Vá Lỗi DNSE Source Override (`vnbroker/common/client.py`)

**Line 257:** Sửa điều kiện Gateway.

```python
# CURRENT:
if self._use_gateway or effective_source.upper() == "GATEWAY":

# PROPOSED:
if (self._use_gateway and (source is None or source.upper() == "GATEWAY")) or effective_source.upper() == "GATEWAY":
```

---

### 2.4 Xóa Hoàn Toàn Screener (Option B)

| File | Action |
|------|--------|
| `vnbroker/api/screener.py` | `git rm` - Xóa file |
| `vnbroker/__init__.py` | Xóa `_ScreenerProxy` class và export (nếu có) |
| `CHANGELOG.md` | Cập nhật: "Removed `api/screener.py` entirely as it was exclusively dependent on TCBS" (giữ nguyên dòng này, xóa dòng "Removed TCBS data source...") |

---

## 3. Danh Sách File Cần Sửa (Implementation Order)

| # | File | Action | Priority |
|---|------|--------|----------|
| 1 | `vnbroker/broker/tcbs/equity.py` | Update 6 method signatures + validation + payload | P0 Critical |
| 2 | `tests/unit/broker/tcbs/test_session_auth.py` | Dynamic mock token expiry | P0 Critical |
| 3 | `vnbroker/common/client.py` | Fix DNSE source override logic | P0 Critical |
| 4 | `vnbroker/api/screener.py` | **DELETE** file | P0 Critical |
| 5 | `vnbroker/__init__.py` | Remove `_ScreenerProxy` export | P0 Critical |
| 6 | `CHANGELOG.md` | Verify screener removal note consistent | P0 Critical |

---

## 4. Kế Hoạch Xác Minh (Verification Plan)

```bash
# 1. Chạy test TCBS equity write flow (81 tests)
.venv\Scripts\python -m pytest tests/unit/broker/tcbs/test_order_write_flow.py -v

# 2. Chạy test session auth (2 tests)
.venv\Scripts\python -m pytest tests/unit/broker/tcbs/test_session_auth.py -v

# 3. Chạy test DNSE source override (nếu có)
.venv\Scripts\python -m pytest tests/ -k "dnse" -v

# 4. Chạy toàn bộ test suite
.venv\Scripts\python -m pytest -v

# Expected: 0 failed / 583 passed (Green build)
```

---

## 5. Implementation Notes

- **Không backward compatibility** - Test sẽ pass với signature mới
- **TCBS payload camelCase** - `pinCode`, `requestId`, `orderId`, `orderIds` theo spec
- **Price type** - `float` thay vì `int` (test truyền 80000 là int nhưng Python auto convert)
- **Request ID validation** - Bắt buộc không rỗng cho tất cả write methods

---

*Plan approved: 2026-06-15 | Ready for implementation*