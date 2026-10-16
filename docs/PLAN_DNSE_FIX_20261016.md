# PLAN_DNSE_FIX: Sửa 11 defect client DNSE OpenAPI (đo production 2026-10-16)

> **Lessons áp dụng: [L-R01, L-R02, L-R03, L-R04, L-R06, L-E01, L-E02, L-E04, L-E06, L-P03, L-P04, L-P05, L-P06]**
>
> **Bản 2** — sửa sau `docs/PLAN_AUDIT_DNSE_FIX_20261016.md` (`NEED_REVISION`,
> 4 blocker · 7 major · 6 nhỏ). Mỗi mục dưới đây đánh số theo mã finding của audit.

- **Repo**: vnbroker · **Author**: coordinator (**Mode B solo** — xem §3)
- **Target Branch**: `feat/dnse-openapi-fix` (tách từ `f6cf68b`)
- **Integration Branch**: `main` (`origin/main`) — **không phải `dev`** (`dev` ở
  `6ca4495`, v3.6.0; `docs/AGENT_PROTOCOL.md` §3)
- **Base hash cho diff/audit**: `f6cf68b` · **Date**: 2026-10-16

## Target Files (phạm vi claim)

| Slice | File sửa | Ghi chú audit |
|---|---|---|
| A | `connector/dnse/core/time_utils.py` (mới) · `services/market_service.py` | import trực tiếp `...core.time_utils`, **không** đụng `core/__init__.py` (**M6**) |
| B | `services/market_service.py` · `client.py` (`_to_dataframe` key list + facade) · `explorer/dnse/quote.py` | thay task ảo bằng việc thật (**M4**) |
| C | `services/order_service.py` · **`client.py:185-201` + `:243-265`** · `docs/DNSE_API_CONTRACT.md` (**M5**) · `vnbroker/broker/capabilities.py:162-165` (**M5**) | `client.py` **bắt buộc** phải sửa, nếu không AC-C1 không thỏa qua API công khai (**M6**) |
| D | `services/market_service.py` · `client.py` · `tests/.../test_market_data_read_methods.py` (**B4**) | |
| E | `services/account_service.py` · `services/position_service.py` · **`tests/contract/test_dnse_endpoint_contract.py`** (**B2**) | **bỏ** `client.py` — lát E không sửa facade (**M6**) |
| F | `scripts/probe_dnse_readonly.py` (**M1**, **M2**) · `docs/DNSE_API_CONTRACT.md` | không sửa code production |
| test | `tests/unit/connector/dnse/test_market_time_units.py` (mới) · `test_order_read_params.py` (mới) · `test_position_id_guard.py` (mới) | |

> **Ngoài phạm vi, đã biết, không sửa:** `connector/dnse/trade.py` (1352L, vượt
> ngân sách từ trước). Hệ quả: `Trade.get_orders`/`get_order_history`
> (`trade.py:1065-1079`, `:1117-1137`) **không forward** `page_index`/`page_size`
> mới. Ghi rõ ở đây để không ai "fix sau" rồi phá L-P03 (**N5**).

---

## 1. Mục tiêu & Bối cảnh

`docs/REPORT_DNSE_LIVE_20261016.md` §9 liệt kê 11 defect (D1-D11) đo được trên
production. **Root cause chung:** vnbroker viết path/tham số theo phỏng đoán rồi
đóng băng, không có lớp kiểm chứng nào bắt được với server thật.

Hai ví dụ đã chứng minh cơ chế này:

1. `services/market_service.py:44-50` — `get_working_dates` trả
   `({"dates": []}, None)`, **không gọi network**. Docstring `:47` khẳng định
   *"DNSE OpenAPI does not have a dedicated working-dates endpoint"*. **Câu đó
   sai** — đo production trả **200, 257 `workingDates`** tại `/market/working-dates`.
2. `services/account_service.py:72` — path `/accounts/{a}/corporate-actions` →
   `404 API ROUTE NOT FOUND`; path `/accounts/{a}/corporate-action-history` →
   **200**.

Cả hai là **path sai**, không phải endpoint vắng. Ghi chú về tiền đề (**N6**): tài
liệu mới nhất trong repo về 2 path này là `docs/PLAN_DNSE_API_PARITY.md:71-81` và
`:118-120`, nói ngược — *"CHƯA XÁC ĐỊNH ĐƯỢC, KHÔNG ĐƯỢC SỬA VỚI"*. Nên lát B/E
ở đây **không phải đảo một quyết định đã ban** — chúng **lần đầu** thực hiện
điều tài liệu đó cấm, dựa trên bằng chứng đo.

## 2. Phạm vi & Giới hạn rõ ràng

### In-Scope
- [x] D8, D9 — `from`/`to` là unix **giây**; `market_index` cần `from`/`to` cùng ngày
- [x] D1 — `get_working_dates`: nối `/market/working-dates` thật
- [x] D2, D3, D4 — `get_orders` thiếu `pageIndex`; `get_order_history` cần cả hai
- [x] D7 — `get_trades_volume_profile`: `time` là date string
- [x] D5 — `get_corporate_action_history`: sửa path
- [x] D6 — `get_position_by_id`: chặn `position_id` không phải số
- [x] D10, D11 — ghi bằng chứng âm + đưa probe vào repo để tái lập được

### Explicit Non-Goals

1. **Không sửa write path** (`post_order`, `put_order`, `cancel_order`,
   `replace_order`, `close_position`, `create_trading_token`, `send_email_otp`).
2. **Không sửa `core/http_client.py`** — write gate là choke point money lane
   (`docs/AGENT_PROTOCOL.md` §5). `validate_query` đã validate ở đó.
3. **Không bịa tập giá trị `boardId`/`marketId`** (lát F).
4. **Không đổi chữ ký public của `DNSEClient`/`Trade`** ngoài **2 case ở lát D và
   lát C** (lát E giữ nguyên chữ ký — chỉ sửa path bên trong thân).
5. **Không chạm `trade.py`** (>800L).
6. **Không nối endpoint mới** ngoài 2 endpoint có bằng chứng 200.
7. Không merge vào `main` — Owner duyệt.
8. **Mọi tham số mới phải giữ `dry_run`/`raw` ở vị trí cuối, không chen `*,` giữa
   các tham số** — `tests/unit/connector/dnse/test_write_safety.py:7` khai danh
   sách read method có `dry_run`.

## 3. Vì sao Mode B (tuần tự)

Lát A, B, D đều sửa `services/market_service.py`; A, B, C, D đều sửa `client.py`.
Giao ⇒ không rời ⇒ chạy song song sẽ tái tạo Hazard 1 (weld hunk). Tiền lệ:
`docs/CLAIMS.md:205-206` (TCBS Round 3).

## 4. Tác động kiến trúc & cấp song hành

| Kiểm | Kết quả |
|---|---|
| Engine/twin-repo | Không — thư viện Python độc lập |
| Migration/leaf | Không |
| Free/Pro boundary | Không có tier trong repo |
| Ngân sách dòng | xem §6 |
| `check_lessons` | **KHÔNG kiểm dòng `Lessons áp dụng`** — script chỉ quét `docs/LESSONS/` (`scripts/check_lessons.py:43`, `:66-153`). Đo: `24/40 lesson`, exit 0. Dòng trong plan là **quy ước của tôi, không phải gate** (**M3**) |

## 5. Lát cắt

Thứ tự: **A → B → C → D → E → F**.

---

### Slice A — Đơn vị thời gian + chặn `market_index` khác ngày (D8, D9)

**Đo được:** `from`/`to` là unix **giây** (ms → `400 range exceeds maximum time
range`). `get_market_index` cần `from`/`to` **cùng một ngày** (khác ngày →
`400 from and to must be in the same date`).

**Vì sao quan trọng:** 5 method khai `from_date: int | None` mà **không nói đơn
vị** — `market_service.py:109-119` (`get_quotes`), `:155-165` (`get_expected_price`),
`:176-186` (`get_foreign_trading`), `:200-209` (`get_market_index`), `:52-78`
(`get_trades`). Truyền `int(time.time()*1000)` — thói quen phổ biến — là hỏng ngay.

**Thay đổi:**
1. `core/time_utils.py` (mới): hàm thuần `to_unix_seconds(value) -> int`,
   `vn_day_bounds(value) -> tuple[int, int]`. Không I/O ⇒ test đơn vị không cần
   network.
2. Docstring ghi rõ **đơn vị = giây** cho 5 method trên, ở **cả** service
   (`market_service.py`) **và** facade (`client.py:438-557`).
3. `get_market_index` chặn khác-ngày **trước** network.
4. `get_trades` (`market_service.py:52-78`) hiện dựng query **thủ công** trong khi 4
   method kia dùng `_history_query` (`:80-107`) cùng tên key → cho nó dùng chung.

**AC (kiểm offline được):**
- **AC-A1**: Given `to_unix_seconds(datetime(...))`, When gọi, Then trả **giây**
  (≈1.7e9), không phải ms (≈1.7e12).
- **AC-A2**: Given `get_market_index(from=ngàyA, to=ngàyB)`, When gọi, Then raise
  `DNSEValidationError(message=..., error_code="MARKET_INDEX_RANGE_NOT_SAME_DAY",
  status_code=400)` và **số request HTTP = 0**.
- **AC-A3**: Given `get_market_index` from/to cùng ngày, When `dry_run`, Then `from`
  và `to` đi qua nguyên giá trị (không bị đổi đơn vị).
- **AC-A4** *(không tautology — **N1**)*: Given monkeypatch `_history_query` thành
  hàm đếm lời gọi, When gọi lần lượt `get_trades` và `get_quotes`, Then **cả hai đều
  gọi nó** ⇒ chặn được người viết lại dict thủ công. *(Nếu chỉ so dict bằng nhau thì
  đây là hệ quả tất nhiên, xanh cả khi lỗi còn — không dùng làm bằng chứng.)*

---

### Slice B — `get_working_dates` (D1)

**Đo được:** `GET /market/working-dates` → **200**, `{"workingDates": [257 phần tử]}`.
Thêm `marketType` → **404**. Nên gọi **không có query**.

**Thay đổi:**
1. `market_service.py:44-50` → `self._http.request("GET", "/market/working-dates",
   dry_run=dry_run)`. Xoá docstring sai ở `:47`.
2. **`client.py:72-77`** — thêm `workingDates` vào danh sách key của `_to_dataframe`.
   Không có bước này thì `get_working_dates(raw=False)` trả DataFrame **1 dòng**
   chứa một cell là list — tức **tái tạo đúng bug "thành công rỗng" mà lát này sinh ra
   để chữa** (**M4**, vi phạm L-R01).
3. `explorer/dnse/quote.py:615-634` — nay **gọi network thật**. Docstring phải nói rõ
   điều này; trên sandbox `/market/*` là 404 ⇒ `except Exception` trả DataFrame rỗng
   **im lặng** — phải giữ `logger.warning` và nói rõ hành vi.
4. ~~`client.py:666-669` bỏ `dry_run` trùng~~ — **xoá, task ảo**: chỉ có một lượt
   truyền `dry_run`, facade vốn đã đúng (**M4**).

**AC (kiểm offline được):**
- **AC-B1**: Given `dry_run=True`, When gọi, Then envelope `url` kết thúc bằng
  `/market/working-dates` và `query == {}` (không `marketType`).
- **AC-B2**: Given `_to_dataframe({"workingDates": ["2026-10-16", ...]})`, When chạy,
  Then DataFrame có **2 dòng** và cột `workingDates` — chứng minh bước 2 thật sự
  tác dụng (không phải task ảo).
- **AC-B3**: Given `explorer/dnse/quote.py::working_dates` chạy với payload thật
  ghim trong test, When chạy, Then DataFrame có cột và **không** phải 1 dòng.

> **CHƯA CHẠY (tách khỏi AC — **N2**):** AC-B3 phiên bản "≥1 dòng với dữ liệu
> thật từ server" cần mạng; xem §9.

---

### Slice C — Tham số đọc lệnh (D2, D3, D4)

**Đo được:**
- `get_orders`: prod `400 pageIndex is required`. Sandbox **không đòi**.
- `get_order_history`: thiếu cả hai → `400 from is required`; chỉ `from` →
  `400 to is required`. Nhận date string `yyyy-MM-dd` → 200.

**Thay đổi:**
- `services/order_service.py:10-25` → thêm `page_index: int = 1`,
  `page_size: int | None = None`, luôn gửi `pageIndex`. Docstring ghi rõ *production
  bắt buộc, sandbox không* — lý do không để `None`.
- **`client.py:185-201`** → forward `page_index`/`page_size`; **`client.py:243-265`**
  → forward `page_index`/`page_size` cho history (**M6**: không có bước này thì
  AC-C1 không thỏa qua API công khai).
- `services/order_service.py:60-84` → `from_date`/`to_date` phải **có cả hai hoặc
  không có gì**; đúng một cái ⇒ `DNSEValidationError(message=...,
  error_code="ORDER_HISTORY_RANGE_INCOMPLETE", status_code=400)` **trước** network
  (L-R01). Docstring nêu rõ format `yyyy-MM-dd` ≠ unix giây của price endpoints (D4).
- `docs/DNSE_API_CONTRACT.md:31` + `vnbroker/broker/capabilities.py:162-165` → cập
  nhật chữ ký/nghĩa (**M5**). `test_capability_contract.py:72-84` dùng
  `inspect.signature` nên **không** bắt được doc drift.

**AC (kiểm offline được):**
- **AC-C1**: Given `client.get_orders(...)` không truyền `page_index`, When
  `dry_run=True`, Then envelope `query["pageIndex"] == 1`.
- **AC-C2**: Given `get_order_history(from_date="2026-10-01")` (thiếu `to`), When gọi,
  Then raise `DNSEValidationError` và **số request HTTP = 0**.
- **AC-C3**: Given đủ `from`+`to`, When `dry_run`, Then `query["from"] ==
  "2026-10-01"` (giữ nguyên chuỗi, không ép sang số).

> **L-R03 — kiểm response thiếu field.** `pageIndex`/`pageSize` **không nằm trong
> `required`** của bất kỳ spec nào trong repo ⇒ phải đọc bằng `.get()` và test
> response **không** có field đó. Đưa vào AC-C1 (envelope có field) + một test
> parse envelope thiếu field.

---

### Slice D — `get_trades_volume_profile` (D7)

**Đo được:** `time=1700` (int) → `400 invalid param 'time', expected format
yyyy-MM-dd`; `time="2026-10-16"` → **hết lỗi time** (server chuyển sang kiểm
`boardId`). Thiếu `boardId` → `400 missing param 'boardId'`.

Client đang khai `time: int` (`market_service.py:226`, `client.py:562`).

**Thay đổi:** `time: str` (date `yyyy-MM-dd`) ở service + facade; `board_id` **bắt
buộc** (chặn trước thay vì để server 400 — L-R01).

> ⚠ **Đổi chữ ký public** — `time` đổi kiểu, `board_id` thành bắt buộc ⇒ caller cũ
> gọi `("MBS", time=1700)` sẽ hỏng. Chấp nhận: số sai kiểu là lỗi thật đã đo, và
> caller cũ đang gửi thứ server từ chối.

**Sửa test cũ — đủ 4 call site (**B4**), không phải 3:

| Dòng | Test | Sửa thành |
|---|---|---|
| `test_market_data_read_methods.py:158-160` | `test_..._path` | `time="2026-10-16", board_id="HOSE"` |
| `:163-166` | `test_..._time_is_required` | `time="2026-10-16", board_id="HOSE"` |
| `:169-171` | `test_..._cannot_drop_the_required_time` | **giữ nguyên** — vẫn là `TypeError` |
| `:310` | trong `test_none_of_the_seven_can_reach_the_write_gate` | `time="2026-10-16", board_id="HOSE"` — plan bản 1 **bỏ sót dòng này** |

**AC (kiểm offline được):**
- **AC-D1**: Given `time="2026-10-16", board_id="HOSE"`, When `dry_run`, Then
  `query["time"] == "2026-10-16"` (**string**) và `query["boardId"] == "HOSE"`.
- **AC-D2**: Given thiếu `board_id`, When gọi, Then `TypeError` **trước** network.
- **AC-D3**: Given `time` là `int`, When gọi, Then raise `DNSEValidationError`
  (`error_code="INVALID_TIME_FORMAT"`) — không gửi `1700` để đổi 1 lượt 400.

---

### Slice E — `corporate_action_history` + `position_by_id` (D5, D6)

**Đo được:**
- D5: `/accounts/{a}/corporate-actions` → `404 API ROUTE NOT FOUND`.
  `/accounts/{a}/corporate-action-history` → **200**, body
  `{accountNo, data, pagination}`. Có và không có `marketType` đều 200.
- D6: `/positions/{id}` — `id="fake"` → `500 For input string: "fake"`;
  `id=0`/`1` → `404 deal not found` (path **đúng**); `id=999999` → `403`.

**Thay đổi:**
- `services/account_service.py:72`: path → `corporate-action-history`. Giữ nguyên
  chữ ký `(account_no, market_type, from_date, to_date)`. SDK có thêm
  `symbol`/`caType`/`caStatus`/`pageIndex`/`pageSize` — **không** thêm (minimal
  change; không có defect đo được cho chúng). **Không sửa `client.py`** (**M6**).
- `services/position_service.py:18-28`: validate `position_id` là số.

> ⚠ **Thứ tự guard đã chốt trước khi code (B3).** `tests/unit/connector/dnse/
> test_market_type_validation.py:160-173` parametrize trên **mọi** method có
> `market_type`, điền mọi tham số bắt buộc bằng `"x"` và assert
> `error_code == "INVALID_MARKET_TYPE"`. Nếu guard `position_id` chạy trước thì
> `error_code` khác ⇒ test đỏ. Vì vậy trong `get_position_by_id`:
> **kiểm `marketType` trước, `position_id` sau** — khớp chính sách "validation
> TRƯỚC gate" ghi ở `core/http_client.py:83-90`. Thêm 1 test ghim thứ tự này.

**AC (kiểm offline được):**
- **AC-E1**: Given `get_corporate_action_history(...)`, When `dry_run`, Then `url`
  chứa `corporate-action-history` và **không** chứa `corporate-actions`.
- **AC-E2**: Given `get_position_by_id(market_type="STOCK", position_id="fake")`, When
  gọi, Then raise `DNSEValidationError` và **số request HTTP = 0**.
- **AC-E3**: Given `position_id=0` (số hợp lệ về hình thức), When `dry_run`, Then
  **không** raise — chỉ chặn sai *kiểu*, không chặn sai *giá trị*.
- **AC-E4** *(thứ tự guard)*: Given `market_type="ALL"` + `position_id="fake"`, When gọi,
  Then `error_code == "INVALID_MARKET_TYPE"` — marketType thắng.

**Sửa test cũ (B2):** `tests/contract/test_dnse_endpoint_contract.py:105` và `:130`
dùng `position_id="POS1"` ⇒ sẽ raise trước ⇒ `capture["url"]` không bao giờ gán ⇒
fail. Sửa thành giá trị số (`"1"`). **Không** đổi *nghĩa* kiểm path.

---

### Slice F — `boardId`/`marketId` (D10, D11) — không sửa code, làm bằng chứng tái lập được

**Đo được — bằng chứng âm:**

| Endpoint | Kết quả với 24 giá trị ứng viên |
|---|---|
| `/price/HPG/secdef?boardId=X` | **500 Internal error** — mọi X, kể cả `HOSE` |
| `/price/HPG/trades/volume-profile?boardId=X` | **404 `not found boardId`** — mọi X |
| `/instruments?marketId=X` | **400 `'oneof'`** — mọi X |

Ứng viên: `0`–`5`, `HOSE`, `HNX`, `UPCOM`, `DOWNNEX`, `HNXUPCOM`, `ALL`,
`HOSE_STOCK`, `HNX_STOCK`, `UPCOM_STOCK`, `HOSE.ETF`, `HOSE_INDEX`,
`HOSE.DERIVATIVE`, `ETF`, `ETFS`, `STOCK`, `EQUITY`, `INDEX`, `HOSE-HNX-UPCOM`,
`HOSE,HNX,UPCOM`, `HOSE|UPCOM`, `HNXUPCOM_STOCK`, `STOCK_HOSE`, `DERIVATIVE`.

**Quyết định: KHÔNG thêm enum.** Thêm tập đoán = bịa spec (L-P06).

**Nhưng từ điển sai có thật, phải thử trước khi kết luận (phản biện của audit):**
- `connector/dnse/websocket.py:19` — kênh `top_price.G1.json`, `tick.G1.json`.
- `websocket.py:278` — `mid = f"{product_group_id or 'STO'}.{board_id}"` ⇒ `board_id`
  kiểu `G1`.
- `explorer/dnse/listing.py:29` — `/instruments` **trả cột `boardId`** ⇒ lấy từ điển
  server tự trả về chỉ tốn 1 request.
- Lỗi `'oneof'` của `marketId` nghĩa là **chính server nói** có một tập giá trị;
  body lỗi đã bị cắt trong lần probe đầu ⇒ phải đọc **đầy đủ** `exc.payload`.

⇒ **Slice F bắt buộc chạy 3 probe này trước khi chốt kết luận**, và chúng phải nằm
trong `scripts/probe_dnse_readonly.py` để người sau không thử lại từ đầu (**M1**,
**M2**). Nếu mạng không cho ⇒ kết luận ghi **CHƯA CHẠY**, không phải "đã hết cách".

**AC (kiểm offline được):**
- **AC-F1**: Given `get_security_definition("HPG")` không truyền `board_id`, When
  `dry_run`, Then envelope **không** chứa `boardId` — tham số thật sự tuỳ chọn.
- **AC-F2**: Given docstring mới, When đọc, Then có câu *"chưa tài liệu hoá"* (test
  assert chuỗi, để lát sau không xoá âm thầm).

## 6. Ngân sách dòng (L-P03) — đo bằng `len(text.splitlines())`

PowerShell `Measure-Object -Line` **không** đếm dòng rỗng, đã làm sai một lần
(`docs/CLAIMS.md:306-312`). Số dưới đây auditor đo lại bằng read tool, **7/7 đúng**.

| File | Hiện tại | Kế hoạch | Kết luận |
|---|---|---|---|
| `client.py` | **713** | **+25** (docstring đơn vị cho 5 method ở `client.py:438-557` + chữ ký lát C/D) — **không phải +10** (**N4**) | ✅ dưới 800L |
| `services/market_service.py` | 275 | +25 | ✅ |
| `services/order_service.py` | 166 | +18 | ✅ |
| `services/account_service.py` | 119 | ±0 | ✅ |
| `services/position_service.py` | 44 | +8 | ✅ |
| `core/time_utils.py` | mới ~45 | | ✅ |
| `explorer/dnse/quote.py` | 682 | ±5 | ✅ |
| `trade.py` | **1352** | **không chạm** (đã vượt từ trước) | ⚠ cấm |

Không lát nào đẩy file nào qua 800L ⇒ **không cần tách file** trong đợt này.

## 7. Chiến lược rollback

Mỗi lát là **một commit riêng**:
```
git revert <commit-lát>      # hoặc: git checkout f6cf68b -- <file của lát>
```
Không migration, không state persist ⇒ rollback thuần đảo file.

## 8. Baseline gate (đo tại `f6cf68b`, máy dev)

| Lệnh | Kết quả | Exit |
|---|---|---|
| `pytest tests/ -q --timeout=300` | **2177 passed, 26 skipped**, 3 subtests (187s) | 0 |
| `pytest tests/contract -q` | **117 passed** (65.86s) — *đã đo lại sau audit B1* | 0 |
| `pytest tests/unit/connector/dnse tests/contract -q` | 332 passed | 0 |
| `ruff check vnbroker tests/unit tests/contract` | All checks passed | 0 |
| `ruff check tests` | **13 lỗi KNOWN-RED** (đỏ có sẵn — chỉ đòi không tăng) | 1 |
| `mypy vnbroker` | ~1138 lỗi — **không phải gate** (`--strict` là no-op) | 1 |
| `scripts/check_mypy_baseline.py` | `OK (baseline 1266, now 1138)` | 0 |
| `scripts/check_lessons.py` | 24/40 lesson | 0 |

> **B1:** bản 1 của plan ghi contract = **72 passed** — con số đó lấy từ
> `docs/AGENT_PROTOCOL.md` cũ, vốn copy `CLAUDE.md` đã lỗi thời. Đo lại: **117**.
> `CLAUDE.md` ghi "1414 passed, 30 skipped" cũngngừng cũ. Mọi số trong bảng này là
> **số đo**, không phải số chép.

## 9. Điều KHÔNG verify được (ghi trước, không tính PASS)

1. **CI GitHub Actions** — job bị từ chối do billing; badge không phải bằng chứng.
2. **Lệnh thật** — không lệnh nào được gửi; write chỉ test dry-run envelope + write
   gate.
3. **`Trade.login()` JWT** — `.env` thiếu `DNSE_USERNAME`/`DNSE_PASSWORD`.
4. **WS tick stream** — 0 frame/60s ở đợt đo trước; chưa xác nhận.
5. **Từ điển `boardId`/`marketId` hợp lệ** — giả thuyết `G1`/`STO.G1` **chưa kịp
   thử**. 24 ứng viên đoán đều thất bại **không** đồng nghĩa là không tồn tại giá
   trị hợp lệ.
6. **`403` ở `position_id=999999`** — chưa rõ là biên quyền hay gì; **không** kết luận.
7. **Điều kiện mạng đã đổi giữa phiên.** Bằng chứng D1/D5 thu được **ở đầu phiên,
   không VPN**. Về sau (~16:40) TLS handshake tới `openapi.dnse.com.vn` timeout
   **3/3 lần** (12.5s/lần) — đúng triệu chứng "có VPN" ở
   `REPORT_DNSE_LIVE_20261016.md` §1. Hệ quả: **re-probe live ở Stage 6 sẽ là
   CHƯA CHẠY** trừ khi mạng về; Slice F chưa chốt được.
8. **Sandbox có chấp nhận `pageIndex` không** — report §9 D2 chỉ nói sandbox "không
   đòi", **không** nói "chấp nhận". `tests/integration/test_dnse_integration.py:189-198`
   là test duy nhất chạm server cho `get_orders` ⇒ **CHƯA CHẠY**.