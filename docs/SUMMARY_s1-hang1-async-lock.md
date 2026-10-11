# SUMMARY S1 — WP-01 async lock per-loop (BL-1)

- commits: `8276600` (claims), `6fa4e2a` (fix) trên `feat/hang1-row1`
- files: `vnbroker/core/utils/async_client.py` (+79/-37),
  `tests/unit/core/test_async_client.py` (+51/-1)
- gates chạy: `pytest tests/unit/core/test_async_client.py` → **9 passed**
  (6 cũ + 3 mới); `ruff check` 2 file → clean; `git diff --numstat` nhỏ,
  không rewrite (hazard 16 clear); grep traversal: không ai dùng
  `_acquire_token`/`mgr._clients`/`RATE_LIMITER._` cũ
- fail-before (L-E06, code thật, lỗi thật):
  - `test_rate_limiter_survives_sequential_event_loops` ĐỎ với đúng
    `RuntimeError: <Lock [locked]> is bound to a different event loop`
  - `test_client_manager_isolates_clients_per_event_loop` ĐỎ (share 1 client)
  - `test_import_creates_no_loop_bound_lock` ĐỎ (Lock ở module scope)
  - phát hiện khi đo: test không-contention XANH giả trên Python 3.13 —
    lock chỉ bind khi có waiter; đã sửa test để contention cả 2 loop
    (bằng chứng: script `loopbind2.py`, loop2-hammer RuntimeError)
- lệch AC đã ghi (L-P06): giữ tên module-level `RATE_LIMITER` (public API
  trong `__all__`, `core/utils` re-export) — sau fix nó không giữ state
  gắn loop; intent AC giữ, chữ AC đổi + lý do ở đây
- rủi ro còn lại: `close()` đóng best-effort client của loop đã chết;
  per-loop pool = churn connection mỗi request Django (đúng giá của isolation,
  httpx chính thức không hỗ trợ share client qua loop)
- out-of-scope chạm mà không sửa: class `TokenBucketRateLimiter` trùng tên
  với `rate_limiter.py` (minor, đã ghi nợ ở S1 §2 quyết định 2)
