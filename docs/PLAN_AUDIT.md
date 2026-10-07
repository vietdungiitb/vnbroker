# PLAN_AUDIT — WP-CLEANUP-01

- **Task:** `WP-CLEANUP-01`
- **Plan được audit:** `docs/PLAN_WORKFLOW_REPAIR.md` (v1 → v2)
- **Auditor:** subagent `sa-0-2dab5f38` (delegation `deleg_e7484699`)
- **Ngày:** 2026-10-07
- **Người xác minh:** supervisor (Hermes) — tự chạy lại MỌI phép đo

## Verdict: `PASS`

Plan v1 nhận `NEED_REVISION` từ auditor. Sau khi supervisor **tự chạy lại từng
claim**, 4/5 finding là đúng và đã sửa ở v2; 1/5 là **auditor sai** và đã bị bác
bỏ. v2 đủ điều kiện qua cổng.

## Trạng thái auditor (bắt buộc ghi lại)

Auditor **thất bại khi chạy**: `status=failed`, `api_calls=10`, `1361.39s`, lý do
*"Model output entered a repetition loop and was truncated mid-loop"*. Đây là
Hazard H2/H7 — kết quả tự báo, phải xác minh độc lập. Chỉ 1 phần output JSON được
giữ; phần còn lại không tồn tại.

## Đối chiếu từng finding — supervisor tự chạy lại

| # | Finding của auditor | Lệnh tự chạy lại | Kết quả thật | Phán quyết |
|---|---|---|---|---|
| 1 | `mypy baseline: now 0, fixed 1266` — tố plan **bịa số** | `.venv/Scripts/python.exe scripts/check_mypy_baseline.py` | `OK: no new strict errors (baseline 1266, now 1233, fixed 33)` | **AUDITOR SAI** — plan đúng. Nếu tin auditor, plan đã bị sửa theo hướng sai |
| 2 | `ruff: command not found (exit 127)` | `ruff --version` → `command not found`; `uvx ruff check ...` → `All checks passed!` | `ruff` không có trên PATH | **ĐÚNG** → v2 mục 6 dùng `uvx ruff` |
| 3 | `node $SKILL/...` không định nghĩa `$SKILL`, thiếu path format Windows | đọc v1 mục 6 | v1 không định nghĩa biến, không nêu `C:/` vs `/c/` | **ĐÚNG** → v2 định nghĩa `$SKILL` + ghi rõ path native |
| 4 | Bỏ sót 6 file stub trong `docs/_workflow/` | `ls -l docs/_workflow/` + `cat` từng file | `gate-07-close.md`/`gate-08-retro.md` là `.md` 1 dòng; `HOOK_CONFIG.template.md` ghi **"eoffice-be"**; `LESSONS.md` ghi **"eoffice-be"**; `VERIFICATION.md:35` ghi `vnbroker: npm test` | **ĐÚNG** → v2 mục 2 mở rộng từ 13 → 20 file |
| 5 | Mâu thuẫn `.gitignore` giữa mục 2 và mục 3 | đọc v1 mục 2 dòng 8 + mục 3 dòng 78-79 | `.gitignore` vừa "KHÔNG đụng" vừa nằm in-scope | **ĐÚNG** → v2 mục 3 viết lại, nói rõ `.gitignore` là ngoại lệ có chủ đích và được commit |

**Tỉ lệ auditor đúng: 4/5.** Finding #1 cho thấy nguy hiểm của việc tin subagent:
auditor tự chạy ở môi trường khác (không dùng `.venv/Scripts/python.exe`) nên đọc
sai kết quả, rồi tố plan bịa số.

## GATE 2 — kiểm chồng lấn claim (đã chạy, hai công cụ)

| Công cụ | Lệnh | Kết quả |
|---|---|---|
| `check-overlap.cjs` (skill) | `node <skill>/scripts/check-overlap.cjs --file docs/CLAIMS.md` | `Agent dang chay (in-progress): 5` · `OK: khong co chong lan` · exit **0** |
| Script Python (đo thứ hai) | `.venv/Scripts/python.exe <scratch>/check_claims.py` | `doc duoc 5 agent, 21 file` · `KET QUA: 0 chong lan` |

**Phát hiện qua đo thứ hai:** bản `CLAIMS.md` đầu tiên dùng **tên trần**
(`LESSONS.md`, `gate-07-close.md`, `gate-08-retro.md`) không khớp đường dẫn đầy
đủ trong kế hoạch, và thiếu 5 file vừa thêm vào scope. Đã sửa: mọi đường dẫn ghi
đầy đủ từ gốc repo, 21 file / 5 agent.

## Lỗi không chặn (ghi lại, không sửa)

- Kế hoạch v2 mục 2 hàng 9 ghi `` `docs/_workflow/gate-07-close.md`, `gate-08-retro.md` `` —
  mục thứ hai thiếu tiền tố `docs/_workflow/`. Chỉ là văn xuôi; `CLAIMS.md` ghi
  đầy đủ nên không ảnh hưởng gate.

## Điều kiện để đi tiếp (đã thoả)

- [x] Verdict `PASS` cho plan v2
- [x] GATE 2 exit 0, đã kiểm bằng hai công cụ độc lập
- [x] Mọi finding của auditor đã được tự chạy lại, phân loại đúng/sai
- [x] `worktree` chưa bật ⇒ đã ghi rõ trong plan + claims rằng GATE 2 là tầng
      phòng ngừa bắt buộc
- [x] `docs/_workflow/` là untracked ⇒ đã ghi vào mục 8 rủi ro rằng commit sẽ
      đưa scaffolding vào repo (có chủ đích)

## CHƯA CHẠY

- `pytest tests/` trên bản v2 của plan: **CHƯA CHẠY** — sẽ chạy ở Stage 6.
- Hook toàn cục `~/.hermes/config.yaml`: chưa sửa (ngoài phạm vi). Đã đo là stub
  exit 0 nên không chặn agent.
