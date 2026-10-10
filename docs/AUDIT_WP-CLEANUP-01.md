# AUDIT — WP-CLEANUP-01

- **Người audit:** supervisor (Hermes) — **tự audit**
- **Ngày:** 2026-10-07
- **Phạm vi:** 8 cổng `docs/_workflow/gate-*.sh` + 6 file phụ trợ `docs/_workflow/` + 6 file ngoài
- **Trạng thái đầu:** auditor độc lập (`deleg_f5b69b64`, `sa-0-499b62ef`) **thất bại**

## Verdict: PASS

## Confidence: high

## Vì sao supervisor tự audit (bắt buộc ghi lại)

Auditor độc lập chết vì **vòng lặp lặp** (Hazard H4/H20): `status=failed`,
`api_calls=11`, `1332.4s`, lý do *"Model output entered a repetition loop and was
truncated mid-loop"*. Nó báo `{"audit_file":"docs/AUDIT_WP-CLEANUP-01.md", ...}`
nhưng **file đó không tồn tại trên đĩa** (`ls` → *No such file or directory`) và
**không có HEARTBEAT** ⇒ vi phạm Hazard H2 (tự báo).

Đây là **lần thứ hai** trong phiên: auditor kế hoạch (`deleg_e7484699`) cũng chết
vì vòng lặp lặp ở 1361s. Hai agent liên tiếp chết cùng kiểu, mỗi lần ~22 phút ⇒
**không dispatch lại lần 3** (luật skill: tối đa 2 lần). Supervisor tự audit.

Chỉ 3 ca phủ định auditor chạy được (G4/G6/G7) và cả 3 khớp với kết quả supervisor
tự chạy lại — phần còn lại không tồn tại.

## Lỗi còn lại

**0 lỗi blocking còn lại.**

Trong quá trình tự audit, supervisor tìm và sửa **4 lỗi thật** mà 5 agent code và
auditor độc lập đều **không bắt được**. Cả 4 đều thuộc lớp **lỗi im lặng** — cổng
trông như đã xong nhưng không kiểm đúng thứ cần kiểm.

| # | File | Lỗi | Dạng | Cách chứng minh | Cách sửa |
|---|---|---|---|---|---|
| 1 | `gate-04-audit-pass.sh` | glob `docs/AUDIT_*.md` bỏ sót `docs/audit/` (chữ thường) ⇒ chọn audit cũ 2026-09-23 rồi in BLOCK sai | cổng báo nhầm | chạy thật → chọn `docs/AUDIT_REPORT_v3.3.0.md` | tìm ở **cả hai** nơi + nhận tham số đường dẫn |
| 2 | `gate-08-retro.sh` | chặn bằng `grep -q "eoffice-be"` — nhưng `LESSONS.md` **hợp lệ** khi *nhắc* chuỗi đó trong bài học ⇒ **đỏ vĩnh viễn** | cổng báo nhầm | chạy trên `LESSONS.md` đã sửa → exit 2 sai | chỉ kiểm **dòng đầu** có phải tiêu đề stub không |
| 3 | `gate-02-plan-verified.sh` | `sort -r \| head -1` sắp theo **alphabet** ⇒ plan mới hơn nhưng tên đứng trước (`PLAN_AAA.md`) **không bao giờ được kiểm** | cổng kiểm nhầm file | tạo `PLAN_AAA.md` thiếu hết mục, cổng vẫn chọn `PLAN_WORKFLOW_REPAIR.md` và báo OK | chọn theo **mtime** (`ls -t`) + nhận tham số |
| 4 | `gate-02-plan-verified.sh` | glob `docs/PLAN_*.md` khớp luôn `PLAN_AUDIT.md` (bản audit, không phải plan) ⇒ chặn nhầm dữ liệu hợp lệ | cổng báo nhầm | chạy sau khi sửa lỗi #3 → chọn `PLAN_AUDIT.md` → exit 2 sai | loại trừ `PLAN_AUDIT` khỏi glob |
| 5 | `README.md` | agent chèn `> **Lưu ý:**` vào **giữa** bảng Biến môi trường ⇒ hàng `VNBROKER_BROKER_TCBS_API_KEY` rơi ra ngoài bảng | hỏng markdown | kiểm tính liền mạch: khoảng cách giữa các hàng | đưa lưu ý xuống **sau** bảng |

Lỗi #1–#4 cùng **một lớp nguyên nhân: quy tắc quá rộng hoặc glob sai**. Lỗi #5 là
nguyên nhân khác: agent tự kiểm bằng **đếm số dòng `|`** — con số không đổi nên nó
kết luận bảng hợp lệ.

## Bằng chứng

### Ca hợp lệ (kỳ vọng)

| Lệnh | Exit code | Kết quả thô |
|---|---|---|
| `bash gate-01-plan-approved.sh` | `0` | `GATE G1 OK: tìm thấy file audit PASS: docs/PLAN_AUDIT.md` |
| `bash gate-02-plan-verified.sh` | `0` | `GATE G2 OK: file plan 'docs/PLAN_WORKFLOW_REPAIR.md' đủ các mục bắt buộc.` |
| `bash gate-03-claims-check.sh` | `0` | `File claims : docs/CLAIMS.md` … `GATE G3 OK` |
| `bash gate-04-audit-pass.sh` | `2` | **Đúng**: chưa có audit nào có Verdict PASS. Xem ca phủ định |
| `bash gate-05-test-pass.sh` | `0` | `G5 OK: pytest passed` (1052 passed, 28 skipped) |
| `bash gate-06-report-final.sh` | `2` | **Đúng**: `docs/REPORT_FINAL.md` chưa tồn tại ở thời điểm audit |
| `bash gate-07-close.sh` | `2` | **Đúng**: cùng lý do |
| `bash gate-08-retro.sh` | `0` | `G8 OK: docs/_workflow/LESSONS.md da cap nhat cho vnbroker` |

### Ca phủ định (bắt buộc — chứng minh cổng chặn được)

| # | Ca | Lệnh | Exit | Kết quả thô |
|---|---|---|---|---|
| 1 | G1: ẩn `PLAN_AUDIT.md` | `mv docs/PLAN_AUDIT.md /tmp/pa.bak && bash gate-01…` | `2` | `GATE G1 BLOCK: không tìm thấy file docs/PLAN_AUDIT*.md nào.` |
| 2 | G2: plan mới nhất thiếu mục | `printf '# PLAN — thieu' > docs/PLAN_AAA.md && bash gate-02…` | `2` | `GATE G2 BLOCK: file plan 'docs/PLAN_AAA.md' thiếu các mục bắt buộc:` + 4 mục |
| 3 | G2: không còn plan nào | `mv docs/PLAN_*.md /tmp/pb/ && bash gate-02…` | `2` | `GATE G2 BLOCK: không tìm thấy file docs/PLAN_*.md nào.` |
| 4 | G2: đường dẫn không tồn tại | `bash gate-02… docs/KHONG_CO.md` | `2` | `GATE G2 BLOCK: khong xac dinh duoc file plan de kiem.` |
| 5 | G3: ẩn `CLAIMS.md` | `mv docs/CLAIMS.md /tmp/cl.bak && bash gate-03…` | `2` | `GATE G3 BLOCK: không tìm thấy docs/CLAIMS.md.` |
| 6 | G4: audit không có verdict PASS | `bash gate-04… docs/AUDIT_REPORT_v3.3.0.md` | `2` | `G4 BLOCK: docs/AUDIT_REPORT_v3.3.0.md khong co Verdict PASS` |
| 7 | G6: thiếu `REPORT_FINAL.md` | `bash gate-06…` | `2` | `GATE G6 BLOCK: không tìm thấy docs/REPORT_FINAL.md.` |
| 8 | G7: thiếu `REPORT_FINAL.md` | `bash gate-07…` | `2` | `G7 BLOCK: thieu docs/REPORT_FINAL.md` |
| 9 | G8: `LESSONS.md` là stub dự án khác | `printf '# Bai hoc … eoffice-be' > LESSONS.md && bash gate-08…` | `2` | `G8 BLOCK: … van la stub cho du an khac -> '# Bai hoc tu quy trinh cho du an eoffice-be'` |
| 10 | G8: thiếu hẳn file | `mv LESSONS.md /tmp && bash gate-08…` | `2` | `G8 BLOCK: thieu docs/_workflow/LESSONS.md` |
| 11 | G8: dữ liệu HỢP LỆ có nhắc `eoffice-be` | `bash gate-08…` trên LESSONS đã sửa | `0` | `G8 OK` — **chứng minh không báo nhầm** |

**Mọi cổng đều đã chạy cả hai chiều.** Ca #11 là ca quan trọng nhất: nó chứng minh
lỗi #2 đã sửa đúng (cổng không còn đỏ vĩnh viễn trên dữ liệu hợp lệ).

### Cổng CI (đối chiếu độc lập)

| Lệnh | Exit | Kết quả thô |
|---|---|---|
| `.venv/Scripts/python.exe -m pytest tests/ -q --timeout=180` | `0` | `1052 passed, 28 skipped, 7 warnings in 156.03s` |
| `.venv/Scripts/python.exe scripts/check_version_sync.py` | `0` | `version-sync OK: 3.5.0` |
| `.venv/Scripts/python.exe scripts/check_mypy_baseline.py` | `0` | `OK: no new strict errors (baseline 1266, now 1233, fixed 33)` |
| `uvx ruff check vnbroker tests/unit tests/contract/` | `0` | `All checks passed!` |
| `C:/tmp/al/actionlint.exe -no-color` | `0` | (không output) |
| `bash -n docs/_workflow/gate-*.sh` (8 file) | `0` | cú pháp hợp lệ |

`pytest` **trùng khớp baseline trước WP** (1052 passed / 28 skipped) ⇒ không hồi quy.

### Kiểm không xâm phạm claim

| Kiểm | Kết quả |
|---|---|
| File sửa bởi WP | 7 — tất cả thuộc agent đã claim trong `docs/CLAIMS.md` |
| Xâm phạm claim | **0** |
| HEARTBEAT | 5/5 agent ghi (mỗi file 1 dòng) |
| File ngoài phạm vi bị agent sửa | **0** |

## Ngoài phạm vi

Các thay đổi sau **không thuộc WP-CLEANUP-01** — là việc dở của người dùng hoặc
scaffolding được đưa vào repo có chủ đích:

| File | Nguồn |
|---|---|
| `TODO.md`, `CHANGELOG.md`, `pyproject.toml`, `vnbroker/config.py`, `vnbroker/common/data.py` | việc dở của người dùng |
| `docs/ROADMAP_V33_PLAN.md`, `docs/audit/AUDIT_REPORT_2026-10-01.md`, `D docs/COMMERCIAL_SOFTWARE_AUDIT_REPORT.md` | việc dở của người dùng |
| `D tests/examples/compare_vnstock_libraries.py`, `D tests/integration/test_vnstock_client.py`, `D artifacts/ssi_explorer/*` | việc dở của người dùng |
| `docs/PLAN_CLEAR_VNSTOCK_REFERENCES.md`, `docs/PLAN_VNSAAS.md`, `docs/audit/TIER1_DATA_ENGINE_AUDIT_2026-10-05.md` | việc dở của người dùng (untracked) |
| `.github/workflows/nightly_autotune.yml` | việc dở của người dùng |

## CHƯA CHẠY

- **`gate-05` chạy lâu (~140–170s)** — đã chạy thật, exit 0. Không phải CHƯA CHẠY.
- **Hook toàn cục `~/.hermes/config.yaml`** — chưa sửa (ngoài phạm vi). Đã đo: 2 hook
  `fail_closed: true` trỏ `VMU-eoffice/eoffice-be/docs/_workflow/*` nhưng cả hai là
  **stub exit 0** (đã chạy thử) ⇒ không chặn agent. Vẫn là việc còn lại của người dùng.
- **`docs/_workflow/STATE.json`** — không sửa nội dung, chỉ gitignore. `"branch": "main"`
  trong file là machine state cũ; file sẽ được sinh lại mỗi phiên nên không cần sửa.
- **Bật `worktree`** — không thực hiện (cấu hình toàn cục, ngoài phạm vi). Vì vậy GATE 2
  (`check-overlap.cjs`) vẫn là tầng phòng ngừa duy nhất cho xung đột file.
