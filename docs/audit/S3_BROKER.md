# S3 — AUDIT ĐƯỜNG TIỀN THẬT (BROKER LANE)

**Scope:** `vnbroker/broker/` + `vnbroker/brokerage/` + `vnbroker/connector/dnse/` + `vnbroker/connector/__init__.py`
**Phạm vi thực:** 59 file / 15.030 LOC (`git ls-files | grep '^vnbroker/\(broker\|brokerage\|connector\)/'`)
**Ngày:** 2026-10-01
**Phương pháp:** đọc toàn bộ + probe runtime bằng `python -c` (mock transport, **không gọi mạng thật tới broker, không đặt lệnh thật**).

> **Baseline supervisor (đã chạy, KHÔNG báo lại):** `pytest tests/unit` = 3 failed / 906 passed / 5 skipped; `ruff` = 2888 lỗi; `check_mypy_baseline` exit 1.

---

## 0. Tóm tắt điều hành

| Mức | Số | Nội dung |
|---|---|---|
| **P0 — chặn merge** | 4 | `write_gate` bypass bằng positional; SSI retry lặp POST đặt lệnh; DNSE connector **không có `dry_run`/`write_gate` nào**; WS log rò `api_key`+signature |
| **P1** | 6 | Session tự đặt EXPIRED khi đọc token; `IdempotencyStore` không được dùng; DNSE ký HMAC không phủ body; Redactor hở `trading-token`/`passcode`; `TCBSClient._WSManager` vỡ với `websockets>=14`; DNSE reconnect đệ quy |
| **P2** | 8 | Redactor thiếu key; DNSE SHA-1 fallback; header `None`; URL không encode; OTP đặt trong dict-key; `trading_token` plaintext attr; thiếu `AuditSink`; không có test |
| **P3 (ghi nhận)** | 3 | Điểm tốt đã làm đúng |

**Kết luận:** lane `broker/ssi` + `broker/tcbs` có hàng rào khá tốt (dry_run default, `@write_gate`, redaction, `__repr__` redact). Nhưng **hàng rào đó thủng ở 2 điểm cốt lõi** (positional bypass + retry mù trên POST), và **toàn bộ `connector/dnse` nằm ngoài hàng rào** — đặt lệnh, hủy lệnh, nạp/rút margin đều **gửi thật ngay lập tức**, không cần `enable_write()`, không `dry_run`, không `write_gate`.

---

## 1. P0 — Chặn merge

### P0-1 · `write_gate` bypass: truyền `dry_run` POSITIONAL → lệnh **không** được gửi, caller tưởng đã gửi

**File:** `vnbroker/broker/security/guards.py:45-58`

```python
def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
    dry_run = kwargs.get("dry_run", True)     # ← chỉ đọc kwargs, BỎ QUA positional
    if dry_run:
        result: Dict[str, Any] = {
            "dry_run": True,
            ...
        }
        return result  # type: ignore[return-value]
```

Decorator chỉ kiểm tra `kwargs["dry_run"]`. Khi `dry_run` được truyền **positional** (Python cho phép vì các internal `_gated_*` có `dry_run` là *keyword-only* ở public wrapper nhưng decorator không enforce được), `kwargs.get` trả `True` → **nhánh dry-run được chọn → hàm gốc không bao giờ chạy**.

**Đã xác minh runtime** (probe với chính `write_gate` của repo, session `is_write_enabled = False`):

```
KWD_FALSE_NOWRITE -> BLOCKED BrokerPermissionError
POS_FALSE_NOWRITE -> {'dry_run': True, 'operation': 'gated', ...} | fn_called= False
POS_FALSE_WRITEON -> {'dry_run': True, 'operation': 'gated', ...} | fn_called= False
```

Dòng `POS_FALSE_WRITEON` là điểm nguy hiểm nhất: **kể cả khi user đã `enable_write()` và cố tình truyền `dry_run=False` positional, lệnh vẫn KHÔNG được gửi**, nhưng hàm trả về dict trông như kết quả bình thường. Đây là **fail-silent theo hướng ngược**: bằng chứng cho thấy guard *hoạt động* (return dry_run envelope) trong khi thực tế **user nghĩ lệnh đã đi**. Với `place_order`, điều này có thể khiến hệ thống đặt lệnh dự phòng "cho chắc" → **double-submit**.

**Root cause:** đọc `dry_run` từ `kwargs` thay vì introspect signature.
**Fix:** bind bằng `inspect.signature(fn).bind(*args, **kwargs)` rồi đọc `arguments["dry_run"]` với default `True`.

> **Lưu ý:** hiện tại *chưa* có call site nào trong repo truyền positional (tất cả đều `dry_run=dry_run`), nên đây là **bẫy chưa nổ** — nhưng nó là **latent landmine** trên đường tiền thật: bất kỳ refactor nào đổi `*, dry_run: bool = True` thành `dry_run: bool = True` (bỏ dấu `*`) là hàng rào biến mất **âm thầm**, không test nào đỏ.

---

### P0-2 · SSI retry **mù** trên POST đặt lệnh → double-submit khi connection reset sau khi broker đã nhận

**File:** `vnbroker/broker/ssi/_transport.py:104-131` + `147-153`

```python
retryer = Retrying(
    stop=stop_after_attempt(self._max_retries),      # default 5
    wait=wait_exponential(multiplier=0.5, max=8.0),
    retry=retry_if_exception_type(
        (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
    ),
    reraise=True,
)
```
```python
def request_signed(self, method, path, body_str, private_key) -> Any:
    signature = rsa_sign_hex(body_str, private_key)
    return self.request(
        method, path,
        raw_content=body_str.encode("utf-8"),
        extra_headers={_HEADER_SIGNATURE: signature},
    )
```

`request_signed` (dùng cho **mọi write SSI**: `POST/PUT/DELETE /api/v3/trading/order` và `/fco/order`) đi qua `request()` — **không phân biệt method**. `requests.exceptions.ConnectionError` được raise **cả khi server đã xử lý xong request nhưng response bị mất** (connection reset sau khi gửi body). Retrier gửi lại **y hệt** body+signature → broker nhận trùng.

**Đã xác minh runtime** (fake session: 2 lần đầu raise `ConnectionError` *sau khi* đã "process", lần 3 trả 200):

```
POST attempts actually sent to the broker: 3
  attempt 1 POST https://api.ssi.com.vn/api/v3/trading/order
  attempt 2 POST https://api.ssi.com.vn/api/v3/trading/order
  attempt 3 POST https://api.ssi.com.vn/api/v3/trading/order
final result: {'orderId': 'SRV-1', 'orderStatus': 'NEW'}
```

**3 lần POST đặt lệnh thật**, cùng `clientRequestId`. Lớp bảo vệ duy nhất là **server-side dedupe theo `clientRequestId`** — mà `ssi/equity.py:100-101` **tự sinh `request_id` mới ngẫu nhiên khi caller không truyền**:

```python
if not request_id:
    request_id = generate_request_id()
    _logger.debug("SSI place_order: sinh request_id mới.")
```
→ mỗi lần gọi lại `place_order` lại có key khác, dedupe vô hiệu.

**Tác động:** double-submit đặt lệnh → mua/bán quá số lượng dự định. Đây là đường tiền thật.
**Fix:** (a) chỉ retry cho idempotent method (`GET`); với write — retry **manual** kèm **tái sử dụng `request_id` cố định**; (b) `generate_request_id()` không được sinh mỗi call khi thiếu — hoặc fail yêu cầu caller, hoặc cache theo (account,symbol,side,type,price,qty) trong TTL ngắn.

---

### P0-3 · `connector/dnse` **hoàn toàn không có** `dry_run` / `write_gate` — đặt lệnh & rút margin gửi thật ngay

**Files:** `vnbroker/connector/dnse/trade.py`, `connector/dnse/client.py`, `connector/dnse/services/order_service.py`

Xác minh bằng grep:
```
$ grep -rn "write_gate\|dry_run: bool = True" vnbroker/connector/
(none)
```
Mọi write method của DNSE **không có tham số `dry_run`**, không có session state, không `enable_write()`:

| Method | File:line | Gửi HTTP thật? |
|---|---|---|
| `place_order` | `trade.py:294` | `requests.post(url, headers=..., json=payload)` — `trade.py:350` |
| `cancel_order` | `trade.py:422` | `requests.delete(...)` — `trade.py:451` |
| `set_deal_pnl_config` | `trade.py:491` | `requests.post(...)` — `trade.py:524` |
| `set_account_pnl_config` | `trade.py:532` | `requests.patch(...)` — `trade.py:563` |
| `close_deal` | `trade.py:571` | `requests.post(...)` — `trade.py:587` |
| **`deposit_derivative_margin`** | `trade.py:595` | `requests.post(...)` — `trade.py:631` |
| **`withdraw_derivative_margin`** | `trade.py:639` | `requests.post(...)` — `trade.py:675` |
| `place_conditional_order` | `trade.py:748` | `requests.post(...)` — `trade.py:794` |
| `cancel_conditional_order` | `trade.py:883` | `requests.patch(...)` — `trade.py:900` |

Đối chiếu contract đã cam kết ở chính repo — `vnbroker/broker/security/guards.py:4-6`:
```
RULE: Mọi write method trong broker lane PHẢI được decorate với @write_gate.
      Không có exception; không được bypass bằng cách truyền dry_run=False
      khi session chưa is_write_enabled.
```
`connector/dnse` **vi phạm tuyệt đối**, và đây là **đường tiền thật**: `withdraw_derivative_margin` chuyển tiền ra khỏi tài khoản chỉ cần `self.token` + `otp` là chạy.

**Tệ hơn:** `DNSEClient`/`OrderService` có `dry_run` param nhưng **default `False`** — mặc định là **gửi thật**:
- `client.py:198-206` `def post_order(self, market_type, payload, trading_token, order_category="NORMAL", dry_run: bool = False, raw: bool = False)`
- `order_service.py:92` `dry_run: bool = False` → `post_order`
- `order_service.py:88` `dry_run: bool = False` → `put_order`
- `order_service.py:132` `dry_run: bool = False` → `cancel_order`
- `order_service.py:152` `dry_run: bool = False` → `replace_order`
- `position_service.py` `close_position` — cùng pattern

Trong khi `broker/ssi` + `broker/tcbs` đặt `dry_run: bool = True` ở **mọi** write. Đây là **trái ngược hoàn toàn với security posture** của lane còn lại.

**Fix:** `dry_run: bool = True` trên toàn bộ write của DNSE + `@write_gate`-equivalent + session write-state.

---

### P0-4 · WebSocket DNSE log **rò `api_key` + HMAC signature** (vĩnh viễn vào log file)

**File:** `vnbroker/connector/dnse/websocket.py:91-101`

```python
async def connect(self) -> None:
    """Establish WebSocket connection."""
    url = self._build_ws_url()
    logger.info(f"Connecting to DNSE WebSocket: {url}")   # ← url chứa credential
```

`_build_ws_url()` (`websocket.py:65-89`) nhúng credential vào **query string**:
```python
params = {
    "api_key": self._config.api_key,
    "date": date_value,
    "signature": signature_header,
    "version": self._config.api_version,
}
return f"{self.WS_BASE_URL}?{urlencode(params)}"
```
và `signature_header` (`core/signature.py:73-76`) chứa `keyId="{api_key}"`:
```python
signature_header = (
    f'Signature keyId="{api_key}",algorithm="{algorithm}",'
    f'headers="{headers_list}",signature="{signature}"'
)
```

→ `logger.info` in ra **`api_key` 2 lần** (param + trong signature) **và chữ ký HMAC**, ở level `INFO` (mặc định bật). Đây là credential đầy đủ để **forge request giả** cho tới khi nonce/date hết hạn.

Không có `Redactor` nào chạm vào connector lane (grep: `Redactor` chỉ dùng ở `broker/ssi/auth.py:102,128`).

---

## 2. P1

### P1-1 · `session.token` **tự hủy session** khi đọc → write bị chặn vĩnh viễn, không phục hồi được

**File:** `vnbroker/broker/session.py:113-131`

```python
@property
def token(self) -> str:
    with self._lock:
        if self.state in (SessionState.EXPIRED, SessionState.LOCKED, SessionState.REVOKED):
            raise BrokerSessionExpiredError("Session expired or revoked")
        if self.token_expires_at is not None:
            buffer = timedelta(seconds=self.TOKEN_REFRESH_BUFFER_SECONDS)  # 300s
            now = datetime.now(self.token_expires_at.tzinfo) if ... else datetime.now()
            if now >= (self.token_expires_at - buffer):
                self.state = SessionState.EXPIRED          # ← SIDE-EFFECT trong getter
                raise BrokerSessionExpiredError(
                    message="Token expired", code="SESSION_EXPIRED", http_status=401,
                )
```

**Getter có side-effect**: đọc token lúc còn **thật sự hợp lệ 4 phút** (`TOKEN_REFRESH_BUFFER_SECONDS = 300`) → vẫn set `state = EXPIRED`.

`TCBSAuthService.is_token_valid()` (`tcbs/auth.py:131-139`) chính là:
```python
def is_token_valid(self) -> bool:
    try:
        return self._session.token is not None
    except BrokerSessionExpiredError:
        return False
```
→ hàm "read-only kiểm tra" này **phá hủy session**. Sau đó `SSIAuthService.is_token_valid` (`ssi/auth.py:238-243`) y hệt, và nó là gate của `ensure_authenticated` (`auth.py:181`).

**Đã xác minh runtime** (`token_expires_at = now + 4min`):
```
state after set_token: authenticated_read
is_token_valid -> False (raised)
state AFTER a read-only validity check: expired
can_write() now: False
is_write_enabled now: False
--> write_gate will now raise BrokerPermissionError forever
enable_write FAILED: BrokerPermissionError Cannot enable write mode from state SessionState.EXPIRED.
real seconds remaining: 240
```

**Token còn 240 giây thật**, nhưng:
- `state = EXPIRED` **vĩnh viễn**
- `write_gate` (`guards.py:61`) → `session.is_write_enabled` = `False` → raise `BrokerPermissionError` **mọi lệnh đặt**
- `enable_write()` **không phục hồi được**: `session.py:97` chỉ cho phép từ `AUTHENTICATED_READ`
- `begin_authenticating()` (`session.py:63-74`) **không chặn `EXPIRED`** → có thể re-auth, nhưng `set_token` (`session.py:91`) reset về `AUTHENTICATED_READ` → **write bị tắt**, phải `enable_write()` lại

**Tác động:** gọi `is_token_valid()` (một call hoàn toàn vô hại, được expose public ở cả 2 client — `tcbs/client.py:110`, `ssi/client.py:159`) là **kill write capability** của session. Đây là đường tiền thật bị chặn bởi một lời gọi kiểm tra.

**Fix:** `token` getter **không được mutate state**; tách thành `_check_expiry()` read-only + `mark_expired()` tường minh; `is_token_valid()` dùng đường read-only; `enable_write()` cho phép hồi từ `EXPIRED` **nếu token còn hạn thật**.

---

### P1-2 · `IdempotencyStore` — **dead code**, không nơi nào gọi; và không thread-safe

**Files:** `vnbroker/broker/security/idempotency.py`, `security/__init__.py:4`

Xác minh:
```
$ grep -rn "IdempotencyStore\|idempotency" vnbroker/ --include=*.py | grep -v security/idempotency.py
vnbroker/broker/security/__init__.py:4:Populated in S2: credentials, redaction, audit, idempotency, guards.
vnbroker/broker/ssi/equity.py:91:    request_id: idempotency key; None → tự sinh nanoid 20 ký tự.
vnbroker/broker/tcbs/equity.py:18:  - request_id bắt buộc cho mọi write call (idempotency).
... (còn lại chỉ là docstring/comment/error message)
```
**Không có import hay call site nào.** Đây là guard chống duplicate-order được viết đầy đủ (TTL purge, in-flight vs completed marker) rồi **không đấu vào bất kỳ write path nào**.

Idempotency hiện chỉ dựa **hoàn toàn** vào việc caller truyền `request_id` — `tcbs/equity.py:975-979` chỉ check "không rỗng", `ssi/equity.py:100` còn **tự sinh** (xem P0-2).

Ngoài ra store **không có lock** (`idempotency.py:19` tự thừa nhận):
```python
Thread-safety: single-thread assumption trong alpha.
```
`check_and_store` là check-then-act (`if key in self._store: ... self._store[key] = ...`, dòng 41-45) → race window. Probe 20 thread cùng key ra `allowed 1 time(s)` — **may mắn do GIL**, không phải do thiết kế. Trên CPython có `-X no_gil`, PyPy, hoặc khi thêm I/O, 2 thread có thể cùng nhận `True`.

---

### P1-3 · DNSE ký HMAC **không phủ body, không phủ query** → không chống được tamper

**File:** `vnbroker/connector/dnse/core/signature.py:26-50`

```python
def build_signature(secret, method, path, date_value, algorithm, nonce=None, header_name="X-Aux-Date"):
    header_key = header_name.lower()
    headers = f"(request-target) {header_key}"
    signature_string = (
        f"(request-target): {method.lower()} {path}\n{header_key}: {date_value}"
    )
    if nonce:
        signature_string += f"\nnonce: {nonce}"
    mac = hmac.new(secret.encode("utf-8"), signature_string.encode("utf-8"), _digest_for_algorithm(algorithm))
```

String-to-sign chỉ gồm **method + path + date + nonce**. **Không có body, không có query string.**

**Đã xác minh:** signature cho hai request khác body là **giống hệt nhau** (`sig_a == sig_b → True`).

**Tác động:** bất kỳ thay đổi nào trên **body lệnh** (`quantity`, `price`, `side`, `accountNo`, `loanPackageId`) hoặc **query** (`marketType`, `orderCategory`) đều **giữ nguyên signature hợp lệ**. MITM/proxy đã can thiệp TLS, hoặc bất kỳ code nào trên đường đi, có thể sửa lệnh mà không phá chữ ký. Với `post_order` (`order_service.py:94-101`, body = `payload` chứa `quantity`/`price`) đây là **sửa khối lượng/giá lệnh**.

*(Lưu ý: có thể đây là spec chính thức của DNSE — nhưng khi đó **thuộc tính bảo mật thực sự của chữ ký chỉ còn = chống replay**, và phải được ghi nhận là chấp nhận rủi ro, không phải là "có verify chữ ký".)*

---

### P1-4 · `Redactor` hở `trading-token`, `passcode`, `signature` — secret lọt qua audit log

**File:** `vnbroker/broker/security/redaction.py:13-47` + `97-108`

`SENSITIVE_KEYS` **không chứa** các key sau (đã xác minh runtime):
```
  'trading-token'        sensitive=False
  'tradingToken'         sensitive=False
  'X-Signature'          sensitive=False
  'signature'            sensitive=False
  'passcode'             sensitive=False
  'otpCode'              sensitive=False
  'smart-otp'            sensitive=False
  'challengeId'          sensitive=False
```

`redact_headers` (`redaction.py:96-108`) chỉ so khớp **đúng** `"authorization"`:
```python
if isinstance(k, str) and k.lower() == "authorization":
    result[k] = Redactor.REDACTED
else:
    result[k] = v          # ← mọi header khác đi nguyên
```

**Đã xác minh runtime:**
```python
Redactor.redact_headers({"X-Signature":"abc","x-api-key":"k","trading-token":"tt","Authorization":"Bearer x"})
→ {'X-Signature': 'abc', 'x-api-key': 'k', 'trading-token': 'tt', 'Authorization': '***REDACTED***'}
```

**Tác động:**
- `trading-token` là credential **đặt lệnh thật** ở DNSE (`order_service.py:99,121,141,164`) → rò nó là rõ khả năng đặt lệnh.
- `x-api-key` + `X-Signature` rò → forge request (xem P0-4).
- `passcode` (OTP) lọt qua `redact_dict` → `TokenService.create_trading_token` (`token_service.py:17`, `body={"otpType":..., "passcode":...}`).

---

### P1-5 · `TCBSClient._WSManager` **vỡ** với `websockets>=14` — mọi WebSocket của brokerage/tcbs chết ngay

**Files:** `vnbroker/brokerage/tcbs/client.py:176, 193`; `brokerage/base.py:316-325, 454-463`

Repo pin `websockets>=12.0` (`pyproject.toml:48`), **cài thật là 16.0**. Ba chỗ vỡ:

**(a) `extra_headers` đã bị đổi tên** → `client.py:176`
```python
self.websocket = await websockets.connect(url, extra_headers=headers)
```
**Đã xác minh runtime:**
```
connect params: ['uri','origin','extensions','subprotocols','compression','additional_headers',...]
extra_headers result: TypeError BaseEventLoop.create_connection() got an unexpected keyword argument 'extra_headers'
```
→ **`intratick_stream` và `order_updates_stream` chết ngay khi gọi `connect()`** — tức là **không có đường nào nhận được update trạng thái lệnh realtime**.

**(b) `websockets.exceptions` không resolve ở module level** → `client.py:193`
```python
except websockets.exceptions.ConnectionClosed:
    self.running = False
```
**Đã xác minh runtime:**
```
hasattr(websockets,'exceptions'): False
EXCEPT CLAUSE BROKEN -> AttributeError : module 'websockets' has no attribute 'exceptions'
```
→ **chính câu lệnh bắt lỗi lại ném `AttributeError`**, che mất lỗi gốc. Import đúng phải là `import websockets.exceptions`.

**(c) lifecycle close triệt tiêu nhau** → `base.py:316-317` + `client.py:454-458`
```python
# base.py BrokerageBase.close()
if self._ws_manager:
    self._ws_manager.close()          # ← _WSManager.close() là coroutine fn
```
```python
# tcbs/client.py TCBSClient.close()
def close(self):
    super().close()
    if self._ws_manager:
        asyncio.run(self._ws_manager.close())
```
**Đã xác minh runtime:**
```
aclose FAILED: AttributeError '_WSManager' object has no attribute 'aclose'
sync close() FAILED: RuntimeError asyncio.run() cannot be called from a running event loop
base.py:317: RuntimeWarning: coroutine 'TCBSClient._WSManager.close' was never awaited
```
→ `aclose()` gọi `self._ws_manager.aclose()` (`base.py:325`) nhưng `_WSManager` **không có** `aclose` (`dir()` xác nhận chỉ có `['_get_ws_token','_message_loop','_route_message','close','connect','subscribe']`) → **`aclose()` luôn ném `AttributeError`**. Sync `close()` **rò connection** vì coroutine không bao giờ được await.

**Không có reconnect nào:** `_message_loop` (`client.py:188-194`) chỉ set `running = False`, **không reconnect, không backoff, không resubscribe**.

---

### P1-6 · DNSE WebSocket: reconnect **đệ quy không giới hạn** + mất connection + backoff reset

**File:** `vnbroker/connector/dnse/websocket.py:213-234`

```python
async def _reconnect(self) -> None:
    """Attempt to reconnect with exponential backoff."""
    if self._reconnect_attempts >= self._max_reconnect_attempts:
        logger.error("Max reconnect attempts reached")
        self._running = False
        return
    self._reconnect_attempts += 1
    delay = self._reconnect_delay * (2 ** (self._reconnect_attempts - 1))
    logger.info(f"Reconnecting in {delay}s (attempt {self._reconnect_attempts})")
    await asyncio.sleep(delay)
    try:
        await self.connect()                    # ← connect() set _reconnect_attempts = 0
        for channel, symbols in self._subscriptions.items():
            if symbols:
                await self.subscribe([channel], list(symbols))
    except Exception as e:
        logger.error(f"Reconnect failed: {e}")
        await self._reconnect()                 # ← ĐỆ QUY
```

Ba lỗi:
1. **Đệ quy không chặn.** Mỗi lần `connect()` thất bại → `_reconnect()` đệ quy. Với `connect()` set `_reconnect_attempts = 0` (`websocket.py:103`) **trước** khi `websockets.connect` raise, guard `>= self._max_reconnect_attempts` (=5) **không bao giờ chạm tới** → đệ quy vô hạn cho tới khi `RecursionError` (~1000 frame ≈ 15 phút với delay 5→10→20→40→80s...). Delay thực tế ≈ `5+10+20+40+80+160+320+640+1280+...` giây.
2. **Backoff không reset đúng.** `connect()` reset counter → mỗi vòng "thành công rồi disconnect" lại bắt đầu từ delay 5s.
3. **Rò connection.** `disconnect()` (`websocket.py:106-112`) set `_running = False` rồi đóng, nhưng `run()` (`websocket.py:176-190`) đang ở `await self._ws.recv()` → nhận `ConnectionClosed` → **gọi `_reconnect()` dù user đã chủ động disconnect**. `connect()` lại set `_running = True` (`websocket.py:102`) → **hồi sinh connection sau khi user đã đóng**.
4. `_handle_message` giả định `data` là dict: `payload = data.get("data", {})` (`websocket.py:199`) — server trả list sẽ ném `AttributeError`.

---

## 3. P2

### P2-1 · DNSE `_digest_for_algorithm` fallback **SHA-1**, và case-sensitive
**File:** `connector/dnse/core/signature.py:16-23`
```python
    return hashlib.sha1     # ← fallback cho MỌI algorithm lạ
```
**Đã xác minh:** `unknown algo -> openssl_sha1`, và `"HMAC-SHA256"` (uppercase, hợp lệ theo chuẩn) → **`openssl_sha1`**. Typo config = silent downgrade SHA-256 → SHA-1, không cảnh báo.

### P2-2 · `trade.py` gửi header `Trading-Token: None` → `InvalidHeader` crash
**File:** `connector/dnse/trade.py:337-340`, `447-450`, `520-523`, `559-562`, `583-586`
```python
headers = {
    "Authorization": f"Bearer {self.token}",
    "Trading-Token": self.trading_token     # ← None nếu chưa get_trading_token()
}
```
**Đã xác minh:** `InvalidHeader: Header part (None) from ('Trading-Token', None) must be of type str or bytes`. Không guard trước → crash thay vì error rõ ràng.

### P2-3 · `trade.py` build URL không encode → **path/query injection**
**File:** `connector/dnse/trade.py:265-268`, `281-284`
```python
params_str = "&".join([f"{key}={value}" for key, value in query_params.items()])
url += f"?{params_str}"
```
**Đã xác minh:** `sub_account = "123&loanPackageId=999"` → `.../accounts/123&loanPackageId=999/ppse?symbol=VNM&price=10` — chèn thêm param. `sub_account` cũng đi thẳng vào path (`trade.py:125, 217, 254`) không `quote()`.

### P2-4 · `get_trading_token`: OTP nằm trong **dict key** (dict literal ternary)
**File:** `connector/dnse/trade.py:166-169`
```python
headers = {
    "Authorization": f"Bearer {self.token}",
    "smart-otp" if smart_otp else "otp": otp
}
```
Chạy được, nhưng **rất dễ đọc nhầm** và làm OTP nằm trong header thay vì body. Cùng pattern ở `deposit_derivative_margin:620-623`, `withdraw_derivative_margin:664-667`.

### P2-5 · `trade.py` lưu credential dạng **plaintext attribute** công khai
**File:** `connector/dnse/trade.py:24-28`
```python
self.token: Optional[str] = None
self.trading_token: Optional[str] = None
self._api_key = api_key
self._api_secret = api_secret
```
Public attribute, không `__repr__` redact (khác `TCBSCredentialConfig.__repr__` ở `credentials.py:38-45` và `BrokerSession.__repr__` ở `session.py:211-221` — 2 chỗ đó làm đúng). Bất kỳ `repr(trade_obj)`/log object/exception traceback nào cũng rò cả 4.

### P2-6 · `AuditSink`/`AuditRecord` — **dead code**, không audit trail cho lệnh
**File:** `broker/security/audit.py`
```
$ grep -rn "AuditSink\|AuditRecord" vnbroker/ --include=*.py | grep -v security/audit.py
(không có kết quả)
```
Module audit hoàn chỉnh (JSON structured, `propagate=False`, `make_record` factory) nhưng **không write path nào gọi**. Kết hợp P1-2 (idempotency dead) → **không có idempotency, không có audit trail** trên đường tiền thật.

### P2-7 · `redact_dict` bỏ sót `args_count`/`kwargs_keys` envelope khi có `pin_code` positional
**File:** `guards.py:48-57` — dry-run envelope chỉ trả `kwargs_keys` (tên, không giá trị) nên **không rò `pin_code`**. Ghi nhận là **đúng**; đưa vào đây để nêu rõ đã kiểm và không phải finding.

### P2-8 · `session.py:25` — import sai chỗ (code smell)
```python
from vnbroker.broker.exceptions import BrokerSessionExpiredError  # noqa: E402
```
`E402` bị suppress; `import threading` ở dòng 11 xen giữa `enum` và `datetime`. Vòng import trong `begin_authenticating:67` và `enable_write:100` cũng lặp lại. Không gây lỗi, nhưng làm khó đọc ở file trọng yếu.

---

## 4. P3 — Đã làm đúng (ghi nhận, không sửa)

1. **Không có `verify=False` / `ssl=False` / `CERT_NONE`** — grep toàn scope: **0 kết quả**. Tất cả TLS verify mặc định (đúng). `httpx.Client` (`base.py:163`) và `requests.Session` (`_transport.py:64`) không override.
2. **Không có secret hardcode.** Grep pattern `(api_key|api_secret|password|secret|token|private_key|otp)\s*=\s*["'][^"']{8,}["']` trên toàn scope → **0 kết quả**. Tất cả credential từ `os.getenv` (`credentials.py:64-69, 91-93, 154-155`; `tcbs/client.py:661-689`) hoặc constructor param.
3. **RSA signing đúng thuật toán.** `_signing.py:90-104`: PKCS#1 v1.5 DigestInfo prefix chuẩn SHA-256 (`_SHA256_DER_PREFIX`), padding `0x00 0x01 0xFF... 0x00 || DigestInfo`, `pow(m, d, n)`, check `pad_len < 8` → raise. `generate_request_id` dùng `os.urandom` + rejection sampling (không dùng `random`). Xem `nanoid` đúng thuật toán.
4. **Throttle SSI thread-safe, đã xác minh hoạt động đúng.** 4 thread × 3 call @10rps → `1.106s` (kỳ vọng ≥1.1s), gap đều `0.1004-0.1006s`. Lock nắm trọn critical section.
5. **`__repr__` redact đúng ở credential config + session.** `credentials.py:38-45, 134-144`; `session.py:211-221` (`_token={'REDACTED' if self._token else None}`).
6. **SSI auth log body đã redact.** `ssi/auth.py:102, 128` dùng `Redactor.redact_dict(body)` trước khi log.
7. **TCBS auth không log payload.** `tcbs/auth.py:69` — `# KHÔNG log payload — chứa api_key và otp`, và `_logger.warning` chỉ in `status` (dòng 98-101).
8. **`TCBSCredentialConfig.from_env` raise rõ ràng** khi thiếu key (`credentials.py:71-78`) thay vì để `api_key=""` chạy tiếp.

---

## 5. Khuyến nghị theo thứ tự ưu tiên

| # | Hành động | File:line | Effort |
|---|---|---|---|
| 1 | `dry_run: bool = True` cho **mọi** write DNSE + `@write_gate` | `connector/dnse/{trade,client}.py`, `services/order_service.py` | M |
| 2 | Bỏ retry tự động cho non-idempotent method; retry write chỉ khi tái dùng `request_id` | `broker/ssi/_transport.py:104-111` | S |
| 3 | `write_gate` bind signature thay vì đọc `kwargs` | `broker/security/guards.py:45-46` | S |
| 4 | `session.token` không mutate state; tách `mark_expired()` | `broker/session.py:113-131` | M |
| 5 | Xóa `logger.info(url)`; chuyển credential khỏi WS query string nếu DNSE cho phép header | `connector/dnse/websocket.py:94` | S |
| 6 | Fix `websockets>=14`: `additional_headers`, `import websockets.exceptions`, `aclose`, bỏ `asyncio.run` trong `close()` | `brokerage/tcbs/client.py:176,193`; `brokerage/base.py:316-325,454-463` | S |
| 7 | Thêm `trading-token`, `tradingToken`, `passcode`, `otpCode`, `signature`, `x-api-key`, `x-signature` vào `SENSITIVE_KEYS`; `redact_headers` dùng substring match | `broker/security/redaction.py:13-47, 96-108` | S |
| 8 | Nối `IdempotencyStore` + `AuditSink` vào mọi write path; thêm lock cho store | `broker/security/idempotency.py` | M |
| 9 | DNSE `_reconnect` → vòng lặp có giới hạn, tôn trọng `_running` | `connector/dnse/websocket.py:213-234` | S |
| 10 | Raise thay vì fallback SHA-1; `.lower()` cho algorithm | `connector/dnse/core/signature.py:16-23` | XS |

---

## 6. Phạm vi chưa phủ / hạn chế

- **Chưa verify:** DNSE OpenAPI spec thực tế (string-to-sign có phủ body không) — P1-3 ghi nhận **tín hiệu trong code**, cần đối chiếu tài liệu DNSE trước khi kết luận là lỗi spec vs lỗi cài.
- **Chưa đọc hết:** `broker/ssi/{market,money,portfolio,account,_enums,_utils}.py`, `broker/tcbs/{account,money,market,portfolio}.py`, `connector/dnse/services/{account,market,position}_service.py`, `connector/binance/client.py` (public market data, không auth), `broker/registry.py`. Đều là read-path hoặc pure-compute; không thấy dấu hiệu write trong grep. **Không khẳng định sạch** — chỉ khẳng định chưa đọc.
- **Không chạy network thật.** Mọi finding đều từ đọc code hoặc probe với mock/fake transport.
- **Không sửa code.** Báo cáo chỉ ghi nhận.