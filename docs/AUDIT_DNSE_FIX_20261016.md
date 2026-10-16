# AUDIT_DNSE_FIX: Kiểm toán mã nguồn & diff (2 vòng)

- **Auditor**: subagent độc lập, read-only (vòng 1 + vòng 2, agent khác nhau)
- **Target Branch**: `feat/dnse-openapi-fix`
- **Diff Command**: `git diff f6cf68b...HEAD`
- **Vòng 1** (`f6cf68b...4746a8f`): **FAIL** — 1 blocker · 4 major · 15 minor
- **Vòng 2** (`f6cf68b...f0cbf68`): **FAIL** — 1 blocker · 1 major · 6 minor
- **Confidence**: `high`

> **Lessons áp dụng: [L-E01, L-E02, L-E06, L-P05, L-P06]**

## 1. Tóm tắt kiểm toán

Cổng 4→5 yêu cầu **0 blocker, 0 major**. Cả hai vòng đều **FAIL**. Điểm đáng
chú ý nhất: **blocker nghiêm trọng nhất do chính tôi tự gây ra**, bằng chính
công cụ dùng để tự kiểm chứng, và **không gate nào hiện có bắt được**.

Supervisor không tin lời subagent: mọi finding lớn đều được **tái lập bằng lệnh
chạy thật** trước khi sửa (mục 5).

## 2. Vòng 1 — 1 blocker + 4 major (đã sửa)

| # | Mức | Vị trí | Vấn đề | Trạng thái |
|---|---|---|---|---|
| 1 | 🔴 Blocker | `explorer/dnse/quote.py` `working_dates()` | Gọi `pd.json_normalize(body)` trực tiếp ⇒ shape **(1,1)** thay vì (3,1), trong khi `client._to_dataframe` cho (3,1). **Docstring tôi viết lại ("một dòng mỗi ngày") mô tả hành vi mà code không làm.** Chính là "thành công rỗng" lát B sinh ra để chữa, ở tầng khác | ✅ sửa: `normalize_payload` |
| 2 | 🟡 Major | `test_market_time_units.py` | `assert "gi" in doc.lower()` — **tautological**: tiếng Việt có "gi" trong "Giá"/"Giao"/"giới", xanh cả khi xoá hẳn ghi chú. Đo: 5/5 vẫn PASS | ✅ sửa: kiểm `"GIÂY"` |
| 3 | 🟡 Major | `core/time_utils.py` | `to_unix_seconds` **không được gọi ở đâu** ⇒ D8 vẫn reachable qua API công khai. Module + 5 test tạo cảm giác an toàn giả trong khi docstring khai là đang chặn | ✅ sửa: nối vào `_history_query` |
| 4 | 🟡 Major | `services/market_service.py` | Docstring secdef khai "24 ứng viên", report ghi **10** — thống số không có trong bằng chứng | ✅ sửa |
| 5 | 🟡 Major | `services/order_service.py` | `page_index=None` ⇒ URL chứa chuỗi `pageIndex=None` (400 khác, khó đọc). Docstring còn mô tả sai cơ chế | ✅ sửa + test |

## 3. Vòng 2 — 1 blocker + 1 major (đã sửa)

| # | Mức | Vị trí | Vấn đề | Trạng thái |
|---|---|---|---|---|
| 1 | 🔴 Blocker | 3 file nguồn | **Mojibake (double-encoding UTF-8)**: 318/65/207 dấu hiệu. File vẫn decode hợp lệ UTF-8 ⇒ **ruff PASS, 399 test PASS** — không gate nào bắt. `_SECONDS_NOTE` mất chữ `GIÂY`; thông điệp `DNSEValidationError` là rác | ✅ khôi phục + **thêm cổng `check_encoding.py`** |
| 2 | 🟡 Major | `get_market_index` | `is_same_vn_day` chạy trên **giá trị thô** trước khi chuẩn hoá ⇒ ms là `OSError: [Errno 22]` | ✅ chuẩn hoá trước, rồi mới so ngày |

### Nguyên nhân gốc của blocker vòng 2 — do tôi tự gây ra

```powershell
$orig = Get-Content -LiteralPath $f -Raw          # đọc UTF-8 bằng CP1252
... sửa ...
[System.IO.File]::WriteAllText($f, $orig, UTF8)    # ghi lại bản đã hỏng
```

Đây là **script mutation-test tôi viết để chứng minh test có giá trị** (bỏ fix
⇒ test phải đỏ). PowerShell 5.1 đọc file UTF-8 bằng codepage ANSI khi không kèm
`-Encoding`, nên biến `Ghi nhắc đơn vị` thành `Ghi nháº¯c Ä‘Æ¡n`, rồi tôi ghi bản
hỏng đó trở lại file và gọi đó là "khôi phục".

**Bài học:** công cụ tự kiểm chứng cũng là mã nguồn, và nó có thể làm hỏng thứ
đang được kiểm chứng. Đã thêm `scripts/check_encoding.py` vào `check_all.ps1`
để lỗi này **tự báo đỏ** thay vì lọt. Cổng ấy cũng bắt được một file hỏng
**có sẵn từ trước**: `tests/unit/core/test_no_guest_quota_runtime.py` có
`20 requests/phút` bị hỏng — khiến assert của test đó **không bao giờ chạm**
vào nguồn thật, tức bảo vệ một thứ vốn đã vô nghĩa mà vẫn xanh.

## 4. Điểm tích cực được ghi nhận

- **`core/http_client.py` không bị chạm** — xác nhận bằng `git diff` rỗng. Write
  gate còn nguyên.
- **Không write method nào bị đụng**; đường mới (`get_working_dates`) bắt buộc đi qua
  `self._http.request`.
- Các guard "chặn trước network" là **thật** — đã xác nhận `requests.api.request`
  dùng `sessions.Session()` rồi gọi `session.request`, nên patch có hiệu lực.
- Ngân sách 800L: `client.py` **779** dòng — dưới trần.
- **Mutation-test 4/4**: bỏ từng fix lần lượt thì test tương ứng đỏ (6/1/1/5 test).
  Đây là bằng chứng test có giá trị, không chỉ "xanh".

## 5. Supervisor tự tái lập (không tin lời subagent)

| Claim | Lệnh chạy | Kết quả thật |
|---|---|---|
| Blocker v1: quote.py shape (1,1) | `pd.json_normalize({"workingDates":[3 ngày]})` | `(1, 1)` — đúng như audit nói |
| Major v1 #2: test tautological | `doc.replace("unix **GIÂY**","")` rồi kiểm `"gi"` | **5/5 vẫn PASS** — đúng như audit nói |
| Major v1 #3: D8 reachable | `get_quotes(from_date=…000)` | `{'from': 1792137600000}` — ms đi thẳng qua |
| Major v1 #5: `pageIndex=None` | `get_orders(page_index=None)` | URL chứa `pageIndex=None` |
| Blocker v2: mojibake | đếm marker trên từng revision | `f6cf68b`: 0 · `3e25b71`: 0 (trừ test file) · `4746a8f`: **318/65/207** |
| Major v2: market_index crash | `get_market_index(from_date=…000)` | `OSError: [Errno 22]` |
| B1 plan audit: contract=117 | `pytest tests/contract -q` | **117 passed** — audit đúng, tôi đã chép nhầm 72 |

## 6. Điều cuối cùng phát hiện (ngoài phạm vi 2 vòng audit)

Khi **mạng production trở lại**, probe đã đóng nốt D10/D11 mà hai vòng audit vẫn
để mở — bằng cách **đọc response của server** thay vì đoán
(`GET /instruments` trả cột `marketId`). Chi tiết ở
`docs/REPORT_DNSE_LIVE_20261016.md` §12.2. Đây là kiểu phát hiện mà audit tĩnh
không thể tự sinh: cần mạng.

## 7. Nội dung KHÔNG verify được

- **`orderCategory` bắt buộc cho `get_orders`** — đo được `400 INVALID_ORDER_CATEGORY`
  khi thiếu, nhưng **quyết định** có nên làm bắt buộc ở client thì **còn treo**
  (xem §13 của báo cáo).
- **`403` ở `position_id=999999`** — đo lại 3 lần, vẫn `403`. Không kết luận.
- **Sandbox** — không probe lại; vẫn chưa biết nó chấp nhận `pageIndex`/`pageSize`.
- **`Trade` facade không forward** `page_index`/`page_size` — chưa sửa vì
  `trade.py` 1352L vượt ngân sách; người dùng `Trade` chỉ lấy được trang đầu.
- **WS tick stream** — không probe trong đợt này.
- **CI GitHub Actions** — billing, không chạy.