# SUMMARY S3 — WP-03 lỗi vĩnh viễn (BL-3 + MA-1)

- commit: xem log `feat/hang1-row1` (`fix(router): ...`)
- files: `vnbroker/core/exceptions.py` (+62),
  `vnbroker/core/utils/client.py` (+40/-11),
  `vnbroker/core/source_router.py` (+27/-1),
  `vnbroker/base.py` (+20/-5, chỉ message fail-fast, giữ nguyên type),
  `tests/unit/core/test_rate_limit_cooldown.py` (+167/-3),
  `docs/CLAIMS.md` (mở rộng claim S3)
- gates chạy: 81 passed (rate_limit_cooldown + source_router_fix +
  circuit_breaker + failover_parity + failover_tier1 + failover_integration);
  `ruff check` 5 file → clean; numstat nhỏ
- fail-before trên code HEAD thật (`bl3_red.py`, không commit):
  401 → `ConnectionError` + `should_failover True` + all-cooling trả
  `['vci', 'kbs']`; sau fix: `ProviderAuthError` + `False` + `[]`
- quyết định thiết kế: lớp lỗi mới KHÔNG kế thừa OSError (ngược với
  RateLimitError) để tenacity + should_failover đều không thấy; message +
  details cố ý không chứa marker (đặc biệt "403") + test ratchet khóa;
  fail-fast khi tất cả cooldown (trả []), probe half-open vẫn đi;
  `common/data.py` và `base.py` tự hưởng (không record_failure) nhờ cùng
  nhánh `should_failover False → raise`, không sửa loop
- lệch/quan sát đã ghi:
  - AC "pool 5 chết ⇒ ≤5 request" đạt theo hướng mạnh hơn: dừng ở provider
    đầu tiên (1 request), vì lỗi vĩnh viễn là đáp án cuối
  - MA-3 của đề xuất SAI tiền đề: `response.json()` hỏng ném ValueError,
    chưa bao giờ thành ConnectionError — đã khóa bằng test hồi quy, ghi
    đính chính ở đây thay vì sửa đề xuất cũ
- đính chính quan sát sai của chính tôi: docstring `RateLimitError` ghi
  `should_failover == False` là LỊCH SỬ đúng (đo ở base `4cd0f2d` trước W3),
  không phải stale — W3 đã sửa thành True có chủ ý (CHANGELOG 3.7.0 bảng W3
  ghi rõ False→True). S3 giữ nguyên True (test_ac_3_5 khóa). Rút kinh nghiệm:
  đọc kỹ thì trước khi ghi "stale" (L-E06 cho cả kết luận audit).
  - bão transient (cả pool 500) vẫn 15 request: cần base.py retry (Hàng 2),
    đã ghi nợ
- breaking có chủ ý: 400/401/403/404/422 không còn vào `except
  ConnectionError` — host bắt builtin sẽ thấy chúng nổi lên dạng
  vnbrokerError; ghi CHANGELOG + PR body ở chốt Hàng 1
