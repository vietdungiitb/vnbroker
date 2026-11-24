# HANDOFF — P1 daily_bars / v3.9.0 (2026-11-24)

- **Repo/branch**: `vnbroker@feat/daily-bars-p1` (base main sau merge `a957bb5`) · claim `daily-bars-p1`
- **Trạng thái**: code + test + gate xong, audit **PASS** (1 reservation O-7), chờ merge/tag
- **Version**: bump **3.9.0** tại `pyproject.toml`, `README.md`, `CLAUDE.md`, `config.py`, dist metadata

## 1. Kết quả + evidence

1. R1–R6 theo `vninvest/docs/REQUIREMENTS_VNBROKER_SSOT_P1_20261124.md`:
   - `Vnbroker.daily_bars(...)` thin wrapper, frame canonical (R1/R2).
   - `CafefReference.bulk_year(...)` XLSX ALL, pacing ≥1 s, retry, cache, BytesIO (R3).
   - Coverage gate phân biệt `missing` / `no_trading_days`; default start 2011 (R4).
   - Giữ nguyên 31 targeted + 153 contract; CafeF không vào pool (R5).
   - `reconcile_prices(frame, ...)` tách đường ghi, drift 0,5% phân loại rebase (R6).
2. R7: golden TPB `04/01/2022 → 42750/17940/11034900/467.26e9` + **assert ngày**
   (bài học nến 1970). Parity cross-repo 3 mã × 3 năm thuộc vninvest P2 — reservation O-7, không chặn.
3. Audit: vòng 1 NEED_REVISION (7 objection O-1..O-7) → vòng 2 **PASS** sau sửa O-1..O-6.

## 2. Gate (output thật)

`pwsh -File scripts/check_all.ps1` với 2 env var (`DNSE_API_SECRET=placeholder…`,
`PYTEST_DEBUG_TEMPROOT=<temp sạch>`): **PASS 10/10 gate** —
ruff-src, version-sync 3.9.0, lessons, tcbs-coverage, tcbs-bodies, provider-consistency,
mypy-baseline 1106/1107, encoding 469 file, pytest-contract **153**, pytest-full **2345 passed/30 skipped**.
`ruff-tests-all` KNOWN-RED 13 lỗi có sẵn. CI GitHub Actions **CHƯA CHẠY** (billing).

## 3. Next steps / owner

1. Merge `feat/daily-bars-p1` vào `main` (merge commit), đóng claim `daily-bars-p1` → `done`.
2. Tạo annotated tag `v3.9.0` + GitHub Release (section Breaking: để trống — không breaking).
3. vninvest pin `vnbroker==3.9.0`, rồi mới vào P2 (dual-write, parity test 3 mã × 3 năm).
4. ToS bulk vẫn chờ owner; UI default đổi ở P3.

## 4. Resume cho phiên kế tiếp

Đọc file này → `vninvest/docs/REQUIREMENTS_VNBROKER_SSOT_P1_20261124.md` →
`docs/evidence/CAFEF_REFERENCE_LAYER_DESIGN_20261124.md`. Nguyên tắc: test assert **ngày**;
không bulk thật khi ToS chưa ký; CafeF không vào AUTO pool; parity test nằm ở vninvest P2.
