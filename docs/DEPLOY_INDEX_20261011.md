# TRIỂN KHAI `vnbroker` — Mục lục bộ tài liệu (2026-10-11)

**Trạng thái:** CHUẨN BỊ. Chưa dispatch agent, chưa sửa dòng code nào.
**Base:** `main @ 662e2ef` (v3.7.0). Mọi số dòng file đo ở commit này.

## 1. Đọc theo thứ tự

| # | Tài liệu | Vai trò | Trạng thái |
|:--|:--|:--|:--|
| 1 | `docs/PROPOSAL_VNINVEST_REQUIREMENTS_20261011.md` | Đề xuất gốc: 5 nguyên tắc, 6 nhóm hợp đồng, 6 BLOCKER + 32 MAJOR, 17 WP | ĐỀ XUẤT — có sai sót, xem [3] |
| 2 | `docs/PROPOSAL_ADDENDUM_A_LESSONS_CROSSCHECK_20261011.md` | Phụ lục A: lesson mục rút, WP-05 viết lại, cơ chế cưỡng chế | ĐỀ XUẤT |
| 3 | `docs/ERRATA_B_CORRECTIONS_20261011.md` | Phụ lục B: sửa citation + hạ cấp số chưa đo về ƯỚC LƯỢNG | **BẮT BUỘC đọc trước khi slice** |
| 4 | `docs/DECISIONS_Q1_Q11_20261011.md` | Q1 đã chốt (CÓ); Q2–Q11 còn mở + chủ sở hữu | Q1 CLOSED, còn lại OPEN |
| 5 | `docs/PLAN_DEPLOY_SLICES_HANG1_20261011.md` | Slice S1–S4 (Hàng 1) claim-ready + template cho Hàng 2–4 | KẾ HOẠCH |
| 6 | `vninvest/docs/AUDIT_VNBROKER_INTEGRATION_20261011.md` | Audit phía consumer (repo `vninvest`) | THAM KHẢO |

## 2. Cổng lên lịch (điều kiện dispatch)

- [x] Q1 đã trả lời bằng chuỗi gọi đo được → WP-01 giữ P0, AC đo qua adapter batch source=VCI.
- [ ] ERRATA B đã đọc — slice nào dùng số 5/9, 17/29, "thiếu 404/422" mà chưa đọc B thì AC vô hiệu.
- [ ] Hàng 1 (S1–S4): **được dispatch** ngay sau khi claim `docs/CLAIMS.md` (file rời nhau, script overlap exit 0).
- [ ] Hàng 3 (tiền thật: WP-05/06/13/14): **CHẶN** tới khi B-1 xong (bảng `rc` đo bằng JWT thật). Không mở R3 trước.
- [ ] Hàng 2 + 4: **chưa slice được** (L-P03) — cần đọc code vị trí đặt trước, xem [5] §4.

## 3. Quy ước bắt buộc mọi slice (tóm tắt, chi tiết ở [5])

1. Claim **trước** khi code, đường dẫn đầy đủ từ gốc repo, overlap exit 0.
2. Mỗi slice có dòng `Lesson áp dụng: [...]` + tick MANDATORY CHECKLIST.
3. Số đo ghi kèm **nơi đo** (main tree / worktree + commit). Thiếu môi trường ⇒ ghi **CHƯA CHẠY**.
4. Worktree: đo baseline riêng; gỡ junction `.venv` bằng `rmdir` không `/s` trước khi xoá cây.
5. AC fail-before/pass-sau gọi **code thật**; assert hình thức = bằng chứng vô giá trị.
6. Không sửa `docs/LESSONS/` (cần coordinator duyệt).

## 4. Việc tiếp theo (chủ sở hữu: coordinator)

1. Trả lời Q2–Q11 (nhất là Q6 CI, Q9 nợ đo `rc`, Q4 `core/settings.py`).
2. Chạy lệnh đếm AST cho B-2/B-3, đóng số ƯỚC LƯỢNG thành số đo.
3. Ghi claim S1–S4 vào `docs/CLAIMS.md`, chạy check-overlap, dispatch.

*Lessons áp dụng: [L-P01, L-P03, L-P04, L-E01] — xem MANDATORY CHECKLIST ở [5] §5.*
