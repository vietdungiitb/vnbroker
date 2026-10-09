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

## 4. Điểm cần kiểm lại

`/tartarus/v1/putThroughSnaps` bị script xếp vào **"khớp"** (có trong cả spec và
`broker/tcbs/market.py`) nhưng tôi lại liệt kê ở §2. **Mâu thuẫn nội bộ của báo cáo
này** — phải sửa một trong hai trước khi dùng làm căn cứ. Nguyên nhân khả năng cao:
script chuẩn hoá `putThroughSnaps` → `put_through_snaps` và so khớp đúng, còn
bảng §2 tôi liệt kê thủ công. Số liệu đáng tin là output script, **không** phải bảng
§2 viết tay.

⇒ **Nguyên tắc:** lấy số từ script, không chép tay bảng. Đã viết lại §2 để bỏ mục
đó.

---

## 5. Auth

| Khía cạnh | Spec | Code |
|---|---|---|
| Cơ chế | `bearerAuth`, HTTP bearer, JWT | `auth_token` truyền xuống client (`quote.py:77`) |
| Đổi key → JWT | `POST /gaia/v1/oauth2/openapi/token`, body `{apiKey, otp}` — **cả hai bắt buộc** | `request_openapi_token(otp, api_key)` (`explorer/tcbs/auth.py:37`) — khớp |

⚠ `otp` là **Smart OTP (iOTP) từ app TCInvest**. Tức là **JWT có thời hạn ngắn**, phải
lấy lại từ app. Đây là nguyên nhân có khả năng cao khiến token trong `.env` hết hạn
và 4 test integration skip (`TCBS_API_KEY not set`).

---

## 6. Bảo mật — cần Owner xử lý, không tự ý đụng

Khóa API TCBS (11 ký tự + 8 hex đầu) đang **đã track trong git**:

```
docs/TCBS_CONNECTION_TEST_REPORT.md:11,28
docs/CENTRAL_MODIFIED_FILES_AUDIT.md:23
docs/TCBS_INVESTMENT_DATA_DESIGN.md:132,235,249,265
```

Handoff ghi: *"Thứ tự bắt buộc: rotate API key TRƯỚC, purge file SAU."* Xóa file
**không** làm key cũ mất hiệu lực. Repo `PRIVATE` ⇒ rủi ro thấp hơn nhưng đã lộ.

---

## 7. Đề xuất, theo thứ tự giá trị

| # | Việc | Rủi ro | Ghi chú |
|---|---|---|---|
| 1 | Nối `/nyx/v2/stock/bars-long-term` cho `history()` D/W/M | thấp | Bỏ `NotImplementedError`; schema đã đúng Lớp A; chỉ cần map `start/end → to/countBack` + đổi múi giờ `tradingDate` |
| 2 | Nối `/nyx/v2/stock/bars` cho nến phút/giờ | thấp | Thay đường tự tính từ `his/paging` (`quote.py:443`) |
| 3 | Probe 19 path "thừa" khi có token còn hạn | thấp | Chỉ đọc, GET; chỉ cần token mới |
| 4 | Sửa 4 test skip — nạp `.env` như đã làm cho DNSE | thấp | Đã có mẫu tái dùng: `tests/integration/test_dnse_integration.py` |
| 5 | Bổ sung 6 endpoint còn lại (§2) | trung bình | Nhiều endpoint tiền thật — cần write gate |
| 6 | Rotate API key rồi purge 3 file docs | — | **Cần Owner quyết** |

⚠ Việc 1 và 2 **không kiểm chứng được bằng live test** khi token hết hạn. Phải
chấp nhận "đúng theo spec, chưa gọi thật" cho tới khi bạn cấp token mới — không
được báo PASS.

---

## 8. Bài học

- **"Provider không hỗ trợ" là loại tuyên bố phải kiểm chứng.** Ở đây nó sai, và nó
  đang chặn một nguồn dữ liệu Tier 1 với lý do không có cơ sở.
- **Chạy script đếm, đừng chép bảng.** §4 là bằng chứng: bảng viết tay của tôi mâu
  thuẫn với output script, và tôi không nêu ngay từ đầu.
- **401 không nói gì về routing.** Giống hệt vụ `post_order` của DNSE.