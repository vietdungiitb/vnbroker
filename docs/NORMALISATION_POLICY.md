# NGUYÊN TẮC KIẾN TRÚC — chuẩn hoá chung của vnbroker vs giữ nguyên DNSE

**Chủ quyền tài liệu:** quyết định Owner 2026-10-09, kèm SDK chính thức
`dnse-tech/openapi-sdk` làm nguồn đối chiếu.

---

## 0. Quyết định (nguyên văn tinh thần)

> Port đầy đủ hàm API từ repo chính thức của DNSE. Thông tin **output nào cần hiệu
> chỉnh theo đúng một form dạng chung của vnbroker (không phụ thuộc provider)** thì
> chỉnh cho về đúng form đó — **đặc biệt là mục thông tin explorer thị trường**. Các
> thông tin **riêng chỉ liên quan đến DNSE** thì **giữ đúng định dạng DNSE quy định**,
> tường minh, để tránh dùng API DNSE bị sai lệch.

---

## 1. Hai lớp dữ liệu — ranh giới định nghĩa

| Lớp | Thuộc về | Quy tắc bắt buộc | Ví dụ |
|---|---|---|---|
| **A. Chuẩn hoá** | Dữ liệu **thị trường**, người dùng so sánh được giữa các provider | Phải về **một form chung** của vnbroker | `history`, `intraday`, `price_depth`, `listing`, `security_definition`, `trades`, `ohlc` |
| **B. Nguyên bản** | Dữ liệu **chỉ DNSE có**, hoặc hành vi riêng của DNSE | **Giữ đúng tên & kiểu của DNSE**, ghi rõ trong docstring | `care-by`, `trading-token`, `pnl-configs`, `foreign-investor`, `durationType`, `conditionOperator`, `rate_limit.subscriptions_max`, `custodyCode` |

### 1.1 Vì sao phải tách

- Lớp A đi qua `BaseAdapter` / `Normalizer` và được so sánh giữa VCI/KBS/TCBS/SSI/DNSE.
  Đổi tên cột ở đây là **hỏng hợp đồng dữ liệu** — người dùng failover giữa provider
  sẽ nhận schema khác nhau mà không biết.
- Lớp B là **hợp đồng với DNSE**. Đổi tên là **gọi sai API**. Ví dụ đã đo được:
  server gửi `bid:[{price, qtty}]` trong khi tài liệu ghi `quantity`. Nếu "chuẩn hoá"
  theo doc thành `quantity`, ta sẽ **im lặng trả 0 khối lượng**.

> **Nguyên tắc suy ra:** *đừng dùng tài liệu để "sửa" tên field mà server không gửi.
> Đo từ server trước.*

### 1.2 Quy tắc phân loại (áp dụng khi port từng hàm)

Hỏi theo thứ tự, dừng ở câu trả lời "có":

1. Field này **có nghĩa giống nhau ở mọi provider không?** → có ⇒ **lớp A**
2. Người dùng có **hay so sánh** giá trị này giữa các provider không? → có ⇒ **lớp A**
3. Field này chỉ tồn tại ở DNSE, hoặc là tham số/điều khiển của DNSE? → **lớp B**

Ngược lại: **mặc định là lớp B**. Giữ nguyên DNSE là lựa chọn an toàn; chuẩn hoá là
việc phải **chứng minh**, không phải mặc định.

---

## 2. Form chung của vnbroker — tham chiếu chính xác

Không tự phát minh. Nguồn:

| Nguồn | Vai trò |
|---|---|
| `vnbroker/core/utils/normalizer.py` | `Normalizer._normalize_frame` — tz-aware `Asia/Ho_Chi_Minh`, lọc `[start, end]`, sort |
| `vnbroker/common/data.py` | `BaseComponent`, `Quote`, `Listing`, … + các map cột |
| `vnbroker/explorer/dnse/quote.py:64-98` | `_OHLC_COLUMN_MAP`, `_TRADES_COLUMN_MAP` — map **đã có sẵn** |
| `vnbroker/explorer/dnse/listing.py:21-34` | map cột listing |
| `tests/contract/` | hợp đồng schema: `time` tz-aware, cột bắt buộc, không có dòng ngoài `[start, end]` |

### 2.1 Cột chuẩn đã dùng

| Nhóm | Cột chuẩn |
|---|---|
| OHLC / nến | `time`, `open`, `high`, `low`, `close`, `volume` |
| Khớp lệnh | `time`, `price`, `volume`, `side` |
| Danh sách mã | `symbol`, `exchange`, `board_id`, `organ_name`, `short_name`, `type`, `status`, `lot_size` |
| Nội giá | `time`, `price`, `volume`, `side` |

### 2.2 Quy tắc bất di bất dịch

1. Cột `time` **luôn** tz-aware `Asia/Ho_Chi_Minh` (kể cả khi provider trả tz-naive).
2. `history()` lọc theo `[start, end]` và sort tăng dần.
3. Frame rỗng vẫn phải **đủ cột** (không phải DataFrame 0 cột).
4. Provider-specific column **giữ thêm** cạnh cột chuẩn, không thay thế — trừ khi
   xung đột tên, khi đó đổi tên DNSE và **ghi rõ trong docstring**.

---

## 3. Bảng ánh xạ DNSE → form chung (lớp A)

Ánh xạ lấy từ field server **thật** đã đo, đối chiếu doc.

### 3.1 `GET /price/{symbol}/quotes` → `price_depth`

| Field DNSE (server thật) | → Cột chuẩn | Ghi chú |
|---|---|---|
| `symbol` | `symbol` | giữ |
| `boardId` | `board_id` | giữ |
| `isin` | `isin` | **lớp B** — DNSE/vnstock quy ước riêng, giữ nguyên |
| `time.Seconds` | `time` | ghép `Seconds` + `Nanos` → tz-aware Asia/Ho_Chi_Minh |
| `bid[]` | `bid` | **giữ nguyên cấu trúc list-of-dict** |
| `bid[].price` | `bid[].price` | **không đổi** |
| `bid[].qtty` | `bid[].qtty` | ⚠ **KHÔNG** đổi thành `quantity`. Doc ghi `quantity`, server gửi `qtty` — đã đo. Đổi là ra 0 |
| `offer[]`, `offer[].price`, `offer[].qtty` | tương tự `bid` | |
| `totalBidQtty`, `totalOfferQtty` | giữ nếu có; **không** tạo | doc khai, chưa thấy server gửi |
| `marketId` | `exchange` | chuẩn hoá |

### 3.2 `GET /price/ohlc` → `history`

Đã có `_OHLC_COLUMN_MAP` (`quote.py:64`). Bổ sung field mới:

| Field DNSE | → Cột chuẩn |
|---|---|
| `resolution`, `lastUpdated`, `type` | **lớp B** — giữ nguyên |

### 3.3 `GET /price/{symbol}/trades` → `trades`

Đã có `_TRADES_COLUMN_MAP` (`quote.py:81`).

| Field DNSE | → Cột chuẩn |
|---|---|
| `matchPrice` | `price` |
| `matchQtty` | `volume` |
| `side` | `side` (chuẩn hoá `B`→`BUY`? — **xác nhận lại**, xem §5) |
| `tradingSessionId`, `grossTradeAmount`, `highestPrice`… | **lớp B** — giữ |

### 3.4 `GET /price/{symbol}/secdef` → `security_definition`

| Field DNSE | → Cột chuẩn |
|---|---|
| `symbol` | `symbol` |
| `boardId` | `board_id` |
| `basicPrice` / `ceilingPrice` / `floorPrice` | giữ — không có cột chuẩn tương ứng |
| `securityStatus`, `securityGroupId`, `productGrpId` | **lớp B** |

### 3.5 `GET /market/instruments`, `/market/working-dates`, `/price/{i}/market-index`

| Nhóm | Quyết định |
|---|---|
| `indexName` → `symbol` | chuẩn hoá |
| `valueIndexes`, `changedValue`, `changedRatio` | **lớp B** — giữ tên DNSE |
| `marketIndexClass`, `tradingSessionId`, `transactTime` | **lớp B** |

---

## 4. Giữ nguyên DNSE — danh sách phải ghi rõ (lớp B)

Không được đổi tên, không được "cho đẹp". Mỗi mục phải có dòng docstring nói rõ
*"giữ nguyên theo DNSE OpenAPI, không chuẩn hoá vì ..."*.

| Nhóm | Field / giá trị |
|---|---|
| **Auth** | `custodyCode`, `investorId`, `name`, `dealAccount`, `derivativeAccount`, `derivative.status` |
| **Đặt lệnh** | `orderCategory` (`NORMAL`/`STOP`/`OCO`), `marketType`, `orderType`, `loanPackageId`, `stopPrice`, `conditionOperator` (`>=`/`<=`), `stopOrderPrice`, `durationType` (`GTD`/`DAY`), `durationDateTime` |
| **Trạng thái lệnh** | `pending`, `pendingNew`, `new`, `partiallyFilled`, `filled`, `pendingReplace`, `pendingCancel`, `canceled`, `rejected`, `expired`, `doneForDay`, `activated`, `cancelledByRightsEvent`, `failed` |
| **WS market data** | `T` (`q`/`e`/…), `multicastReceiveTime`, `bid[].qtty`, `offer[].qtty`, `totalBidQtty`, `totalOfferQtty` |
| **WS control** | `rate_limit.messages_per_second`, `rate_limit.subscriptions_max`, `capabilities.batch_delivery` |
| **PnL config** | toàn bộ `/pnl-configs` |
| **Broker** | `care-by`, `smart-otp/handoff` |
| **Lỗi** | `code` (`OA-401`), `message`, 429 vs 403 (rate/giờ vs quota/ngày) |

---

## 5. Điểm **chưa** quyết — cần đo, không đoán

| Mục | Vì sao chưa chốt |
|---|---|
| `side` DNSE gửi `BUY`/`SELL`; vnbroker chuẩn là gì? | Test `test_match_type_contract.py` có `b-Buy → Buy` nhưng đó là **match_type** của KBS/VCI, không phải `side` của DNSE. Phải đọc lại contract trước khi chuẩn hoá |
| `bid[].qtty` vs `quantity` | Server gửi `qtty` (đã đo). Doc ghi `quantity`. **Tạm giữ `qtty`**, ghi chú trong docstring là tên chuẩn thực tế |
| Cột chuẩn cho `security_definition`, `market_index` | Chưa có map sẵn — cần thống nhất trước khi viết map |

---

## 5b. DNSE **tự mâu thuẫn** trong tài liệu — bằng chứng 2026-10-09

Từ `POST /accounts/{accountNo}/orders` (endpoint page) đối chiếu trang guide
`trading-api/trading_order`: **cùng một trường, hai kiểu chữ khác nhau.**

| Nguồn | `orderStatus` |
|---|---|
| Endpoint page, ví dụ response | `"PendingNew"`, `"New"` — **PascalCase** |
| Guide page, mô tả trạng thái | `pendingNew`, `partiallyFilled`, `filled` — **camelCase** |

**Quy tắc rút ra (bắt buộc):**

1. `orderStatus` là **lớp B** — giữ nguyên, **không** chuẩn hoá hoa/thường.
2. Tuyệt đối **không** hardcode một danh sách trạng thái trong code. Nếu mai DNSE đổi
   `PendingNew` → `pendingNew`, code hardcode sẽ hỏng âm thầm.
3. Vì hiện **chưa xác minh được server trả kiểu nào** (cần trading token thật) ⇒
   bất kỳ logic lọc/trạng thái nào thêm vào sau này **bắt buộc** so khớp
   case-insensitive, và ghi rõ là tạm.

Cùng kiểu mâu thuẫn này đã xuất hiện ở `bid[].qtty` (doc `quantity` / server `qtty`).
**Đây không phải lỗi vnbroker — đây là DNSE tài liệu thiếu chính xác.** Chính vì vậy
quy tắc số 6 ở §1 ("đừng dùng tài liệu để sửa tên field server không gửi") là bắt buộc,
không phải thói quen.

---

## 5c. Tiêu chuẩn bằng chứng cho thay đổi đường tiền thật

Từ vụ `post_order` (2026-10-09). Trước khi sửa **bất kỳ** endpoint đặt/hủy lệnh, cần đủ
3 mức bằng chứng:

| Mức | Nguồn | Ví dụ vụ `post_order` |
|---|---|---|
| 1 | Tài liệu chính thức | `POST /accounts/{accountNo}/orders`, `accountNo` path, required |
| 2 | SDK chính thức | `client.post_order` dùng đúng path đó |
| 3 | **Đo trực tiếp server** | `GET /accounts/orders` → **405**, không phải 404 ⇒ route thật |

Chỉ với mức 1+2 mà **không** có mức 3 thì **không sửa** — vì không biết route body-form
còn tồn tại hay không. Vụ này đủ 3 mức ⇒ đề xuất sửa **có cơ sở**.

### Kỹ thuật chẩn đoán: `405` phân biệt "route sai" với "route thật nhưng sai verb"

Khi không có token để POST, dùng **GET** (thường miễn token) để dò route:

```
GET /accounts/{acc}/orders   -> 200                          route thật, hợp lệ
GET /accounts/orders         -> 405 Method Not Allowed       route THẬT, chỉ nhận POST
GET /accounts/XYZ/orders     -> 401 "no access to account"    route thật + có kiểm tra quyền theo accountNo
GET /accounts/{acc}/nothing  -> 404 page not found            control: route không tồn tại
```

`405` chứng minh route tồn tại; `404` mới là bằng chứng route sai. Trước đó tôi chỉ thấy
`401` trên cả hai biến thể nên **không kết luận được** — và đã đúng khi không sửa.

---

## 5d. Kết luận vụ `post_order`

| Bằng chứng | Kết luận |
|---|---|
| Doc + SDK: `POST /accounts/{accountNo}/orders` | path-form là dạng chính thức |
| `GET /accounts/orders` → 405 | path-form **không** sai, vẫn chạy được |
| 5 method anh em trong `order_service.py` đã dùng path-form | `post_order` là **kẻ lạc lõng duy nhất** |
| `GET /accounts/XYZ/orders` → "no access to this account" | DNSE kiểm tra quyền **theo accountNo trong path** ⇒ path-form chặt hơn, body-form phải đoán account từ `trading-token` |

⇒ **Đề xuất:** đưa `post_order` về `/accounts/{account_no}/orders`, `accountNo` khỏi body.
Rủi ro thấp (route body-form vẫn tồn tại nên lỗi sẽ lộ ra ngay, không phải đặt nhầm lệnh).

**Chưa thực hiện** — cần Owner duyệt vì đây là đường đặt lệnh thật.

---

## 6. Quy tắc bất di bất dịch khi port

1. **Port đủ 39 method REST + 12 kênh WS market data.** Thiếu = chưa xong.
2. Mỗi method mới **bắt buộc** có docstring ghi:
   - lớp A hay B
   - nếu A: map field DNSE → cột chuẩn
   - nếu B: *"giữ nguyên theo DNSE OpenAPI, vì ..."*
3. Verb ghi (`POST/PUT/PATCH/DELETE`) **không** được bypass `DNSEHttpClient.request` —
   gate ở đó rồi (PM-01). Không thêm guard thủ công ở tầng trên.
4. Contract test: mọi method lớp A phải khớp `tests/contract/` hiện có.
5. Không sửa path khi chưa có bằng chứng từ server (bài học `post_order`).

---

## 7. Tài liệu tham chiếu trong repo

| File | Nội dung |
|---|---|
| `docs/provider/DNSE_WEBSOCKET.md` | Tài liệu WebSocket của DNSE + **bảng sai lệch đã đo** |
| `docs/provider/dnse_ws_schema_observed.json` | Schema quan sát được từ server thật |
| `docs/PLAN_DNSE_API_PARITY.md` | Kế hoạch port đủ API, chia 4 đợt |
| `docs/NORMALISATION_POLICY.md` | File này |

---

## 8. Bài học liên quan (đã trả giá)

- **Đo trước, sửa sau.** "Đổi `quantity` theo doc" sẽ ra 0 khối lượng, vì server gửi
  `qtty`. Nguyên tắc: tài liệu là điểm khởi đầu, **server mới là sự thật**.
- **Giả thuyết về path đã bị thực thi bác bỏ.** `post_order` được nghi ngờ sai; cả hai
  biến thể đều tồn tại. Không sửa đường tiền thật theo tài liệu khi chưa đo.
