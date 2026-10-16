# REPORT_FINAL_DNSE_FIX: Tổng kết & đóng task sửa 11 defect DNSE OpenAPI

- **Supervisor**: coordinator (Mode B solo — xem §1)
- **Base**: `f6cf68b` · **HEAD**: `d8fab65` · **Branch**: `feat/dnse-openapi-fix`
- **Ngày**: 2026-10-16
- **Trạng thái**: **đóng về kỹ thuật, chưa merge** (Owner duyệt)

> **Lessons áp dụng: [L-R01, L-R02, L-R03, L-R04, L-R06, L-E01, L-E02, L-E04, L-E06, L-E07, L-P03, L-P04, L-P05, L-P06]**

## 1. Vì sao Mode B (solo) chứ không phải Mode A (song song)

Skill yêu cầu song song chỉ khi tập file của các worker **rời nhau tuyệt đối**.
Sáu lát cắt ở đây: A/B/D cùng sửa `services/market_service.py`; A/B/C/D cùng sửa
`client.py`. Giao nhau ⇒ chạy song song sẽ tái tạo Hazard 1 (weld hunk). Tiền lệ
đã có: `docs/CLAIMS.md:205-206` (TCBS Round 3). Vì vậy chạy tuần tự, nhưng **vẫn
giữ tính độc lập ở tầng audit** bằng subagent read-only riêng.

## 2. Kết quả: 11/11 defect đã đóng và **đo lại live**

| # | Defect | Bằng chứng trước | Sau khi sửa (đo lại) |
|---|---|---|---|
| D1 | working-dates trả hằng | 0ms, không gọi network | **200**, 257 ngày |
| D2 | `get_orders` thiếu phân trang | `400 pageIndex is required` | **200** (thêm cả `pageSize`) |
| D3 | `order_history` thiếu một vế | `400 from/to is required` | **200** khi đủ cả hai |
| D4 | format ngày dễ nhầm unix giây | — | **200** với `yyyy-MM-dd` |
| D5 | corporate-action 404 | `404 API ROUTE NOT FOUND` | **200** |
| D6 | `position_id` rác ⇒ server 500 | `500 For input string` | **chặn client-side** |
| D7 | volume-profile sai contract | `400 invalid param 'time'` | **200** với `boardId="G1"` |
| D8 | ms bị từ chối | `400 range exceeds…` | **tự chuẩn hoá → 200** |
| D9 | market_index khác ngày | không guard | chặn trước network |
| D10 | `boardId` không tìm ra giá trị | 24 giá trị đoán đều hỏng | **G1,G2,G3,G4,G7,G8 → 200** |
| D11 | `marketId` không tìm ra giá trị | 24 giá trị đoán đều hỏng | **STO,HCX,UPX,STX,DVX → 200** |

Probe: `scripts/probe_dnse_readonly.py` → **`PASS=40 FAIL=16`**, 16 FAIL là **probe
phủ định có chủ ý**.

## 3. Số đo độc lập (supervisor tự chạy, không tin báo cáo của ai)

| Trường hợp | Lệnh | Kết quả thực |
|---|---|---|
| Baseline | `pytest tests/ -q` @ `f6cf68b` | 2177 passed, 26 skipped, exit 0 |
| Post-change | `check_all.ps1` FULL @ `d8fab65` | **exit 0** — 2246 passed, 26 skipped (**+69**) |
| Type | `check_mypy_baseline.py` | 1266 → **1133** (fixed 133) |
| Lint | `ruff check vnbroker scripts tests/unit tests/contract` | All checks passed |
| Encoding | `check_encoding.py` (+ self-test) | 449 file, 0 mojibake · 3/3 |
| Kiểm chứng test | mutation-test 4/4 | bỏ fix ⇒ test đỏ (6/1/1/5) |

## 4. Audit: 2 vòng, cả 2 đều FAIL — và tôi là người gây blocker

| Vòng | Verdict | Phát hiện chính |
|---|---|---|
| 1 | **FAIL** 1 blocker · 4 major | Tầng explorer vẫn trả 1 dòng; test docstring **tautological**; `to_unix_seconds` không ai gọi; `pageIndex=None` lên URL; docstring sai thống số |
| 2 | **FAIL** 1 blocker · 1 major | **Mojibake 3 file nguồn** do chính script mutation-test của tôi gây ra; `market_index` crash với ms |

**Blocker nghiêm trọng nhất do tôi tự gây ra.** Script tự kiểm chứng dùng
`Get-Content -Raw` (PowerShell 5.1 đọc UTF-8 bằng CP1252) rồi "khôi phục" file từ
bản đã hỏng. Hỏng tới mức `_SECONDS_NOTE` **mất chữ `GIÂY`** — tức tài liệu chống
lỗi D8 không đọc được — và thông điệp lỗi người dùng thấy là rác. **Không gate nào
bắt được** vì file hỏng vẫn decode hợp lệ UTF-8 (ruff PASS, 399 test PASS).

⇒ Thêm `scripts/check_encoding.py` vào `check_all.ps1`. Cổng mới này cũng phát
hiện một file hỏng **có sẵn từ trước** — `tests/unit/core/test_no_guest_quota_runtime.py`
— khiến assert của test đó **không bao giờ chạm** vào nguồn thật. Đã sửa (ngoài phạm
vi, ghi rõ).

## 5. Ba kết luận sai đã bị bác bỏ trong chính phiên này

1. **"DNSE không có endpoint working-dates"** (docstring trong code). Đo:
   `200`, 257 ngày. Kế hoạch đầu tiên định **xoá method** vì tin câu đó.
2. **"`corporate-action-history` không tồn tại"** — nó tồn tại, code chỉ sai
   một dấu gạch nối: `corporate-actions` vs `corporate-action-history`.
3. **"Không tồn tại `boardId`/`marketId` hợp lệ"** — tồn tại; 24 lần đoán sai, và
   cách đúng là **đọc response server** (`GET /instruments` trả cột `marketId`).

Cả ba đều là cùng một mẫu: **tin một docstring/kết luận cũ hơn là đo lại**.

## 6. Waivers (ghi rõ, không giấu)

| # | Nhỏ | Vì sao chấp nhận |
|---|---|---|
| 1 | `Trade.get_orders`/`get_order_history` **không forward** `page_index`/`page_size` | `trade.py` **1352 dòng**, vượt trần 800L. Người dùng `Trade` chỉ lấy được trang đầu. Sửa cần tách file trước — việc riêng. |
| 2 | `orderCategory` cho `get_orders` **đang tuỳ chọn** dù server bắt buộc | Đo thấy `400 INVALID_ORDER_CATEGORY`. Làm bắt buộc là **thay đổi hành vi** chưa có yêu cầu rõ ràng ⇒ để Owner chốt (xem §7) |
| 3 | `BOARD_IDS`/`MARKET_IDS` **không validate cứng** | Tập đo trên **một** mã, **một** ngày. Chặn cứng sẽ chặn oang mỗi khi DNSE thêm sàn. Khác biệt có chủ ý với `marketType` (bắt buộc & đóng). |
| 4 | `403` ở `position_id=999999` | Đo 3 lần đều 403. **Không** kết luận là lỗi client ⇒ không sửa. |
| 5 | Bằng chứng **không** có HTTP transcript gốc trong repo | Chuỗi lỗi lấy từ `str(exc)` lúc chạy. Ghi rõ hạn chế thay vì làm bằng chứng trông mạnh hơn nó là. |

## 7. Quyết định còn treo — cần Owner

1. **`orderCategory` cho `get_orders` có bắt buộc không?** Đo: thiếu ⇒
   `400 INVALID_ORDER_CATEGORY`. Hiện client cho phép `None`.
2. **`Trade` (legacy, 1352L) có được tách file để forward tham số mới không?**
3. **`docs/LESSONS/evidence.md` đã đầy** (120/120 dòng non-blank, trần của
   `check_lessons`). Bài học **L-E08** ("khi validator từ chối mà không liệt kê tập
   hợp — đọc response server, đừng đoán") rất đáng lưu nhưng **không nạp được**
   vì nạp vào sẽ phải xoá một lesson đang có. Nội dung đầy đủ nằm ở
   `docs/REPORT_DNSE_LIVE_20261016.md` §12.2.

## 8. Cập nhật sổ cái bắt buộc

- [x] `docs/CLAIMS.md` — dòng claim `coordinator-dnse-fix` chuyển `in-progress`
      → **`released`**, kèm bảng 10 commit và kết quả gate.
- [x] `CHANGELOG.md` — mục `Unreleased` đầy đủ: breaking changes, bảng so
      trước/sau, 2 hằng mới, cổng mới, số đo gate.
- [x] `docs/AGENT_PROTOCOL.md` — tạo mới (repo chưa có): cổng, bảng chân lý đo
      được, deny list, quy tắc Lessons.
- [ ] **Chưa merge** — Owner duyệt.

## 9. Retrospective: bài học để lặp lại

1. **Công cụ tự kiểm chứng cũng là mã nguồn, và nó có thể phá thứ đang được kiểm
   chứng.** Mutation-test của tôi hỏng 3 file nguồn rồi "khôi phục" bản hỏng.
   *Cổng:* `check_encoding.py` — nhưng cổng mới này chỉ bắt được **một** lớp hỏng
   (encoding). Bài học rộng hơn: **trước khi "khôi phục" file bằng script, hãy
   kiểm bằng `git diff` rằng file đã về đúng trạng thái mong muốn.**
2. **Test xanh không phải bằng chứng.** 4 test trong đợt này xanh vì **không thể
   fail** (assert `"gi" in doc` khi tiếng Việt chứa "gi"; một test khẳng định
   ngược với điều server thật sự đòi). *Cổng:* mutation-test đã bắt được 4/4 —
   đây là bài học thành **thói quen**, không phải sự kiện một lần.
3. **Đoan từ trực giác là tốn kém và nguy hiểm.** 69 request không ra thông tin,
   rồi sinh ra ba kết luận sai (một trong đó đã được ghi vào docstring của 3 file).
   *Cổng:* chưa có cổng nào ép điều này; quy tắc đã rút ra ở §12.2 của báo cáo.
4. **Số trong tài liệu cũ hoá nhanh hơn tưởng.** `CLAUDE.md` ghi "1414 passed" và
   "contract 72"; thực tế 2177 và 117. Tôi chép cả hai vào tài liệu mới của mình,
   và chỉ audit độc lập mới bắt được. *Cổng:* `docs/AGENT_PROTOCOL.md` §2 giờ ghi
   rõ **số đo** + nguồn.
5. **Khi mạng là biến số, "không chạy được" phải ghi thành vậy.** Giữa phiên này
   mạng DNSE tắt 2 lần; lần đầu suýt đóng bằng kết luận suy đoán. Khi nó về lại,
   **2 defect đã bị bác bỏ**. *Bài học:* đừng kết luận về server khi chưa gọi được
   nó — cứ ghi CHƯA CHẠY rồi quay lại.