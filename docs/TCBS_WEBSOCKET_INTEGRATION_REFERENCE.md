# TCBS WebSocket Integration — Tài liệu tham chiếu

**Version:** 1.0  
**Ngày tạo:** 2026-06-21  
**Trạng thái:** Draft — chờ triển khai  
**Tác giả:** vnbroker team

---

## 1. Tổng quan

Tài liệu này tổng hợp toàn bộ thông tin kỹ thuật về TCBS iFlash OpenAPI và WebSocket integration, bao gồm:
- API endpoints đã xác minh (REST + WebSocket)
- Auth flow (JWT token exchange)
- WebSocket streaming protocol
- OHLC computation từ intraday data
- Reference documents (PDFs, OpenAPI spec, developer portal)
- Implementation plan cho WebSocket client

---

## 2. TCBS iFlash OpenAPI — Thông tin chung

### 2.1 Base URL

| Môi trường | URL |
|---|---|
| Production | `https://openapi.tcbs.com.vn` |
| SIT (Testing) | `https://openapisit.tcbs.com.vn` |

### 2.2 WebSocket Endpoint

| Protocol | URL | Ghi chú |
|---|---|---|
| WSS | `wss://openapi.tcbs.com.vn/ws/ouranos/v1/stream` | Real-time streaming, text frames (JSON) |
| WSS | `wss://openapi.tcbs.com.vn/ws/aither` | Real-time matching info (stock) |
| WSS | `wss://openapi.tcbs.com.vn/ws/nesoi` | Real-time matching info (derivatives) |

**Heartbeat:** Client phải gửi ping mỗi 2 giây để duy trì kết nối.

### 2.3 Authentication

TCBS iFlash OpenAPI yêu cầu JWT token cho hầu hết endpoints.

**Flow:**
1. Đăng ký API Key tại TCBS Developer Portal
2. Nhận OTP từ TCBS mobile app/email
3. Exchange API Key + OTP → JWT Token

**Endpoint:**
```
POST https://openapi.tcbs.com.vn/gaia/v1/oauth2/openapi/token
Content-Type: application/json

{
  "apiKey": "<your-api-key>",
  "otp": "<6-digit-otp>"
}
```

**Response:**
```json
{
  "token": "<JWT string>",
  "expiredTime": "<ISO8601 or epoch millis>"
}
```

**Token validity:** ~**24 giờ** (đo được 2026-10-10 từ JWT thật: `exp - iat = 86400s`) từ thời điểm cấp.

**Usage:**
```
Authorization: Bearer <JWT>
```

### 2.4 Scopes (từ JWT token)

JWT token chứa các scopes:
- `bond` — Trái phiếu
- `fund` — Quỹ
- `stock` — Cổ phiếu
- `socket:all` — WebSocket access (tất cả streams)

---

## 3. REST Endpoints — Đã xác minh

### 3.1 Working Endpoints ✅

| Endpoint | Method | Mô tả | Path Constant |
|---|---|---|---|
| `/gaia/v1/oauth2/openapi/token` | POST | Exchange API Key + OTP → JWT | — |
| `/tartarus/v1/derivatives` | GET | Danh sách mã phái sinh (8 KRX symbols) | `TARTARUS_PATH` |
| `/nyx/v1/intraday/{ticker}/his/paging` | GET | Intraday tick data (latest day) | `NYX_PATH` |
| `/tartarus/v1/tickerCommons` | GET | Current price info | `TARTARUS_PATH` |

**Intraday endpoint details:**
```
GET /nyx/v1/intraday/{ticker}/his/paging?page=0&size=100&headIndex=-1
```

Response fields:
- `t` — Time (HH:MM:SS format)
- `p` — Price
- `v` — Volume
- `a` — Match type (A/B/C)

### 3.2 Broken/Unavailable Endpoints ❌

| Endpoint | Method | Status | Ghi chú |
|---|---|---|---|
| `/ligo/v1/watchlist/preview` | POST | 404 | Không còn trên new API |
| `/v2/stock/bars` | GET | Not available | OHLC bars endpoint không tồn tại |
| `apiextaws.tcbs.com.vn/*` | — | 401 | Old API đã ngưng hoàn toàn |

### 3.3 Full OpenAPI Spec

Tất cả endpoints được mô tả trong OpenAPI 3.1.0 spec:
- **File:** `docs/references/tcbs_iflash_openapi.json`
- **Source:** https://developers.tcbs.com.vn

---

## 4. WebSocket Protocol — Chi tiết

### 4.1 Ouranos Stream (`/ws/ouranos/v1/stream`)

**Mục đích:** Real-time market data streaming (OHLC, Order Book, Ticker, Trade)

**Protocol:**
- WebSocket Secure (WSS)
- Text frames (JSON)
- Heartbeat: 2 seconds (client → server)

**Authentication:**
- JWT token required (từ iFlash OpenAPI)
- Token passed via query parameter hoặc handshake header

**Data types (dự kiến):**
- `OHLC` — Open, High, Low, Close bars
- `OrderBook` — Bid/Ask levels
- `Ticker` — Last price, volume, change
- `Trade` — Individual trade events

### 4.2 Aither Stream (`/ws/aither`)

**Mục đích:** Real-time matching information for stock orders

**Reference:** OpenAPI spec section 5.4.4 — "Lấy thông tin khớp lệnh (realtime)"

### 4.3 Nesoi Stream (`/ws/nesoi`)

**Mục đích:** Real-time matching information for derivative orders

**Reference:** OpenAPI spec section 6.3.3 — "Lấy thông tin khớp lệnh (realtime)"

---

## 5. OHLC Computation — Từ Intraday Data

Vì new API không có OHLC bars endpoint, OHLC được compute từ intraday tick data:

### 5.1 Algorithm

```python
# Fetch intraday data for date range
intraday_df = fetch_intraday(symbol, start_date, end_date)

# Group by date and compute OHLC
ohlc_df = intraday_df.groupby('date').agg(
    open=('price', 'first'),
    high=('price', 'max'),
    low=('price', 'min'),
    close=('price', 'last'),
    volume=('volume', 'sum')
).reset_index()
```

### 5.2 Limitations

- Intraday API chỉ trả về data của **latest trading day**
- Không thể compute OHLC cho historical dates (trừ khi fetch day-by-day)
- WebSocket stream sẽ là primary source cho real-time OHLC

### 5.3 Interval Mapping

| Timeframe | TCBS API Key | Notes |
|---|---|---|
| 1m | `1` | Intraday |
| 5m | `5` | Intraday |
| 15m | `15` | Intraday |
| 30m | `30` | Intraday |
| 1H | `60` | Intraday |
| 1D | `D` | Computed from intraday |
| 1W | `W` | Computed from daily |
| 1M | `ME` | Computed from daily |

---

## 6. Reference Documents

### 6.1 Official TCBS Documentation

| Tài liệu | URL | Loại |
|---|---|---|
| TCBS Developer Portal | https://developers.tcbs.com.vn | Website |
| iFlash OpenAPI Documentation | https://developers.tcbs.com.vn | Website |
| WebSocket Bảng Giá (PDF) | https://developers.tcbs.com.vn/file/Websocket_bang_gia_1.0.0.pdf | PDF |
| WebSocket Lịch Sử Giá & Cung Cầu (PDF) | https://developers.tcbs.com.vn/file/Websocket_lich-su-gia_cung-cau_1.0.0.pdf | PDF |

### 6.2 Local Reference Files

| File | Đường dẫn | Mô tả |
|---|---|---|
| OpenAPI Spec | `docs/references/tcbs_iflash_openapi.json` | Full OpenAPI 3.1.0 spec |
| Auth Token Reference | `docs/references/tcbs_auth_token.txt` | Auth token reference |
| JWT Token | `docs/tcbs_jwt.txt` | Valid JWT token (expires ~8h) |
| DNSE Credentials | `docs/references/dnse_credentials.txt` | DNSE API key/secret |

### 6.3 Internal Documentation

| File | Đường dẫn | Mô tả |
|---|---|---|
| API Contract | `docs/TCBS_API_CONTRACT.md` | Broker lane API contract |
| Integration Master Plan | `docs/TCBS_INTEGRATION_MASTER_PLAN.md` | Full implementation plan (S0-S11) |
| Module Structure | `docs/TCBS_MODULE_STRUCTURE.md` | File structure for broker/explorer |
| Investment Data Design | `docs/TCBS_INVESTMENT_DATA_DESIGN.md` | Data model design |
| Broker Spec | `docs/TCBS_BROKER_SPEC.md` | Broker platform specification |
| Broker Platform RFC | `docs/TCBS_BROKER_PLATFORM_RFC.md` | RFC for broker platform |
| Coding Guide | `docs/TCBS_CODING_GUIDE.md` | Coding conventions |
| Audit Checklist | `docs/TCBS_AUDIT_CHECKLIST.md` | Audit requirements |
| Connection Test Report | `docs/TCBS_CONNECTION_TEST_REPORT.md` | Live connection test results |
| Executive Decision Brief | `docs/TCBS_EXECUTIVE_DECISION_BRIEF.md` | Strategic decisions |
| Implementation Playbook | `docs/TCBS_IMPLEMENTATION_EXECUTION_PLAYBOOK.md` | Execution guide |
| Index | `docs/TCBS_INDEX.md` | Master index |
| Slice Definition of Done | `docs/TCBS_SLICE_DEFINITION_OF_DONE.md` | DoD criteria |
| Sprint Task Board | `docs/TCBS_SPRINT_TASK_BOARD.md` | Task tracking |

### 6.4 Test & Debug Files

| File | Đường dẫn | Mô tả |
|---|---|---|
| TCBS Test Spec | `docs/TCBS_TEST_SPEC.md` | Test specifications |
| Final TCBS Test | `docs/test_tcbs_final.py` | Final test script |
| Debug Auth | `docs/debug_tcbs_auth.py` | Auth debugging |
| Debug Auth 2 | `docs/debug_tcbs_auth2.py` | Auth debugging v2 |
| Debug Endpoint | `docs/debug_tcbs_endpoint.py` | Endpoint debugging |
| Login TCBS | `docs/login_tcbs.py` | Login flow test |
| Test with JWT | `docs/test_with_jwt.py` | JWT-based test |

### 6.5 Compatibility & Migration

| File | Đường dẫn | Mô tả |
|---|---|---|
| TCBS Compatibility | `vnbroker/explorer/tcbs/tcbs_compatibility.py` | Compatibility layer |
| Migration Guide | `vnbroker/explorer/tcbs/MIGRATION_GUIDE.md` | Migration from old API |
| Implementation Summary | `vnbroker/explorer/tcbs/IMPLEMENTATION_SUMMARY.md` | Implementation summary |

---

## 7. Implementation Plan — WebSocket Integration

### 7.1 Phase 1: Core WebSocket Client

**File:** `vnbroker/explorer/tcbs/websocket.py`

**Responsibilities:**
- Async WebSocket connection management
- Heartbeat (2s ping)
- Reconnection logic with exponential backoff
- Subscribe/unsubscribe to streams
- Message parsing (JSON text frames)

**Key methods:**
```python
class TCBSWebSocketClient:
    async def connect(self) -> None
    async def disconnect(self) -> None
    async def subscribe(self, symbols: List[str], channels: List[str]) -> None
    async def unsubscribe(self, symbols: List[str], channels: List[str]) -> None
    async def _heartbeat_loop(self) -> None
    async def _message_handler(self) -> None
```

### 7.2 Phase 2: Data Models

**File:** `vnbroker/explorer/tcbs/models.py`

**Dataclasses:**
```python
@dataclass(frozen=True)
class OHLC:
    symbol: str
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

@dataclass(frozen=True)
class OrderBook:
    symbol: str
    time: datetime
    bids: List[Tuple[float, int]]
    asks: List[Tuple[float, int]]

@dataclass(frozen=True)
class Ticker:
    symbol: str
    time: datetime
    last_price: float
    volume: int
    change: float
    change_percent: float

@dataclass(frozen=True)
class Trade:
    symbol: str
    time: datetime
    price: float
    volume: int
    match_type: str
```

### 7.3 Phase 3: Stream Service

**File:** `vnbroker/explorer/tcbs/stream.py`

**High-level async generators:**
```python
class TCBSStreamService:
    async def stream_ohlc(self, symbols: List[str], interval: str) -> AsyncGenerator[OHLC, None]
    async def stream_orderbook(self, symbols: List[str]) -> AsyncGenerator[OrderBook, None]
    async def stream_ticker(self, symbols: List[str]) -> AsyncGenerator[Ticker, None]
    async def stream_trades(self, symbols: List[str]) -> AsyncGenerator[Trade, None]
```

### 7.4 Phase 4: Integration with Quote Module

**File:** `vnbroker/explorer/tcbs/quote.py` (modify)

**New methods:**
```python
class Quote:
    async def history_ws(self, start: str, end: str, interval: str) -> pd.DataFrame
    async def stream_ohlc_async(self, interval: str) -> AsyncGenerator[pd.DataFrame, None]
```

### 7.5 Phase 5: Integration with Listing Module

**File:** `vnbroker/explorer/tcbs/listing.py` (modify)

**WebSocket-based listing:**
- Subscribe to ticker stream for all symbols
- Build real-time symbol list from stream data
- Fallback to REST if WebSocket unavailable

### 7.6 Phase 6: Requirements Update

**File:** `requirements.txt` or `pyproject.toml`

Add:
```
websockets>=12.0
```

### 7.7 Phase 7: Example Scripts

**File:** `examples/tcbs_websocket_example.py`

```python
import asyncio
from vnbroker.explorer.tcbs.websocket import TCBSWebSocketClient

async def main():
    client = TCBSWebSocketClient()
    await client.connect()
    await client.subscribe(["VNM", "HPG", "FPT"], ["ohlc", "ticker"])
    
    async for message in client.messages():
        print(message)
    
    await client.disconnect()

asyncio.run(main())
```

### 7.8 Phase 8: Unit Tests

**File:** `tests/unit/explorer/tcbs/test_websocket.py`

- Mock WebSocket server
- Test connection/reconnection
- Test subscribe/unsubscribe
- Test message parsing
- Test heartbeat

### 7.9 Phase 9: Documentation

- Update this file with actual WebSocket message formats
- Add API contract for WebSocket endpoints
- Update migration guide

---

## 8. Current State — Summary

### 8.1 Completed ✅

| Task | Status |
|---|---|
| Migrate to `openapi.tcbs.com.vn` | ✅ Done |
| Update `const.py` with new paths | ✅ Done |
| Implement `all_future_indices()` | ✅ Done (8 KRX symbols) |
| Implement `history()` with OHLC computation | ✅ Done |
| Implement `intraday()` with `/nyx/v1/` | ✅ Done |
| Update auth flow for JWT | ✅ Done |
| Save JWT token to `docs/tcbs_jwt.txt` | ✅ Done |
| Benchmark (KBS, TCBS, VCI, DNSE) | ✅ Done |
| Create implementation plan | ✅ Done |

### 8.2 In Progress 🔄

| Task | Status |
|---|---|
| WebSocket core client | 📋 Planned |
| WebSocket data models | 📋 Planned |
| WebSocket stream service | 📋 Planned |
| Integration with quote.py | 📋 Planned |
| Integration with listing.py | 📋 Planned |

### 8.3 Blocked ❌

| Task | Reason |
|---|---|
| `all_symbols()` listing | `/ligo/v1/watchlist/preview` returns 404 |
| VCI testing | Rate limited (429) |
| DNSE testing | Requires API keys (credentials saved) |

---

## 9. Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `TCBS_AUTH_TOKEN` | JWT token for authentication | Yes (for most endpoints) |
| `VNBROKER_TCBS_AUTH_TOKEN` | Alternative JWT token var | No |
| `TCBS_OPENAPI_API_KEY` | API Key for token exchange | Yes (for auth flow) |
| `VNBROKER_TCBS_OPENAPI_API_KEY` | Alternative API key var | No |
| `TCBS_OPENAPI_BASE_URL` | Override base URL | No |

---

## 10. Known Issues & Workarounds

### 10.1 OHLC Limited to Latest Trading Day

**Issue:** `/nyx/v1/intraday/{ticker}/his/paging` only returns data for the current/latest trading day.

**Workaround:** 
- Use WebSocket stream for real-time OHLC
- For historical data, fetch day-by-day (slow, rate-limited)
- Consider caching OHLC data locally

### 10.2 `all_symbols()` Listing Broken

**Issue:** `/ligo/v1/watchlist/preview` returns 404 on new API.

**Workaround:**
- Use `/tartarus/v1/derivatives` for derivatives listing (8 symbols)
- Wait for TCBS to provide alternative endpoint
- Consider scraping from TCBS website (not recommended)

### 10.3 JWT Token Expiry

**Issue:** JWT tokens expire after ~**24 giờ** (đo được 2026-10-10 từ JWT thật: `exp - iat = 86400s`).

**Workaround:**
- Implement automatic token refresh
- Store API key securely for re-authentication
- Monitor token expiry and refresh proactively

---

## 11. Python Environment

| Package | Version |
|---|---|
| Python | 3.13.14 |
| ruff | 0.15.17 |
| mypy | 2.1.0 |
| pytest | 9.0.3 |
| websockets | >=12.0 (required, not yet installed) |

---

## 12. Checklist — Before Production Merge

- [ ] WebSocket client implemented and tested
- [ ] Data models defined and validated
- [ ] Stream service with async generators
- [ ] Integration with quote.py complete
- [ ] Integration with listing.py complete (or workaround documented)
- [ ] `websockets>=12.0` added to requirements
- [ ] Unit tests with mocked WebSocket
- [ ] Example scripts created
- [ ] Documentation updated (this file + migration guide)
- [ ] Debug test files cleaned up
- [ ] Security review (no hardcoded secrets)
- [ ] Performance benchmark completed

---

## 13. Contact & Support

| Resource | Link |
|---|---|
| TCBS Developer Portal | https://developers.tcbs.com.vn |
| TCBS Customer Support | cskh@tcbs.com.vn |
| vnbroker Issues | (internal) |
| TCBS API Community | (check developer portal) |

---

## 14. Changelog

| Date | Version | Changes |
|---|---|---|
| 2026-06-21 | 1.0 | Initial creation — comprehensive reference document |

---

*Document ends. For questions or updates, contact the vnbroker team.*
