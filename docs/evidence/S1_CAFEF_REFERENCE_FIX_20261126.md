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

## Version / release

- `pyproject.toml` → `3.10.0`; `README.md`, `CLAUDE.md`, `vnbroker/config.py`, `CHANGELOG.md` đã sync; importlib.metadata trả `3.10.0`.
- **BLOCKER**: không có credential PyPI trên máy local lẫn VPS (`~/.pypirc` missing, `TWINE_*`/`PYPI_TOKEN`/`POETRY_PYPI_TOKEN_PYPI` unset). ⇒ **KHÔNG tag/publish `v3.10.0`**, không tự build tay. `vninvest` vẫn pin `3.9.0` cho tới khi có token và publish thành công (S3 bump pin).
- Không tạo GitHub tag/release trong slice này.

## CHƯA CHẠY

- Full `pytest` (có integration test chạm mạng; lệnh bị huỷ khi server restart — không báo PASS).
- Live probe `bulk_range` 3 sàn từ container staging sau khi publish (S3).
- `vninvest` pin bump + migration/schema + rebase job (S2–S7).
