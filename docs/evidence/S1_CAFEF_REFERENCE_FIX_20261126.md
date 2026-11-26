# S1 — Sửa 4 bug CafeF reference (2026-11-26)

- **Branch**: `feat/cafef-reference-fix` · **Claim**: `cafef-reference-fix` · base `main` @ `8fa97b6`.
- **Nguồn yêu cầu**: `vninvest/docs/PLAN_PRICE_REBASE_AND_RECOVERY_20261126.md` S1 + điều kiện owner C3 (tag/publish PyPI 3.10.0).
- **Phạm vi**: `vnbroker/reference/{client,const,parser,cafef}.py`, `vnbroker/common/client.py`, version docs, test mới. Không đụng provider tier-1, không đụng AUTO pool.

## 4 bug đã sửa (fail-before → pass-after)

| # | Bug | `file:line` cũ | Fix | Test fail-before |
|---|---|---|---|---|
| 1 | `bulk_year` hard-code `EndDate=12/31/{year}` → HTTP 400 cho năm hiện tại | `reference/client.py:202-203` (cũ) | `bulk_year(..., end_date=None, use_cache=True)` clamp `min(end_date, today_vn)`; thêm `bulk_range()` | `test_bulk_year_clamps_end_date_to_today` — `TypeError: unexpected keyword end_date` |
| 2 | `_BULK_CACHE` vô hạn trong worker chạy dài | `reference/client.py:160,218` (cũ) | TTL 300 s + key theo resolved end date; `use_cache=False` **bypass cả đọc lẫn ghi**; prune entry hết hạn | `test_bulk_year_use_cache_false_refetches` — `TypeError: unexpected keyword use_cache` |
| 3 | `reconcile_prices` không nhận `exchange`, mặc định HOSE → 400 cho HNX/UPCOM | `common/client.py:289-306` (cũ) | Tham số `exchange="HOSE"` truyền xuống `CafefReference(exchange=...)` | `test_reconcile_prices_passes_exchange` — `AttributeError`/`TypeError` |
| 4 | Frame reference có `time` nhưng không có `date`/`change_pct` → `vninvest` importer `KeyError: 'date'` | `reference/parser.py:12-34,50` (cũ) | Thêm `date` (`datetime.date`) + `change_pct` (parse `"Thay đổi"`); map `"Thay đổi" → change_pct`; `change_pct` vào `CANONICAL_FIELDS` | `test_parse_records_exposes_date_and_change_pct` — `AssertionError: 'date' not in columns` |

Regression đã gặp và sửa trong phiên: test cache cũ `test_bulk_year_all_uses_one_xlsx_call_and_cache` bị ô nhiễm vì bản đầu `use_cache=False` vẫn **ghi** cache. Sửa thành bypass cả ghi ⇒ 378/378 unit PASS.

## Gates đã chạy thật

| Gate | Kết quả |
|---|---|
| `pytest -m unit` (venv local) | **378 passed · 3 skipped · 0 failed** (3 live-integration module bị disable theo default) |
| `pytest tests/contract/test_cafef_reference_contract.py` | **4 passed** |
| `python scripts/check_version_sync.py` | **version-sync OK: 3.10.0** (sau `pip install -e . --no-deps` để refresh dist metadata) |
| `git diff --numstat` | 10 file source/docs, số dòng khớp dự kiến, không đổi hàng loạt (L-T01) |
| Lệnh hệ điều hành | dùng `PYTEST_DEBUG_TEMPROOT` trỏ thư mục temp đã tạo để tránh `PermissionError` khi dọn temp trên Windows |

**CI GitHub (PR #7)**: lint (mypy baseline), code-quality, security, dependencies, performance, test 3.13 (ubuntu+windows) **đều PASS**. Còn đỏ: 2 contract test trên Python 3.10 (`pandas` cũ: `OutOfBoundsDatetime` cho năm 3000 và annotation `pandas.core.frame.DataFrame`) + coverage do `TestEnvVisibility` đòi `DNSE_API_SECRET`. Đây là **baseline có sẵn trên `main`** (5 run gần nhất đều failure), không phải do change này; nhánh `main` không có branch protection nên merge vẫn được phép. Đã sửa phần có thể sửa gọn (tomli backport cho 3.10, placeholder env cho coverage).

## Version / release

- `pyproject.toml` → `3.10.0`; `README.md`, `CLAUDE.md`, `vnbroker/config.py`, `CHANGELOG.md` đã sync; importlib.metadata trả `3.10.0`.
- **Publish ĐÃ xong (2026-11-26)**: PR #7 merge vào `main` @ `2b306b7` (merge-commit) → tag annotated `v3.10.0` → GitHub Release https://github.com/vietdungiitb/vnbroker/releases/tag/v3.10.0 → workflow `publish.yml` run `45807367035` **Build + Publish to PyPI thành công** (dùng Trusted Publishing/OIDC, không cần token local).
- PyPI verify: `GET https://pypi.org/pypi/vnbroker/3.10.0/json` → `version=3.10.0`, 2 file `vnbroker-3.10.0-py3-none-any.whl` + `tar.gz` (upload 2026-11-26T11:08Z).
- Lưu ý trước đó ghi "blocked do thiếu token" là **sai**: publish dùng OIDC qua GitHub Actions, không cần credential local.
- `vninvest` vẫn pin `3.9.0` — việc bump pin sang `3.10.0` nằm ở S3 (file shared, cần claim/coordinator).

## CHƯA CHẠY

- Full `pytest` (có integration test chạm mạng; lệnh bị huỷ khi server restart — không báo PASS).
- Live probe `bulk_range` 3 sàn từ container staging sau khi publish (S3).
- `vninvest` pin bump + migration/schema + rebase job (S2–S7).
