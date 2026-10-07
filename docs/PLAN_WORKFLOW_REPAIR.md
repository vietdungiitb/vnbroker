# PLAN — WP-CLEANUP-01: Làm sạch codebase & sửa cổng workflow hỏng

- **Task ID:** `WP-CLEANUP-01`
- **Planner:** supervisor (Hermes)
- **Ngày:** 2026-10-07
- **Workdir:** `C:/Mujoco Projects/vnbroker`
- **Trạng thái:** `REVISED` (v2 — sau Plan Audit `deleg_e7484699`)
- **Quy trình:** SDLC khép kín theo mô hình stage-gate (Requirements → Design →
  Gate Review → Implementation → Independent Code Review → Verification →
  Release → Retrospective), ánh xạ 1-1 vào 9 giai đoạn của skill
  `multi-agent-workflow`.

## Lịch sử revision

| Ver | Ngày | Thay đổi |
|---|---|---|
| v1 | 2026-10-07 | Bản đầu |
| v2 | 2026-10-07 | Sau Plan Audit `deleg_e7484699` (`NEED_REVISION`). Sửa 3 lỗi kế hoạch + mở rộng phạm vi 6 file bị bỏ sót. |

### Đối chiếu Plan Audit — supervisor tự chạy lại MỌI phép đo

Audit agent chết vì **vòng lặp lặp** (1361s, bị cắt giữa chừng). Theo luật skill,
phát hiện của subagent là **tự báo**, nên supervisor tự chạy lại từng claim:

| # | Audit claim | Tự chạy lại | Kết luận |
|---|---|---|---|
| 1 | `mypy baseline: now 0, fixed 1266` — tố kế hoạch bịa số | `OK: no new strict errors (baseline 1266, now 1233, fixed 33)` | **AUDIT SAI** — kế hoạch đúng |
| 2 | `ruff: command not found (exit 127)` | `ruff` không có trên PATH; `uvx ruff` → `All checks passed!` | **AUDIT ĐÚNG** — kế hoạch viết thiếu `uvx` → sửa mục 6 |
| 3 | `node $SKILL/...` không định nghĩa `$SKILL` | Đúng — v1 không định nghĩa biến, không nêu path format Windows | **AUDIT ĐÚNG** → sửa mục 6 |
| 4 | Bỏ sót 6 file stub trong `docs/_workflow/` | Đúng — `gate-07-close.md`/`gate-08-retro.md` là file `.md` 1 dòng, không phải script | **AUDIT ĐÚNG** → mở rộng mục 2 |
| 5 | Mâu thuẫn `.gitignore` giữa mục 2 và mục 3 | Đúng về diễn đạt | **AUDIT ĐÚNG** → viết lại mục 3 |

**Bài học cho retrospective:** audit agent chết vì lặp ⇒ mọi claim phải tự chạy
lại; claim "bịa số" của agent là SAI, nếu tin nó thì kế hoạch đã bị sửa theo
hướng sai.

## 0. Ground truth đã đo trước khi lập kế hoạch

| # | Đo gì | Lệnh (nguyên văn, chạy được) | Kết quả |
|---|---|---|---|
| 1 | Trạng thái cây | `git status --porcelain` | 18 modified + 4 untracked |
| 2 | Suite | `.venv/Scripts/python.exe -m pytest tests/ -q` | **1052 passed, 28 skipped, exit 0** |
| 3 | ruff | `uvx ruff check vnbroker tests/unit tests/contract/` | `All checks passed!`, exit 0 |
| 4 | ruff (bare) | `ruff --version` | `command not found` — **phải dùng `uvx`** |
| 5 | mypy baseline | `.venv/Scripts/python.exe scripts/check_mypy_baseline.py` | `baseline 1266, now 1233, fixed 33`, exit 0 |
| 6 | version-sync | `.venv/Scripts/python.exe scripts/check_version_sync.py` | `version-sync OK: 3.5.0`, exit 0 |
| 7 | actionlint | `C:/tmp/al/actionlint.exe -no-color` | exit 0 |
| 8 | `worktree` (A4) | `hermes config get worktree` | `Config key not set` → **CHƯA BẬT** |
| 9 | `child_timeout_seconds` (A3) | `hermes config get delegation.child_timeout_seconds` | `900` |
| 10 | `max_concurrent_children` | `hermes config get delegation.max_concurrent_children` | `6` |
| 11 | `gate-05` | `bash docs/_workflow/gate-05-test-pass.sh` | **exit 2** — `npm error ENOENT` |
| 12 | Hook toàn cục | `bash <eoffice gate-01>` / `gate-03` | **exit 0 cả hai** → stub, không chặn agent |
| 13 | Script skill (3 cái) | `node <skill>/scripts/<x>.cjs --self-test` | `17/17`, `16/16`, `30/30 DETECTED` — PASS |

**Sự thật quyết định thiết kế:** `worktree` chưa bật ⇒ mọi agent con dùng chung
một working directory ⇒ GATE 2 (`check-overlap.cjs`) là tầng phòng ngừa duy
nhất, **bắt buộc chạy**, và file set của các lát cắt phải rời nhau tuyệt đối.

## 1. Mục tiêu

**Hiện trạng — cổng hỏng theo HAI kiểu khác nhau (phân biệt này quyết định cách sửa):**

| Cổng | Kiểu hỏng | Bằng chứng |
|---|---|---|
| `gate-01-plan-approved.sh` | **fail-OPEN** — thân chỉ có comment | 3 dòng, không lệnh nào → exit 0 |
| `gate-02-plan-verified.sh` | fail-OPEN | 3 dòng |
| `gate-03-claims-check.sh` | fail-OPEN | 3 dòng |
| `gate-06-report-final.sh` | fail-OPEN | 3 dòng |
| `gate-04-audit-pass.sh` | **fail-CLOSED vĩnh viễn** — `exit 2` cứng | 4 dòng, luôn exit 2 |
| `gate-05-test-pass.sh` | **sai lệnh** — `npm test` trong repo Python | dòng 5; `gates.json:8` |
| `gate-07-close.md` | **không phải script** | file `.md` 1 dòng `# CHUA CHAY` |
| `gate-08-retro.md` | không phải script | file `.md` 1 dòng |

**Hiện trạng — 5 file còn lại của `docs/_workflow/`:**

- `HOOK_CONFIG.template.md` — 3 dòng, ghi **"Mau hook cho du an eoffice-be"** (sinh nhầm dự án).
- `LESSONS.md` — 2 dòng, ghi **"Bai hoc ... cho du an eoffice-be"**.
- `VERIFICATION.md:35` — ghi `vnbroker: npm test (Python)` → xác nhận nguyên nhân gốc: template Node áp cho dự án Python.
- `STATE.json:3` — `"branch": "main"` trong khi nhánh làm việc là `dev`; không bị gitignore.
- `README.md` — mô tả đúng cấu trúc nhưng không nhắc 2 cổng `.md` không chạy được.

**Hiện trạng — tài liệu/cấu hình sai:**

- `.env.example:18-19`, `.env.dnse.example:21-22` khai `DNSE_USERNAME`/`DNSE_PASSWORD`;
  `README.md:234-235` quảng cáo "DNSE JWT Trading" — nhưng `grep -rn 'DNSE_USERNAME' vnbroker/`
  trả **rỗng** (chỉ có trong `tests/`), `vnbroker/brokerage/dnse/` **không tồn tại**.
- `docs/SSI_EXPLORER_IMPLEMENTATION_PLAN.md:395`, `docs/VNBROKER_IMPROVEMENT_PLAN.md:85`
  trỏ `artifacts/ssi_explorer/` — thư mục đã bị xoá.

**Mục tiêu:** mỗi cổng trong `docs/_workflow/` là **lệnh chạy được, chặn đúng khi
phải chặn** (chứng minh bằng ca phủ định); tài liệu/cấu hình không còn quảng cáo
tính năng không tồn tại; `STATE.json` không gây xung đột. Kết thúc: commit + push.

## 2. In-scope (phạm vi sửa)

| # | Path | Mô tả thay đổi dự kiến |
|---|---|---|
| 1 | `docs/_workflow/gate-01-plan-approved.sh` | Chặn (exit 2) nếu không có `docs/PLAN_AUDIT*.md` chứa verdict `PASS` |
| 2 | `docs/_workflow/gate-02-plan-verified.sh` | Chặn nếu thiếu `docs/PLAN_<TASK>.md` hoặc thiếu mục bắt buộc |
| 3 | `docs/_workflow/gate-03-claims-check.sh` | Chặn nếu thiếu `docs/CLAIMS.md` hoặc `check-overlap.cjs` exit ≠ 0 |
| 4 | `docs/_workflow/gate-04-audit-pass.sh` | Bỏ `exit 2` cứng → chặn nếu audit verdict ≠ `PASS` / confidence ≠ `high` |
| 5 | `docs/_workflow/gate-05-test-pass.sh` | Thay `npm test` → `pytest tests/ -q` |
| 6 | `docs/_workflow/gate-06-report-final.sh` | Chặn nếu thiếu `docs/REPORT_FINAL.md` hoặc thiếu xác nhận gate |
| 7 | `docs/_workflow/gate-07-close.sh` | **Mới** — thay `gate-07-close.md`; chặn nếu `REPORT_FINAL.md` không nêu đủ gate |
| 8 | `docs/_workflow/gate-08-retro.sh` | **Mới** — thay `gate-08-retro.md`; chặn nếu `LESSONS.md` còn nguyên stub |
| 9 | `docs/_workflow/gate-07-close.md`, `gate-08-retro.md` | **Xoá** (đã thay bằng `.sh`) |
| 10 | `docs/_workflow/gates.json` | `cmd` → lệnh Python thật; thêm G7/G8 |
| 11 | `docs/_workflow/HOOK_CONFIG.template.md` | Bỏ "eoffice-be" → vnbroker; ghi rõ chưa bật |
| 12 | `docs/_workflow/LESSONS.md` | Bỏ "eoffice-be" → vnbroker; thêm bài học WP này |
| 13 | `docs/_workflow/VERIFICATION.md` | Sửa dòng 35 (`vnbroker: npm test`) + ghi trạng thái thật |
| 14 | `docs/_workflow/README.md` | Cập nhật mô tả G1–G8 (không còn cổng `.md`) |
| 15 | `.gitignore` | Thêm `docs/_workflow/STATE.json` |
| 16 | `.env.example` | Ghi rõ `DNSE_USERNAME`/`DNSE_PASSWORD` chưa được hỗ trợ |
| 17 | `.env.dnse.example` | Cùng nội dung |
| 18 | `README.md` | Bảng biến môi trường: ghi rõ chưa hỗ trợ |
| 19 | `docs/SSI_EXPLORER_IMPLEMENTATION_PLAN.md` | Bỏ/gạch tham chiếu `artifacts/ssi_explorer/` |
| 20 | `docs/VNBROKER_IMPROVEMENT_PLAN.md` | Cùng nội dung |

## 3. Non-goals (KHÔNG làm)

- **KHÔNG** đụng `CLAUDE.md` — Hermes bảo vệ file này (approval prompt đã hết hạn
  một lần). Mục env-var trong CLAUDE.md ghi vào báo cáo như việc còn lại.
- **KHÔNG** sửa `~/.hermes/config.yaml` (hook toàn cục `fail_closed: true` trỏ
  `VMU-eoffice/eoffice-be`). Đã đo: stub exit 0, không chặn agent. Ảnh hưởng dự án
  khác → chỉ báo cáo.
- **KHÔNG** sửa `vnbroker/**` — audit không tìm thấy bug code nào.
- **KHÔNG** bump version, không publish PyPI.
- **KHÔNG** bật `worktree` (cấu hình toàn cục, ngoài phạm vi).
- **KHÔNG** thêm dependency mới.
- **KHÔNG** sửa nội dung `STATE.json` — chỉ gitignore. `"branch": "main"` là machine
  state, sẽ được sinh lại mỗi phiên.

**Về `.gitignore` — nói rõ để không mâu thuẫn (v2 sửa mục này):** `.gitignore`
ĐANG nằm trong việc dở của người dùng (dòng 2: `/vnstock_data/` → `/vnbroker_data/`,
đã kiểm là đúng). WP này **có** sửa nó (mục 15) và **commit cả hai thay đổi** — vì
mục đích WP là để lại cây sạch. Mọi file khác thuộc việc dở của người dùng **không**
bị agent đụng; supervisor commit chúng ở một commit riêng sau khi quét secret.

## 4. Claim dự kiến

| Agent | Claim |
|---|---|
| `agent-gate-core` | `docs/_workflow/gate-01-plan-approved.sh`, `gate-02-plan-verified.sh`, `gate-03-claims-check.sh`, `gate-06-report-final.sh`, `docs/_workflow/README.md` |
| `agent-gate-verify` | `docs/_workflow/gate-04-audit-pass.sh`, `gate-05-test-pass.sh`, `gate-07-close.sh`, `gate-08-retro.sh`, `gate-07-close.md`, `gate-08-retro.md`, `docs/_workflow/gates.json` |
| `agent-repo-hygiene` | `.gitignore` |
| `agent-doc-env` | `.env.example`, `.env.dnse.example`, `README.md` |
| `agent-doc-refs` | `docs/SSI_EXPLORER_IMPLEMENTATION_PLAN.md`, `docs/VNBROKER_IMPROVEMENT_PLAN.md`, `docs/_workflow/LESSONS.md`, `docs/_workflow/HOOK_CONFIG.template.md`, `docs/_workflow/VERIFICATION.md` |

5 lát cắt, file set **rời nhau tuyệt đối**. Kiểm bằng
`node <skill>/scripts/check-overlap.cjs --file docs/CLAIMS.md` (GATE 2).

## 5. Tác động repo khác

| Hệ thống bị ảnh hưởng | Bản chất ảnh hưởng | Cần thông báo ai |
|---|---|---|
| Hook toàn cục `~/.hermes/config.yaml` | `pre_tool_call` trỏ script `eoffice-be`; chạy cả khi agent ghi file trong repo này (stub, exit 0) | người dùng — nên trỏ sang `vnbroker` hoặc tắt |
| `docs/_workflow/` dùng chung 6 dự án | Mỗi repo giữ bản riêng; sửa ở đây không ảnh hưởng dự án khác | không |
| PyPI `vnbroker 3.5.0` | KHÔNG ảnh hưởng — không bump, không publish | không |

## 6. Cách kiểm chứng

`$SKILL` = `C:/Users/Pham Viet Dung/AppData/Local/hermes/skills/software-development/multi-agent-workflow`
(đường dẫn native — Node là chương trình Windows gốc, **KHÔNG** dùng `/c/...`).

| # | Lệnh | Exit mong đợi | Ý nghĩa khi pass |
|---|---|---|---|
| 1 | `bash docs/_workflow/gate-01-plan-approved.sh` (có `PLAN_AUDIT` PASS) | `0` | Mở đúng khi hợp lệ |
| 2 | `bash docs/_workflow/gate-01-plan-approved.sh` (không có PASS) | `2` | **Chặn đúng** — cổng sống |
| 3 | `bash docs/_workflow/gate-03-claims-check.sh` | `0` | Claim không chồng lấn |
| 4 | `bash docs/_workflow/gate-05-test-pass.sh` | `0` | Chạy `pytest tests/ -q` thật |
| 5 | `bash docs/_workflow/gate-07-close.sh` (có REPORT_FINAL) | `0` | Cổng mới hoạt động |
| 6 | `bash docs/_workflow/gate-08-retro.sh` (LESSONS đã cập nhật) | `0` | Cổng mới hoạt động |
| 7 | `.venv/Scripts/python.exe -m pytest tests/ -q --timeout=180` | `0` | Không hồi quy |
| 8 | `.venv/Scripts/python.exe scripts/check_version_sync.py` | `0` | Doc khớp `pyproject.toml` |
| 9 | `.venv/Scripts/python.exe scripts/check_mypy_baseline.py` | `0` | Không lỗi strict mới |
| 10 | `uvx ruff check vnbroker tests/unit tests/contract/` | `0` | Không lỗi lint (**phải có `uvx`**) |
| 11 | `node $SKILL/scripts/check-gates.cjs --test docs/TEST_REPORT.md --audit docs/AUDIT_WP-CLEANUP-01.md --require pytest,version-sync,mypy,ruff` | `0` | GATE 5 |
| 12 | `grep -rn 'npm test' docs/_workflow/` | `1` | Đã xoá hết lệnh sai |
| 13 | `grep -rn 'eoffice-be' docs/_workflow/` | `1` | Đã xoá hết tham chiếu dự án khác |
| 14 | `ls docs/_workflow/*.md` | `0` | Chỉ còn `.md` tài liệu, không còn cổng `.md` |
| 15 | `git status --porcelain` (đối chiếu mục 2) | — | Không file ngoài scope bị sửa |

**Mọi cổng mới/sửa phải có ca phủ định** (mục 2, 12, 13) — cổng chỉ chạy ca "thật"
là cổng chưa được chứng minh.

## 7. Rollback

- `git revert <sha>` (mỗi nhóm 1 commit nếu cần) hoặc `git checkout -- <file>`.
- Kiểm sau rollback: `git status --porcelain` → chỉ còn việc dở của người dùng.
- Không đổi schema/DB/dependency ⇒ rollback an toàn tuyệt đối.

## 8. Rủi ro

| Rủi ro | Xác suất | Tác động | Giảm thiểu |
|---|---|---|---|
| Agent ghi đè việc dở của người dùng | Trung bình | Cao | Claim rời nhau; GATE 2; commit theo danh sách file chỉ định |
| Hook `eoffice-be` chặn agent ghi file | Thấp | Cao | Đã đo stub exit 0. Nếu chặn → tắt hook, ghi hazard |
| `worktree` chưa bật ⇒ 2 agent cùng sửa 1 file | Thấp | Cao | GATE 2 bắt buộc; file set đã kiểm rời nhau |
| Cổng mới báo nhầm | Trung bình | Trung bình | Mỗi cổng có ca phủ định + ca hợp lệ |
| `docs/_workflow/` là untracked ⇒ commit đưa scaffolding vào repo | **Chắc chắn** | Thấp | Có chủ đích: người dùng yêu cầu cây sạch. Báo rõ trong REPORT_FINAL |
| `pytest tests/` chậm (~140s) trong `gate-05` | Cao | Thấp | Chấp nhận; ghi rõ trong script |

## 9. Điều kiện Done

- [ ] Mọi lệnh mục 6 trả exit code như mong đợi
- [ ] Mỗi cổng mới/sửa đã chứng minh **chặn được** (ca phủ định)
- [ ] Không file nào ngoài mục 2 bị sửa
- [ ] Không file nào thuộc claim của agent khác bị sửa
- [ ] `docs/REPORT_FINAL.md` xác nhận mọi gate kèm output thô
- [ ] Đã commit + push lên `dev`; `main` không bị đụng
- [ ] `CHƯA CHẠY` ghi rõ cho mọi thứ chưa kiểm (không suy đoán `PASS`)
