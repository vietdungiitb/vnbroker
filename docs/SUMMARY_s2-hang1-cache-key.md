# SUMMARY S2 — WP-02 cache key fallback (BL-2)

- commits: xem log `feat/hang1-row1` (`fix(cache): ...`)
- files: `vnbroker/core/utils/cache.py` (+107/-4),
  `tests/unit/core/test_cache_key.py` (+119)
- gates chạy: `pytest tests/unit/core/test_cache_key.py` → **58 passed**
  (52 cũ + 6 mới); `ruff check` 2 file → clean; numstat nhỏ
- fail-before (L-E06): proxy/tenant key byte-identical pre-fix
  (`obj:..._TenantListingLike|<... object at <addr>>` cho cả 2 tenant);
  decorator cache opaque pre-fix (`calls==1`); cả 3 ĐỎ rồi XANH
- đo trên class thật (`bl2_real.py`, không commit): VCI proxy A/B khác key,
  show_log F/T khác key, DNSE tenant A/B khác key, same-instance ổn định,
  không key nào chứa `0x`
- thiết kế: `_encode_state_deep` 2 tầng (terminal/Enum/container-audited/
  đệ quy instance `vnbroker.*` + `cyclic`/`opaque` type-only, không id —
  giữ hợp đồng address-free và trần repr của pandas); decorator từ chối
  key mang `state=<bare:uncacheable>` (bypass, không collide)
- lệch AC đã ghi (L-P06): `show_log` giữ trong key theo đúng AC S2 đã duyệt
  (phân biệt, không bỏ — WP-09 Hàng 2 muốn bỏ thì sửa AC riêng, đã ghi nợ);
  DNSE/SSI "key phân biệt" đạt bằng deep-encode `_config`, không phải
  refuse-toàn-bộ — intent (không phục vụ chéo tenant) giữ
- out-of-scope không sửa: single-flight (MA-4), trả bản sao (MA-5),
  `@lru_cache` (WP-09 Hàng 2); class `TokenBucketRateLimiter` trùng tên
