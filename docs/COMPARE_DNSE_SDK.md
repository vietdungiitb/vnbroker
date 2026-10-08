# So sánh `vnbroker/connector/dnse` với SDK chính thức của DNSE

- **Nguồn chuẩn:** `https://github.com/dnse-tech/openapi-sdk` → `python/dnse/api/client.py` (665 dòng), port về `%TEMP%/opencode/dnse-sdk`
- **So sánh:** `dev` @ `28db3de`
- **Ngày:** 2026-10-08
- **Vì sao cần:** `developers.dnse.com.vn` không truy cập được (`502`/`403`, TLS timeout). Trước đó tôi phân loại endpoint ghi/đọc **bằng đoán theo tên hàm** — cách đó sai. SDK trên GitHub là nguồn chính thức, đọc được.

> **Tool dùng để so:** script AST đọc `client.py` của SDK, lấy cặp `(HTTP verb, path template)` từ mọi lời gọi `self._request(...)`. Đối chiếu với path literal trong `vnbroker/**`.
> **Instrument tĩnh trước đó bị bác bỏ:** quét AST tìm `requests.post(...)` trong `trade.py` trả **0 verb** vì các method uỷ quyền qua service wrapper (`services/*_service.py`).

---

## A. Chỗ `vnbroker` **KHÁC** SDK chính thức

| # | Endpoint | SDK chính thức | `vnbroker` | Đánh giá |
|---|---|---|---|---|
| **A1** | `close_position` | `POST /positions/{position_id}/close` | `/accounts/positions/{position_id}/close` — `services/position_service.py:35` | **Thừa `/accounts`**. URL sai theo đặc tả duy nhất công bố ⇒ đóng vị thế sẽ hỏng |
| **A2** | `get_position_by_id` | `GET /positions/{position_id}` | `/accounts/positions/{position_id}` — `services/position_service.py:21` | Cùng lỗi thừa `/accounts` |
| **A3** | `send_email_otp` | `POST /registration/send-email-otp` | `POST /registration/otp` body `{"otpType":"email_otp"}` — `services/token_service.py:11` | **Sai path và sai body**. `/registration/otp` + `otpType` trông như endpoint OTP trading-token, không phải email OTP |
| **A4** | `post_order` | `POST /accounts/{account_no}/orders` | `/accounts/orders` — `services/order_service.py:96` | **CHƯA KẾT LUẬN**. SDK có `account_no`, vnbroker không. Cần gọi API thật mới biết bên nào đúng. **Không sửa khi chưa verify.** |
| **A5** | host | chỉ `https://openapi.dnse.com.vn` | 3 method hardcode `https://api.dnse.com.vn` — `trade.py` (`close_deal`, `set_deal_pnl_config`, `set_account_pnl_config`) | Host **không tồn tại trong SDK công bố**. Có thể là họ API derivative riêng — **không tự ý xóa**. Làm thành tham số cấu hình, mặc định giữ nguyên. |
| **A6** | thiếu endpoint | 22 endpoint | không có | Gồm **`reverse_position`** (`POST /positions/{}/reverse` — đảo vị thế, là **tiền thật**), `patch_account_pnl_configs`, `post_position_pnl_configs`, `create_smart_otp_handoff`, `get_account_pnl_configs`, `get_position_pnl_configs`, `get_quotes`, `get_expected_price`, `get_foreign_trading`, `get_market_index`, `get_trades_volume_profile`, `get_latest_quote`, `get_working_dates`, `get_lastest_session`, `get_instruments`, `get_loans`, `get_corporate_action_history`, `get_list_care_by`, `get_orders`, `get_order_detail`, `get_positions`, `get_accounts` |

### A6 — các path `vnbroker` **ĐÚNG** (không nằm trong danh sách sai)

`order_service.py` khớp SDK: `get_orders` `/accounts/{account_no}/orders` (L22) · `get_order_detail` (L40) · `get_execution_detail` (L55) · `get_order_history` (L81) · `put_order` (L118) · `cancel_order` (L139) · `get_balances` · `get_loan_packages` · `get_ppse` · `get_positions` (`position_service.py:13`) · `get_ohlc` `/price/ohlc` · `create_trading_token` `/registration/trading-token`.

⇒ Phần lớn path **đúng**. Sai tập trung ở **position theo id** và **OTP**.

---

## B. Chỗ `vnbroker` **ĐÚNG HOẶC TỐT HƠN** SDK

| # | Hạng mục | SDK chính thức | `vnbroker` | Vì sao là tốt hơn |
|---|---|---|---|---|
| **B1** | **dry-run không rò credential** | `client.py:604-610` in **toàn bộ** `req_headers`, gồm `x-api-key` **và** `X-Signature` **và** `trading-token` | `core/http_client.py:53-55` mask `trading-token` | `vnbroker` tốt hơn thư viện của nhà cung cấp. **Nhưng chưa đủ:** `x-api-key` và `X-Signature` không bị mask (xem B1-gap) |
| **B2** | dry-run trả về | `return None, None` | trả envelope dict có `url/method/headers/body` | caller kiểm tra được thay vì nhận `None` |
| **B3** | **write gate** | **không có gì** | `_require_write()` + `enable_write()` (`trade.py:35-72`) | Có thiết kế an toàn tiền thật. **Nhưng chỉ áp cho 4/14 method ghi** — đây là P0 đã ghi |
| **B4** | **module redaction** | không có | `broker/security/redaction.py` + đã dùng cho WebSocket | Có nền tảng dùng chung (thiếu hẳn ở SDK) |
| **B5** | timeout | hardcode `Timeout(connect=30, read=330)` **chỉ cho smart-otp** | `timeout=self._config.timeout_seconds` cho **mọi** request (`http_client.py:73`) | Cấu hình được, phủ toàn bộ |
| **B6** | **X-Request-ID** | không đọc | `response.headers.get("X-Request-ID")` (`http_client.py:91`) | Truy được về phía DNSE khi lỗi |
| **B7** | **đa provider + failover** | chỉ DNSE, không failover, không health | KBS/VCI/TCBS/SSI/DNSE + cooldown + retry **theo từng provider** + circuit breaker | Đây là giá trị lõi của `vnbroker`, vượt xa SDK một bậc |
| **B8** | **conditional orders** | không có | `place_conditional_order` / `cancel_conditional_order` | Năng lực vượt SDK — nhưng **chưa verify** với API thật |
| **B9** | chuẩn hoá dữ liệu | không có | `Normalizer` (tz-aware, lọc biên) + `match_type` + contract test | Người dùng nhận cùng schema dù provider khác nhau |

### B-gap — chỗ `vnbroker` **còn thiếu** so với chính nó đã tuyên bố

Dry-run envelope mask `trading-token` nhưng **không** mask `x-api-key`/`X-Signature` (`http_client.py:53-55`). SDK in cả 3 ⇒ vnbroker tốt hơn 1/3, chưa đủ.

### B-đối-lập — chỗ **SDK tốt hơn**

| Hạng mục | SDK | `vnbroker` |
|---|---|---|
| WebSocket | **879 dòng** — event handler, `asyncio.Queue`, `is_healthy()`, `__aiter__` (`websocket/client.py`) | **249 dòng** |
| Phủ endpoint | 22 endpoint mà `vnbroker` thiếu (A6) | — |

⇒ `vnbroker` **thua** SDK ở WebSocket và độ phủ endpoint. Ghi rõ, không giấu.

---

## C. Đính chính một claim sai trong báo cáo trước

Báo cáo `vninvest` ledger Entry 256 (và tin nhắn cho Owner) đã ghi: *"envelope dry-run chỉ mask `trading-token`, header thực gửi là `Trading-Token`"*.

**Sai.** SDK gửi header `trading-token` **viết thường** (`client.py:474`, `:512`), và envelope của `vnbroker` mask đúng chữ thường đó. Phần đúng của claim chỉ là: envelope **không** mask `x-api-key`/`X-Signature`.

## D. Đính chính claim "dry_run=False là không an toàn"

`dry_run=False` là **mặc định của chính SDK**, kể cả `post_order`/`put_order`/`cancel_order`/`close_position`. Vậy nên `dry_run=False` mặc định ở `vnbroker` **khớp hợp đồng nhà cung cấp** — không phải lỗi của `vnbroker`.

Câu hỏi còn lại là **chính sách**: `vnbroker` có nên **an toàn hơn SDK** (yêu cầu `enable_write()`) hay **khớp SDK**? Đây là quyết định của Owner, không phải kết luận kỹ thuật. Plan `TIER1_ROUND2` chọn phương án **an toàn hơn SDK** và ghi rõ đây là breaking change.