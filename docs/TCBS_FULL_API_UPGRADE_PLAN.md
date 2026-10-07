# TCBS iFlash OpenAPI — Kế hoạch nâng cấp toàn diện

<!-- TRẠNG THÁI ĐỐI CHIẾU — WP-PLAN-CLEANUP-01, 2026-10-07 -->

> ## ⚠️ Trạng thái đối chiếu (2026-10-07) — KHÔNG đọc các ô `[ ]` bên dưới như việc còn dở
>
> File ghi *"✅ Approved — Đang triển khai"* (2026-06-21). Nay **đã triển khai xong**.
>
> **Đã xác minh bằng lệnh — XONG:**
> Broker registry · auth flow OTP → JWT (`vnbroker/broker/tcbs/auth.py`) ·
> account/money/equity services · `dry_run=True` + idempotency key + write gate ·
> phái sinh (`derivatives.py`) · WebSocket (`vnbroker/explorer/tcbs/websocket.py`)
> · `Vnbroker.broker(provider='TCBS')` gọi được · suite TCBS **318 passed**.
>
> **6 mục cuối file là bước hành chính đã qua:** review/approve plan · confirm API
> key + OTP · setup SIT (`openapisit.tcbs.com.vn`) · cài `websockets>=12.0`
> (nay `pyproject.toml` đã pin `websockets>=12.0`) · tạo feature branch · cập nhật
> `docs/TCBS_SPRINT_TASK_BOARD.md` (file tồn tại).


**Version:** 2.0  
**Ngày tạo:** 2026-06-21  
**Trạng thái:** ✅ Approved — Đang triển khai  
**Nguồn:** TCBS Developer Portal (https://developers.tcbs.com.vn) + OpenAPI Spec v1.0.0

---

## 1. Tổng quan TCBS iFlash OpenAPI

### 1.1 Thông tin chung

| Thuộc tính | Giá trị |
|---|---|
| **Tên** | iFlash Open API |
| **Version** | 1.0.0 |
| **Base URL (Production)** | `https://openapi.tcbs.com.vn` |
| **Base URL (SIT)** | `https://openapisit.tcbs.com.vn` |
| **Auth** | JWT Token (Bearer) |
| **Contact** | cskh@tcbs.com.vn |
| **Portal** | https://developers.tcbs.com.vn |

### 1.2 Authentication Flow

```
1. Đăng ký API Key tại TCBS Developer Portal
2. Nhận OTP từ TCBS mobile app/email
3. POST /gaia/v1/oauth2/openapi/token → JWT Token
4. Sử dụng JWT cho mọi request: Authorization: Bearer <token>
5. Token hết hạn sau ~8 giờ → cần refresh
```

### 1.3 WebSocket Endpoints

| Endpoint | Mục đích | Protocol |
|---|---|---|
| `wss://openapi.tcbs.com.vn/ws/ouranos/v1/stream` | Real-time market data (OHLC, OrderBook, Ticker, Trade) | WSS, text frames, heartbeat 2s |
| `wss://openapi.tcbs.com.vn/ws/aither` | Real-time matching info (stock) | WSS |
| `wss://openapi.tcbs.com.vn/ws/nesoi` | Real-time matching info (derivatives) | WSS |

---

## 2. Inventory — 48 Endpoints từ OpenAPI Spec

### 2.1 Nhóm 1: Authentication (1 endpoint)

| # | Method | Path | Summary | Status trong vnbroker |
|---|---|---|---|---|
| 1 | POST | `/gaia/v1/oauth2/openapi/token` | Trao đổi API Key để lấy JWT Token | ✅ Đã implement (`auth.py`) |

### 2.2 Nhóm 2: Account Information (14 endpoints)

| # | Method | Path | Summary | Status |
|---|---|---|---|---|
| 2 | GET | `/eros/v2/get-profile/by-username/{custodyCode}` | 3.1.1. Lấy thông tin tiểu khoản | ❌ Chưa |
| 3 | GET | `/erebos/v1/account/asset` | 3.1.2. Lấy thông tin tài sản | ❌ Chưa |
| 4 | GET | `/erebos/v1/account/available-balance` | 3.1.3. Lấy thông tin số dư khả dụng | ❌ Chưa |
| 5 | GET | `/erebos/v1/portfolio-asset` | 3.1.4. Lấy thông tin danh mục tài sản | ❌ Chưa |
| 6 | GET | `/erebos/v1/portfolio-asset/token` | 3.1.5. Danh mục phái sinh & chứng quyền | ❌ Chưa |
| 7 | GET | `/erebos/v1/portfolio/stock/{accountNo}/statistic` | 3.1.6. Thống kê danh mục | ❌ Chưa |
| 8 | GET | `/erebos/v2/accounts/{accountNo}/asset` | 3.1.7. Thông tin tài sản (v2) | ❌ Chưa |
| 9 | GET | `/erebos/v2/accounts/{accountNo}/available-balance` | 3.1.8. Số dư khả dụng (v2) | ❌ Chưa |
| 10 | GET | `/erebos/v2/accounts/{accountNo}/stock-statistic` | 3.1.9. Thống kê danh mục (v2) | ❌ Chưa |
| 11 | GET | `/erebos/v2/accounts/{accountNo}/orders/history` | 3.1.10. Lịch sử lệnh | ❌ Chưa |
| 12 | GET | `/erebos/v2/accounts/{accountNo}/orders/matching` | 3.1.11. Lịch sử khớp lệnh | ❌ Chưa |
| 13 | GET | `/erebos/v2/accounts/{accountNo}/withdraw` | 3.1.12. Lịch sử rút tiền | ❌ Chưa |
| 14 | GET | `/erebos/v2/accounts/{accountNo}/deposit` | 3.1.13. Lịch sử nộp tiền | ❌ Chưa |
| 15 | GET | `/erebos/v2/accounts/{accountNo}/dividend` | 3.1.14. Lịch sử cổ tức | ❌ Chưa |

### 2.3 Nhóm 3: Stock Trading — Order Management (7 endpoints)

| # | Method | Path | Summary | Status |
|---|---|---|---|---|
| 16 | POST | `/akhlys/v1/accounts/{accountNo}/orders` | 5.1.1. Đặt lệnh thường | ❌ Chưa |
| 17 | PUT | `/akhlys/v1/accounts/{accountNo}/orders/{orderId}` | 5.2.1. Sửa lệnh thường | ❌ Chưa |
| 18 | PUT | `/akhlys/v1/accounts/{accountNo}/cancel-orders` | 5.3.1. Huỷ lệnh thường | ❌ Chưa |
| 19 | GET | `/aion/v1/accounts/{accountNo}/orders` | 5.4.1. Lấy sổ lệnh | ❌ Chưa |
| 20 | GET | `/aion/v1/accounts/{accountNo}/orders/{orderID}` | 5.4.2. Lấy sổ lệnh theo Order ID | ❌ Chưa |
| 21 | GET | `/aion/v1/accounts/{accountNo}/matching-details` | 5.4.3. Lấy thông tin khớp lệnh | ❌ Chưa |
| 22 | GET | `/ws/aither` | 5.4.4. Lấy thông tin khớp lệnh (realtime) | ❌ Chưa (WebSocket) |

### 2.4 Nhóm 4: Stock Trading — Stop Limit Orders (4 endpoints)

| # | Method | Path | Summary | Status |
|---|---|---|---|---|
| 23 | POST | `/erebos/v2/order/stop-limit` | 5.1.2. Đặt lệnh điều kiện | ❌ Chưa |
| 24 | GET | `/erebos/v2/order/stop-limit/orders` | 5.4.5. Lấy sổ lệnh điều kiện | ❌ Chưa |
| 25 | PUT | `/erebos/v2/order/stop-limit/{orderId}/cancel` | 5.3.2. Hủy lệnh điều kiện | ❌ Chưa |
| 26 | PUT | `/erebos/v2/order/stop-limit/{orderId}` | 5.2.2. Sửa lệnh điều kiện | ❌ Chưa |

### 2.5 Nhóm 5: Purchasing Power & Margin (7 endpoints)

| # | Method | Path | Summary | Status |
|---|---|---|---|---|
| 27 | GET | `/aion/v1/accounts/{accountNo}/ppse` | 5.5.1. Lấy sức mua | ❌ Chưa |
| 28 | GET | `/aion/v1/accounts/{accountNo}/ppse/{symbol}` | 5.5.2. Lấy sức mua theo mã | ❌ Chưa |
| 29 | GET | `/aion/v1/accounts/{accountNo}/ppse/{symbol}/{price}` | 5.5.3. Lấy sức mua theo mã, giá | ❌ Chưa |
| 30 | GET | `/aion/v1/customers/{custodyId}/accounts` | 5.5.4. Hạn mức margin | ❌ Chưa |
| 31 | GET | `/hydros/v1/account/{accountNo}/risk` | 5.5.5. Tổng nợ gốc, lãi, Rtt, tỷ lệ ký quỹ | ❌ Chưa |
| 32 | GET | `/campaign-management/v1/margin/subscription/{accountNo}/addons/detail` | 5.5.6. Gói vay bổ trợ | ❌ Chưa |
| 33 | GET | `/khaos/v1/loan/{accountNo}` | 5.5.7. Danh sách khoản vay | ❌ Chưa |

### 2.6 Nhóm 6: Asset & Cash Management (4 endpoints)

| # | Method | Path | Summary | Status |
|---|---|---|---|---|
| 34 | GET | `/aion/v1/accounts/{accountNo}/se` | 5.6.1. Tra cứu tài sản cổ phiếu theo tiểu khoản | ❌ Chưa |
| 35 | GET | `/aion/v1/accounts/{accountNo}/cashInvestments` | 5.6.2. Lấy thông tin số dư tiền | ❌ Chưa |
| 36 | GET | `/erebos/v2/digital/trans-hist-cashStatements` | 5.6.3. Thông tin sao kê tiền | ❌ Chưa |
| 37 | GET | `/erebos/v2/digital/margin-info` | 5.6.4. Tra cứu nợ | ❌ Chưa |

### 2.7 Nhóm 7: Derivatives Trading (8 endpoints)

| # | Method | Path | Summary | Status |
|---|---|---|---|---|
| 38 | GET | `/khronos/v1/account/status` | 6.1.1. Tổng quan tiền, ký quỹ phái sinh | ❌ Chưa |
| 39 | GET | `/khronos/v1/account/portfolio/position/close` | 6.2.1. Tài sản, vị thế đóng | ❌ Chưa |
| 40 | GET | `/khronos/v1/account/portfolio/status` | 6.2.2. Tài sản, vị thế mở | ❌ Chưa |
| 41 | GET | `/khronos/v1/order/in-day` | 6.3.1. Tra cứu sổ lệnh thường | ❌ Chưa |
| 42 | GET | `/khronos/v1/order/condition/detail` | 6.3.2. Tra cứu sổ lệnh điều kiện | ❌ Chưa |
| 43 | GET | `/ws/nesoi` | 6.3.3. Lấy thông tin khớp lệnh (realtime) | ❌ Chưa (WebSocket) |
| 44 | POST | `/khronos/v1/order/place` | 6.4.1. Đặt lệnh thường | ❌ Chưa |
| 45 | POST | `/khronos/v1/order/condition/place` | 6.4.2. Đặt lệnh điều kiện | ❌ Chưa |
| 46 | POST | `/khronos/v1/order/change` | 6.5.1. Sửa lệnh thường | ❌ Chưa |
| 47 | POST | `/khronos/v2/order/condition/change` | 6.5.2. Sửa lệnh điều kiện | ❌ Chưa |
| 48 | POST | `/khronos/v1/order/cancel` | 6.5.3. Hủy lệnh | ❌ Chưa |

### 2.8 Nhóm 8: Market Data (Explorer/Public) — Đã implement

| Endpoint | Method | Summary | Status |
|---|---|---|---|
| `/tartarus/v1/derivatives` | GET | Danh sách mã phái sinh | ✅ Đã implement |
| `/nyx/v1/intraday/{ticker}/his/paging` | GET | Intraday tick data | ✅ Đã implement |
| `/tartarus/v1/tickerCommons` | GET | Current price info | ✅ Đã implement |

---

## 3. Gap Analysis — Hiện trạng vs Mục tiêu

### 3.1 Coverage Summary

| Nhóm | Total Endpoints | Đã implement | Chưa | Coverage |
|---|---|---|---|---|
| Authentication | 1 | 1 | 0 | 100% |
| Account Information | 14 | 0 | 14 | 0% |
| Stock Trading — Orders | 7 | 0 | 7 | 0% |
| Stock Trading — Stop Limit | 4 | 0 | 4 | 0% |
| Purchasing Power & Margin | 7 | 0 | 7 | 0% |
| Asset & Cash Management | 4 | 0 | 4 | 0% |
| Derivatives Trading | 8 | 0 | 8 | 0% |
| Market Data (Explorer) | 3 | 3 | 0 | 100% |
| WebSocket | 3 | 0 | 3 | 0% |
| **TOTAL** | **51** | **4** | **47** | **8%** |

### 3.2 Priority Classification

| Priority | Nhóm | Lý do |
|---|---|---|
| **P0 — Critical** | Account Information (core), Stock Trading (read) | Cần thiết cho portfolio tracking |
| **P1 — High** | Purchasing Power & Margin, Asset & Cash | Cần thiết cho trading decisions |
| **P2 — Medium** | Derivatives Trading, Stock Trading (write) | Advanced features |
| **P3 — Low** | Stop Limit Orders, WebSocket | Nice-to-have, complex |

---

## 4. Implementation Plan — 6 Phases

### Phase 1: Foundation & Account Services (P0)

**Mục tiêu:** Xây dựng nền tảng broker lane + account information services

**Duration:** 2-3 weeks

| Task ID | Task | Files | Endpoints covered |
|---|---|---|---|
| P1.1 | Tạo broker package skeleton | `vnbroker/broker/**` | — |
| P1.2 | Credential model & config partition | `vnbroker/broker/security/credentials.py` | — |
| P1.3 | Redaction, audit, secure HTTP substrate | `vnbroker/broker/security/redaction.py`, `audit.py` | — |
| P1.4 | Broker session & auth service | `vnbroker/broker/session.py`, `vnbroker/broker/tcbs/auth.py` | 1 (auth) |
| P1.5 | Account profile service | `vnbroker/broker/tcbs/account.py` | 2, 3, 4, 5, 6, 7, 8, 9, 10 |
| P1.6 | Account history service | `vnbroker/broker/tcbs/account.py` | 11, 12, 13, 14, 15 |

**DoD:**
- [ ] Broker registry hoạt động
- [ ] Auth flow hoàn chỉnh (OTP → JWT)
- [ ] Account profile/data retrieval hoạt động
- [ ] Tests pass cho tất cả endpoints
- [ ] No secret leakage trong logs

---

### Phase 2: Trading — Order Management (P0 + P1)

**Mục tiêu:** Stock order query + purchasing power

**Duration:** 2-3 weeks

| Task ID | Task | Files | Endpoints covered |
|---|---|---|---|
| P2.1 | Order query service | `vnbroker/broker/tcbs/equity.py` | 19, 20, 21 |
| P2.2 | Purchasing power service | `vnbroker/broker/tcbs/money.py` | 27, 28, 29, 30 |
| P2.3 | Margin & risk service | `vnbroker/broker/tcbs/money.py` | 31, 32, 33 |
| P2.4 | Asset & cash service | `vnbroker/broker/tcbs/money.py` | 34, 35, 36, 37 |

**DoD:**
- [ ] Order query hoạt động (read-only)
- [ ] Purchasing power/margin data retrieval
- [ ] Asset/cash balance retrieval
- [ ] Tests pass
- [ ] No write side-effects

---

### Phase 3: Trading — Write Operations (P2)

**Mục tiêu:** Place/update/cancel orders (dry_run first)

**Duration:** 2-3 weeks

| Task ID | Task | Files | Endpoints covered |
|---|---|---|---|
| P3.1 | Place order service | `vnbroker/broker/tcbs/equity.py` | 16 |
| P3.2 | Update order service | `vnbroker/broker/tcbs/equity.py` | 17 |
| P3.3 | Cancel order service | `vnbroker/broker/tcbs/equity.py` | 18 |
| P3.4 | Stop-limit order service | `vnbroker/broker/tcbs/equity.py` | 23, 24, 25, 26 |
| P3.5 | Write guard & idempotency | `vnbroker/broker/security/guards.py`, `idempotency.py` | — |

**DoD:**
- [ ] All write methods support `dry_run=True`
- [ ] Idempotency keys implemented
- [ ] Write gate prevents accidental execution
- [ ] Audit logging for all write operations
- [ ] Tests with mocked responses

---

### Phase 4: Derivatives Trading (P2)

**Mục tiêu:** Derivatives position + order management

**Duration:** 2 weeks

| Task ID | Task | Files | Endpoints covered |
|---|---|---|---|
| P4.1 | Derivatives overview service | `vnbroker/broker/tcbs/derivatives.py` | 38, 39, 40 |
| P4.2 | Derivatives order query | `vnbroker/broker/tcbs/derivatives.py` | 41, 42 |
| P4.3 | Derivatives place order | `vnbroker/broker/tcbs/derivatives.py` | 44, 45 |
| P4.4 | Derivatives update/cancel | `vnbroker/broker/tcbs/derivatives.py` | 46, 47, 48 |

**DoD:**
- [ ] Derivatives position tracking
- [ ] Order query/place/update/cancel
- [ ] Dry-run support
- [ ] Tests pass

---

### Phase 5: WebSocket Integration (P3)

**Mục tiêu:** Real-time streaming for market data + order matching

**Duration:** 3-4 weeks

| Task ID | Task | Files | Endpoints covered |
|---|---|---|---|
| P5.1 | WebSocket core client | `vnbroker/explorer/tcbs/websocket.py` | 49 (ouranos) |
| P5.2 | WebSocket data models | `vnbroker/explorer/tcbs/models.py` | — |
| P5.3 | Stream service | `vnbroker/explorer/tcbs/stream.py` | — |
| P5.4 | Aither stream integration | `vnbroker/explorer/tcbs/websocket.py` | 22 (aither) |
| P5.5 | Nesoi stream integration | `vnbroker/explorer/tcbs/websocket.py` | 43 (nesoi) |
| P5.6 | Quote module integration | `vnbroker/explorer/tcbs/quote.py` | — |

**DoD:**
- [ ] WebSocket connection management
- [ ] Heartbeat (2s ping)
- [ ] Reconnection logic
- [ ] Subscribe/unsubscribe
- | Message parsing (JSON)
- [ ] Async generators for stream data
- [ ] Tests with mocked WebSocket

---

### Phase 6: Portfolio Engine & Integration (P0)

**Mục tiêu:** Portfolio tracking + public API integration

**Duration:** 2 weeks

| Task ID | Task | Files | Endpoints covered |
|---|---|---|---|
| P6.1 | Portfolio engine | `vnbroker/broker/tcbs/portfolio.py` | — |
| P6.2 | Holdings ledger | `vnbroker/broker/tcbs/portfolio.py` | — |
| P6.3 | PnL calculation | `vnbroker/broker/tcbs/portfolio.py` | — |
| P6.4 | Public API integration | `vnbroker/api/broker.py`, `vnbroker/common/client.py` | — |
| P6.5 | Documentation | `docs/TCBS_*.md` | — |

**DoD:**
- [ ] Holdings, cost basis, PnL
- [ ] Reconciliation
- [ ] `Vnbroker.broker(provider='TCBS')` hoạt động
- [ ] Documentation complete
- [ ] All tests pass

---

## 5. Dependency Graph

```
Phase 1 (Foundation)
    ↓
Phase 2 (Trading Read)
    ↓
Phase 3 (Trading Write)
    ↓
Phase 4 (Derivatives)
    ↓
Phase 5 (WebSocket)
    ↓
Phase 6 (Portfolio & Integration)
```

**Parallel tracks:**
- Phase 5 (WebSocket) có thể bắt đầu sau Phase 2 (không cần chờ Phase 3-4)
- Phase 6 (Portfolio) có thể bắt đầu sau Phase 2

---

## 6. File Structure — Final Target

```
vnbroker/
├── broker/
│   ├── __init__.py
│   ├── base.py
│   ├── registry.py
│   ├── session.py
│   ├── security/
│   │   ├── __init__.py
│   │   ├── credentials.py
│   │   ├── redaction.py
│   │   ├── audit.py
│   │   ├── idempotency.py
│   │   └── guards.py
│   └── tcbs/
│       ├── __init__.py
│       ├── client.py
│       ├── auth.py
│       ├── account.py          # Phase 1
│       ├── money.py            # Phase 2
│       ├── equity.py           # Phase 2-3
│       ├── derivatives.py      # Phase 4
│       ├── portfolio.py        # Phase 6
│       └── exceptions.py
│
├── explorer/
│   └── tcbs/
│       ├── __init__.py
│       ├── const.py
│       ├── auth.py             # Legacy (keep for compat)
│       ├── listing.py
│       ├── quote.py            # Modify Phase 5
│       ├── websocket.py        # Phase 5
│       ├── models.py           # Phase 5
│       └── stream.py           # Phase 5
│
├── api/
│   └── broker.py               # Phase 6
│
└── common/
    └── client.py               # Modify Phase 6

tests/
└── unit/
    └── broker/
        └── tcbs/
            ├── __init__.py
            ├── fixtures.py
            ├── test_credentials.py
            ├── test_security.py
            ├── test_session_auth.py
            ├── test_account.py
            ├── test_money.py
            ├── test_equity.py
            ├── test_derivatives.py
            ├── test_portfolio.py
            └── test_order_write_flow.py
```

---

## 7. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| TCBS API contract drift | Medium | High | Mocked contract tests + live smoke tests |
| Secret leakage in logs | High | Critical | Complete Phase 1.3 before any broker service |
| Token expiry during operations | Medium | High | Auto-refresh logic + session state machine |
| Duplicate order submission | Medium | Critical | Dry-run default + idempotency keys + status check |
| WebSocket connection drops | High | Medium | Reconnection logic with exponential backoff |
| Rate limiting | Medium | Medium | Request queuing + retry with backoff |

---

## 8. Timeline Estimate

| Phase | Duration | Start | End |
|---|---|---|---|
| Phase 1: Foundation | 2-3 weeks | Week 1 | Week 3 |
| Phase 2: Trading Read | 2-3 weeks | Week 4 | Week 6 |
| Phase 3: Trading Write | 2-3 weeks | Week 7 | Week 9 |
| Phase 4: Derivatives | 2 weeks | Week 10 | Week 11 |
| Phase 5: WebSocket | 3-4 weeks | Week 7 | Week 10 (parallel) |
| Phase 6: Portfolio | 2 weeks | Week 12 | Week 13 |
| **Total** | **~13 weeks** | | |

---

## 9. Reference Documents

### 9.1 Official TCBS Resources

| Resource | URL |
|---|---|
| TCBS Developer Portal | https://developers.tcbs.com.vn |
| TCBS iFlash OpenAPI Docs | https://developers.tcbs.com.vn |
| WebSocket Bảng Giá (PDF) | https://developers.tcbs.com.vn/file/Websocket_bang_gia_1.0.0.pdf |
| WebSocket Lịch Sử Giá & Cung Cầu (PDF) | https://developers.tcbs.com.vn/file/Websocket_lich-su-gia_cung-cau_1.0.0.pdf |
| TCBS Customer Support | cskh@tcbs.com.vn |

### 9.2 Local Reference Files

| File | Path |
|---|---|
| OpenAPI Spec | `docs/references/tcbs_iflash_openapi.json` |
| All Endpoints List | `docs/tcbs_all_endpoints.txt` |
| JWT Token | `docs/tcbs_jwt.txt` |
| Auth Token Reference | `docs/references/tcbs_auth_token.txt` |
| DNSE Credentials | `docs/references/dnse_credentials.txt` |
| WebSocket Integration Reference | `docs/TCBS_WEBSOCKET_INTEGRATION_REFERENCE.md` |
| API Contract | `docs/TCBS_API_CONTRACT.md` |
| Integration Master Plan | `docs/TCBS_INTEGRATION_MASTER_PLAN.md` |
| Module Structure | `docs/TCBS_MODULE_STRUCTURE.md` |

### 9.3 External References

| Resource | URL |
|---|---|
| vnbrokers-bruno (Bruno collections) | https://github.com/vnbrokers/vnbrokers-bruno |
| open-api-tcbs (PyPI) | https://www.piwheels.org/project/open-api-tcbs/ |
| DNSE API Platform | https://developers.dnse.com.vn/docs/guide/intro/api_platform |
| SSI FastConnect Data | https://guide.ssi.com.vn/ssi-products/tieng-viet/fastconnect-data |

---

## 10. Checklist — Before Starting

- [ ] Review và approve plan này
- [ ] Confirm API key + OTP access cho TCBS
- [ ] Setup test environment (SIT: `https://openapisit.tcbs.com.vn`)
- [ ] Install `websockets>=12.0` dependency
- [ ] Create feature branch (`feature/tcbs-full-api-support`)
- [ ] Update `docs/TCBS_SPRINT_TASK_BOARD.md` với plan mới

---

## 11. Changelog

| Date | Version | Changes |
|---|---|---|
| 2026-06-21 | 2.0 | Comprehensive upgrade plan based on full OpenAPI spec review |
| 2026-06-21 | 1.0 | Initial WebSocket integration reference |

---

*Document ends. For questions or updates, contact the vnbroker team.*
