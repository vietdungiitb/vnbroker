# AUDIT ĐỘC LẬP — `docs/PLAN_TCBS_ROUND2.md`

**Auditor:** agent chỉ-đọc, khác model với tác giả plan · **Ngày:** 2026-10-10
**Đối tượng:** `docs/PLAN_TCBS_ROUND2.md` @ `dev @ b18e47b`
**Cây repo sau audit:** sạch (chỉ có file plan chưa commit). Auditor không sửa file nào.

## Verdict: `AGREE` (sau khi sửa) — ban đầu `NEED_REVISION`

Plan đúng về **mặt số liệu**: auditor tự viết script riêng, đo lại **7/7 gate rẻ khớp
tuyệt đối** và **4/4 tiền đề đúng về dữ kiện**. Vấn đề nằm ở **3 chỗ plan mô tả sai
thế giới thực**, đều đúng vị trí agent sẽ dựa vào để code.

---

## 0. Baseline auditor đo lại được

| Gate | Lệnh | Exit | Số auditor đo | Khớp plan |
|---|---|---|---|---|
| ruff src | `ruff check vnbroker` | 0 | `All checks passed!` | ✅ |
| ruff tests | `ruff check tests` | **1** | `Found 13 errors` | ✅ |
| mypy | `scripts/check_mypy_baseline.py` | 0 | `no new strict errors (baseline 1266, now 1161)` | ✅ |
| contract | `pytest tests/contract -q` | 0 | `72 passed` | ✅ |
| pytest `-k tcbs` | `pytest tests/ -q -k "tcbs"` | 0 | `491 passed, 7 skipped, 1224 deselected` | — |
| collect-only | `pytest tests/ --collect-only` | 0 | `1719 collected` | ⚠ lệch với 1696+26=1722 |
| ngân sách 800L | đếm file | — | 12 file >800L toàn repo | ✅ |

**CHƯA CHẠY:** full pytest (3 phút) — auditor được yêu cầu bỏ qua. Không suy ra "chắc là
xanh".

---

## 1. Phản bác tiền đề — auditor tự viết script, không dùng script của plan

| Tiền đề | Kết luận auditor | Đối chiếu của coordinator |
|---|---|---|
| P1 — không có endpoint refresh token | ✅ Đúng. Quét 48 path × 48 operation; chuỗi `refresh` (không phân biệt hoa thường) trong toàn spec = **0 lần** | ✅ Tôi tự đếm: **0** |
| P2 — response token không có `expiredTime` | ✅ Đúng về dữ kiện. `auth.py:118` → `_parse_expires(None)` → `auth.py:157` trả `None` | ✅ |
| P2 — *"hệ quả: session không bao giờ hết hạn"* | ❌ **SAI.** `session.py:87-90` rơi vào `else` ⇒ `now + 28800s`. Session hết hạn sau **8 giờ bịa đặt** | ✅ Tôi đọc `session.py:76,87-90` — xác nhận |
| P3 — 48 / 36 dict / 12 ngoài dict / 9 thật | ✅ Khớp từng con số | ✅ `scripts/verify_tcbs_coverage.py` cho **9** |
| P4 — `apikey/extend` gia hạn API key, cần OTP | ✅ Đúng cả hai vế (`required: ['apiKey','otp']`) | ✅ |
| §1b — spec cũ 75.678 B, 3.1.0, 18 path `/erebos/*`, untracked | ✅ Khớp tuyệt đối | ✅ |

---

## 2. CONTRADICTIONS (plan vs code)

| # | Plan nói | Code thực tế | Tác động |
|---|---|---|---|
| C-1 | Plan dựa cả plan vào `docs/references/openapi-v1.0.0.json` + `verify_tcbs_coverage.py` | **Cả hai file KHÔNG tồn tại** khi audit | **Blocker** — 3 agent sẽ phải đoán field, đúng thứ plan cấm |
| C-2 | "session không bao giờ tự hết hạn" | `session.py:76,87-90` bịa 8 giờ | **Blocker** — bug sống: token chết vẫn dùng, 401 thay vì lỗi sạch |
| C-3 | "chỉ `akhlys/…/cancel-orders` mới cần `requestId`" | Spec `required: ['ordersList']`, **không** có `requestId`. `equity.py:523-525` vẫn gửi | **Major** — chú thích plan sai ⇒ AC M6 viết trên tiền đề sai |
| C-4 | Lát E tách `condition_orders.py` trong khi §6.8 cấm chạm `derivatives.py` | `derivatives.py:44,46,48` giữ 3 anh em + `_write_request` 69L | **Blocker** — mâu thuẫn nội tại của plan |
| C-5 | Danh sách coordinator giữ không có `__init__.py` | Cả 3 lát tạo symbol mới cần vào `__all__` | **Major** — file không có chủ ⇒ tranh chấp hoặc export fail |
| C-6 | Ghi "thư mục test (mới)" | `tests/unit/explorer/tcbs/` đã tồn tại | **Minor** — diễn đạt |

---

## 3. Findings

| ID | Mức | Mô tả | Đã xử lý |
|---|---|---|---|
| F-1 | **blocker** | Spec không tồn tại trong repo ⇒ không agent nào chạy được | ✅ Commit spec (sha `7f97d27b…42bd4a`) + `scripts/verify_tcbs_coverage.py` |
| F-2 | **blocker** | Hệ quả P2 sai ⇒ bug 8 giờ bịa đặt | ✅ Sửa thành P2b; AC T7 chặn |
| F-3 | **blocker** | Mâu thuẫn nội tại về `condition_orders.py` | ✅ Coordinator chốt phương án (c), ghi lý do + N8 |
| F-4 | major | 1722 vs 1719 collect — số không tái lập | ✅ Ghi cả hai + nguyên nhân (skip mức module phụ thuộc mạng) |
| F-5 | major | `__init__.py` không có chủ | ✅ Đưa vào danh sách coordinator giữ |
| F-6 | major | `requestId` là hư cấu (0 lần trong spec) | ✅ Thành P5 + N7 + cảnh báo agent M không copy |
| F-7 | major | T10 trỏ vào contract test **không tồn tại** (`tests/contract/` 0 file TCBS) | ✅ T10 → `test_session_auth.py` + `inspect.signature` |
| F-8 | minor | `quote.py` 793L / `websocket.py` 791L không có trong bảng ngân sách | ✅ Thêm vào §0b |
| F-9 | minor | `write_gate` envelope trả `kwargs_keys` — tên `pin`/`otp` lọt log | Ghi backlog, không chặn |
| F-10 | minor | `docs/references/` untracked chứa `dnse_credentials.txt` | ✅ Chỉ mở đúng 1 file bằng negation; các file khác vẫn ignore |

---

## 4. AC không kiểm chứng được / proxy observable

| AC | Vấn đề | Xử lý |
|---|---|---|
| T3 | Đặt hằng 300 riêng ⇒ **2 nguồn sự thật** với `session.py:51` | ✅ T3 viết lại: dùng hằng của `BrokerSession` |
| T9 | "grep + caplog" — grep không thấy log qua `repr(self)`/`exc` | ✅ AC thành test `caplog` mọi level, assert không lộ giá trị |
| T10 | Trỏ vào test không tồn tại | ✅ Sửa như F-7 |
| T7 | Nhánh `expiredTime` **chết** với server thật — test xanh nhưng production không reachable | ✅ AC ghi rõ, cấm báo "đã kiểm chứng production" cho nhánh đó |
| M1 | Spec **không** mô tả hành vi khi thiếu `productId` | Ghi chú: AC chốt hành vi theo mặc định hợp lý, không phải theo spec |
| M6 | Đúng về field nhưng chú thích dẫn sai | ✅ Sửa (P5) |
| E2 | `filter` lấy từ `description`, không có validator | Chấp nhận là proxy |
| E5 | "response schema rỗng" thực ra là **thiếu tài liệu** (`responses.200` không có `content`) | ✅ Diễn đạt lại cho đúng |
| **M5** | Auditor **chạy thật** ⇒ đúng | ✅ Giữ nguyên |

---

## 5. Cắt lát: có file bị chồng không?

Auditor tự tính, không tin câu "kiểm bằng script" của plan (vì script không tồn tại).

| File | T | M | E | Coord | Kết luận |
|---|---|---|---|---|---|
| `token_manager.py` (mới) | ✓ | | | | rời |
| `auth.py` | ✓ | | | | rời |
| `money.py` | | ✓ | | | rời |
| `condition_orders.py` (mới) | | | ✓ | | rời về file |
| `listing.py` | | | ✓ | | rời — auditor xác nhận **chỉ lát E** động vào |
| 4 file test (mới) | ✓/ | ✓ | ✓ | | rời |
| `client.py` | | | | ✓ | rời |
| **`__init__.py`** | — | — | — | — | ❌ **không chủ** → đã giao coordinator |
| **`derivatives.py`** | ⛔ | | ⚠ | | ❌ xung đột → đã chốt phương án (c) |

**Trả lời câu hỏi auditor:** `condition_orders.py` **không bắt buộc** phải import từ file
lát khác — nó có thể tự mang `_post`. Đây chính là lựa chọn đã chọn.

---

## 6. Câu hỏi cần Owner quyết

1. **N1 `/api/v1/derivatives/contracts` — REST hay WebSocket?** Spec tự mâu thuẫn, response
   không có `content`. Đã **hoãn**, chưa giao agent.
2. **`requestId` (N7)** — để nguyên hay mở ticket riêng? Đã ghi backlog.
3. **JWT không decode được thì xử lý sao (T7)?** Đã chốt: `expires_in_seconds=None` ⇒
   session không tự chế; `is_expired()` trả `None` ⇒ để caller quyết.

---

## 7. Kết luận

Implement được sau khi sửa 3 blocker. Điểm mạnh cần giữ: ranh giới lát **rời nhau ở mức
file** (auditor kiểm độc lập), và cơ chế "coordinator giữ `client.py` để tránh weld".

**Không có môi trường ⇒ không có kết luận:** full pytest **CHƯA CHẠY**; **không** probe
server thật (không có Smart OTP). Mọi kết luận về hành vi runtime của TCBS chỉ dựa trên
spec + code, **không** phải quan sát thực tế.

`confidence: high`