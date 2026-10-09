# KẾ HOẠCH — Bổ sung đầy đủ API DNSE chính thức vào `vnbroker`

**Ngày:** 2026-10-09 · **Căn cứ:** đối chiếu với SDK chính thức `dnse-tech/openapi-sdk`
(`python/dnse/api/client.py`, 665 dòng, 39 method REST) + tài liệu `developers.dnse.com.vn`.
**Nguyên tắc:** mọi con số dưới đây lấy từ script đếm trên source, không đếm tay.
Repo hiện tại: `dev = a84818a`, working tree có 1 file test chưa commit (xem §8).

> **Quy tắc bắt buộc khi port:** đọc `docs/NORMALISATION_POLICY.md` **trước khi viết code**.
> Mỗi method mới phải phân loại **lớp A (chuẩn hoá về form chung của vnbroker)** hay
> **lớp B (giữ nguyên định dạng DNSE)**. Mặc định là **lớp B** — chuẩn hoá phải được
> chứng minh, không phải mặc định. Đặc biệt mọi thông tin **explorer thị trường** thuộc lớp A.

---

## 1. Tổng quan thực trạng

| Bề mặt | SDK chính thức | vnbroker | Thiếu |
|---|---|---|---|
| **REST trading/account** | 39 method | 24 | **15** |
| **REST marketdata** | (13, gộp trong 39) | 5 | **8** (xem §3) |
| **REST broker** (`care-by`) | 1 | 0 | **1** |
| **WS marketdata** | 12 kênh | 11/12 alias | **1** (`market_index_influence`) |
| **WS trading** (order/position/broker_*) | 4 kênh | **0** | **4** |
| REST client (core) | 26 method | 47 method | — (legacy, sắp bỏ) |

**Kết luận quan trọng:** vnbroker đã phủ **24/39** method REST. Phần thiếu **không phải
toàn bộ** như handoff ghi "22 endpoint còn thiếu" — con số đó lấy từ so sánh thủ công và
đã lệch. Đo lại bằng script cho **15**.

---

## 2. Bảng 15 method REST còn thiếu

Kèm `verb` và `path` lấy thẳng từ SDK.

### 2.1 Nhóm chỉ đọc, rủi ro thấp — làm trước (7)

| # | Method | Verb | Path | Ghi chú |
|---|---|---|---|---|
| 1 | `get_quotes` | GET | `/price/{symbol}/quotes` | Độ sâu thị trường lịch sử, có `from_date/to_date/limit/order` |
| 2 | `get_latest_quote` | GET | `/price/{symbol}/quotes/latest` | Bản "mới nhất" |
| 3 | `get_expected_price` | GET | `/price/{symbol}/expected-price` | Dùng cho ATO/ATC |
| 4 | `get_foreign_trading` | GET | `/price/{symbol}/foreign-trading` | Room NĐT nước ngoài |
| 5 | `get_market_index` | GET | `/price/{index_name}/market-index` | Có phân trang `next_page_token` |
| 6 | `get_trades_volume_profile` | GET | `/price/{symbol}/trades/volume-profile` | Khối lượng theo bước giá |
| 7 | `get_loans` | GET | `/accounts/{account_no}/loans` | 6 tham số lọc |

### 2.2 Nhóm PnL config — **chạm tiền thật**, cần gate (5)

| # | Method | Verb | Path |
|---|---|---|---|
| 8 | `get_position_pnl_configs` | GET | `/positions/{position_id}/pnl-configs` |
| 9 | `post_position_pnl_configs` | POST | `/positions/{position_id}/pnl-configs` |
| 10 | `get_account_pnl_configs` | GET | `/accounts/{account_no}/pnl-configs` |
| 11 | `patch_account_pnl_configs` | PATCH | `/accounts/{account_no}/pnl-configs` |

> Đây là **cùng họ endpoint** với `trade.py:set_deal_pnl_config` / `set_account_pnl_config`
> đã có gate. Thêm vào OpenAPI **không được** quên gate — đó là đúng lỗi `eeb1965` mắc phải.

### 2.3 Nhóm ghi khác (3)

| # | Method | Verb | Path | Rủi ro |
|---|---|---|---|---|
| 12 | `reverse_position` | POST | `/positions/{position_id}/reverse` | **Cao** — đảo vị thế, tiền thật |
| 13 | `create_smart_otp_handoff` | POST | `/registration/smart-otp/handoff` | Trung bình — auth flow |
| 14 | `get_list_care_by` | GET | `/brokers/accounts/care-by` | Thấp — chỉ đọc |
| 15 | `get_lastest_session` | GET | `/market/trading-session` | Thấp — chỉ đọc (lỗi chính tả "lastest" của SDK, **giữ nguyên** để khớp) |

---

## 3. 4 path đang lệch — **CHƯA XÁC ĐỊNH ĐƯỢC, KHÔNG ĐƯỢC SỬA VỘI**

| Method | SDK | vnbroker |
|---|---|---|
| `get_instruments` | `/market/instruments` | `/instruments` |
| `get_working_dates` | `/market/working-dates` | `/working-dates` |
| `get_corporate_action_history` | `/accounts/{a}/corporate-action-history` | `/accounts/{a}/corporate-actions` |
| `post_order` | `/accounts/{account_no}/orders` | `/accounts/orders` |

**Đã thử cả hai bên trên sandbox `https://sb-openapi.dnse.com.vn`** → **cả 6 đều 404**.
Sandbox không implement nhóm market-data này, nên 404 **không chứng minh gì**.

### 3.1 `post_order` — **ĐÃ ĐÓ**, chờ Owner duyệt (2026-10-09)

Tài liệu `POST /accounts/{accountNo}/orders` + đo trực tiếp (kỹ thuật `405` phân biệt
"route sai" với "route thật nhưng sai verb"):

| Bằng chứng | Kết quả |
|---|---|
| Doc + SDK | `POST /accounts/{accountNo}/orders`, `accountNo` là **path param required** |
| `GET /accounts/orders` | **405 Method Not Allowed** ⇒ route body-form **tồn tại**, path hiện tại **không sai** |
| `GET /accounts/{acc}/orders` | **200** ⇒ path-form hợp lệ |
| `GET /accounts/XYZ/orders` | **401 "You do not have access to this account"** ⇒ DNSE kiểm tra quyền theo `accountNo` **trong path** |

⇒ `order_service.py:96` là **kẻ lạc lõng duy nhất**: 5 method anh em
(`get_orders:22`, `get_order_detail:40`, `put_order:118`, `cancel_order:139`,
`replace_order:161`) đều path-form, riêng `post_order` gửi `accountNo` trong **body**.

**Đề xuất:** đổi sang `/accounts/{account_no}/orders`, bỏ `accountNo` khỏi body.
Rủi ro thấp — route cũ vẫn tồn tại nên lỗi sẽ lộ ra ngay, **không** đặt nhầm lệnh.

⚠ **Chưa sửa** — đường đặt lệnh thật, cần Owner duyệt.

### 3.2 Ba điều tài liệu mới tiết lộ (đã kiểm tra — **không phải** bug)

| Phát hiện | Kết quả |
|---|---|
| `version` header **Required: true** | ✅ `http_client` đã gửi |
| Lệnh điều kiện (STOP/OCO) trả **201 Created** | ✅ `http_client.py:155` dùng `>= 400` ⇒ 201 hợp lệ |
| Response có `X-Ratelimit-Limit/Remaining/Reset` | ⚠ Chưa đọc — cơ hội cảnh báo hết quota **trước** khi gặp 429 |

### 3.3 DNSE tự mâu thuẫn: `orderStatus` PascalCase vs camelCase

Cùng một trường, hai kiểu chữ: endpoint page viết `"PendingNew"`, guide page viết
`pendingNew`. ⇒ **không chuẩn hoá, không hardcode danh sách trạng thái.**
Chi tiết: `NORMALISATION_POLICY.md` §5b.

> **Cấm sửa 3 path còn lại khi chưa có bằng chứng.** Bài học đã trả giá trong phiên này:
> giả thuyết "path sai" của tôi về `post_order` bị **thực thi bác bỏ**; nếu sửa theo
> tài liệu thì đã đổi đường đặt lệnh tiền thật dựa trên tin tưởng sai.

---

## 4. WebSocket trading — **4 kênh hoàn toàn thiếu**

SDK có `python/websocket-trading/`: `order.py`, `position.py`, `broker_order.py`,
`broker_position.py`. vnbroker **không có** tầng này.

| Kênh | Nội dung dự kiến | Rủi ro |
|---|---|---|
| `order` | Sự kiện lệnh của tài khoản | Trung bình — cần trading token |
| `position` | Sự kiện vị thế | Trung bình |
| `broker_*` | Dành cho broker/SACO (`/docs/guide/broker`) | Thấp — chỉ khi là broker |

**Quyết định đề xuất: hoãn.** Cần xác minh auth + protocol trước; tôi **chưa** đọc
4 file này đủ để kế hoạch chi tiết mà không đoán.

---

## 5. Kế hoạch thực thi — chia 4 đợt

### Đợt 1 — Market data read-only (rủi ro thấp, giá trị cao)

| Việc | File | Lớp | Gate |
|---|---|---|---|
| `get_quotes` → `price_depth` | `services/market_service.py` | **A** | contract test |
| `get_latest_quote` | `services/market_service.py` | **A** | contract test |
| `get_expected_price` | `services/market_service.py` | A (wrapper) | path test |
| `get_foreign_trading` | `services/market_service.py` | **B** | path test |
| `get_market_index` | `services/market_service.py` | A (wrapper) | path test |
| `get_trades_volume_profile` | `services/market_service.py` | A | contract test |
| `get_loans` | `services/account_service.py` | **B** | path test |
| thêm `market_index_influence` vào `CHANNEL_ALIASES` | `websocket.py` | A (kênh) | test alias |

**Không** chạm write gate. Đây là đợt có giá trị cao nhất vì phần lớn là **lớp A** — tức
đi thẳng vào form chung, dùng được ngay cho so sánh đa provider.

Bảng ánh xạ field cụ thể cho từng method: `docs/NORMALISATION_POLICY.md` §3.

⚠ **Cặm bẫy đã đo:** `bid[].qtty` — server gửi `qtty`, tài liệu ghi `quantity`. Map sang
`quantity` sẽ **im lặng trả 0 khối lượng**. Xem policy §3.1.

### Đợt 2 — Broker + PnL config **read** (chưa ghi)

| Việc | Ghi chú |
|---|---|
| `get_list_care_by`, `get_position_pnl_configs`, `get_account_pnl_configs`, `get_loans` | GET ⇒ **không cần** `enable_write`; gate hiện chỉ chặn verb ghi |

### Đợt 3 — PnL config **ghi** (4 method)

- `post_position_pnl_configs` (POST), `patch_account_pnl_configs` (PATCH)
- Bắt buộc: method mới ở service ⇒ `http_client.request` tự chặn (gate theo verb, đã
  làm ở PM-01) ⇒ **không cần** thêm guard thủ công
- Bắt buộc: test chặn `requests` chứng minh 0 request lọt — theo mẫu
  `test_write_gate_layer.py`

### Đợt 4 — `reverse_position` + `create_smart_otp_handoff`

- Chỉ làm sau khi đợt 3 có test thật
- `reverse_position` là **đảo vị thế** — cần xác nhận body/payload từ tài liệu
- `create_smart_otp_handoff` rate limit chỉ **3 request/giờ** (thấp nhất bảng) ⇒ cần
  chốt chống gọi dồn

---

## 6. Việc cần làm **ngoài** phạm vi bổ sung API (chặn correctness)

### 6.1 ✅ ĐÃ XONG — commit `3717306`

| Việc | Bằng chứng | Kết quả |
|---|---|---|
| `api_version` `2026-05-07` → `2026-07-23` | Doc + changelog | Sửa `config.py:11` **và** `client.py:24` — sửa một chỗ thì client vẫn truyền bản cũ |
| `get_accounts()` nuốt `name`/`custodyCode`/`investorId` | **Đã verify trên sandbox** | `_to_dataframe` lặp scalar của envelope vào mọi dòng; xác minh live sau khi sửa |
| ~~`403` = hết quota ngày, không được coi là lỗi failover~~ | **BỊ BÁC BỎ** | Không phải bug — xem §6.2 |

### 6.2 `403` — tôi đọc sai, đã bác bỏ giả thuyết

Tôi kết luận "cần sửa" sau khi **đọc** danh sách marker trong `source_router.py` mà **chưa chạy** code. Chạy thật:

```
str(DNSEAuthError('Quota exceeded', status_code=403)) == 'Quota exceeded'
should_failover(...)                              == False
```

Marker `"403"` **có** trong danh sách nhưng **chết**: `raise_for_status` lưu 403 vào
`.status_code`, không đưa vào message. Hành vi đã đúng ngay từ đầu.

3 test tương ứng giữ lại thành **characterisation test** — khoá hành vi đúng để refactor
sau này không vô tình coi mọi 403 là lỗi retry được.

### 6.3 Còn lại

| Việc | Cần cứu | Ưu tiên |
|---|---|---|
| Enum `OrderSide` nhân đôi, **trái giá trị** | `brokerage/base.py:19-21` = `"BUY"` vs `broker/ssi/_enums.py:16-18` = `"B"` | **cao** — `SIDE_NORMALISATION_RESEARCH.md` §2.1 |
| Bỏ `str(order_id)` nếu có | Changelog nói version mới tự trả string | trung bình — **chưa xác minh có code ép kiểu không** |

---

## 7. Rủi ro và điều kiện chặn

| Rủi ro | Mức | Xử lý |
|---|---|---|
| Production `openapi.dnse.com.vn` không phản hồi từ máy này | **cao** | Chỉ test được trên Sandbox. Sandbox **không** có nhóm market-data ⇒ đợt 1 chỉ verify được bằng **contract test đọc path**, không gọi thật |
| Sandbox không có `/market/*` | cao | Xác nhận bằng probe trước khi tin báo "chạy thật" |
| `qtty` vs `quantity` trong WS `bid`/`offer` | trung bình | Server gửi `qtty`, doc ghi `quantity`. Vì client WS **không parse payload**, vnbroker không lỗi — nhưng **tài liệu cho người dùng** phải nói `qtty` |
| `PONG_DEADLINE_SECONDS` là hằng chết | trung bình | Không liên quan đợt này, nhưng để mở |
| Client gửi PING vs doc nói PONG | thấp | Chưa rõ server chấp nhận cái nào |

---

## 8. Trạng thái repo khi lập kế hoạch

```
HEAD  : a84818a  [dev]  (sạch, đã push)
Untracked:
  docs/NORMALISATION_POLICY.md          <- quy tắc chuẩn hoá (mới)
  docs/PLAN_DNSE_API_PARITY.md         <- file này
  docs/provider/DNSE_WEBSOCKET.md      <- tài liệu DNSE + bảng sai lệch đã đo
  docs/provider/dnse_ws_schema_observed.json
  tests/unit/connector/dnse/test_provider_contract_fixes.py
```

File test là test cho **3 việc ở §6** (viết theo TDD, chưa implement). Nó **chưa** được
commit vì chưa chạy fail-before/pass-after. Kế hoạch §6 nên làm tiếp từ đây, **không**
viết lại file.

---

## 8b. Nguồn sandbox đã dùng để kiểm chứng

`https://sb-openapi.dnse.com.vn` — key `SB_API_KEY`/`SB_API_SECRET` trong `.env`.

Đã xác minh trên sandbox:
- `GET /accounts` → **200** (có `name`, `custodyCode`, `investorId`, `accounts`)
- `GET /accounts/{acc}/orders` → **200** `{'orders': []}`
- `POST /accounts/orders` **và** `POST /accounts/{acc}/orders` → **cả hai 401** ⇒ cả hai
  route tồn tại ⇒ path hiện tại **không sai**
- Nhóm `/market/*` và `/price/*` → **404** ⇒ sandbox **không** implement ⇒ các method
  market-data **chưa kiểm chứng được bằng server thật**, chỉ verify được bằng contract
  test đọc path

Rate limit theo tài liệu: `/Get Accounts` 1.000/giờ · `/Place Order` 50.000/giờ
(`Quotas: 100.000/ngày`) — sandbox có trần riêng.

---

## 9. Lệnh tái lập độ chênh lệch

```powershell
cd "C:\Mujoco Projects\vnbroker"
$py = ".\.venv\Scripts\python.exe"
# 39 method SDK -> %TEMP%\dnse_sdk\_rest_methods.txt   (download tu raw.githubusercontent)
# so sanh voi vnbroker:
& $py "$env:TEMP\gap.py"        # -> CO 24 / THIEU 15
& $py "$env:TEMP\sdk_client.py" # -> bang 39 method + verb + path tu SDK
```

---

## 10. Tóm tắt cho quyết định

- **Ưu tiên 1 (đề xuất):** §6 ba việc correctness — rẻ, đã có bằng chứng, không thêm API mới.
- **Ưu tiên 2:** Đợt 1 — 7 method market-data read-only + 1 WS alias. Giá trị cao nhất, rủi ro thấp nhất.
- **Ưu tiên 3:** Đợt 2 — 4 method read.
- **Hoãn:** Đợt 4 (`reverse_position`), WS trading (4 kênh), 3 path chưa xác định.

**Cần Owner:**

1. Duyệt `post_order` → `/accounts/{account_no}/orders` (đã đủ 3 mức bằng chứng, §3.1).
2. ~~`side` DNSE chuẩn hoá không?~~ **ĐÃ CHỐT 2026-10-09:** giữ nguyên `NB`/`NS` (lớp B).
   Chi tiết + cảnh báo cột `side` của `trades`: `NORMALISATION_POLICY.md` §5a.
3. Production `openapi.dnse.com.vn` timeout 3/3 dù không giới hạn IP — nguyên nhân?
   Đợt 1-4 chỉ kiểm chứng được trên Sandbox; production phải chờ bạn mở.
