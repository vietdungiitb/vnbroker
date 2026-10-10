# PM + SYSTEM INSPECTOR — BÁO CÁO THỰC TRẠNG ĐỘC LẬP `vnbroker`

**Ngày:** 2026-10-09 · **Vai trò:** PM + System Inspector (audit độc lập, không sửa code)
**Phạm vi:** toàn bộ repo `C:\Mujoco Projects\vnbroker`, branch `dev`, `HEAD = 22d3d0a`
**Cơ sở:** codebase trên đĩa + thực thi thật. **Không** lấy tài liệu làm nguồn sự thật.
**Trạng thái sau audit:** `git status --short` = 0 dòng. Không sửa, không commit.

> **Cập nhật 2026-10-09 (sau audit):** PM-01 đã **sửa xong** (`12cb29c`, merge `8cb3e8e`) và
> `async_client.py` đã hạ xuống `minor`. Mục 11 ghi kết quả **live probe** với credential
> DNSE thật — 2 phát hiện mới, 1 nghi ngờ được giải tỏa, và 1 giới hạn quan trọng.
> Báo cáo gốc bên dưới giữ nguyên như bản gốc `22d3d0a`.

---

## 11. KẾT QUẢ LIVE PROBE (2026-10-09) — bổ sung sau báo cáo gốc

Owner cấp `DNSE_API_KEY` + `DNSE_API_SECRET` trong `.env` (chưa từng được commit — đã verify
619 commit lịch sử). Probe **chỉ read + WebSocket auth**: không `enable_write()`, không
method ghi. `.env` đọc bằng parser thuần vì `python-dotenv` chưa cài (xem C11).

### 11.1 Xác minh được — những thứ 1414 test server giả không bắt được

| Hạng mục | Kết quả thật |
|---|---|
| HMAC-SHA256 signature | ✅ sinh đúng, **không chứa `api_secret`** |
| WebSocket auth in-band | ✅ `authenticated=True`, `session_id=conn_1791515486322648579` |
| **`rate_limit` shape** | ✅ **ĐÚNG NHƯ DOC**: `{'messages_per_second': 100, 'subscriptions_max': 100}` |
| `capabilities` | ✅ `{action: auth_success, capabilities: {batch_delivery: False}, user_id: <jwt>}` |
| Subscribe + dữ liệu thật | ✅ **19 frame** trong 12s; giá bán ACB **20.3**, VNM **57.8**; ISIN, boardId, `multicastReceiveTime` thật |
| dry_run envelope | ✅ không lọt secret; `trading-token` → `***REDACTED***` |

**Kết luận quan trọng:** bản rewrite WebSocket `95f68e6` **hoạt động thật** — không chỉ khớp
tài liệu mà đã chạy với server thật và nhận dữ liệu thị trường. `rate_limit` là mục handoff
§3.2.1 ghi "chưa xác minh được" — nay đã đóng.

### 11.2 PHÁT HIỆN MỚI 1 (major) — `openapi.dnse.com.vn` không phản hồi

Đo 3 lần, cùng kết quả:

```
openapi.dnse.com.vn/accounts      -> timeout 15.002s   (3/3 lần, curl exit 28)
api.dnse.com.vn/user-service/api/me -> HTTP 401 trong 1.249s   (SỐNG)
ws-openapi.dnse.com.vn/v1/stream    -> HTTP 400 trong 1.220s   (SỐNG)
```

Không phải DNS (resolve OK, `103.151.242.24`), không phải firewall (TCP 443 mở), TLS bị
đóng ngay (`unexpected EOF`). Chỉ **một** host trong ba không trả lời.

**Hệ quả — nghiêm trọng hơn vẻ ngoài:**
1. **Toàn bộ OpenAPI surface (25 method) không kiểm chứng được từ máy này**, kể cả
   `post_order`, `close_position`, `create_trading_token`. Fix PM-01 chỉ được chứng minh
   bằng egress tripwire, **không** bằng server thật.
2. 25 method `api.dnse.com.vn` (legacy) — host này **đang sống** (401 = thiếu token, đúng
   như mong đợi), nhưng **SDK chính thức không hề nhắc tới**. Rủi ro path sai vẫn nguyên
   và **không ai có thể dò** từ phía này.
3. `send_email_otp` (không gate, chủ đích) cũng nằm trên host OpenAPI ⇒ **luồng đăng nhập
   OpenAPI không hoạt động từ Việt Nam** với code hiện tại.

**Câu hỏi cho Owner:** đây là DNSE chặn IP/geo từ VN, host đang down, hay credential này
thuộc môi trường nào đó? Trả lời quyết định có thể mở được tầng xác minh thứ 2 hay không.

### 11.3 PHÁT HIỆN MỚI 2 (minor, đã sửa) — `subscribe` im lặng với Mapping

Đây là **sai lầm của chính probe tôi**, và nó chỉ lộ ra vì tôi đọc output thay vì tin nó.
Lỗi gọi: `subscribe({"quote": ["ACB", "VNM"]})`. API thật là
`subscribe(channels: List[str], symbols: Optional[List[str]])` — tôi truyền dict nên
`symbols` = `None`. Frame gửi đi:

```json
{"action":"subscribe","channels":[{"name":"top_price.G1.json","symbols":[]}]}
```

Server trả:

```
{'action':'subscribed','channel':'top_price.G1.msgpack','status':'active','symbols':None}
```

⇒ **subscribe thành công, không exception, không cảnh báo, nhưng 0 symbol.** Người dùng
tưởng đang stream 2 mã và thực tế không nhận gì. `List[str]` không bắt được dict trong
Python thuần. Cùng loại lỗi: `subscribe("quote", [...])` bị tách thành 5 kênh một chữ.

**Đã sửa** (`test_subscribe_contract.py`, 9 test): validate ở `subscribe`/`unsubscribe`,
raise `TypeError` với **lời gọi đúng** trong message, và chặn trước khi gửi/ghi mirror nội bộ.

### 11.4 PHÁT HIỆN MỚI 3 (minor, đã sửa) — `msgpack` không khai báo dependency

`encoding="msgpack"` raise đúng (giữ nguyên chính sách **không fallback im lặng**), nhưng
`msgpack` không có trong `pyproject.toml` ⇒ người dùng phải tự đoán `pip install msgpack`.
**Đã sửa:** thêm extra `msgpack = ["msgpack>=1.0"]`, message nói rõ
`pip install "vnbroker[msgpack]"` và giải thích vì sao không fallback.

Ghi chú thiết kế: **không** import msgpack ở `__init__` — dựng client để xem URL/tên kênh
phải hoạt động không cần package. Lần đầu tôi raise ở `__init__`, làm hỏng 2 test có sẵn
(`test_msgpack_encoding_is_reflected_in_the_url`, `test_channel_name_follows_the_encoding`)
vì chúng dựng client msgpack chỉ để kiểm protocol. Đã ghi nhận và đảo lại.

### 11.5 NGHI NGỜ ĐƯỢC GIẢI TỎA — `subscriptions_max` tính theo SỐ KÊNH

Báo cáo gốc §4.2 nghi ngờ `websocket.py:582` so `len(wire)` (số kênh) trong khi server có
thể tính theo **số cặp** (kênh × symbol). **Đo thật: server tính theo số KÊNH.**

| subscribe | channels | pairs | server |
|---|---|---|---|
| 1 kênh × 120 symbols | 1 | 120 | `active` |
| 2 kênh × 60 symbols | 2 | 120 | `active` |
| 5 kênh × 100 symbols | 5 | **500** | `active` ×5 |

500 pairs trong khi `cap = 100` vẫn OK ⇒ `websocket.py:582` **đúng**. Nghi ngờ **không
thành finding**. Đóng mục handoff §3.2.7.

### 11.6 Vẫn CHƯA xác minh được

| Nội dung | Vì sao |
|---|---|
| 25 method OpenAPI bất kỳ | `openapi.dnse.com.vn` không phản hồi (§11.2) |
| 25 method legacy `api.dnse.com.vn` | Host sống nhưng cần `DNSE_USERNAME`/`PASSWORD` + OTP để có token |
| msgpack binary frame thật | Extra mới khai báo, `msgpack` chưa cài trong `.venv` |
| `MAX_DURATION_EXCEEDED` + close 1008 | Cần chạy liên tục 8 giờ |
| Conditional orders | Cần trading token thật |

### 11.7 Ba lỗi của probe — ghi lại để không ai tin nhầm

Cả ba đều là lỗi **của tôi**, phát hiện trước khi báo cáo, và là lý do "ACCEPTED" xuất hiện
trong một lần chạy là **kết quả giả**:

1. Dùng sai signature `__init__` (nhận `DNSEConfig`, không nhận `api_key=`).
2. Không `await subscribe()` — coroutine không bao giờ chạy, nên "ACCEPTED" nghĩa là
   *client không từ chối*, **không** phải *server chấp nhận*. Đã chạy lại với `await`.
3. Truyền dict vào `channels` → `symbols` rỗng; tưởng là bug code, hoá ra lỗi probe.

Hai "phát hiện" (`connect()` trả `False`, `ws.url` không tồn tại) **không phải bug**:
`connect()` khai báo `-> None` đúng thiết kế (raise khi thất bại), `ws.url` không phải API
công khai. Đã bỏ khỏi báo cáo.

---

## 0. TÓM TẮT 5 PHÁT HIỆN NGHIÊM TRỌNG NHẤT

1. **`blocker` — P0 write gate của DNSE vòng qua được bằng 1 dòng code hợp lệ.** `Trade.as_openapi_client()`
   (`vnbroker/connector/dnse/trade.py:93-99`) là method **public** trả về `DNSEClient` — object **không có**
   `_write_enabled`/`enable_write`. Tôi đã **tự chạy lại** và đo được **6 request tiền thật** (POST đặt lệnh,
   PUT sửa lệnh, DELETE huỷ, POST đóng vị thế, PATCH, POST cấp token) **với gate đang TẮT**.
   ⇒ Commit `eeb1965` vá 10/10 method trên `Trade` là đúng, nhưng đặt gate ở **sai tầng**.
   **[ĐÃ SỬA 2026-10-09 — xem §11 và commit `12cb29c`]**

2. **`major` — Rò credential thật trong 3 file docs được track.** Số tài khoản TCBS 11 chữ số + 8 hex ký tự
   đầu API key (`TCBS_AUTH_TOKEN`) nằm trong `docs/TCBS_CONNECTION_TEST_REPORT.md:11`,
   `docs/CENTRAL_MODIFIED_FILES_AUDIT.md:23`, `docs/TCBS_INVESTMENT_DATA_DESIGN.md:132,235,249,265`.
   Cần **rotate key** trước khi purge file.

3. **`major` — `BrokerSession.__repr__` in nguyên văn `api_key`** (`vnbroker/broker/session.py:215`),
   trong khi `_token` ngay dòng sau (`:218`) lại redact. Mâu thuẫn nội bộ với `credentials.py:41` đã redact.

4. **`major` — Hệ thống có 4 chính sách failover, không phải 2.** `should_failover`
   (`source_router.py:357-391`) thiếu `RuntimeError`/`ValueError`/`json.JSONDecodeError` so với
   `bulk_router.PROVIDER_ERRORS` (`bulk_router.py:69-76`). Đo thực thi: provider trả HTML lỗi ⇒
   **không failover** ở đường single trong khi đường bulk vẫn chạy.

5. **`major` — `mypy vnbroker --strict` là NO-OP, `pyproject.toml` ghi sai.** Cả hai lệnh cho **1207 lỗi y hệt**.
   Comment `pyproject.toml:146` "global --strict is NOT enabled here" **sai thật**: `strict=true` trong
   `[[tool.mypy.overrides]]` (`pyproject.toml:152-159`) bị mypy nâng thành global.

---

## 1. GATE BASELINE — CHẠY THẬT, EXIT CODE THẬT

Lệnh chạy tại `22d3d0a`, venv `Python 3.13.14 / ruff 0.16.9 / mypy 1.20.2 / pytest 9.0.2`.

| Gate | Lệnh | Kết quả | Exit |
|---|---|---|---|
| Test toàn bộ | `pytest tests/ -q --timeout=300` | **1414 passed, 30 skipped** (185.6s) | **0** |
| Lint scope hẹp | `ruff check vnbroker tests/unit tests/contract` | All checks passed | **0** |
| Lint toàn bộ test | `ruff check tests --output-format=concise` | **13 errors** | **1** |
| Type check | `mypy vnbroker` | 1207 errors / 119 files | **1** |
| Type check "strict" | `mypy vnbroker --strict` | 1207 errors (**y hệt**) | **1** |

**Số liệu handoff sai 2 chỗ** — cần sửa trong `docs/`:

| Handoff ghi | Thực tế | Lệnh kiểm lại |
|---|---|---|
| "Ruff toàn bộ `tests/` để **8** lỗi F401/F841" (§3.5.1) | **13 lỗi** | `ruff check tests --output-format=concise` |
| "32 method dùng host `api.dnse.com.vn`" (§1.3) | **25 method** | AST scan `self._api_base_url` |

Nguy cơ: session sau chạy lại sẽ tưởng **mình vừa thêm 5 lỗi mới** ⇒ mất thời gian điều tra không có.

---

## 2. ĐÁNH GIÁ 3 COMMIT ĐỘI CODE VỪA LÀM

**Kết luận: làm thật, làm đúng phần lớn, nhưng cả 3 đều có khoảng trống mà báo cáo của họ không nêu.**

| Commit | Handoff khai | Xác minh độc lập | Verdict |
|---|---|---|---|
| `eeb1965` | 10 method tiền thật qua `_require_write` | **Đúng 10/10.** AST đọc từ `git show eeb1965~1`: 10 method money **không gate** → nay gate. 5 method trước đó **không có tham số `dry_run`** (`NO_PARAM`) — khớp handoff | Đúng, nhưng **thiếu 1 tầng** |
| `b505766` | 4 lỗ hổng rò credential + failover parity | Redaction fix **đúng và có bằng chứng**: replay bản cũ từ git cho thấy `X-Signature`, `smart-otp`, `Trading-Token` **không** được che; nay 5/5 header thật đều che. Failover parity: thêm `OSError` — **đúng, nhưng chỉ 1/4 nhóm lệch** | Đúng, **chưa đủ** |
| `95f68e6` | Viết lại WebSocket theo protocol provider | 8/11 điểm protocol đúng + có test khoá (chữ ký HMAC, nonce micro-giây string, `channels:[{name,symbols}]`, tên `tick.G1.json`, auth in-band). **3 điểm còn lại có lỗi** (mục 4.2) | Đúng phần lớn, **có 3 major** |

### 2.1 Điểm tốt — ghi nhận công bằng

- Bộ test `test_trade_write_gate.py:75-89` chặn `requests.Session.request` và assert **trên request ra ngoài**,
  không spy lên hàm guard. Đây là nguyên tắc đúng: **không tin tên hàm**.
- `test_every_declared_key_actually_matches` bắt được `smart-otp` còn sót **ngay lần sửa đầu tiên** —
  test tự tái hiện được lớp lỗi. Đây là test có giá trị thật.
- Handoff **tự thừa nhận** giới hạn: §3.2 ghi rõ "chưa có bằng chứng nào chạm server thật",
  §4 ghi lại quy tắc "commit trước, đo fail-before sau" sau 2 lần mất code. Đây là hành vi đúng.

---

## 3. FINDINGS — ĐỘC LẬP TOÀN DỰ ÁN

Severity cố định: `blocker` / `major` / `minor`. Mỗi mục có `file:line @ 22d3d0a`.

### 3.1 Blocker

| ID | Vị trí | Thực tế | Tác động |
|---|---|---|---|
| **PM-01** | `vnbroker/connector/dnse/trade.py:93-99` + `connector/dnse/client.py` + `connector/__init__.py:11` | `as_openapi_client()` public trả `DNSEClient` không có gate. **Đo thật: 6 write request với gate TẮT** | Gate P0 vòng qua bằng đường hợp lệ |

**Output thô tôi tự chạy** (không phải con số báo lại):
```
Trade._write_enabled = False
as_openapi_client -> DNSEClient
has _write_enabled: False | has enable_write: False
  post_order             -> POST   https://openapi.dnse.com.vn/accounts/orders?marketType=X&orderCategory=NORMAL
  put_order              -> PUT    https://openapi.dnse.com.vn/accounts/X/orders/X?marketType=X
  cancel_order           -> DELETE https://openapi.dnse.com.vn/accounts/X/orders/X?marketType=X
  close_position         -> POST   https://openapi.dnse.com.vn/positions/X/close?marketType=X
  replace_order          -> PATCH  https://openapi.dnse.com.vn/accounts/X/orders/X?marketType=X
  create_trading_token   -> POST   https://openapi.dnse.com.vn/registration/trading-token
TOTAL WRITE REQUESTS VIA PUBLIC PATH WITH TRADE GATE OFF = 6
```

**Đề xuất:** đưa `_write_enabled` xuống `DNSEClient` (tầng thấp nhất, không bypass được),
hoặc cho `DNSEHttpClient.request` nhận cờ `write` và raise nếu verb ∈ {POST,PUT,PATCH,DELETE} mà không cờ.

### 3.2 Major

| ID | Vị trí | Thực tế | Tác động |
|---|---|---|---|
| **PM-02** | `docs/TCBS_CONNECTION_TEST_REPORT.md:11` · `CENTRAL_MODIFIED_FILES_AUDIT.md:23` · `TCBS_INVESTMENT_DATA_DESIGN.md:132,235,249,265` | Số TK TCBS + 8 hex đầu `TCBS_AUTH_TOKEN` thật, trong **file đang được track** (xác minh `git ls-files`) | PII tài chính + tiền tố credential |
| **PM-03** | `vnbroker/broker/session.py:215` | `api_key={self.api_key!r}` nguyên văn; `:218` `_token` lại redact | Rò vào log/traceback/print |
| **PM-04** | `vnbroker/core/source_router.py:357-391` vs `bulk_router.py:69-76` | `should_failover` thiếu `RuntimeError`/`ValueError`/`json.JSONDecodeError` | Provider trả HTML lỗi ⇒ **không failover** ở đường single |
| **PM-05** | `vnbroker/common/data.py:330-334` | `_call_with_fallback` chỉ fallback khi `source != self.source`; trên primary `raise` **mọi** exception | `Listing`/`Company`/`News`/`Finance`/`Trading`/`Screener` mất fallback dù `FALLBACK_MAP` có cấu hình |
| **PM-06** | `pyproject.toml:146` vs `:152-159` | `mypy vnbroker --strict` **y hệt** `mypy vnbroker` (1207 = 1207). Comment "NOT enabled here" sai | `CLAUDE.md:7,255` mô tả sai; gate `check_mypy_baseline.py` yếu hơn tưởng |
| **PM-07** | `vnbroker/core/health_store.py:119-130` + `source_router.py:148` | `save()` không `DELETE`; dòng `failures>0` không bao giờ bị xoá | Provider đã hồi phục lại vào cooldown sau **mỗi** lần restart |
| **PM-08** | `CLAUDE.md:31-33` vs `common/data.py:740` | Doc nói `_normalize_quote_result` là "single enforcement point"; `history` thực tế gọi `core/utils/normalizer.py:55` — **hai bản sao** | Sửa một bên không sửa bên kia |
| **PM-09** | `api/bulk.py:40` · `base.py:160-162` · `api/quote.py:132,183,221` | 5 đường trả DataFrame **không** gọi `Normalizer` | `BulkAPI` + `BaseAdapter(source='AUTO')` vi phạm hợp đồng tz-aware |
| **PM-10** | `pyproject.toml:2` | `requires = ["setuptools>=42"]` nhưng dùng PEP 639. Build với `setuptools==76.0.0` → `ValueError` | Người dùng build từ sdist với môi trường cũ sẽ fail không giải thích được |
| **PM-11** | `vnbroker/analytics/indicators.py:11` | `import numpy as np` nhưng **không khai báo numpy** | Lỗi runtime cho người dùng nếu pandas đổi chính sách |
| **PM-12** | `.github/workflows/*.yml` | **74 commit** merge vào `dev` từ 2026-10-02 không có gate nào chạy. Nguyên nhân: billing (`"spending limit needs to be increased"`), không phải config sai | `ruff` + `pytest tests/contract` (2 gate blocking duy nhất) **chưa từng chạy**. Merge không có chặn |

### 3.3 Minor (chọn lọc)

| ID | Vị trí | Thực tế |
|---|---|---|
| PM-13 | `websocket.py:490-495` | `connection_expired` log `"reconnecting"` nhưng **không có code reconnect** — phiên 8h chết im lặng. Test `:447` khoá lại hành vi sai |
| PM-14 | `websocket.py:365-366, 645-688` | `connect()` tạo task mà không cancel bản cũ ⇒ đo được **8 task sống** sau 3 reconnect (đúng là 2) |
| PM-15 | `websocket.py:379-380, 437` | `except Exception` **không bắt** `CancelledError`; `AUTH_FAILED` sau khi đã auth bị nuốt ⇒ client còn `is_authenticated=True` với credential đã thu hồi |
| PM-16 | `broker/security/guards.py:44-58` vs `brokerage/guards.py:167-185` | 2 cơ chế gate cùng mục đích, hành vi lệch: `write_gate` **không** validate signature (thiếu `dry_run` ⇒ method chết cứng, im lặng), `guarded_write` thì chặn ngay lúc import |
| PM-17 | `redaction.py:15-23` + `brokerage/guards.py:40-54` | `X-TCBS-APIKEY`, `X-TCBS-SIGNATURE`, `consumer_id` **không** được che. HMAC signature TCBS tái dùng được để ký |
| PM-18 | `core/utils/cache.py:153-154` | `_MAX_DEPTH=6` ⇒ mọi dict ≥7 tầng dùng chung key ⇒ trả nhầm dữ liệu |
| PM-19 | `source_router.py:150-151, 97-98` | `except: pass` nuốt lỗi ghi/đọc state **không log** ⇒ mất cooldown, không chẩn đoán được |
| PM-20 | `core/registry.py:210-217` | `clear()` là public API không scope, xoá registry toàn cục (gốc rò của bug `42f3548`) |
| PM-21 | `MANIFEST.in:1-11` + `vnbroker.egg-info/SOURCES.txt` | sdist **không tất định**: build trên cây có egg-info ⇒ kèm `tests/test_acb_all_providers.py` (script gọi mạng thật); xoá egg-info ⇒ sạch |
| PM-22 | `scripts/check_dist_contents.py:140` | `print()` tiếng Việt ⇒ `UnicodeEncodeError` trên cp1252, **exit 1 dù artifact sạch** |
| PM-23 | `.gitignore:110` | Chỉ có `.env`, thiếu `.env.local`, `.env.production`, `*.env` |
| PM-24 | 12 file >800 dòng | `common/data.py` **1876** · `connector/dnse/trade.py` 1344 · `kbs_mappings.py` 1304 · `parser.py` 1106 · `transform.py` 1056 · +7 file nữa. **12.717 dòng = 23.7% codebase** |
| PM-25 | `core/settings.py`, `core/exceptions.py`, `common/indices.py` | 38 hàm + 20 class module-level **không nơi nào gọi** (gồm 7 exception class) |

---

## 4. PHẦN CÒN DANG DỞ CỦA ĐỘI CODE — ĐÁNH GIÁ LẠI

### 4.1 P0 — `async_client.py` TokenBucketRateLimiter trùng lặp (claim `leader-t2-policy` = `partial`)

**Đánh giá của handoff: P0. Đánh giá của tôi: `minor`, và handoff đã đánh giá quá cao.**

Tôi đã đọc cả hai bản và chạy probe:

```
async variant : rpm=300 enabled=True capacity=300
std  variant signature: (self, rate: float, capacity: Optional[float] = None)
async variant signature: (self, rpm: 'int' = 500)
rpm=0 -> enabled: False
async _acquire_token có bounded wait: False
std  wait có max_wait: True
```

| | `core/utils/rate_limiter.py` (SSOT) | `core/utils/async_client.py:34` (trùng) |
|---|---|---|
| API | `rate` (per **second**), `capacity` tùy chọn | `rpm` (per **minute**), đơn vị khác |
| Bounded wait | **Có** — `max_wait=30.0`, raise `TimeoutError` | **Không** — `while True: await asyncio.sleep(...)` |
| Lỗi | 0 | 0 |

**Vì sao không phải P0:** bản async **không bao giờ** treo vô hạn trong cấu hình hiện tại —
`capacity = rpm = 300`, `_refill_rate = 5/s`, nên luôn có token sau tối đa 0.2s. `rpm=0` thì `_enabled=False`
và `__aenter__` return ngay. Đây là **nợ kỹ thuật + rủi ro tương lai**, không phải lỗi đang nổ.

**Đề xuất PM:** hạ xuống `minor`. Sửa kiểu **một slice nhỏ, không cần claim P0**. Ràng buổc:
giữ `__aenter__`/`__aexit__` (nếu không, `async_client.py:360` sẽ `AttributeError` ngay) và
giữ bounded wait (`asyncio.wait_for`) để không biến thành chặn vô hạn.

**Cũng lưu ý:** `docs/CLAIMS.md:34` ghi `leader-t2-policy` chưa làm `tests/unit/core/test_rate_limiter.py` —
nhưng file **đã tồn tại** (174 dòng, 15 test, từ commit `b2f43ff`). Ghi chú claim sai;
việc còn lại chỉ là hợp nhất trong `async_client.py`.

### 4.2 P1 — Chưa xác minh runtime (DNSE/SSI/TCBS server thật)

Handoff nêu 6 mục. **Tôi xác nhận mục 1-5 là đúng** — không có bằng chứng nào trong repo chạm server thật.

**Bổ sung 1 mục handoff chưa nêu — có rủi ro thật:**
`websocket.py:582` so `subscriptions_max` với `len(wire)` = **số kênh**. Nếu server tính trần theo
**số cặp (kênh × symbol)**, thì 2 kênh × 100 symbol = 200 subscription nhưng code coi là 2 ⇒ **vượt trần thật**.
Cần xác nhận từ doc/server — đây là loại lỗi "gate có vẻ đúng nhưng đo sai thứ cần chặn".

**Ưu tiên P1 thực tế (nếu Owner cấp credential):**
1. `POST /accounts/orders` — xác nhận gate chặn **ở tầng `DNSEClient`** sau khi sửa PM-01
2. `rate_limit` shape + `subscriptions_max` (kênh hay cặp?)
3. 25 method `api.dnse.com.vn` — SDK chính thức **không hề nhắc**, rủi ro endpoint sai cao nhất
4. msgpack binary frame
5. `MAX_DURATION_EXCEEDED` + close code 1008

### 4.3 P2 — A6: 22 endpoint thiếu + `match_type` enum

Đồng ý với quyết định **cố ý hoãn** của team. Lập luận đúng: thêm `reverse_position` (đảo vị thế)
lúc này = thêm endpoint tiền thật chưa có gate.

**Nhưng thứ tự phải đảo:** hoãn cho tới khi có gate là hợp lý — **chỉ khi PM-01 đã sửa**. Nếu sửa theo thứ tự
ngược (thêm endpoint trước, vá gate sau), sẽ lặp lại đúng lỗi `eeb1965` vừa vá: vá 10 method thủ công,
1 tuần sau lại phát hiện 6 method nữa nằm ngoài tầm gate.

### 4.4 P3 — Housekeeping

Handoff nói "8 lỗi ruff có sẵn ở HEAD". **Thực tế 13 lỗi** (mục 1). Đề xuất: commit riêng dọn cả 13,
nếu không thì **không sửa số trong handoff** — sửa để session sau không điều tra nhầm.

---

## 5. BẢNG CONTRADICTIONS DOC vs CODE

| # | Doc nói | Code thật | Tác động |
|---|---|---|---|
| C1 | `CLAUDE.md:79-80` "indicators.py Currently empty" | **379 dòng**, 11 hàm, 8 test PASS | Agent tương lai làm lại việc đã xong |
| C2 | `CLAUDE.md:118,198` + `README.md:307` "1001 tests" | `pytest --collect-only` = **1441**; `tests/unit tests/contract` = 1343 | Stale 40%, sai cả scope (TCBS chỉ 224) |
| C3 | `CLAUDE.md:113` DNSE Company/Finance = `NotImpl` | Cả 3 **đã đăng ký**, trả **empty DataFrame có schema** (`explorer/dnse/company.py:291`) | Nguy hiểm hơn NotImpl: người dùng âm thầm tưởng "DNSE không có dữ liệu" |
| C4 | `CLAUDE.md:217` "**`dry_run=True`** default for all write" | `trade.py`: **25 method `dry_run=False`**, chỉ 4 là `True`. An toàn đến từ `enable_write()` | Claim an toàn **sai hướng** — đọc doc dễ tưởng mặc định là an toàn |
| C5 | `CLAUDE.md:15` "800 max" | **12 file vượt**, max 1876 | Quy tắc chết trong file hướng dẫn agent |
| C6 | `CLAUDE.md:31-33` `_normalize_quote_result` = single enforcement | `history` dùng `normalizer.py:55` — hai bản sao | Sửa một bên không sửa bên kia |
| C7 | `CLAUDE.md:255` `mypy vnbroker --strict` | Y hệt `mypy vnbroker` (1207=1207) | Cổng chặn không tồn tại |
| C8 | `COMPARE_DNSE_SDK.md:32` A5 "chưa xử lý" | Đã thêm `api_base_url` (`trade.py:23,33`) | File stale 6 commit; handoff lại dặn "đọc trước khi sửa DNSE" |
| C9 | `COMPARE_DNSE_SDK.md:41-45` A7 WS "sai ở mọi mặt" | Đã rewrite `95f68e6` | Đọc A7 hôm nay là đọc thông tin sai |
| C10 | `CLAUDE.md:212` "conftest loads `.env`" | `python-dotenv` **không khai báo**, `.venv` **chưa cài**, nuốt trong `except ImportError` | Tính năng âm thầm không hoạt động |

---

## 6. PHẦN ĐÃ LÀM TỐT (nói rõ để không bị sửa nhầm)

- **Write gate đã có ở cả 3 lane**, không chỉ DNSE: `broker/tcbs` + `broker/ssi` (`@write_gate`),
  `brokerage/tcbs` (`@guarded_write`), `connector/dnse` (`_require_write`). Đo thực thi:
  **60/60 probe = 0 request lọt**. Giả định ban đầu của tôi rằng "SSI/TCBS không có gate" **SAI** — đã bị dữ liệu bác bỏ.
- **Redaction fix có bằng chứng thật.** Replay bản cũ từ git cho thấy `X-Signature` + `smart-otp` in nguyên văn;
  nay che hết. Cơ chế `_norm_key` là nguồn duy nhất — **0 entry chết**.
- **Không có secret DNSE/SSI thật trong lịch sử git.** Scan 110 MB / 619 commit: `.env` chưa từng được track,
  327 nhóm khớp pattern đều là placeholder hoặc PNG base64 trong notebook.
- **Wheel sạch**: 217 entry, 0 hit trong 18 pattern nhạy cảm, không file >1 MB.
- **Không có test rỗng**: AST quét 451 test function — 1 assertion phủ định hợp lệ, 0 tautology, 0 skip vô điều kiện.
- **Token chỉ ở RAM**: `broker/` + `brokerage/` grep `pickle|sqlite3|shelve|keyring|open(` = 0 kết quả.
- **SSI private key không rò**: chuỗi `private_key` không xuất hiện trong bất kỳ log/exception nào.
- **Codebase sạch TODO**: 0 `TODO`/`FIXME`/`HACK`; chỉ 4 marker thật + 25 `NotImplementedError` có chủ đích.

---

## 7. BACKLOG ĐỀ XUẤT — XẾP THEO RỦI RO, KHÔNG THEO DOC

Thứ tự này **khác** handoff. Lý do: PM-01 là gốc, và 3 mục P1/P2 của handoff đều phụ thuộc nó.

| # | Việc | Mức | Vì sao ở đây |
|---|---|---|---|
| 1 | **PM-02** rotate TCBS API key, **rồi** purge 3 file docs | blocker | Rotate trước — purge trước thì 8 hex đã public, sửa file không còn tác dụng |
| 2 | **PM-12** khôi phục CI (billing / self-hosted runner) + branch protection | blocker | 74 commit không gate. **Mọi việc khác đều vô nghĩa khi merge tự do** |
| 3 | ~~**PM-01** đưa write gate xuống `DNSEClient`~~ | ~~blocker~~ | **XONG 2026-10-09** (`12cb29c` / `8cb3e8e`). Gate chuyển xuống `DNSEHttpClient.request`, quyết định theo HTTP verb. 6 request lọt → **0**. Breaking change: `DNSEClient` cần `enable_write()` |
| 3b | **PM-26** (mới, §11.2) làm rõ `openapi.dnse.com.vn` không phản hồi | major | Chặn **toàn bộ** xác minh OpenAPI. Cần Owner trả lời: chặn geo/IP, host down, hay credential thuộc môi trường nào |
| 3c | **PM-03** redact `api_key` trong `BrokerSession.__repr__` | major | 1 dòng, PII |
| 3d | **PM-17** thêm `X-TCBS-*`/`consumer_id` vào `SENSITIVE_KEYS` | major | HMAC signature tái dùng được |
| 3e | **PM-04 + PM-05** 4 chính sách failover → 1 | major | Đo được bằng thực thi, không tranh luận |
| 3f | **PM-10 + PM-11** `setuptools>=77`, khai báo `numpy` | major | Sửa `pyproject.toml`, 10 phút, không đụng code |
| 3g | **PM-22** fix encoding `check_dist_contents.py` | minor | Đang báo đỏ giả ⇒ mất niềm tin vào gate |
| 9 | Sửa 5 số liệu sai trong handoff (§1) + 10 contradictions §5 | minor | Rẻ, ngăn session sau điều tra nhầm |
| 10 | P3 dọn 13 lỗi ruff (commit riêng) | minor | |
| 11 | **PM-14 + PM-15** WebSocket task leak + `CancelledError` | major nhưng **chưa tới** | Cần test trước; hiện 0 test chạm `_reconnect` |
| 12 | P1 runtime verification | blocked | Cần credential thật — **việc của Owner, không phải của đội code** |
| 13 | P2 22 endpoint + `match_type` enum | **đã hoãn, giữ nguyên** | Điều kiện mở: PM-01 xong |

---

## 8. KIẾN NGHỊ VỀ QUY TRÌNH

**Không có protocol file** (`docs/AGENT_PROTOCOL.md` không tồn tại). `CLAIMS.md:3-6` tự ghi:
*"`worktree` chưa bật (mọi agent dùng chung working directory)"*. Hậu quả đo được:

- **9 worktree còn sót** trong `%TEMP%\opencode\` (`t1-bulk`, `t1-failover`, `t1-fixes-bulk`,
  `t1-fixes-cache`, `t1-netpool`, `t2-policy`, `t2-secrecy`, `t2-trade`) — tổng 3 branch `feat/t2-*`
  đã merge nhưng **chưa dọn**. 9 worktree × source tree = nhiễu cho mọi lần đo LOC/file-size sau này.
- Toàn bộ claim ghi `branch = dev` — **commit thẳng vào nhánh tích hợp**, không có điểm merge,
  không review được. Đây là vi phạm nguyên tắc "integration branch gets no direct commits".
- `docs/CLAIMS.md:51-53` trỏ tới script ở đường dẫn Hermes cục bộ — **không tồn tại trong repo này**
  ⇒ kiểm chồng lấn **không chạy được**. Claim registry hiện không có cơ chế thật sự ngăn chồng file.

**Đề xuất 3 việc, không tốn nhiều thời gian:**
1. Dọn 9 worktree đã merge (kiểm tra không có commit chưa push trước — `check-worktree-safety.cjs` có sẵn).
2. Tạo `docs/AGENT_PROTOCOL.md` + bật worktree trước đợi agent sau.
3. Đưa `scripts/check_*.py` (đã có 3 script chạy thật) vào một entrypoint `scripts/check_all.ps1`
   để 1 lệnh = toàn bộ gate, thay vì phải nhớ 4 lệnh rời rạc.

---

## 9. CHƯA XÁC MINH ĐƯỢC

| Nội dung | Lý do |
|---|---|
| **Toàn bộ hành vi với server DNSE/TCBS/SSI thật** | Đã thử với credential DNSE thật 2026-10-09. **WebSocket xanh hoàn toàn** (§11.1). OpenAPI **không** — host không phản hồi (§11.2). TCBS/SSI vẫn chưa có credential |
| `rate_limit` shape, msgpack binary frame, `MAX_DURATION_EXCEEDED` | `rate_limit` **ĐÃ XÁC MINH** (§11.1). msgpack cần `pip install "vnbroker[msgpack]"` rồi chạy lại. `MAX_DURATION_EXCEEDED` cần chạy 8 giờ |
| `subscriptions_max` tính theo kênh hay cặp (kênh × symbol) | **ĐÃ XÁC MINH: theo số KÊNH** — 5 kênh × 100 symbols = 500 pairs vẫn `active` khi `cap=100` (§11.5). `websocket.py:582` **đúng**, nghi ngờ của báo cáo gốc không thành finding |
| 22 endpoint A6 có đúng như SDK không | Chưa clone `dnse-tech/openapi-sdk` để so |
| Dependency CVE | Chưa chạy `pip-audit`/`safety`/`bandit` (CI cũng chưa từng chạy) |
| Secret trong dangling git object | Chỉ quét `git log --all -p` (619 commit); chưa `git fsck` — nếu repo push public thì cần `filter-repo --analyze` |
| Coverage `tests/acceptance` + `tests/integration` | Chỉ đo `tests/unit tests/contract` = 58% |
| Lỗi mypy chênh 59 so với baseline 1266 | Không xác định cái nào là xoá có chủ ý, cái nào là regression bị nuốt |

---

## 10. PHỤ LỤC — LỆNH TÁI LẬP

```powershell
cd "C:\Mujoco Projects\vnbroker"
$py = ".\.venv\Scripts\python.exe"

git rev-parse HEAD                                   # 22d3d0a6c9e75020c8d1fdaadfd55b32dabbf39b
& $py -m pytest tests/ -q --timeout=300             # 1414 passed, 30 skipped  -> exit 0
& $py -m ruff check vnbroker tests/unit tests/contract   # exit 0
& $py -m ruff check tests --output-format=concise    # 13 errors            -> exit 1
& $py -m mypy vnbroker                               # 1207 errors          -> exit 1
& $py -m mypy vnbroker --strict                      # 1207 errors (y hệt)  -> exit 1

# fat file — dùng splitlines, KHÔNG dùng Measure-Object -Line (sai)
& $py -c "import pathlib;print(sorted(((len(p.read_text(encoding='utf-8').splitlines()),p.as_posix()) for p in pathlib.Path('vnbroker').rglob('*.py') if '__pycache__' not in str(p)),reverse=True)[:12])"

# PM-01 write gate bypass
& $py "$env:TEMP\opencode\audit-vnbroker\pm_verify_f01.py"

# claims overlap — đường dẫn trong CLAIMS.md KHÔNG tồn tại
git check-ignore -v .env.local                        # NOT IGNORED
Select-String -Path docs\*.md -Pattern "10000928344"   # 7 hit, file đang tracked
```

---

**Kết luận PM:** Dự án **không có blocker ngữ lý chức năng** — 1414 test xanh, 3 commit gần nhất làm
đúng phần lớn việc, không rò secret thật trong lịch sử git, wheel đóng gói sạch. Vấn đề không nằm ở
chất lượng code mà nằm ở **3 chỗ khác**: (a) hàng rào an toàn tiền thật được đặt ở tầng cao nên vòng qua được,
(b) **không có gate nào thực sự chạy** trong 74 commit qua, (c) tài liệu lệch code ở 10 chỗ — trong đó
`CLAUDE.md:217` mô tả sai hướng về an toàn. Ba việc đầu của backlog là đủ để chặn được rủi ro mất tiền thật.
