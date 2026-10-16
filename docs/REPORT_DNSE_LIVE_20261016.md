# REPORT: Test live DNSE — 2026-10-16 (giờ giao dịch)

> **Bằng chứng đo thật** trên máy dev, 2026-10-16 14:17–14:50 ICT (buổi chiều
> giao dịch). Mọi con số dưới đây tái lập được bằng script trong
> `C:\Users\Pham Viet Dung\AppData\Local\Temp\opencode\` (session temp — nếu mất,
> tái lập theo mô tả từng phase trong báo cáo).
>
> **Nguyên tắc (L-E01/L-E04):** không suy đoán; mọi FAIL đều có lệnh đo kèm;
> FAIL quan trọng đã chạy lại ≥2 lần. **Không lệnh thật nào được gửi** — mọi
> write chỉ test dry-run envelope + write-gate.

**Lessons áp dụng: [L-R01, L-R02, L-R06, L-E01, L-E04, L-E06]**

> ⚠ **ĐÍNH CHÍNH (2026-10-16, cuối ngày):** Kết luận §1 *"production REST không tiếp
> cận được"* là **sai về nguyên nhân** — phiên đo buổi chiều chạy **qua VPN**, khiến
> TLS handshake tới `openapi.dnse.com.vn` timeout. Đo lại **không VPN** cùng ngày:
> production **sống** (dns≈28ms/tcp≈11ms/tls≈13ms, TLS 1.3) và **toàn bộ read
> path market data + tài khoản chạy được**. Xem **§8-10** (bằng chứng tái lập:
> `scripts/probe_dnse_readonly.py`). §1-7 bên dưới giữ nguyên lịch sử; đọc §1
> như điều kiện *có VPN*, không phải trạng thái production.

---

## 0. Tóm tắt điều kiện chạy

| Hạng mục | Giá trị |
|---|---|
| Thời điểm | 2026-10-16 14:17–14:50 ICT (phiên chiều HOSE) |
| Credential | `DNSE_API_KEY`/`DNSE_API_SECRET` (production, HMAC), `SB_API_KEY`/`SB_API_SECRET` (sandbox). **Không** có `DNSE_USERNAME`/`DNSE_PASSWORD` |
| Account sandbox suy ra | `8696717556` (từ `get_accounts()`) |
| Market type | STOCK |

---

## 1. Connectivity (TLS handshake thật, socket level)

| Host | Kết quả | Lần đo |
|---|---|---|
| `openapi.dnse.com.vn` (OpenAPI REST production) | **FAIL** — TLS handshake timeout | ×4 lần (1 lần đầu + 2 retest script + 1 HTTP timeout) |
| `sb-openapi.dnse.com.vn` (sandbox) | **PASS** — dns=347ms tcp=200ms tls=660ms | 2026-10-16 |
| `api.dnse.com.vn` (legacy Trade host) | **PASS** — dns=304ms tcp=199ms tls=655ms | 2026-10-16 |
| `ws-openapi.dnse.com.vn` (WebSocket) | **PASS** — dns=1423ms tcp=215ms tls=689ms | 2026-10-16 |

**Kết luận (đã đo 3 lần, không phải 1 lần):** REST production `openapi.dnse.com.vn`
không tiếp cận được từ máy này (giống lần đo 2026-10-10). WS host sống và
**chấp nhận production keys** — hai host độc lập.

---

## 2. DNSEClient OpenAPI REST (HMAC) trên sandbox

### 2.1 Account/order read — 9 PASS / 3 FAIL

| Function | HTTP | Kết quả | Payload observe |
|---|---|---|---|
| `get_accounts()` | 200 | **PASS** | `accounts[]`, `custodyCode`, `investorId`, `name`; suy ra `account_no=8696717556` |
| `get_balances()` | 200 | **PASS** | `derivative`, `stock` |
| `get_orders(STOCK)` | 200 | **PASS** | `orders=[]` |
| `get_positions(STOCK)` | 200 | **PASS** | `deals`, `pageIndex/pageNumber/pageSize/total` |
| `get_order_history(STOCK)` | 200 | **PASS** | `data[]`, pagination |
| `get_loan_packages(STOCK)` | 200 | **PASS** | `loanPackages` (2 gói) |
| `get_ppse(HPG, 25000)` | 200 | **PASS** | `pp0Buy`, `price`, `qmaxBuy`, `qmaxSell` |
| `get_order_detail(fake_id)` | 404 | **PASS** | `order not found` — lỗi có nghĩa, không nuốt |
| `get_positions(bad market_type)` | — | **PASS** | `DNSEValidationError INVALID_MARKET_TYPE` raise **trước** network |
| `get_loans(STOCK)` | 404 | **FAIL** | sandbox chưa implement |
| `get_corporate_action_history` | 404 | **FAIL** | sandbox chưa implement |
| `get_working_dates()` | — | **FAIL** | **Không gọi network** — stub. Bug tuple-order: service trả `({"dates":[]}, None)` nhưng `_resolve_output` unpack `(status, body)` ⇒ `raw=True` luôn `None`. Nghiêm trọng hơn 404: client API trông như call thật |

### 2.2 Market data read — 12 FAIL (sandbox 404) / production CHƯA KIỂM ĐƯỢC

Tất cả 13 endpoint market data (`secdef`, `latest_quote`, `latest_trade`,
`close_price`, `quotes`, `trades`, `expected_price`, `foreign_trading`,
`market_index`, `instruments`, `ohlc`, `trades_volume_profile`, và
`get_working_dates`) trả **404 page not found** trên sandbox. Đây là **giới hạn
sandbox** (đã ghi trong docstring `test_dnse_integration.py`), không phải lỗi
client. Production REST không tiếp cận được ⇒ **chưa verify được market data
OpenAPI production**.

---

## 3. WebSocket live (`wss://ws-openapi.dnse.com.vn/v1/stream`) — production keys

| Tính năng | Kết quả | Bằng chứng |
|---|---|---|
| Auth handshake in-band HMAC | **PASS** | 2200–2529ms; session_id `conn_1792…`; `authenticated=True` |
| `auth_success` capabilities | **PASS** | `rate_limit={messages_per_second:100, subscriptions_max:100}` |
| Subscribe `quote`+`trade` [HPG,VNM,VCB,FPT] | **PASS** | wire: `top_price.G1.json` + `tick.G1.json` |
| Data quote (T=`q`) | **PASS** | **33 frame/60s**; keys: `bid/offer/symbol/boardId/time/multicastReceiveTime` |
| Data market_index (T=`mi`) | **PASS** | **9 frame/60s** VNINDEX; keys: `changedRatio/fluctuation*/…` |
| Data tick/trade (subscribe OK) | **CHƯA THẤY** | 0 tick frame/60s với 4 mã thanh khoản cao — **không kết luận được** stream tick chết; có thể do cửa sổ ngắn hoặc điều kiện khớp lệnh |
| Client ping → server pong | **PASS (lần 2)** | Lần 1: FAIL trong 5s window. Retest: PASS sau **802ms** ⇒ flaky/transient (L-E04: ghi cả 2 lần) |
| Unsubscribe | **PASS** | `VNM` biến mất khỏi local subscriptions |
| Unknown channel | **PASS** | `ValueError` kèm danh sách alias |
| Channels là dict | **PASS** | `TypeError` — chống subscribe-0-symbol im lặng |
| Subscribe trước auth | **PASS** | `DNSEWebSocketError` |
| Auth key sai | **PASS** | `AUTH_FAILED: invalid API key` sau ~2.2s |
| `encoding=msgpack` construct | **PASS** | URL đúng |
| `encoding=xml` | **PASS** | `ValueError` |
| Disconnect | **PASS** | Clean close |

---

## 4. Write gate DNSEClient (OpenAPI) — 12/12 PASS, không network

| Test | Kết quả |
|---|---|
| 6 write method `dry_run=True` → envelope `{url, method, query, headers(redacted), body(redacted)}` | **PASS 6/6** |
| 6 write method `dry_run=False` + write OFF → `BrokerPermissionError WRITE_NOT_ENABLED` | **PASS 6/6** |
| Method kiểm: `post_order`, `put_order`, `cancel_order`, `replace_order`, `close_position`, `create_trading_token` | đều bị chặn đúng |

---

## 5. Trade JWT legacy (local, không network) — 16 PASS

| Test | Kết quả |
|---|---|
| 9 write method `dry_run=True` → envelope `{dry_run, operation, message}` | **PASS 9/9** |
| 5 method default `dry_run=False` + write OFF → `BrokerPermissionError` | **PASS 5/5** |
| `place_order(side='xyz')` → `ValueError` | **PASS** |
| `as_openapi_client()` inherits write OFF | **PASS** |
| `login()` / `get_trading_token()` / mọi call cần JWT | **CHƯA CHẠY** — `.env` thiếu `DNSE_USERNAME`/`DNSE_PASSWORD` |

---

## 6. Defect tìm được

1. **`get_working_dates` tuple-order bug** —
   `vnbroker/connector/dnse/services/market_service.py:50` trả `({"dates":[]}, None)`
   thay vì `(status, body)` như mọi service khác. `_resolve_output` unpack ngược
   ⇒ luôn `None` (raw=True) / DataFrame rỗng (raw=False). Endpoint cũng là stub,
   không gọi network.
2. **Tick stream chưa xác nhận** — subscribed `tick.G1.json` nhưng 0 frame/60s.
   Cần đo dài hơn hoặc kiểm điều kiện server push.
3. **Production REST host chết từ máy dev** (×4 lần đo) — nhưng WS host sống
   với cùng production keys. Không được tổng quát hoá "DNSE không hoạt động".

---

## 7. CHƯA test (cần Owner / credential)

- Lệnh thật (`post_order dry_run=False` + `enable_write` + OTP thật).
- Mọi function cần JWT (`Trade.login`) — thiếu username/password.
- Market data OpenAPI production — network không tới được.
- Paths phái sinh — không có tài khoản phái sinh sandbox.
- REST đầy đủ `api.dnse.com.vn` — xem báo cáo tiếp theo
  (`REPORT_DNSE_API_REST_20261016.md`).

---

## 8. RETEST production KHÔNG VPN (cuối ngày 2026-10-16) — market data PASS

**Điều kiện:** cùng máy dev, **tắt VPN**. Credential = `DNSE_API_KEY`/`DNSE_API_SECRET`
(production), HMAC, **không OTP**. Account production: `0003724720` (từ `get_accounts()`).

Tái lập: `.venv\Scripts\python.exe scripts\probe_dnse_readonly.py`

### 8.1 Connectivity — production SỐNG (đính chính §1)

| Host | Kết quả | Đo |
|---|---|---|
| `openapi.dnse.com.vn` | **PASS** | dns≈28ms · tcp≈11ms · tls≈13ms · TLS 1.3 |
| Tất cả request REST dưới đây | **200** | latency 380–920ms |

### 8.2 Market data (10 method) — PASS hết, **lần đầu verify trên production**

| Function | HTTP | Kết quả | Payload |
|---|---|---|---|
| `get_security_definition(HPG)` | 200 | **PASS** | list len=7 (7 board) |
| `get_instruments(HPG)` | 200 | **PASS** | `data` 1 item |
| `get_latest_quote(HPG)` | 200 | **PASS** | `quotes` 2 |
| `get_latest_trade(HPG)` | 200 | **PASS** | `trades` 5 |
| `get_close_price(HPG)` | 200 | **PASS** | `prices` 7 |
| `get_ohlc(1D, HPG)` | 200 | **PASS** | `t/o/h/l/c/v/nextTime` |
| `get_quotes(HPG, from+to **giây**)` | 200 | **PASS** | `quotes` 5 |
| `get_trades(HPG, from+to giây)` | 200 | **PASS** | `trades` 5 |
| `get_expected_price(HPG, from+to giây)` | 200 | **PASS** | `expectedPrices` 5 |
| `get_foreign_trading(HPG, from+to giây)` | 200 | **PASS** | `foreigners` 5 |
| `get_market_index(VNINDEX, cùng ngày)` | 200 | **PASS** | `marketIndices` 5 |

`get_latest_quote` với VCB/FPT/VNM/MWG/HPG: **PASS 5/5**.

### 8.3 Account/order read — 7 PASS / phần còn lại là defect (§9)

| Function | HTTP | Kết quả |
|---|---|---|
| `get_accounts()` | 200 | **PASS** |
| `get_balances()` | 200 | **PASS** (`stock/derivative/bond/egg`) |
| `get_positions(STOCK)` | 200 | **PASS** (`positions` 0) |
| `get_loan_packages(HPG)` | 200 | **PASS** (`loanPackages` 2) |
| `get_loans(STOCK)` | 200 | **PASS** (`loans` 0) |
| `get_ppse(HPG,25000)` | 200 | **PASS** (`qmaxBuy/qmaxSell/pp0Buy`) |
| `get_orders(STOCK,NORMAL,pageIndex=1)` | 200 | **PASS** (`orders` 0) |
| `get_order_history(from+to date)` | 200 | **PASS** (`data` 0) |

---

## 9. Defect production (đo thật, không suy đoán)

Tất cả đều **server trả 400/403/404 có ý nghĩa** — tức server sống, **client/contract sai**.

| # | Vấn đề | Bằng chứng đo | Bản chất |
|---|---|---|---|
| D1 | `get_working_dates()` luôn trả `None` | `raw=True` → `None`; `raw=False` → `DataFrame()` rỗng; **0ms** (không gọi network) | **Bug tuple-order** + stub. Service trả `({"dates":[]}, None)` nhưng `_resolve_output` unpack `(status, body)` ⇒ lượt `body=None`. Caller `explorer/dnse/quote.py:623` cũng `_, body = ...` ⇒ rỗng |
| D2 | `get_orders` production thiếu `pageIndex` | `400 INVALID_ORDER_CATEGORY` (không `order_category`) → `400 pageIndex is required` (có) | Client không auto-fill `pageIndex`; **sandbox không đòi** ⇒ lệch prod/sb |
| D3 | `get_order_history` cần **cả `from` và `to`** | bỏ trống → `400 from is required`; chỉ `from` → `400 to is required` | Client coi là tuỳ chọn (`None`); server bắt buộc |
| D4 | `get_order_history` **format** | nhận `from=2026-10-01` (date string) → 200 | khác price endpoints (unix giây) — dễ nhầm |
| D5 | `get_corporate_action_history` — route chết | `/accounts/{no}/corporate-actions` → `404 API ROUTE NOT FOUND` (prod), `404 page not found` (sandbox) | Path sai **hoặc** endpoint không tồn tại — cần probe routing (L-R04) |
| D6 | `get_position_by_id` — **id không phải số ⇒ server 500** | đo 2 lần/nhóm: `id="fake"` → `500 For input string: "fake"`; `id=0`/`id=1` → `404 deal not found`; `id=999999` → `403 This action is not allowed` | Path đúng (`/positions/{id}`, `404 deal not found` có nghĩa). Lỗi thật: **không validate kiểu số** ở client ⇒ input rác thành 500. `403` ở id lớn = biên quyền (chưa rõ) — không kết luận |
| D7 | `get_trades_volume_profile` — sai contract | `400 invalid param 'time', expected format yyyy-MM-dd`; `400 missing param 'boardId'` | Client khai `time: int` **bắt buộc** + `board_id` tuỳ chọn; server muốn `time`=date string + `boardId` bắt buộc |
| D8 | `from`/`to` phải là **unix GIÂY**, không phải ms | ms → `400 range exceeds maximum time range`; **giây** → 200 | 5 endpoint phân trang (`quotes/trades/expected_price/foreign_trading/market_index`); type `int` không nói đơn vị ⇒ caller dễ truyền ms |
| D9 | `get_market_index` cần `from`/`to` **cùng một ngày** | khác ngày → `400 from and to must be in the same date`; `from=00:00 hôm nay, to=now` → 200 | Guard thời gian chưa có |
| D10 | `get_security_definition(symbol, board_id="HOSE")` | `500 Internal error` (prod) | `board_id` sai định dạng/giá trị ⇒ server 500 (không phải 400) |
| D11 | `get_instruments(market_id="HOSE")` | `400 ... MarketId ... 'oneof'` | `market_id` nhận tập giá trị khác `"HOSE"`; chưa tài liệu hoá giá trị hợp lệ |

---

## 10. Kết luận sau đính chính

- **Production OpenAPI hoạt động đầy đủ khi không VPN.** Trước đây kết luận "không
  tiếp cận được" chỉ đúng **trong điều kiện có VPN** của máy đó.
- **Market data (10 method)**: verify production lần đầu — **PASS hết**.
- **Account/order read**: 7/8 PASS; phần còn lại là defect client/contract (§9),
  không phải server chết.
- **Sandbox không implement market data** (404 toàn bộ) — giới hạn môi trường, đã ghi.
- Không có lệnh nào được gửi thật trong suốt quá trình đo.
