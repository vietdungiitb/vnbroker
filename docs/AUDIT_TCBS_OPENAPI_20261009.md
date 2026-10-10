# RÀ SOÁT THƯ VIỆN TCBS — đối chiếu `openapi-v1.0.0.json`

**Ngày:** 2026-10-09 · **Nguồn:** `openapi-v1.0.0.json` — *TCBS iFlash Open API* v1.0.0,
OpenAPI 3.0.3, server `https://openapi.tcbs.com.vn`, **48 endpoint**.

**Cách đo:** script Python parse `paths` của spec + AST parse mọi file `*tcbs*.py`
trong `vnbroker/` để trích path từ dict `_PATHS` và biểu thức nối chuỗi. Không đếm
tay, không regex thô.

---

## 0. Tóm tắt

| | |
|---|---|
| Endpoint trong spec | **48** |
| Path trong code TCBS | **54** |
| Khớp | **35** |
| Có trong spec, **chưa dùng** | **13** |
| Có trong code, **không có trong spec** | **19** — chưa xác minh được |

**Một phát hiện làm thay đổi đánh giá về TCBS:** code đang **từ chối** một chức năng
mà TCBS thực sự có, với lý do ghi trong docstring **sai sự thật**.

---

## 1. `[P0]` Lý do báo "không hỗ trợ" là **sai**

**Code nói** (`explorer/tcbs/quote.py:344-347` và `:421`):

```python
# TCBS iFlash OpenAPI does not support multi-day daily OHLC bars
raise NotImplementedError(
    "TCBS iFlash OpenAPI does not support historical daily/weekly/monthly OHLC bars. "
    "TCBS OpenAPI only provides intraday tick data for the current session. "
    "For historical daily/weekly/monthly OHLC data, please use source='VCI' or source='KBS' "
)
```

**Spec nói** (`/nyx/v2/stock/bars-long-term`):

> Get long-term OHLCV bars (day/week/month) for a ticker.
>
> | tham số | kiểu | bắt buộc |
> |---|---|---|
> | `ticker` | string | **true** |
> | `type` | string | **true** — `stock` \| `coveredWarr` \| `index` |
> | `resolution` | string | **true** — `D` (1 day), `W` (1 week), `M` (1 month) |
> | `to` | number | **true** — epoch seconds |
> | `countBack` | number | **true** — số nến lấy ngược từ `to` |

**Kết luận: TCBS CÓ daily/weekly/monthly OHLC.** vnbroker chưa nối, rồi ghi lý do
sai vào docstring và hướng người dùng sang VCI/KBS.

### Schema response — đã đúng shape Lớp A

```
{ ticker: string,
  data: [ { open, high, low, close, volume: number,
            tradingDate: string } ] }        # tradingDate = ISO 8601 UTC
```

So với `NORMALISATION_POLICY.md` §2.1 (`time, open, high, low, close, volume`):

| TCBS trả | → Cột chuẩn |
|---|---|
| `data[].open` | `open` |
| `data[].high` | `high` |
| `data[].low` | `low` |
| `data[].close` | `close` |
| `data[].volume` | `volume` |
| `data[].tradingDate` | `time` (ISO 8601 UTC → phải chuyển tz-aware `Asia/Ho_Chi_Minh`) |
| `ticker` | `symbol` (lớp B, giữ nguyên) |

### Còn `/nyx/v2/stock/bars`

Cùng shape, dùng cho nến phút/giờ — `resolution` tính **bằng phút** (`60` = nến 60 phút).
Có thể thay luôn đường tính từ `his/paging` hiện tại (`quote.py:443`).

### Điều kiện tiên quyết

Root `security: [{"bearerAuth": []}]` ⇒ **mọi** endpoint đều cần JWT, kể cả market data.
`quote.py:77` đã có `auth_token` và truyền xuống ⇒ điều kiện đủ để nối.

---

## 2. 13 endpoint trong spec, code chưa dùng

| Endpoint | Verb | Nhóm |
|---|---|---|
| `/nyx/v2/stock/bars` | GET | **OHLCV intraday** — xem §1 |
| `/nyx/v2/stock/bars-long-term` | GET | **OHLCV D/W/M** — xem §1 |
| `/ananke/v1/securities` | GET | Thông tin chứng khoán |
| `/api/v1/derivatives/contracts` | GET | Board giá phái sinh |
| `/tartarus/v1/putThroughSnaps` | GET | Dữ liệu put-through *(code có dùng — xem §4)* |
| `/hydros/v1/account/{accountNo}/pricing-policy` | GET | Chính sách giá vay |
| `/campaign-management/v1/margin/subscription/{accountNo}/addons/detail` | GET | Gói vay bổ sung |
| `/khronos/v1/cash/deposit/update` | POST | Nộp tiền ký quỹ |
| `/khronos/v1/cash/withdraw/update` | POST | Rút tiền ký quỹ |
| `/khronos/v1/order/condition/cancel` | POST | Hủy lệnh điều kiện (phái sinh) |
| `/physis/v1/stock/transfer` | POST | Chuyển nội bộ |
| `/gaia/v1/oauth2/openapi/token` | POST | Đổi API key → JWT |
| `/gaia/v1/oauth2/openapi/apikey/info` · `/extend` | POST | Hạn dùng / gia hạn API key |

⚠ **Cảnh báo về bảng này:** `/nyx/v2/stock/bars-long-term` chỉ nằm ở đây vì script
đếm path, **không** phải vì `quote.py` gọi nó ở chỗ khác bằng cách viết khác. Kiểm
tra trực tiếp: `explorer/tcbs/` chỉ tham chiếu `his/paging`, `bsa`, `bsa-ext`,
`bsa-month`, `tickerSnaps`, `tickerCommons`, `derivatives` — **không** có
`stock/bars`. Xem lại §4 trước khi kết luận.

---

## 3. 19 path trong code, không có trong spec 1.0.0

| Nhóm | Path |
|---|---|
| `erebos/v1` (5) | `/account/asset`, `/account/available-balance`, `/portfolio-asset`, `/portfolio-asset/token`, `/portfolio/stock/{accountNo}/statistic` |
| `erebos/v2` account (9) | `/accounts/{a}/asset`, `/available-balance`, `/deposit`, `/dividend`, `/orders/history`, `/orders/matching`, `/stock-statistic`, `/withdraw` |
| `erebos/v2` stop-limit (4) | `/order/stop-limit`, `/order/stop-limit/orders`, `/order/stop-limit/{id}`, `/order/stop-limit/{id}/cancel` |
| khác (1) | `/aion/v1/accounts`, `/aion/v1/accounts/{a}/orders/history` |

Tất cả tập trung ở `broker/tcbs/account.py` và `broker/tcbs/equity.py`.

**Chưa kết luận được là legacy hay sai.** Lý do:

- Token trong `.env` đã **hết hạn** ⇒ probe trả `401 {"code":"validate.token.error"}`.
- 401 chạy **trước routing** ⇒ không phân biệt được "path tồn tại" với "path không có"
  — đúng bài học đã gặp ở DNSE (`GET /accounts/orders` → 405 chứng minh route có,
  401 thì không chứng minh gì).
- Mốc thời gian thêm hỗn loạn: các path `erebos/v2` được **thêm vào** ở commit
  `38eec3a` (2026-09-22), **sau** commit `b9207fb "rewrite entire library with
  official iFlash Open API paths"` (2026-05-20). Nên chúng không phải tàn dư cũ chưa
  dọn — chúng là phần thêm mới, không có trong spec.

**Cần token còn hiệu lực để phân định.** Đề xuất: một script probe, gọi từng path
và ghi lại status; `404` = không tồn tại, `400`/`200` = tồn tại.

---

## 4. Đối chiếu chéo với Postman collection — và **hai lỗi của tôi**

Nguồn thứ hai: `tcbs-openapi-v1.0.0.postman_collection.json`, cùng phiên bản
*TCBS iFlash Open API v1.0.0*. Không phải bản sao của OpenAPI spec — nó có
**48 REST + 5 WebSocket**.

```
SPEC     : 48
POSTMAN  : 48 + WS: 5
CODE     : 54
```

### 4.1 Kết luận vững hơn cho 19 path "thừa"

**Cả hai tài liệu đều không có chúng.** Trước đây tôi chỉ có một nguồn phủ định
(spec) và phải ghi "chưa kết luận được". Giờ là hai nguồn độc lập cùng phủ định:

```
/aion/v1/accounts                                   broker/tcbs/account.py
/aion/v1/accounts/{accountNo}/orders/history        broker/tcbs/equity.py
/erebos/v1/account/asset                            broker/tcbs/account.py
/erebos/v1/account/available-balance                broker/tcbs/account.py
/erebos/v1/portfolio-asset                          broker/tcbs/account.py
/erebos/v1/portfolio-asset/token                    broker/tcbs/account.py
/erebos/v1/portfolio/stock/{accountNo}/statistic    broker/tcbs/account.py
/erebos/v2/accounts/{accountNo}/asset               broker/tcbs/account.py
/erebos/v2/accounts/{accountNo}/available-balance   broker/tcbs/account.py
/erebos/v2/accounts/{accountNo}/deposit             broker/tcbs/account.py
/erebos/v2/accounts/{accountNo}/dividend            broker/tcbs/account.py
/erebos/v2/accounts/{accountNo}/orders/history      broker/tcbs/account.py
/erebos/v2/accounts/{accountNo}/orders/matching     broker/tcbs/account.py
/erebos/v2/accounts/{accountNo}/stock-statistic     broker/tcbs/account.py
/erebos/v2/accounts/{accountNo}/withdraw            broker/tcbs/account.py
/erebos/v2/order/stop-limit                         broker/tcbs/equity.py
/erebos/v2/order/stop-limit/orders                  broker/tcbs/equity.py
/erebos/v2/order/stop-limit/{orderId}               broker/tcbs/equity.py
/erebos/v2/order/stop-limit/{orderId}/cancel        broker/tcbs/equity.py
```

Hai tài liệu **khớp nhau 48/48** ở phần REST. Những gì chúng cùng vắng mặt thì
nhiều khả năng là endpoint đã bị TCBS gỡ (spec 1.0.0 là bản mới) hoặc từng tồn tại
trong tài liệu cũ. **Vẫn chưa xác minh bằng server** — token hết hạn, mà 401 chạy
trước routing nên không phân biệt được (bài học DNSE).

Điểm đáng chú ý: `broker/tcbs/account.py` dùng **cả hai thế hệ** — `/aion/v1/...`
(có trong spec, ví dụ `/aion/v1/accounts/{a}/se`) lẫn `/erebos/v1`, `/erebos/v2/...`
(không có trong spec). Tức tài khoản đang được đọc qua lớp vừa mới vừa cũ.

### 4.2 Lỗi của tôi #1 — script bỏ sót WebSocket

Script báo `/ws/ouranos/v1/stream`, `/ws/aither`, `/ws/nesoi` **"CHƯA dùng"**. **Sai.**
`explorer/tcbs/websocket.py:38-40` dùng cả ba, nhưng lưu dạng URL đầy đủ
(`wss://openapi.tcbs.com.vn/ws/...`), còn script chỉ quét giá trị bắt đầu bằng `/`.

| WS stream | Postman | Code |
|---|---|---|
| `/ws/ouranos/v1/stream` — History & supply/demand | ✅ | ✅ `:38` |
| `/ws/aither` — Order matching (stock) | ✅ | ✅ `:39` |
| `/ws/nesoi` — Order matching (derivative) | ✅ | ✅ `:40` |
| `/ws/thesis/v1/stream/normal` — Price board | ✅ | ❌ **chưa dùng** |
| `/ws/thesis/v1/stream/derivative` — Price board | ✅ | ❌ **chưa dùng** |

⇒ Phủ 3/5. Hai stream `thesis` là **bảng giá (price board)** — mà DNSE không có.
Cần đọc spec riêng cho chúng; Postman không kèm message schema.

### 4.3 Lỗi của tôi #2 — môi trường SIT không tồn tại

`websocket.py:45-47` có sẵn cấu hình SIT:

```
wss://openapisit.tcbs.com.vn/ws/ouranos/v1/stream
wss://openapisit.tcbs.com.vn/ws/aither
wss://openapisit.tcbs.com.vn/ws/nesoi
```

Đo thật:

```
openapi.tcbs.com.vn     -> DNS 103.4.129.48   TLS OK   HTTP 401
openapisit.tcbs.com.vn  -> DNS FAIL: getaddrinfo failed
```

**SIT không phân giải được.** Cấu hình này không dùng được với DNS công cộng —
hoặc TCBS chỉ cấp cho mạng nội bộ của họ, hoặc host đã đổi. Hệ quả: **không có
môi trường test nào** để kiểm chứng 19 path kia mà không cần tài khoản production.

### 4.4 Auth khớp giữa 2 tài liệu

| | Spec | Postman |
|---|---|---|
| Cơ chế | `bearerAuth`, HTTP bearer JWT | `{"type":"bearer","bearer":[{"key":"token","value":"{{access_token}}"}]}` |
| Đổi key → JWT | `POST /gaia/v1/oauth2/openapi/token` | cùng path |
| Body | `{apiKey, otp}` — cả hai bắt buộc | cùng path |

Cả hai xác nhận `otp` là Smart OTP từ app TCInvest ⇒ **JWT có thời hạn ngắn**, phải
lấy lại thủ công. Đây là nguyên nhân có khả năng cao khiến token trong `.env` chết
và 4 test integration skip.

### 4.5 Điểm phải giữ: `accountId` ≠ `accountNo`

`broker/tcbs/derivatives.py:9-10` ghi rõ, và code làm đúng:

```
CRITICAL: Phái sinh dùng accountId (custody code 105C format) không phải accountNo.
Ví dụ: accountId = '105C334455'
```

Postman xác nhận: `/khronos/v1/account/status?accountId=&subAccountId=&getType=`.
Đây là bẫy thật — hai họ tham số cùng nghĩa khác tên, lẫn vào nhau sẽ ra 400 chứ
không phải 401. **Giữ nguyên, đã đúng.**

---

## 5. Nhìn tổng thể — TCBS đang ở đâu

### 5.1 Về API surface

| | |
|---|---|
| REST trong spec | 48 |
| vnbroker dùng | **35/48 (73%)** |
| Path không có trong cả 2 tài liệu | **19** — cần probe để xác định số phận |
| WebSocket | **3/5** — thiếu 2 stream `thesis` (bảng giá) |

Về *đường* thì TCBS phủ khá. **Nhưng tỉ lệ đó che một vấn đề lớn hơn** ở §1.

### 5.2 Vấn đề thật: một tuyên bố sai đang chặn nguồn dữ liệu

`quote.py:347` và `:421` nói TCBS không có OHLCV D/W/M và đẩy người dùng sang
VCI/KBS. Spec chứng minh sai. **Đây là hậu quả nặng hơn 13 endpoint chưa dùng**:
13 endpoint thiếu thì thêm sau được, còn này là **đang chủ động loại TCBS khỏi
Tier 1 với lý do sai** — và người dùng tin lời giải thích đó.

### 5.3 So với DNSE — bức tranh đối chiếu

| | DNSE | TCBS |
|---|---|---|
| Tài liệu đối chiếu | Web + SDK chính thức | OpenAPI spec + Postman (2 nguồn) |
| Còn sống | REST `openapi.dnse.com.vn` **treo TLS** | `openapi.tcbs.com.vn` **TLS OK, 401** |
| Gọi server thật được | Không | Không (token hết hạn) nhưng **server đáp** |
| Môi trường test | Sandbox (`sb-openapi`) — chỉ `/accounts*` | SIT **không phân giải** |
| Test live trong gate | 7 pass (đã bật) | 4 skip (`TCBS_API_KEY` chưa set) |
| WS | Production chạy thật | Code có, **chưa từng chạy** |
| Bug âm thầm | `price_depth()` trả rỗng — **đã sửa** | `history()` raise với lý do sai — **chưa sửa** |

TCBS **dễ kiểm chứng hơn DNSE** ở chỗ: server phản hồi, chỉ thiếu token. Và có
WebSocket market data sẵn trong code.

### 5.4 Thứ tự nên làm

| # | Việc | Vì sao | Rủi ro |
|---|---|---|---|
| 1 | Nối `bars-long-term` + `bars`, bỏ `NotImplementedError` | Mở Tier 1 cho TCBS; schema đã đúng Lớp A | thấp |
| 2 | Bật 4 test TCBS — nạp `.env` như đã làm DNSE | Đang tự lừa mình về độ phủ | thấp |
| 3 | Sửa docstring sai ở `quote.py:347`, `:421` | Đang nói dối người dùng | rất thấp |
| 4 | Probe 19 path khi có token — script chỉ GET | Biết số phận chúng | thấp |
| 5 | Đọc + nối 2 stream `thesis` | Bổ sung bảng giá, TCBS không có ở nơi khác | trung bình |
| 6 | Rotate khóa API trong git, rồi purge 3 file docs | An ninh | **cần Owner quy** |

⚠ Mục 1 **không verify được bằng live test** khi token chết. Ghi "đúng theo spec,
chưa gọi thật", không báo PASS.
---

## 6. Bảo mật — **đã xử lý 2026-10-09**

### 6.1 Đã làm (commit `b0dca5e`)

Khóa API TCBS từng nằm trong git. Đã xoá ở HEAD:

| Vị trí | Nội dung | Xử lý |
|---|---|---|
| `TCBS_CONNECTION_TEST_REPORT.md:11` | tiền tố khóa `10000928344-488b082e-…` | ✅ xoá |
| `TCBS_CONNECTION_TEST_REPORT.md:22` | OTP thật | ✅ xoá |

Quét lại: không còn fragment khóa hay OTP trong bất kỳ file tracked nào.

**Cách xác minh khóa mà không phải lộ nó** — thay cho giá trị thật trong tài liệu:

```
POST /gaia/v1/oauth2/openapi/apikey/info  {"apiKey": <từ .env>}
  -> 200 {"expireDate": "..."}                    khoa hop le
POST /gaia/v1/oauth2/openapi/token    {"apiKey": …, "otp": sai}
  -> 400 {"code":"203033","message":"Invalid OTP"}  khoa duoc chap nhan
```

### 6.2 Owner quyết định: phương án **A + revoke**

| | Cách | Đánh giá |
|---|---|---|
| **A** | Xoá ở HEAD | ✅ **đã làm** — chặn tái phát |
| B | `git filter-repo` + force-push | ❌ bị từ chối — ghi đè lịch sử chung |
| C | Rotate/revoke khóa | **Owner tự thực hiện** |

**Vì sao A + revoke là đủ:** sau khi revoke, khóa cũ **vô hiệu lực** dù còn trong
lịch sử git. Bỏ phương án B là đổi lấy hiệu quả gần như bằng 0 với rủi ro cao.

### 6.3 Việc còn tồn đọng

- **Khóa vẫn còn trong lịch sử git** ở commit `2696334`, đã push lên `origin/dev`:
  `git show 2696334:docs/TCBS_CONNECTION_TEST_REPORT.md`
  Chấp nhận rủi ro này sau khi revoke — khoá cũ không còn dùng được.
- **Số tiểu khoản + `custodyID`** (`10000928344`, `105C836591`) còn ở 7 chỗ.
  Không phải credential, nhưng là dữ liệu định danh tài khoản thật. **Chưa có ý
  kiến từ Owner.**

### 6.4 Hệ quả với việc kiểm chứng

Khóa hiện tại còn hiệu lực đến **19/05/2027** (đo bằng `apikey/info`). Sau khi
Owner revoke:

1. `.env` → `TCBS_AUTH_TOKEN` **mất hiệu lực** ⇒ mọi lệnh TCBS dừng.
2. Cần **API key mới** tạo trên TCInvest.
3. Vẫn cần **Smart OTP** để đổi key → JWT. Bước này **không tự động hoá được**.

⇒ Giai đoạn 0 (probe 19 path) **bị chặn** cho tới khi có key mới + OTP. Giai đoạn 1
(nối `bars`) viết và test offline được — **không** phụ thuộc token.
