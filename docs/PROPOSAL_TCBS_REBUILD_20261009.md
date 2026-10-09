# ĐỀ XUẤT TÁI TRIỂN KHAI LẠI THƯ VIỆN TCBS

**Tác giả:** vai trò PM + Tech Lead + System Designer
**Ngày:** 2026-10-09 · **Trạng thái:** đề xuất, chờ Owner duyệt
**Phạm vi:** 25 file · 9.006 dòng · `vnbroker/broker/tcbs/` + `vnbroker/explorer/tcbs/` + `vnbroker/brokerage/tcbs/`

---

## 0. Kết luận điều hành

Thư viện TCBS **không lạc hậu về đường dẫn** — nó **lạc hậu về kiến trúc**, ở mức
khiến **hai phần chưa từng hoạt động với server TCBS thật**:

| # | Phát hiện | Mức | Bằng chứng |
|---|---|---|---|
| **F1** | **WebSocket sai hoàn toàn ở tầng wire** | **P0** | `explorer/tcbs/websocket.py:166-173, 187-192, 208+, 251+` |
| **F2** | `history()` từ chối daily OHLCV với **lý do sai** | **P0** | `explorer/tcbs/quote.py:344-347, 421` |
| **F3** | 19 path thuộc API **trước khi ra mắt v1.0.0** | **P0** | `broker/tcbs/account.py`, `equity.py` |
| **F4** | JWT hết hạn 8 giờ, **không có chiến lược làm mới** | **P1** | docs `/auth/token/`, `explorer/tcbs/auth.py` |
| **F5** | Cấu hình SIT trỏ host **không tồn tại** | **P1** | `explorer/tcbs/websocket.py:45-47` |
| **F6** | Không xử lý quy ước **field null không xuất hiện** | **P1** | docs `/data-types/` |
| **F7** | 13/48 endpoint chưa dùng | **P1** | đối chiếu spec + Postman |
| **F8** | `account.py` trộn **hai thế hệ API** | **P2** | `broker/tcbs/account.py:39-45` |
| **F9** | `OrderSide` nhân đôi, **trái giá trị** | **P2** | `brokerage/base.py:19` vs `broker/ssi/_enums.py:16` |
| **F10** | API key nằm trong git history | **P0 an ninh** | 3 file `docs/` |

**Đề xuất:** tái triển khai theo **6 giai đoạn**, giữ nguyên hợp đồng công khai của
vnbroker, ưu tiên giai đoạn 1–2 để mở Tier 1 cho TCBS.

---

## 1. Nguồn bằng chứng

Bốn nguồn, đã đối chiếu chéo:

| # | Nguồn | Nội dung | Tình trạng |
|---|---|---|---|
| S1 | `developers.tcbs.com.vn/docs/v1.0.0/*` | 48 trang tài liệu chi tiết | ✅ đọc trực tiếp |
| S2 | `/specs/openapi-v1.0.0.json` | OpenAPI 3.0.3, 48 endpoint | ✅ đọc |
| S3 | `/specs/tcbs-openapi-v1.0.0.postman_collection.json` | 48 REST + **5 WebSocket** | ✅ đọc |
| S4 | `/specs/tcbs-openapi-v1.0.0-vi.pdf` | toàn bộ tài liệu | ⚠ mô hình không đọc PDF — **S1-3 đã đủ** |

**Xác nhận:** 3 file người dùng cung cấp **chính là** file chính thức tải từ
`/specs/` trên trang docs (liên kết ở `/docs/v1.0.0/introduction/`).

**Changelog — điểm mấu chốt về mặt lịch sử:**

```
31/07/2026  v1.0.0  Mới
  - Tài liệu REST API (Xác thực, Tài khoản, Tiền, Lệnh)
  - Tài liệu WebSocket real-time (Bảng giá, Khớp lệnh)
```

**Chỉ có MỘT phiên bản.** v1.0.0 là bản **ra mắt đầu tiên** 31/07/2026, không phải
bản nâng cấp. ⇒ Các path `erebos/*` trong code **không phải** "phiên bản cũ hơn
1.0.0"; chúng thuộc **API trước khi iFlash OpenAPI ra mắt**. Đây là căn cứ để xóa
(F3).

---

## 2. Bản đồ thư viện hiện tại

### 2.1 Hai tầng, hai base class, hai hệ auth — không thống nhất

```
vnbroker/explorer/tcbs/        12 file · 3.506 dòng     (dữ liệu thị trường)
  quote.py         801   ← history/intraday/price_depth  ← CÓ LỖI F2
  company.py       504
  listing.py       373
  tcbs_compatibility.py 330  ← lớp tương thích, nghi vấn trùng lặp
  websocket.py     412   ← CÓ LỖI F1
  financial.py     265
  screener.py      186
  stream.py        170
  trading.py       141
  const.py         137
  ws_models.py      89
  auth.py           86

vnbroker/broker/tcbs/           12 file · 4.846 dòng     (giao dịch tiền thật)
  equity.py        980   ← CÓ LỖI F3
  account.py       937   ← CÓ LỖI F3, F8
  derivatives.py   852
  client.py        689
  money.py         563
  market.py        395
  portfolio.py     296
  auth.py          178
  exceptions.py     30
  __init__.py       34

vnbroker/brokerage/tcbs/
  client.py        485   ← facade tầng brokerage
```

**Vấn đề kiến trúc:** `explorer/tcbs/auth.py` (86 dòng) và `broker/tcbs/auth.py`
(178 dòng) là **hai module auth song song** với hai base URL và hai biến môi trường.
`explorer/tcbs/const.py` lại chứa thêm một bảng hằng số. Ba nơi, một khái niệm.

### 2.2 Kiến trúc đích — một trục duy nhất

```
              ┌──────────────────────────────────────────┐
              │  vnbroker/connector/tcbs/   (MỚI)       │
              │  ├── endpoints.py    48 path, 1 dict     │
              │  ├── auth.py         token 8h + refresh  │
              │  ├── transport.py    timeout, retry, err │
              │  ├── schema.py       parse + ép kiểu     │
              │  └── ws/             protocol pipe `|`   │
              └───────────────┬──────────────────────────┘
                              │  (duy nhất hiểu wire format)
        ┌─────────────────────┴──────────────────────┐
        │                                            │
┌───────▼────────────────┐              ┌────────────▼────────────┐
│ explorer/tcbs/          │              │ broker/tcbs/            │
│ BaseComponent           │              │ BrokerClient            │
│ → registry              │              │ → write_gate            │
└─────────────────────────┘              └─────────────────────────┘
```

**Nguyên tắc bất di bất dịch:** chỉ `connector/tcbs/` được biết wire format. Mọi
tầng trên chỉ làm việc với kiểu dữ liệu đã chuẩn hoá. Đây là thứ **thiếu hiện nay** —
`explorer/tcbs/quote.py:443` tự dựng URL, `broker/tcbs/equity.py:144` tự `.format()`,
`brokerage/tcbs/client.py` lại gọi thẳng `requests`.

---

## 3. F1 [P0] — WebSocket sai ở tầng wire

### 3.1 Đối chiếu từng dòng

Protocol chính thức (S1, `/stock/ws-price-board/`): **TEXT frame phân tách bằng pipe
`|`**, không phải JSON.

| Bước | Chính thức | vnbroker hiện tại | File:dòng |
|---|---|---|---|
| Xác thực | `d\|a\|\|\|<base64(token)>` — text frame sau connect, **chờ** `d\|0\|{"success":true}` | **không có frame nào**; chỉ header HTTP `Authorization: Bearer` | `:105-107` |
| Subscribe | `d\|s\|tk\|bp+bi+tm+mp+op+fe\|FPT,VCS` | `{"cmd":"subscribe","symbols":[…],"channels":[…]}` | `:166-173` |
| Unsubscribe | `d\|u\|tk\|bp+bi+…\|TCB` | `{"cmd":"unsubscribe",…}` | `:187-192` |
| Heartbeat | `d\|p\|\|\|` text frame, **mỗi 2 giây** | `{"cmd":"ping"}` | `:208+` |
| Dữ liệu | `s\|<CHANNEL_ID>\|<JSON>` | `json.loads(raw)` — không tách pipe | `:251+` |
| Auto-ping | **BẮT BUỘC tắt** (tắt sai thì lỗi `1002`) | `ping_interval=None` ✅ | `:115` |
| Tên kênh | `bp bi tm mp op fe tmh rt ptm ptb pts` | `["ohlc","ticker","trade","orderbook"]` | `:161` |
| Giá/khối lượng | Kênh 1,2,3,6 trả **string**; kênh 4,5,8 trả **number** | không ép kiểu | `_parse_message` |

Điểm duy nhất đúng là `ping_interval=None` — có thể là do tác giả biết điều kiện
bắt buộc nhưng chưa đọc phần protocol còn lại.

### 3.2 Kết luận

**Client này không thể xác thực với server TCBS.** Server chỉ nhận `d|a|||…`;
mọi thứ vnbroker gửi sẽ bị bỏ qua, và sau 15 giây không heartbeat server sẽ ngắt.

⇒ **Chưa từng chạy được.** Chưa có bất kỳ test nào chứng minh điều đó — và
`test_tcbs_*` không hề đụng WebSocket.

### 3.3 Bổ sung: 2 endpoint bảng giá chưa dùng

| Stream | Postman | vnbroker | Nội dung |
|---|---|---|---|
| `/ws/ouranos/v1/stream` | ✅ | ✅ `:38` | lịch sử + cung cầu |
| `/ws/aither` | ✅ | ✅ `:39` | khớp lệnh cổ phiếu |
| `/ws/nesoi` | ✅ | ✅ `:40` | khớp lệnh phái sinh |
| **`/ws/thesis/v1/stream/normal`** | ✅ | ❌ | **bảng giá cổ phiếu** (bid/offer top-3, trần/sàn/tham chiếu, chỉ số) |
| **`/ws/thesis/v1/stream/derivative`** | ✅ | ❌ | **bảng giá phái sinh** |

⚠ **Cảnh báo bắt buộc (S1):** channel ID của `thesis/normal` và `thesis/derivative`
**khác nhau hoàn toàn**, và kiểu dữ liệu cũng khác — *"KHÔNG dùng chung parser cho
cổ phiếu và phái sinh"*.

```
                /stream/normal      /stream/derivative
Bid             s|1                 s|23
Offer           s|2                 s|24
Foreign         s|3                 —
Base price      s|4                 —
Matched/day     s|5                 s|27
Ticker match    s|6                 s|21
Stock index     s|8                 —
```

---

## 4. F2 [P0] — `history()` từ chối daily OHLCV với lý do sai

`explorer/tcbs/quote.py:344-347` và `:421` ném `NotImplementedError`:

> *"TCBS iFlash OpenAPI does not support historical daily/weekly/monthly OHLC bars.
> TCBS OpenAPI only provides intraday tick data for the current session. For
> historical daily/weekly/monthly OHLC data, please use source='VCI' or source='KBS'"*

**S1 §5.13 có `GET /nyx/v2/stock/bars-long-term`** — "Dữ liệu nến OHLCV (dài hạn)",
`resolution: D | W | M`. Response:

```json
{ "ticker": "...", "data": [ { "open":…, "high":…, "low":…,
                              "close":…, "volume":…,
                              "tradingDate": "ISO-8601 UTC" } ] }
```

Đã đúng shape Lớp A. Hệ quả hiện tại: **TCBS bị loại khỏi Tier 1 với lý do sai**,
và `test_tcbs_quote_history_not_implemented.py` mã hoá luôn tuyên bố sai đó thành
test — làm cho nó trông như quyết định có chủ đích.

---

## 5. F3 [P0] — 19 path của API trước khi ra mắt

| Nhóm | Path | File |
|---|---|---|
| `erebos/v1` (5) | `/account/asset`, `/account/available-balance`, `/portfolio-asset`, `/portfolio-asset/token`, `/portfolio/stock/{accountNo}/statistic` | `account.py:39-43` |
| `erebos/v2` tài khoản (9) | `/accounts/{a}/asset`, `/available-balance`, `/deposit`, `/dividend`, `/orders/history`, `/orders/matching`, `/stock-statistic`, `/withdraw` | `account.py:45+` |
| `erebos/v2` stop-limit (4) | `/order/stop-limit`, `/order/stop-limit/orders`, `/order/stop-limit/{id}`, `/order/stop-limit/{id}/cancel` | `equity.py` |
| `aion` (2) | `/aion/v1/accounts`, `/aion/v1/accounts/{a}/orders/history` | `account.py`, `equity.py` |

**Cả S2 (OpenAPI) và S3 (Postman) đều không có.** Với changelog chỉ có một phiên bản,
kết luận hợp lý nhất: đây là **API trước khi iFlash OpenAPI ra mắt**.

**Chưa xác minh bằng server** — token hết hạn, mà `401` chạy trước routing nên không
phân biệt được (bài học DNSE: `GET /accounts/orders → 405` mới chứng minh route có).

⚠ **Không xóa vội.** Xóa mà TCBS vẫn phục vụ sẽ làm hỏng chức năng tiền thật.
Cần probe trước — xem §9, Giai đoạn 0.

---

## 6. F4 [P1] — Vòng đời token

S1 (FAQ): *"Token có hiệu lực tối đa 8 giờ."* S1 (WS): *"Server ngắt connection khi
token hết hạn."*

Luồng chính thức: `apiKey` + `otp` (Smart OTP từ app TCInvest) → JWT.

**Khoảng trống:**
- Không có cơ chế phát hiện hết hạn trước khi gọi.
- `explorer/tcbs/auth.py` có `request_openapi_token()` nhưng không có cache/refresh.
- Token trong `.env` (`TCBS_AUTH_TOKEN`) là **JWT 8 giờ**, tức **luôn hết hạn khi lưu
  vào file** ⇒ 4 test integration skip vĩnh viễn.

**Thiết kế đích:** `TokenManager` giữ token trong bộ nhớ, đếm ngược thời hạn từ
JWT payload (`exp`), tự refresh khi còn < 5 phút. `otp` vẫn phải do người dùng
cung cấp — **đây là giới hạn không giải quyết được bằng code.**

---

## 7. F5, F6, F7 [P1]

**F5 — SIT không tồn tại.** `websocket.py:45-47` trỏ `wss://openapisit.tcbs.com.vn`.
Đo: `DNS FAIL`. Cấu hình chết, gây hiểu nhầm.

**F6 — field null không xuất hiện.** S1 `/data-types/`: *"Response chỉ chứa các field
có giá trị. Field null sẽ không xuất hiện trong JSON."* ⇒ mọi chỗ đọc field tùy chọn
phải dùng `.get()`; dùng `[...]` sẽ `KeyError` **khi server trả về thiếu**, tức
lỗi tương lai không đoán trước được.

**F7 — 13 endpoint chưa dùng:**

| Endpoint | Nhóm | Mức |
|---|---|---|
| `/nyx/v2/stock/bars-long-term` | thị trường | **P0 — xem F2** |
| `/nyx/v2/stock/bars` | thị trường | P1 |
| `/ananke/v1/securities` | thị trường | P1 |
| `/hydros/v1/account/{a}/pricing-policy` | vay | P2 |
| `/campaign-management/…/addons/detail` | vay | P2 |
| `/khronos/v1/cash/deposit/update` | tiền — **ghi** | P2 |
| `/khronos/v1/cash/withdraw/update` | tiền — **ghi** | P2 |
| `/khronos/v1/order/condition/cancel` | lệnh — **ghi** | P2 |
| `/physis/v1/stock/transfer` | tiền — **ghi** | P2 |
| `/gaia/v1/oauth2/openapi/token` · `/info` · `/extend` | auth | P2 |
| `/api/v1/derivatives/contracts` | phái sinh | P2 |

---

## 8. Hợp đồng tích hợp — **không được phá**

Refactor lớn chỉ an toàn nếu bền mặt không đổi. Danh sách phải giữ nguyên:

| Hợp đồng | Vị trí | Ràng buộc |
|---|---|---|
| `ProviderRegistry.register("quote"/"listing"/"company"/"financial"/"trading"/"news", "dnse"…)` | `explorer/tcbs/__init__.py` | tên provider `"tcbs"` là hợp đồng |
| `Quote(symbol, ...).history/intraday/price_depth/…` | `explorer/tcbs/quote.py` | chữ ký + tên tham số |
| `source='TCBS'` | `api/quote.py` và các `api/*.py` | người dùng gọi bằng chuỗi này |
| Cột chuẩn `time, open, high, low, close, volume` tz-aware | `common/data.py`, `Normalizer` | `tests/contract/` kiểm |
| `Vnbroker.broker("tcbs")` | `brokerage/tcbs/client.py` | entrypoint |
| `enable_write()` + write gate | `broker/tcbs/` | **bắt buộc** cho mọi verb ghi |

**Cấm**: đổi tên module công khai, đổi tên phương thức public, đổi tên cột chuẩn,
bỏ provider khỏi registry.

---

## 9. Kế hoạch triển khai 6 giai đoạn

### Giai đoạn 0 — Chặn an toàn (1–2 ngày)

Không viết tính năng. Đo và xác minh trước khi xóa bất kỳ thứ gì.

| Việc | Cổng |
|---|---|
| Lấy JWT mới (`apiKey` + OTP từ app TCInvest) | **Cần Owner** |
| Probe **19 path F3** — chỉ GET, ghi status | `404` = xác nhận xóa · `400/200` = giữ |
| Probe 13 path F7 — xác nhận tồn tại | ghi lại |
| Xoay khóa API đã lộ, **rồi** purge 3 file docs | **Cần Owner** |
| Đo `type` hợp lệ cho `bars`: `stock`/`index`/`coveredWarr` | tránh đoán |

**Cổng ra:** bảng trạng thái 19+13 path, có bằng chứng. Không có cổng này thì
Giai đoạn 3 **không được bắt đầu**.

### Giai đoạn 1 — Mở Tier 1 cho TCBS (2–3 ngày) · *giá trị cao nhất*

| Việc | Rủi ro |
|---|---|
| Nối `/nyx/v2/stock/bars-long-term` → `history()` D/W/M | thấp |
| Nối `/nyx/v2/stock/bars` → nến phút/giờ | thấp |
| Map `tradingDate` → `time` tz-aware `Asia/Ho_Chi_Minh` | thấp |
| **Sửa docstring sai** ở `quote.py:347`, `:421` | rất thấp |
| Xoá `test_tcbs_quote_history_not_implemented.py`, thay bằng test thật | thấp |

Chuyển `start/end` → `to` (epoch giây) + `countBack`.

⚠ Chưa verify được bằng live test cho tới khi có token. Ghi *"đúng theo spec, chưa
gọi thật"*, không báo PASS.

### Giai đoạn 2 — Viết lại WebSocket (4–5 ngày) · P0

| Việc |
|---|
| `connector/tcbs/ws/protocol.py`: auth/subscribe/unsubscribe/heartbeat theo pipe `|` |
| Base64 token; **chờ** `d\|0\|{"success":true}` trước khi subscribe |
| `d\|p\|\|\|` mỗi 2s; theo dõi `d\|33\|15` |
| Parse `s\|<ch>\|<json>`; map channel ID → tên |
| **Ép kiểu theo từng kênh** (1,2,3,6 = string · 4,5,8 = number) |
| Reconnect: `min(2^attempt, 30)` giây, tối đa 10 lần |
| Xoá `_WS_ENDPOINTS_SIT` (F5) |
| Thêm `thesis/normal` và `thesis/derivative` — **parser riêng**, không dùng chung |

**Cổng ra:** test protocol offline với frame thật lấy từ tài liệu + 1 test live
(bỏ qua ngoài phiên, phải heartbeat).

### Giai đoạn 3 — Dọn path chết (2–3 ngày)

Chỉ bắt đầu sau cổng Giai đoạn 0.

1. Chuyển 19 path F3 vào `legacy_paths.py`, đánh dấu **deprecated**, phát `DeprecationWarning`.
2. Ghi log cảnh báo khi gọi.
3. Giữ 1 phiên bản; xoá ở bản sau.

`account.py` 937 dòng trộn hai thế hệ → tách `account_legacy.py`.

### Giai đoạn 4 — TokenManager (1–2 ngày)

Cache trong bộ nhớ, đếm ngược `exp` từ JWT, tự refresh trước 5 phút, phát sự kiện
`token_refreshed` để WS reconnect. Thay `.env` `TCBS_AUTH_TOKEN` bằng cơ chế này.

### Giai đoạn 5 — Bổ sung 13 endpoint + `schema.py` (3–4 ngày)

| Nhóm | Endpoint |
|---|---|
| Thị trường | `bars`, `ananke/v1/securities`, `api/v1/derivatives/contracts` |
| Vay | `pricing-policy`, `addons/detail` |
| Tiền (**ghi**) | `deposit/update`, `withdraw/update`, `stock/transfer` |
| Lệnh (**ghi**) | `order/condition/cancel` |
| Auth | `apikey/info`, `apikey/extend` |

Mọi verb ghi **bắt buộc** qua write gate. Áp dụng F6: `.get()` cho field tùy chọn.

---

## 10. Hợp đồng chuẩn hoá — Lớp A / Lớp B

Theo `docs/NORMALISATION_POLICY.md`. Quy tắc: **mặc định Lớp B**; Lớp A phải
được chứng minh.

### 10.1 Lớp A — dữ liệu thị trường (chuẩn hoá)

| Nguồn TCBS | → Cột chuẩn | Ghi chú |
|---|---|---|
| `bars[].open/high/low/close/volume` | `open/high/low/close/volume` | giữ nguyên tên |
| `bars[].tradingDate` | `time` | ISO-8601 **UTC** → `Asia/Ho_Chi_Minh` |
| `his/paging[].matchPrice` | `price` | string → **số** |
| `his/paging[].matchQtty` | `volume` | string → **số** |
| WS `s\|6.matchPrice/matchQtty` | `price` / `volume` | string → số |
| WS `s\|1.bidPrice01..03` / `bidQtty01..03` | `bid` | giữ cấu trúc 3 mức |
| WS `s\|2.offerPrice01..03` / `offerQtty01..03` | `offer` | |
| WS `s\|4.ceilPrice/floorPrice/refPrice` | `ceil/floor/ref_price` | số |
| WS `s\|5.high/low/avg/open` | `high/low/avg/open` | số |

⚠ **Về `side`** — TCBS dùng **ba** giá trị khác nhau trong cùng hệ:

| Nơi | Giá trị | Lớp |
|---|---|---|
| `kbs/const.py:290` — trade side | `B` / `S` | A (tên cột) nhưng **giá trị để thô** |
| `broker/tcbs/client.py:351` — đặt lệnh | `BUY` / `SELL` | **B** |
| `broker/tcbs/equity.py:67` — execType | `NB` / `NS` | **B** |

Giữ nguyên cả ba, ghi rõ trong docstring. Xem `SIDE_NORMALISATION_RESEARCH.md` §5a —
vnbroker chuẩn hoá *tên cột* nhưng không chuẩn hoá *giá trị*, và đó là hành vi có
sẵn, không phải thứ TCBS tạo ra.

### 10.2 Lớp B — giữ nguyên TCBS

`accountId` (custody code dạng `105C`) **khác** `accountNo` — `derivatives.py:9-10`
đã ghi đúng, phải giữ. `getType`, `subAccountId`, `side` (`NB`/`NS`), `orderStatus`,
`tradeCode`, mọi trường tiền tệ VND (int64, không thập phân), `room`, `color`, `status`.

---

## 11. Chiến lược kiểm thử

| Tầng | Nội dung | Cổng |
|---|---|---|
| Offline protocol | Frame thật lấy từ tài liệu, replay không cần mạng | bắt buộc |
| Contract | URL + verb + tên query đúng spec | `tests/contract/` |
| Chuẩn hoá | `time` tz-aware, đủ cột, 0 dòng vẫn đủ schema | `tests/contract/` |
| Live | Smoke trên JWT thật, **bỏ qua ngoài phiên** | không chặn gate |
| Chống hồi quy | Test khẳng định **không** còn path legacy | bắt buộc |

⚠ **Bài học từ chính phiên này — phải áp dụng:**
1. *Đo bằng script, đừng chép tay bảng.* (§4 audit đã bắt tôi sai 2 lần.)
2. *Test luôn xanh mà không chạm server là tự lừa mình.* — 4 test TCBS skip vĩnh viễn,
   4 test DNSE skip vĩnh viễn. Đã sửa cho DNSE; TCBS còn yếu.
3. *"Provider không hỗ trợ" phải được kiểm chứng.* F2 là hậu quả của việc tin tuyên bố
   sai.
4. *Một endpoint hỏng không đồng nghĩa mạng hỏng.* DNSE `.24` treo TLS trong khi
   `.88`/`.89` cùng dải bình thường.

---

## 12. Rủi ro

| Rủi ro | Khả năng | Tác động | Giảm thiểu |
|---|---|---|---|
| Xóa 19 path nhưng TCBS vẫn phục vụ | trung bình | **Hỏng tiền thật** | Cổng Giai đoạn 0 bắt buộc |
| JWT không lấy lại được không có OTP | **chắc chắt** | Test live không chạy | Owner cấp OTP khi cần |
| WS protocol tạm thời đổi | thấp | Đứt stream | Bám sát `s\|34\|1` ack |
| Breaking change cột chuẩn | trung bình | Vỡ `tests/contract` | `test_tier1_dod.py` chặn |
| 9.006 dòng refactor trong một lần | cao | Hỏng hàng loạt | 6 giai đoạn, mỗi giai đoạn một PR |

---

## 13. Câu hỏi cần Owner quyết

1. **Token:** cấp JWT mới + cho phép lưu OTP trong `.env` hay nhập tay mỗi lần?
2. **F3:** xác nhận xoá 19 path sau khi probe trả `404`? Có cần giữ nhánh legacy
   cho đến hết v3.5 không?
3. **Khóa API đã lộ trong git:** rotate ngay hay chấp nhận rủi ro (repo `PRIVATE`)?
4. **`thesis/normal` + `derivative`:** có đưa vào phạm vi lần này không, hay chia PR riêng?
5. **Tiêu chí "xong":** ưu tiên Tier 1 (GĐ1) hay bao phủ API (GĐ5) trước?

---

## 14. Ước lượng

| Giai đoạn | Nội dung | Công |
|---|---|---|
| 0 | Chặn an toàn, probe, rotate key | 1–2 ngày |
| 1 | Mở Tier 1 (`bars`) | 2–3 ngày |
| 2 | Viết lại WebSocket + 2 stream mới | 4–5 ngày |
| 3 | Dọn 19 path legacy | 2–3 ngày |
| 4 | TokenManager | 1–2 ngày |
| 5 | Bổ sung 13 endpoint | 3–4 ngày |
| | **Tổng** | **13–19 ngày công** |

**Không tính** thời gian chờ Owner cấp token/OTP.

---

## 15. Đề xuất thứ tự thực thi

Bắt đầu **Giai đoạn 1** ngay (giá trị cao nhất, rủi ro thấp nhất, không cần token để
viết test). Song song, Owner xử lý token + khóa API để mở đường cho Giai đoạn 0.

**Không** bắt đầu Giai đoạn 3 trước khi có bảng probe.

Và một điều không nên bỏ qua: **F1 và F2 đều là loại lỗi "trông như đã làm xong
nhưng chưa từng chạy"**. Trước khi coi bất kỳ phần nào của TCBS là hoàn tất, cần
một bằng chứng chạy thật — không phải một test xanh trên mock.