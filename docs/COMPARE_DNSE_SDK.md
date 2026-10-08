# So sánh `vnbroker/connector/dnse` với SDK + tài liệu chính thức của DNSE

- **Nguồn chuẩn 1 (SDK):** `https://github.com/dnse-tech/openapi-sdk` → `python/dnse/api/client.py` (665 dòng) — port về `%TEMP%/opencode/dnse-sdk`
- **Nguồn chuẩn 2 (doc):** `https://developers.dnse.com.vn/docs/sdk/trading/` và `.../build_websocket/` — tải được, **phải có dấu `/` cuối**, nếu không server trả `301` sang `http://` rồi loop
- **So sánh:** `dev` @ `28db3de`
- **Ngày:** 2026-10-08

> **Vì sao cần cả hai:** `developers.dnse.com.vn/docs/dnse/trading` (URL cũ) trả `502`. Đường đúng là `/docs/sdk/trading/`. Và SDK GitHub **tự mâu thuẫn với doc** ở một chỗ — xem A4.

---

## A0. `post_order` — `vnbroker` ĐÚNG, SDK SAI

| | Nguồn | Hình dạng |
|---|---|---|
| **Doc chính thức** | `docs/sdk/trading/` | `client.post_order(market_type="STOCK", payload=payload, trading_token=…, order_category="NORMAL")` — **không có tham số `account_no`**; `accountNo` nằm **trong `payload`** |
| **SDK GitHub** | `client.py:473` | `post_order(self, account_no, market_type, payload, trading_token, …)` → path `/accounts/{account_no}/orders` |
| **`vnbroker`** | `services/order_service.py:96` | path `/accounts/orders`, `accountNo` trong payload |

⇒ **`vnbroker` khớp doc. SDK tự mâu thuẫn với doc của chính họ.** Đây là trường hợp ta **không** sửa, và đó là quyết định đúng. Trước đó tôi ghi "chưa kết luận, cần gọi API thật" — nay đã có câu trả lời không cần mạng.

---

## A. Chỗ `vnbroker` **KHÁC** chuẩn

| # | Endpoint | Chuẩn | `vnbroker` | Trạng thái |
|---|---|---|---|---|
| ~~**A1**~~ | `close_position` | `POST /positions/{id}/close` | ~~`/accounts/positions/{id}/close`~~ | ✅ **ĐÃ SỬA** → `/positions/{id}/close` |
| ~~**A2**~~ | `get_position_by_id` | `GET /positions/{id}` | ~~`/accounts/positions/{id}`~~ | ✅ **ĐÃ SỬA** → `/positions/{id}` |
| ~~**A3**~~ | `send_email_otp` | `POST /registration/send-email-otp`, **không body** | ~~`/registration/otp` + `{"otpType":"email_otp"}`~~ | ✅ **ĐÃ SỬA** → đúng path, bỏ body |
| **A4** | `post_order` | doc: `/accounts/orders` + `accountNo` trong payload | `/accounts/orders` | ✅ **`vnbroker` ĐÚNG** (xem A0). **Không sửa.** |
| **A5** | host | chỉ `openapi.dnse.com.vn` (doc lẫn SDK) | 3 method hardcode `api.dnse.com.vn` — `trade.py` | 🔴 **Chưa xử lý**. Host không có trong SDK **hay doc**. Có thể là họ API derivative riêng — **không tự ý xoá**. Làm thành tham số cấu hình, mặc định giữ nguyên. |
| **A6** | thiếu endpoint | 22 endpoint trong SDK | không có | 🔴 **Chưa xử lý**. Gồm `reverse_position` (`POST /positions/{}/reverse`), `patch_account_pnl_configs`, `post_position_pnl_configs`, `create_smart_otp_handoff`, và 14 endpoint dữ liệu thị trường. Lưu ý: `reverse_position` có trong **SDK nhưng không có trong doc trading**. |

### A7 — WebSocket của `vnbroker` **KHÔNG** implement protocol DNSE (mới)

Đối chiếu `docs/sdk/build_websocket/`:

| | Doc chính thức | `vnbroker/connector/dnse/websocket.py` |
|---|---|---|
| Host | `wss://ws-openapi.dnse.com.vn` | `wss://openapi.dnse.com.vn/ws` (`:40`) — **khác host** (`openapi` ≠ `ws-openapi`) |
| Path | `/v1/stream?encoding={json\|msgpack}` | `/ws`, **không** `encoding` |
| Xác thực | message `auth` **in-band** sau `welcome`, ký `HMAC(api_secret, "{api_key}:{timestamp}:{nonce}")`, **bắt buộc trong 30 giây** | query param trên HTTP upgrade, ký kiểu REST qua `build_signature_header` (`:65-89`) |
| Giữ kết nối | server PING mỗi **3 phút**, client phải **PONG trong 1 phút** | **không có PONG** (`pong` = 0 hit) |
| Định dạng | `msgpack` hoặc `json` | không `msgpack` |

Đây là **hai mô hình xác thực khác nhau hoàn toàn**, không phải khác biệt nhỏ. Client nằm trong `__all__` (`connector/dnse/__init__.py:5`) nhưng **0 caller nội bộ**; `vninvest` dùng websocket của riêng nó (Django Channels), không dùng cái này.

⇒ **Chưa kết luận là hỏng với API thật** — cần credential thử. Nhưng nó **không khớp tài liệu**, và đó là điều cần nói thẳng. Đề xuất: hoặc viết lại theo protocol doc, hoặc gỡ khỏi `__all__` cho tới khi làm đúng.

### A8 — Phần lớn path `vnbroker` **ĐÚNG**

`get_orders` · `get_order_detail` · `get_execution_detail` · `get_order_history` · `put_order` · `cancel_order` · `get_balances` · `get_loan_packages` · `get_ppse` · `get_positions` · `get_ohlc` · `create_trading_token` — **khớp cả SDK lẫn doc**.

---

## B. Chỗ `vnbroker` **ĐÚNG HOẶC TỐT HƠN**

| # | Hạng mục | SDK / doc chính thức | `vnbroker` | Vì sao tốt hơn |
|---|---|---|---|---|
| **B1** | **dry-run không rò credential** | `client.py:604-610` in **toàn bộ** `req_headers`, gồm `x-api-key` **và** `X-Signature` **và** `trading-token` | `core/http_client.py:53-55` mask `trading-token` | `vnbroker` tốt hơn thư viện của nhà cung cấp. **Chưa đủ:** `x-api-key`/`X-Signature` chưa mask |
| **B2** | dry-run trả về | `(None, None)` | envelope dict có `url/method/headers/body` | caller kiểm tra được |
| **B3** | **write gate** | **không có gì** | `_require_write()` + `enable_write()` | Có thiết kế an toàn tiền thật — nhưng mới áp 4/14 method ghi |
| **B4** | **module redaction** | không có | `broker/security/redaction.py` + dùng cho log WebSocket | Có nền tảng dùng chung (thiếu hẳn ở SDK) |
| **B5** | timeout | hardcode `Timeout(connect=30, read=330)` **chỉ smart-otp** | `timeout=self._config.timeout_seconds` cho **mọi** request | Cấu hình được, phủ toàn bộ |
| **B6** | **X-Request-ID** | không đọc | `http_client.py:91` đọc `X-Request-ID` | Truy được lỗi về phía DNSE |
| **B7** | **đa provider + failover** | chỉ DNSE, không health | 5 provider + cooldown + retry **theo từng provider** + circuit breaker | Giá trị lõi, vượt xa SDK một bậc |
| **B8** | **conditional orders** | không có ở SDK lẫn doc trading | `place_conditional_order` / `cancel_conditional_order` | Vượt — nhưng **chưa verify** với API thật |
| **B9** | chuẩn hoá dữ liệu | không có | `Normalizer` tz-aware + `match_type` + contract test | Người dùng nhận cùng schema dù provider khác nhau |
| **B10** | **`post_order`** | **SDK sai** (thêm `account_no` vào path, trái doc) | khớp doc | xem A0 |

### B-đối-lập — chỗ **chuẩn tốt hơn**

| Hạng mục | Chuẩn | `vnbroker` |
|---|---|---|
| WebSocket | protocol doc + `websocket/` của SDK (879 dòng: `AuthManager`, event handler, `asyncio.Queue`, `is_healthy()`, `__aiter__`) | 249 dòng, **không khớp protocol** (A7) |
| Phủ endpoint | 22 endpoint (SDK) | thiếu (A6) |

### B-gap — envelope dry-run mask `trading-token` nhưng **không** mask `x-api-key`/`X-Signature` (`http_client.py:53-55`). SDK in cả 3 ⇒ vnbroker tốt hơn 1/3.

---

## C. Đính chính claim đã báo cho Owner (quan trọng)

| Claim cũ | Thực tế |
|---|---|
| *"header thực gửi là `Trading-Token` Title-Case"* | **SAI.** Cả SDK lẫn doc dùng `trading-token` **viết thường**. vnbroker mask đúng chữ đó. |
| *"`dry_run=False` mặc định là không an toàn"* | **SAI.** Đó là mặc định của **chính SDK**, kể cả `post_order`. `vnbroker` **khớp** hợp đồng nhà cung cấp. |
| *"3 method gọi host cứng cần trỏ về `base_url`"* | **CHƯA KẾT LUẬN / có thể sai.** `api.dnse.com.vn` không có trong SDK **hay doc**; nó có thể là họ derivative riêng. Làm thành **tham số cấu hình**, giữ mặc định — không trỏ thẳng. |

## D. Đã đóng trong vòng này

`tests/contract/test_dnse_endpoint_contract.py` — 4 test khoá path theo đặc tả nhà cung cấp, assert trên **URL cuối do tầng HTTP phát ra** (không assert chuỗi trung gian).
**Fail-before/pass-after:** trên `28db3de` → **4 failed**; tại HEAD → **4 passed**.