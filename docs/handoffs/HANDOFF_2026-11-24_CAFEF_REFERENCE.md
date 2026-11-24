# HANDOFF — CafeF reference layer + route `adjusted=False` (2026-11-24)

- **Repo/branch**: `vnbroker@feat/cafef-reference` · base `e996cb4` + slice adjusted (chưa merge)
- **Trạng thái**: `in-progress` — code + test xong, gate chính thức **CHƯA CHẠY** (thiếu `.venv`)
- **Claim**: `cafef-reference` (`docs/CLAIMS.md`, dòng cuối, đã đổi tên từ `kbs-vci-adjusted-param`)

## 1. Kết quả + evidence

1. **Quyết định Owner 2026-11-24**: XLSX primary + JSON fallback; expose `Vnbroker.reference("cafef")`;
   route `KBS/VCI adjusted=False` sang CafeF. CafeF là **reference/cross-check**, không phải
   provider tầng 1 — không đăng ký registry/AUTO pool (contract test khóa).
2. Code:
   - `vnbroker/reference/{__init__,const,client,parser,reconcile,cafef}.py` (module mới).
   - `vnbroker/common/client.py`: method `reference()` (lazy import, validate tên).
   - `vnbroker/explorer/kbs/quote.py`, `vci/quote.py`: thay guard fail-only bằng route CafeF;
     helper import trễ, trả records native (KBS `t`=chuỗi `YYYY-MM-DD 07:00`, VCI `t`=epoch int);
     gắn `attrs source/data_origin='cafef'`.
3. Plan + audit: `docs/PLAN_CAFEF_REFERENCE_20261124.md`. Vòng 1 NEED_REVISION (9 objection),
   vòng 2 AGREE (2 reservation đã đóng bằng chữ), vòng 3 re-audit code cuối — verdict ở §3.
4. TDD: RED `ModuleNotFoundError` → GREEN **31 passed** targeted (sau khi thêm test
   `reconcile_requires_symbol` + assert ngày ở tầng API). Full unit chạy 2 lần theo L-E04:
   lần 1 `2 failed, 2088 passed` (flake), lần 2 `1 failed, 2089 passed` — failure cố định duy
   nhất là version drift. Contract **153 passed** (149 → +4).

## 2. Gate — output thật

| Gate | Lệnh | Kết quả |
|---|---|---|
| Targeted | `pytest tests/unit/reference tests/unit/explorer/test_quote_adjusted_parameter.py tests/unit/core/test_adjusted_failover.py tests/contract/test_cafef_reference_contract.py -q` | **31 passed** |
| Unit full (L-E04: chạy 2 lần) | `python -m pytest tests/unit -q` | lần 1 `2 failed, 2088 passed`, lần 2 `1 failed, 2089 passed, 6 skipped`. Failure cố định: `test_check_version_sync.py` (pyproject 3.8.2 vs dist-info 1.0.2), có sẵn; lần 1 có thêm 1 flake |
| Contract | `python -m pytest tests/contract -q` | **153 passed** |
| Ruff | `python -m ruff check <file đổi>` | **All checks passed** |
| Mypy | `python -m mypy vnbroker/reference vnbroker/common/client.py --follow-imports=silent` | reference module **0 lỗi**; 7 lỗi còn lại đều có sẵn trong `common/client.py` |
| `check_all.ps1` FULL | `pwsh -File scripts/check_all.ps1` | **PASS** — 10/10 gate (ruff-src, version-sync, lessons, tcbs-coverage, tcbs-bodies, provider-consistency, mypy-baseline, encoding, pytest-contract **153**, pytest-full **2337 passed/30 skipped**). `ruff-tests-all` KNOWN-RED 13 lỗi có sẵn |

`.venv` đã được tạo (`python -m venv .venv` + `pip install -e ".[test,lint]"`). Hai env var cần thiết cho
gate FULL trên máy này: `DNSE_API_SECRET=placeholder-for-env-gate-no-live-call` (test gác cổng,
không có `.env`) và `PYTEST_DEBUG_TEMPROOT=<temp sạch>` (né junction hỏng
`pytest-of-...\pytest-current` gây atexit PermissionError). Không có request mạng thật trong gate.

## 3. Re-audit cuối

- Vòng 1: **NEED_REVISION** (9 objection O-1..O-9 — VCI epoch time, attrs source, AUTO pool,
  vị trí helper, test mock seam, claim identity…) → đã đóng trong plan.
- Vòng 2: **AGREE** (2 reservation O-10/O-11 — xoá 4 guard cũ, nhánh raw nhảy thẳng tới
  `pd.DataFrame(records)`, hành vi `to_df=False`) → đã đóng bằng chữ.
- Vòng 3 (code cuối): **NEED_REVISION** với blocker B-1 — VCI dùng `source="cafef"` khiến
  `ohlc_to_df` hiểu epoch là nanosecond → nến **1970** (test xanh vì chỉ assert close, không
  assert ngày). Đã đổi `source="VCI"` tại `vci/quote.py:329,592` + thêm assert ngày vào test.
- Vòng 4: **PASS** — auditor xác nhận B-1 đóng, không còn blocker.

Bài học: test phải assert **ngày**, không chỉ giá — nếu không, frame sai lịch vẫn xanh hợp đồng.

## 4. Next steps / owner

- Gate FULL đã PASS → có thể merge `feat/cafef-reference` vào `main` (merge commit), đóng claim `cafef-reference` → `done`.
- Scripts check versions: mypy-baseline đã regenerate (1107 lỗi, expiry 2026-12-31) do tool drift — đã ghi lý do trong script.
- ToS/rate-limit CafeF đã được Owner biết từ plan vninvest; không tự bulk tải tất cả mã.
- Không bump version (chưa có tag/release).

## 5. Resume cho phiên kế tiếp

1. Đọc file này → `docs/PLAN_CAFEF_REFERENCE_20261124.md` → `docs/evidence/CAFEF_REFERENCE_LAYER_DESIGN_20261124.md`.
2. `git status --short` + `git branch --show-current` (phải là `feat/cafef-reference`).
3. Nếu cần sửa: giữ nguyên quy tắc — CafeF ở `vnbroker/reference/`, **không** đăng ký provider;
   mọi test phải assert **ngày** (bài học B-1: nến 1970 vẫn xanh nếu chỉ assert giá).
4. Chạy lại: targeted (31 test) → contract (153) → full unit (kỳ vọng 1 fail version drift) →
   ruff → mypy → `check_all.ps1` FULL khi có `.venv`.
5. Re-audit độc lập bắt buộc trước khi báo PASS; cập nhật CHANGELOG + file handoff này.

## 6. Nhật ký thay đổi (CHANGELOG)

`CHANGELOG.md` mục `Unreleased — CafeF reference + adjusted cho history()` ghi đủ Added/Changed/Evidence.
Không có `docs/CODE_CHANGE_AUDIT_LEDGER.md` trong repo này (đã kiểm; đây là quy ước của repo khác).
