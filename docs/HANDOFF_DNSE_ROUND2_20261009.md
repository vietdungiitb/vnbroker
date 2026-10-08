# HANDOFF — phiên DNSE round 2 (kết thúc 2026-10-09)

Trạng thái tại lúc đóng phiên: `dev` = `95f68e6`, đã push `origin/dev`, working tree sạch.
Tất cả gate chạy **local** — GitHub Actions của repo này không chạy (`steps: []`, `duration_ms: 0`).

---

## 1. Đã xong (3 commit)

| Commit | Nội dung |
|---|---|
| `eeb1965` | P0 write gate 10 method tiền thật + sửa 3 path sai |
| `b505766` | Đóng 4 lỗ hổng rò credential + sửa failover parity |
| `95f68e6` | Viết lại WebSocket client theo protocol provider hiện tại |

### 1.1 P0 write gate — `eeb1965`

Đo bằng **thực thi**, không đọc tên hàm: `Trade(api_key, api_secret)` không gọi
`enable_write()` vẫn phát **7 request tiền thật** ra ngoài:

```
POST   /accounts/orders?marketType=STOCK      <-- đặt lệnh
PUT    /accounts/ACC/orders/OID
DELETE /accounts/ACC/orders/OID
POST   /accounts/positions/POS/close
POST   /registration/trading-token
POST   /registration/otp
POST   api.dnse.com.vn/derivative-core/deals/1/close
```

Chỉ 4 method cũ có hàng rào. Nay 10 method tiền thật đều qua `_require_write`:
`set_deal_pnl_config`, `set_account_pnl_config`, `close_deal`,
`place_conditional_order`, `cancel_conditional_order`, `post_order`, `put_order`,
`cancel_order_openapi`, `create_trading_token`, `close_position`.

**5 method trước đó không có tham số `dry_run` nào** — không có lối thoát, luôn gửi:
`set_deal_pnl_config`, `set_account_pnl_config`, `close_deal`,
`place_conditional_order`, `cancel_conditional_order`.

**Quyết định thiết kế (giữ nguyên, đừng đảo):** giữ `dry_run` mặc định `False` để
**khớp SDK chính thức** (`client.py:473`). An toàn đến từ `enable_write()`. Đổi sang
`True` như 4 method cũ sẽ biến "gửi tiền ngoài ý muốn" thành **"lệnh biến mất im
lặng"** sau `enable_write()` — tệ hơn.

**4 method phiên/OTP cố ý KHÔNG gate** (quyết định Owner 2026-10-08): `login`,
`get_trading_token`, `login_and_get_trading_session`, `send_email_otp` — gate sẽ
hỏng luồng đăng nhập. Có test khoá lại để không đổi nhầm.

### 1.2 Ba path sai — `eeb1965`

Nguồn: `github.com/dnse-tech/openapi-sdk` + `developers.dnse.com.vn/docs/sdk/trading/`

| Method | Sai | Đúng |
|---|---|---|
| `close_position` | `/accounts/positions/{id}/close` | `/positions/{id}/close` |
| `get_position_by_id` | `/accounts/positions/{id}` | `/positions/{id}` |
| `send_email_otp` | `/registration/otp` + body `otpType` | `/registration/send-email-otp`, không body |

Chỉ **danh sách** `/accounts/{account_no}/positions` vẫn đúng.

### 1.3 Hai chỗ Owner đã chỉnh đúng — KHÔNG được "sửa" lại

**A4 `post_order` — cố ý KHÔNG sửa.** Doc chính thức mẫu
`client.post_order(market_type, payload, trading_token, order_category)` — **không có
`account_no`**, nó nằm trong `payload`. **SDK tự mâu thuẫn với doc của họ** (thêm
`account_no` vào path). `vnbroker` khớp doc. Sửa theo SDK sẽ làm hỏng.

**A5 không phải bug.** `BASE_URL = api.dnse.com.vn` là **họ API thứ hai**
(`auth-service`/`order-service`/`deal-service`/`conditional-api`) dùng bởi **32 method**;
SDK chỉ phủ API mới. Lỗi thật nhỏ hơn nhiều: nó là **hằng cấp class** nên không set
theo instance ⇒ 32 URL đó không intercept/test được. Đã thêm tham số `api_base_url`,
**giữ nguyên mặc định**.

### 1.4 Rò credential — `b505766`

Nguyên nhân gốc là **cấu trúc**, không phải thiếu một entry:

- `SENSITIVE_KEYS` lưu entry theo nhiều cách viết, còn chỗ tra lại chuẩn hoá `-` → `_`
  ⇒ **mọi entry viết bằng dấu gạch là chết vĩnh viễn**.
- `redact_dict` / `redact_headers` **tự so khớp theo luật riêng**, nép qua helper.

Đo được trước khi sửa (output test in ra credential thật):
```
x-api-key: REAL_API_KEY
X-Signature: Signature keyId="REAL_API_KEY",...signature="8BpSh0AiYdc97Q9P..."
```
`trading-token` có che; **`X-Signature` và `x-api-key` — gửi trên mọi request — in nguyên
văn**. SDK chính thức còn tệ hơn: in toàn bộ header dict.

Đã sửa: `_norm_key()` là nguồn sự thật duy nhất, set chuẩn hoá **tại định nghĩa** nên không
thể viết ra entry mà chỗ tra không khớp; cả 3 entry point đi qua cùng một matcher.

> **Bằng chứng lớp lỗi này tự tái hiện:** test
> `test_every_declared_key_actually_matches` bắt được `smart-otp` còn sót **ngay lần
> sửa đầu tiên** — `smartotp` trong set, nhưng `smart-otp` chuẩn hoá thành `smart_otp`.

### 1.5 Failover parity — `b505766`

`bulk_router.PROVIDER_ERRORS` có `OSError`, `source_router.should_failover` **thiếu**.
Vì `requests.RequestException → IOError → OSError`, nên DNS failure, SSL error,
connection reset — **toàn bộ họ lỗi mạng** — không failover ở đường single-symbol trong
khi đường bulk vẫn chạy. Cùng provider, cùng sự cố, hai câu trả lời.

**Cố ý KHÔNG** thêm `TypeError`/`ValueError`/`AttributeError`: lỗi code provider vẫn lọt
lên thay vì bị failover giấu đi. Có test riêng khoá.

### 1.6 A7 WebSocket viết lại — `95f68e6`

Nguồn: `developers.dnse.com.vn/docs/sdk/build_websocket/`
(**bắt buộc có dấu `/` cuối; không có sẽ 301-loop**). Trang là HTML Docusaurus nên được
tải về và tách text để đọc nguyên văn, không đoán.

Client cũ **sai ở mọi mặt**, không phải thiếu sót — không một request nào của nó có thể
ra được:

| Mục | Cũ | Thực tế |
|---|---|---|
| endpoint | `wss://openapi.dnse.com.vn/ws` | `wss://ws-openapi.dnse.com.vn/v1/stream` |
| auth | HMAC REST trong query string | message `{"action":"auth"}` in-band |
| chữ ký | `keyId=..`, `(request-target)` | `HMAC-SHA256(sec,"key:ts:nonce").hex` |
| nonce | không gửi | unix **micro** giây, **string**, unique |
| subscribe | `channels:[str]` phẳng | `channels:[{name,symbols}]` |
| tên kênh | `quote`, `trade`, `sec_def` | `top_price.G1.json`, `tick.G1.json`… |
| heartbeat | WS protocol frame 20s | app-level `{"action":"pong"}`, ≤60s hoặc close 1008 |
| phân loại | `data.get("channel")` | control set vs trường `T` |

Quy tắc protocol đã encode vào code + test:
- `welcome` → phải auth trong **30s**
- `timestamp` = unix **giây**, ±5 phút; `nonce` = unix **micro** giây, là **string**, không
  tái dùng trong 10 phút, sinh lại mỗi lần reconnect (kể cả khi đồng hồ lùi do NTP)
- subscribe **trước** khi auth thành công bị từ chối
- symbols phải **UPPERCASE**
- PONG phải **echo timestamp** để server đo round-trip latency
- `connection_expired` sau 8h là **bình thường**, server mong đợi reconnect
- error dùng trường `message`, **không phải** `msg`
- `action` chỉ là control khi thuộc `CONTROL_ACTIONS`; `estimated_market_index` có cả
  `action` **lẫn** `T`, nên "có action" không phải cách phân loại hợp lệ
- `rate_limit.subscriptions_max` từ `auth_success` được lưu và chặn subscribe vượt trần

Tên kênh cũ (`quote`/`trade`/`sec_def`…) **giữ làm alias** nên code gọi cũ không vỡ; tên
wire đầy đủ (`tick.G1.json`) vẫn chạy. Thêm `msgpack` (lazy import, **không fallback im
lặng** sang json).

**Deadlock tôi tự gây ra, test bắt được:** `connect()` chờ `_authenticated` nhưng task đọc
chỉ khởi động *sau* khi auth xong ⇒ `auth_success` nằm trong hàng đợi không ai lấy ⇒
production cũng timeout 30s. Đã sửa bằng cách đọc inline có deadline.

---

## 2. Gate (đều chạy thật, exit code thật)

| Gate | Trước | Tại `95f68e6` |
|---|---|---|
| `pytest tests/unit tests/contract` | 1275 | **1343** |
| `pytest tests/` | 1346 | **1414** |
| ruff (`vnbroker`, `tests/unit`, `tests/contract`) | 0 | **0** |
| mypy baseline | OK | **OK** (baseline 1266 → 1207) |
| acceptance `test_tier1_dod.py` | 26/26 | **26/26** |

**Fail-before / pass-after** (đo bằng cách ghi bản cũ ra file, **không** `git checkout --`):

- `test_trade_write_gate.py`: **23 failed** ở `28db3de` → **34 passed**
- `test_dnse_endpoint_contract.py`: **4 failed** → **4 passed**
- `test_redaction.py`: **9 failed** → **9 passed**
- `test_failover_parity.py`: **8 failed** → **16 passed**
- WebSocket: fail-before chứng minh bằng **AST đọc bản cũ từ git** (host cũ,
  `ping_interval=20`, `channels` là list chuỗi)

---

## 3. Còn lại — session sau

### 3.1 P0 — sửa tiếp `async_client.py` (claim `leader-t2-policy` còn `partial`)

`vnbroker/core/utils/async_client.py` có **TokenBucketRateLimiter trùng lặp** với bản ở
`vnbroker/core/`. Chưa đụng tới. Cần: xác định bản nào là SSOT, hợp nhất, và phải **giữ
được bounded wait** — đừng biến thành chặn vô hạn. Gate hiện chưa đổi: `tests/unit/core/test_rate_limiter.py` **chưa được tạo** (claim ghi tên nó nhưng thực tế chưa làm).

### 3.2 P1 — không có credential thật nên **chưa xác minh runtime**

Cần DNSE/SSI/TCBS credentials để chạy, cho tới giờ **mọi test là server giả theo doc**:

1. `rate_limit` server thật trả về có đúng `{messages_per_second, subscriptions_max}` không
2. msgpack: server có thực sự gửi binary frame không
3. `MAX_DURATION_EXCEEDED` + close code 1008 sau 8h
4. Họ API **legacy** `api.dnse.com.vn` — 32 method dùng host này, **SDK không hề nhắc tới**
5. Conditional orders (`place`/`cancel_conditional_order`)
6. Hết hạn token sau 25 phút cho `copilot`-style credential — **chưa áp dụng ở DNSE WS**

### 3.3 P2 — A6: 22 endpoint còn thiếu so với SDK

**Cố ý hoãn.** Thêm `reverse_position` (đảo vị thế) lúc này = thêm **endpoint tiền thật
chưa có write gate**. Phải làm sau khi có gate ở tầng khác.

### 3.4 P2 — `match_type` vẫn là string, chưa đổi sang enum

Bị chặn cùng lý do: thêm type mới cho lệnh là thêm đường gửi lệnh mới.

### 3.5 P3 — housekeeping

1. **Ruff trên toàn bộ `tests/` đỏ 8 lỗi F401/F841 — CÓ SẴN Ở HEAD**, ở
   `test_tier1_dod.py`, `vci_proxy_demo.py`, `test_acb_all_providers.py`. Không phải của
   round 2. Gate scope đang chạy là `vnbroker` + `tests/unit` + `tests/contract`.
   Muốn gate xanh toàn bộ `tests/` thì cần **một commit riêng** dọn 8 lỗi này.
2. `websockets` 16.0 đã gỡ `WebSocketClientProtocol` khỏi top-level (từ v14 → `websockets.legacy`).
   Annotation cũ đã chết — đã bỏ trong bản viết lại.

---

## 4. Quy trình — 2 lần tôi tự phá file, đừng lặp lại

Tôi đã **mất code 2 lần** trong phiên này bằng `git show HEAD:... > file` khi fix chưa
commit. Lần 2 xoá sạch bản rewrite WebSocket và phải viết lại từ đầu. Cả hai lần đều ở
bước fail-before.

**Quy tắc cho session sau:**

1. **Commit fix TRƯỚC**, rồi mới đo fail-before.
2. Đo fail-before bằng cách **ghi bản cũ ra thư mục tạm rồi import như module độc lập**,
   hoặc **AST đọc từ `git show`** (read-only, không đụng working tree).
3. **Không bao giờ** dùng `git show HEAD:<file> > <file>` hay `git checkout HEAD -- <file>`
   khi thay đổi chưa commit.

Ngoài ra `docs/COMPARE_DNSE_SDK.md` là nơi đối chiếu SDK chính thức với vnbroker — **đọc
file này trước** khi sửa bất kỳ endpoint DNSE nào, tránh lặp lại việc tin nhầm SDK hơn doc.

---

## 5. vninvest: KHÔNG cần sửa

Owner yêu cầu kiểm tra xem `vninvest` có cần đổi theo không. Đã grep toàn repo:

- `DNSEWebSocketClient` → **0 kết quả trong code**; 8 kết quả đều là **prose** trong
  `docs/CODE_CHANGE_AUDIT_LEDGER.md` và archive docs
- các tên kênh cũ (`foreign_investor`, `sec_def`, `top_price`, `tick.G1`, `ohlc_closed`,
  `expected_price`) → **0 kết quả** trong `packages/core`
- market-data sync của vninvest dùng Django Channels riêng, không đi qua client này

⇒ Toàn bộ rewrite nằm gọn trong vnbroker. **Trong phiên này không ghi gì vào vninvest.**
Lưu ý cho session sau: Entry 256 từng lần bị đưa nhầm vào `vninvest`; bản cứu nằm ở
`%TEMP%\opencode\ledger-rescue\`, **không được áp dụng**.