# REPORT FINAL — Corporate actions Slice 1–4 + fix P0 3.8.2 (2026-11-20)

- **Repo/branch**: `vnbroker@fix/corporate-actions-exrightdate`, base `main@99dabbe`.
- **Status**: code + tests + evidence **xong**; merge + tag + GitHub Release **xong**;
  **PyPI 3.8.2 CHƯA publish** — CI publish bị chặn billing (xem §7).
- **Claim**: `corporate-actions-exrightdate`.
- **Lessons áp dụng (đã tick)**: `[L-E01 (số kèm lệnh), L-E02 (fixture trong repo),
  L-E04 (ghi cả lần đỏ), L-E06 (fail-before gọi hàm thật), L-P05 (tự chạy lại gate),
  L-R01 (HTTP 200 ≠ dữ liệu đúng)]`.

## 1. Slice 4 — tổng hợp kết quả cuối (phía vninvest, đã verify lại)

Lệnh: `gh api repos/vietdungiitb/vninvest/pulls/{464,465,466,467} --jq '{number,title,state,merged_at,merge_commit_sha}'`

| PR | Nội dung | Merge commit | UTC |
|---|---|---|---|
| #464 | Follow-ups F-NEW-1..5 (DIV guard, cờ ambiguous + migration 0009, W/M adj_close, contract/mapping) | `b8514bf2` | 13:26:32Z |
| #465 | Đóng claim follow-ups | `6100c5d6` | 13:34:06Z |
| #466 | Bump pin `vnbroker==3.7.2 → 3.8.1` + evidence re-probe | `1374ddb4` | 14:12:23Z |
| #467 | Đóng claim bump pin | `2d9c669c` | 14:19:48Z |

- Pin trên `origin/dev` verify bằng `gh api repos/vietdungiitb/vninvest/contents/packages/core/backend/requirements.txt?ref=dev`
  → `vnbroker==3.8.1` (dòng 38). Claim `bump-vnbroker-381 = done`, Ledger Entry 575.
- PyPI verify: `https://pypi.org/pypi/vnbroker/3.8.1/json` → `version=3.8.1`,
  `upload_time_iso_8601=2026-11-20T13:17:40.951813Z`, `bdist_wheel + sdist`, `yanked=false`.
- Pre-push gate cuối (theo owner): **36 PASS / 0 FAIL**.
- Re-probe 3.8.1: contract 14 cột OK, facade chạy được; VNM 1057 / FPT 1079 / VCB 1023
  dòng raw; ESOP vẫn `unparsed`. **Pipeline vninvest không ảnh hưởng** (vẫn dùng
  legacy `events()` + parser riêng); flag `CORPORATE_ACTIONS_ENABLED` giữ `False`.

## 2. P0 phát hiện khi re-probe

| Tác động | Bằng chứng |
|---|---|
| `ex_date=None` 100% dòng | raw VCI dùng `exrightDate`, source 3.8.1 `_pick` thiếu key (`vnbroker/common/corporate_actions.py:155`) |
| `group_id='VNM:None'` cho 1057 dòng | `group_id=f"{symbol}:{ex_date}"` (`:183`) |
| 1000 news lẫn vào 57 event | `isEvent=False`, không `eventCode` |
| R3 (so sánh cùng ngày) vô nghĩa qua API mới | hệ quả của 2 dòng trên |

Chi tiết: `vninvest/docs/evidence/corporate-actions/REPROBE_VNBROKER_381_20261120.md`
+ bản mirror/đối chiếu trong repo này: `docs/evidence/CORPORATE_ACTIONS_FIX_381_EVIDENCE_20261120.md`.

## 3. Fix (branch này)

- `vnbroker/common/corporate_actions.py`: `_pick(row, "exrightDate", "exright_date",
  "exRightDate", "ex_date")`; helper `_is_event_row()` lọc news; normalize chỉ event.
- `tests/fixtures/vci_news_events_vnm_20261120.json`: 57 event thật + 20 news
  (captured từ endpoint live VCI, `fromDate=20100101&toDate=20261120`).
- `tests/unit/common/test_corporate_actions_parser.py`: 6 test mới (key thật,
  lọc news, golden 57, 2 DIV 2024-09-24, tương thích legacy, drop news).
- Bump `3.8.1 → 3.8.2`: `pyproject.toml`, `README.md`, `CLAUDE.md`,
  `vnbroker/config.py`, `CHANGELOG.md`.

**Kết quả**

| Item | Trước fix | Sau fix |
|---|---|---|
| Fixture `normalize_events(rows,'VNM')` | 77 dòng · 77 None · `VNM:None` | 57 dòng · 0 None · 48 group |
| Test `-k RealVCI` | **5 failed / 1 passed** | 6 passed |
| 3 file unit slice | — | **25 passed** |
| Live VNM / FPT / VCB | — | 57 / 79 / 23 dòng, 0 None |
| Facade VNM | — | 57 dòng, `source=VCI`, 2 DIV `2024-09-24` |

## 4. Gates (chạy thật, không suy)

| Gate | Lệnh | Kết quả |
|---|---|---|
| ruff-src | `python -m ruff check vnbroker scripts tests/unit tests/contract` | **exit 0** |
| ruff 2 file đổi | `python -m ruff check vnbroker/common/corporate_actions.py tests/unit/common/test_corporate_actions_parser.py` | `All checks passed!` |
| lessons | `python scripts/check_lessons.py` | **exit 0** |
| tcbs-coverage | `python scripts/verify_tcbs_coverage.py` | **exit 0** |
| tcbs-bodies | `python scripts/check_tcbs_bodies.py --baseline docs/tcbs_body_baseline.json` | **exit 0** (0 lệch) |
| provider-consistency | `python scripts/check_provider_consistency.py` | **exit 0** (cảnh báo: không có `.env`) |
| encoding | `python scripts/check_encoding.py` | **exit 0** (458 file) |
| pytest-contract | `python -m pytest tests/contract -q -p no:cacheprovider` | **149 passed** |
| pytest-full | `python -m pytest tests/ -q -p no:cacheprovider` | **2304 passed, 30 skipped, 2 failed** (xem §5) |
| `scripts/check_all.ps1` | — | **CHƯA CHẠY**: script từ chối chạy khi thiếu `.venv\Scripts\python.exe` (exit 2); không tự `pip install`. Các gate thành phần được chạy trực tiếp bằng interpreter hệ thống như bảng trên. |
| CI publish 3.8.2 | — | **CHƯA CHẠY** — chờ merge + tag/release |

## 5. Hai cái đỏ của full suite — đều là môi trường, không phải code

1. `tests/integration/test_dnse_integration.py::TestEnvVisibility::test_the_env_is_actually_visible`
   — assert `DNSE_API_SECRET` tồn tại; repo không có `.env` (các test DNSE khác đều skip vì lý do này).
2. `tests/unit/scripts/test_check_version_sync.py::test_declared_version_matches_the_installed_distribution_or_the_gate_fails`
   — dist editable đang cài `1.0.2`, pyproject `3.8.2`. Cùng lỗi ở `3.8.1`
   (xác nhận bằng `runtime_metadata_drift('3.8.1','1.0.2')` trả lý do), tức **pre-existing**.
   Sửa bằng `pip install -e .` trong môi trường có quyền cài — **KHÔNG tự chạy**.

`mypy-baseline` cũng đỏ: `FAIL: baseline đã HẾT HẠN (2026-11-01)`, 1266 lỗi strict
trong baseline — hết hạn theo ngày, độc lập với thay đổi ở branch này.

## 6. Next steps / owner

1. Review → merge commit branch này vào `main` (không squash).
2. Tag annotated `v3.8.2` + GitHub Release có section Breaking (để trống: không breaking)
   → workflow publish lên PyPI. Chạy lại PyPI JSON verify sau release.
3. vninvest: bump pin `3.8.1 → 3.8.2`, re-probe VNM/FPT/VCB (kỳ vọng 57/79/23),
   chạy lại 66 test pipeline + full BE/FE + deploy staging; **sau đó** mới đổi
   `ingest.fetch_corporate_actions` sang field số (mapping `FIELD_MAPPING_VNBROKER.md`,
   lưu ý `is_esop ↔ ambiguous_ratio_pct`). Giữ `CORPORATE_ACTIONS_ENABLED=False`.
4. Đóng claim `corporate-actions-exrightdate` sau khi merge. **Đã đóng** tại `eaa7487`.

## 7. TRẠNG THÁI RELEASE 3.8.2 (cập nhật 2026-11-20T14:56Z) — BLOCKER ngoài code

| Việc | Trạng thái | Evidence |
|---|---|---|
| Merge vào `main` | ✅ xong | `0da4df4` (merge commit), push `99dabbe..eaa7487 main -> main` |
| Claim đóng | ✅ xong | `eaa7487` |
| Annotated tag `v3.8.2` | ✅ xong | trỏ `eaa7487`; push tag thành công |
| GitHub Release | ✅ xong | https://github.com/vietdungiitb/vnbroker/releases/tag/v3.8.2 · `publishedAt=2026-11-20T14:55:12Z` |
| CI publish lên PyPI | 🔴 **CHƯA CHẠY ĐƯỢC** | run `44758095521` (failed), re-run cùng run cũng failed: annotation *"The job was not started because recent account payments have failed or your spending limit needs to be increased"* — GitHub Actions billing, **không phải lỗi code/test** |
| PyPI 3.8.2 | ❌ **chưa có** | chưa có artifact; không báo đã publish |

Lệnh kiểm chứng: `gh run list --workflow publish.yml --limit 3 --json databaseId,status,conclusion`,
`gh run view 44758095521`. So sánh: run 3.8.1 `44742622962` **success** lúc 13:14:52Z —
nghĩa là billing block phát sinh sau đó (AGENT_PROTOCOL.md ghi "CI bị chặn billing là stale"
đã **hết hạn** tại thời điểm này; cần owner cập nhật).

Không có fallback local: `~/.pypirc` không tồn tại và không có biến
`TWINE_USERNAME/TWINE_PASSWORD/PYPI_TOKEN/PYPI_API_TOKEN` trong môi trường; publish
dùng Trusted Publishing OIDC của GitHub Actions nên **không tự upload được từ máy này**.

**Hành động bắt buộc của owner**: khôi phục billing GitHub → `gh run rerun 44758095521`
(hoặc tạo lại release) → verify `https://pypi.org/pypi/vnbroker/3.8.2/json` → mới báo
vninvest bump pin. Trước đó mọi tuyên bố "3.8.2 đã phát hành" là **sai**.
