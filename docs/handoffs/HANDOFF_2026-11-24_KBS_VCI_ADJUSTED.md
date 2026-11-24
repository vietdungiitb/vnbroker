# HANDOFF — KBS/VCI `history(adjusted=...)` (2026-11-24)

- **Repo/branch**: `vnbroker@feat/kbs-vci-adjusted-param` · base `e996cb4` (`main`)
- **Trạng thái**: `in-progress` — code + test xong, gate chính thức **CHƯA CHẠY** (thiếu `.venv`), chờ merge
- **Claim**: `kbs-vci-adjusted-param` = `in-progress` (`docs/CLAIMS.md`, 1 dòng cuối)

## 1. Kết quả + evidence

1. Đo lường trước: KBS/VCI **chỉ trả giá đã điều chỉnh**; VCI `raw-chart` → 404,
   mọi payload/query `adjust*` vô dụng; KBS mọi `adjust*` trả y hệt baseline.
   Bằng chứng + lệnh tái lập: `docs/evidence/KBS_VCI_RAW_PRICE_PROBE_20261124.md`.
   ⇒ AC gốc "lấy giá thô" **không thi hành được** (L-P06), đã đổi thành "fail rõ ràng".
2. Implement:
   - `vnbroker/explorer/kbs/quote.py`: helper `_require_raw_price_support` +
     `adjusted` trong `history` (guard ở dòng đầu, trước nhánh parallel) và `fetch_multiple`.
   - `vnbroker/explorer/vci/quote.py`: tương tự cho `history`, `history_async`, `fetch_multiple`.
   - `vnbroker/api/quote.py`: chữ ký `adjusted: Optional[bool] = None`; `@retry` thêm
     `retry_if_not_exception_type(ProviderBadRequestError)` + `reraise=True` để lỗi
     không bị bọc `RetryError` (network error vẫn retry).
   - Dùng `ProviderBadRequestError` thay `NotImplementedError` vì
     `core/source_router.py:476-479,493`: cái trước `should_failover=False`, cái sau `True`.
3. Plan + 3 vòng audit độc lập: `docs/PLAN_KBS_VCI_ADJUSTED_PARAM_20261124.md`,
   verdict cuối **AGREE** (không blocker/major).
4. TDD: fail-before `9 failed, 4 passed` (7 TypeError + 2 RetryError) → sau fix
   `15 passed` (đã thêm 2 test `adjusted=None` tường minh theo reservation của re-audit:
   guard đổi từ truthiness sang `is not False`). Lệnh:
   `python -m pytest tests/unit/explorer/test_quote_adjusted_parameter.py tests/unit/core/test_adjusted_failover.py -q`.
5. Re-audit code cuối: **AGREE**; 3 reservation đã đóng: `None` → default (fix ở trên),
   ma trận plan `docs/PLAN_KBS_VCI_ADJUSTED_PARAM_20261124.md:69-72` đã có AC-7/8/9,
   CHANGELOG `Unreleased` đã ghi behavior change `reraise=True`.

## 2. Gate — output thật

| Gate | Lệnh | Kết quả |
|---|---|---|
| Targeted test | `python -m pytest <2 file mới> -q` | **15 passed** |
| Targeted + regression | `python -m pytest <2 file mới> tests/unit/common/test_quote_kwargs.py tests/unit/api/test_quote.py -q` | **26 passed** (đo trước khi thêm 2 test `None`; sau khi thêm: chạy lại targeted = 15 passed) |
| Unit full | `python -m pytest tests/unit -q` | **1 failed, 2076 passed, 6 skipped** — 1 fail là `test_check_version_sync.py` (pyproject 3.8.2 vs dist-info 1.0.2, lỗi môi trường có sẵn, đã ghi ở `docs/handoffs/HANDOFF_2026-11-20_CORPORATE_ACTIONS.md:16`) |
| Contract | `python -m pytest tests/contract -q` | **149 passed** |
| Ruff | `python -m ruff check <5 file đổi>` | **All checks passed** |
| `check_lessons.py` | `python scripts/check_lessons.py` | **PASS** (26/40 lesson) |
| `check_encoding.py` | `python scripts/check_encoding.py` | **OK: 460 file, không mojibake** |
| `mypy` trên 3 file đổi | `python -m mypy ... --follow-imports=silent` | 33 → **32 lỗi** (xóa đúng lỗi mới do mình: `params: Dict[str, Any]`) |
| `mypy-baseline` | `python scripts/check_mypy_baseline.py` | **FAIL có sẵn**: baseline hết hạn 2026-11-01 (1266 lỗi) — không tự `--update` |
| `check_all.ps1 -Quick` | `pwsh -File scripts/check_all.ps1 -Quick` | **CHƯA CHẠY** — `[FATAL] Khong tim thay .venv\Scripts\python.exe`. Không tự `pip install` |

Máy này **không có `.venv`** (`Test-Path .venv\Scripts\python.exe` → False);
dùng Python hệ thống 3.13.14. CI GitHub Actions của repo **không chạy** (billing) —
không dùng badge làm bằng chứng.

## 3. Next steps / owner

- Owner: coordinator merge branch `feat/kbs-vci-adjusted-param` vào `main` (merge commit).
- Trước merge: tạo `.venv` + `pip install -e ".[test,lint]"` rồi chạy
  `pwsh -File scripts/check_all.ps1` FULL; nếu `mypy-baseline` vẫn đỏ do hết hạn,
  hỏi owner gia hạn baseline — **không** tự `--update`.
- Đóng claim `kbs-vci-adjusted-param` → `done` sau merge.
- CHANGELOG đã có mục `Unreleased` ghi rõ behavior change `reraise=True`.
- Không bump version (chưa có tag/release).
- **Câu hỏi mở (đã thu hẹp):** maintainer vnstock xác nhận tại issue #129 rằng **giá thô
  có tồn tại nhưng chỉ trong bản sponsor `vnstock_data`, không có trong API public**
  (xem evidence §5.0). Phép thử của ta chỉ khẳng định *"chưa tìm thấy trong API public"*.
  Nếu sau này có license sponsor hoặc tìm ra endpoint public khác, chỉ cần thay nội dung
  `_require_raw_price_support` ở 2 explorer — bề mặt `adjusted` đã có sẵn. Việc dùng bản
  sponsor hoặc route sang nguồn khác (phương án B/C) cần Owner duyệt riêng.
