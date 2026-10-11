# SUMMARY S4 — WP-04 rỗng-vs-lỗi (BL-6)

- commit: xem log `feat/hang1-row1` (`fix(explorer): ...`)
- files: `vnbroker/explorer/kbs/listing.py` (except→re-raise ×3,
  rỗng→EmptyProviderResult ×3, helper `_get_full_stock_data` ném ra),
  `vnbroker/explorer/kbs/trading.py` (non-200→raise_for_status,
  exception→re-raise, body rỗng→EmptyProviderResult, log success chỉ khi
  non-empty), `vnbroker/explorer/vci/quote.py`
  (`_normalize_ohlc_response` ném thay vì `[]`), `common/data.py`
  **KHÔNG chạm**, `tests/unit/explorer/kbs/test_empty_result.py` (mới, 12
  test) + `tests/unit/explorer/kbs/__init__.py`
- gates chạy: S4 file 12/12; explorer+common+contract **504 passed, 3
  skipped** (skip là live-gated, đúng quy ước); `ruff check` 4 file → clean
- fail-before: 10/12 test ĐỎ `DID NOT RAISE` trên base (2 lock-in predicate
  xanh sẵn theo thiết kế)
- quyết định then chốt (L-P06, sửa AC approved): **KHÔNG đổi
  `_is_unusable_provider_result`** — AC gốc ("rỗng có cột ⇒ True") mâu thuẫn
  với AC holiday ("rỗng có cột ⇒ dùng được") và với docstring 449-488 của
  chính predicate. Sửa phía PRODUCER (không sinh frame lỗi) thay vì đổi
  định nghĩa rỗng. Predicate giữ nguyên + 2 test khóa.
- dung sai một phần giữ nguyên (ngoài scope, có chủ ý): per-industry
  warn+continue, `_get_industries_internal`/`_get_symbols_by_industry_internal`
  trả `[]` (được chặn bởi EmptyProviderResult ở aggregate)
- import `EmptyProviderResult` ở module-level an toàn: `common/data`
  không import explorer (registry lazy), không chu trình
- hệ quả có chủ ý: `industry_peers` (common/data.py:1524) nay ném ra khi KBS
  chết thay vì trả "không có peer" — đúng P-1 (thất bại phải kêu)
- `test_non_429...`-tương đương: không có (không test cũ nào khóa hành vi nuốt)
