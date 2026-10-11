# AUDIT — HANG1 Row 1 (S1–S4), code audit sau Stage 4

Phạm vi: `git diff main...HEAD` trên `feat/hang1-row1` (16 file tracked +
6 docs deployment). Vai trò auditor độc lập về quyền (read-only) nhưng cùng
người thực hiện (solo Mode B) — xem `confidence` ở cuối.

## Blocker: 0

## Major: 0

## Minor / quan sát (không chặn merge, ghi để reviewer quyết)

- M1: `AsyncClientManager.close()` đóng best-effort client của loop đã chết —
  chưa đo đường này (không test nào kết nối thật). Rủi ro thấp, ghi nhận.
- M2: `_pick_initial_source` nay ném khi tất cả đang cooldown (trước đây
  constructor vẫn dựng rồi mới lỗi ở lần gọi). Cùng type ValueError, message
  rõ hơn — hệ quả có chủ ý của fail-fast, đã ghi vào SUMMARY_s3.
- M3: `ProviderAuthError` và họ hàng không vào `except ConnectionError` nữa
  (breaking có chủ ý) — host nào bắt builtin sẽ thấy chúng nổi lên dạng
  vnbrokerError. Đã ghi CHANGELOG + PR body; cần Owner xác nhận với vninvest.
- M4: bão transient (cả pool 500) vẫn 15 request — cần base.py retry (Hàng 2).
- M5: `common/data.py` định nghĩa class `Config` riêng đè tên (dòng 205) —
  bẫy cho người mới, ngoài scope, đã ghi handover.

## Đã kiểm bằng traversal (hazard 7), không bằng đọc lướt

- Không ai dùng `_acquire_token` / `mgr._clients` / `mgr._lock` /
  `RATE_LIMITER._` cũ (grep toàn repo, 0 match).
- Không ai import `vnbroker.explorer.kbs.listing` tĩnh (registry lazy) ⇒
  import module-level `EmptyProviderResult` không chu trình.
- Mọi caller của `symbols_by_industries` / `_fetch_stock_board` /
  `_normalize_ohlc_response` đã rà: `api/snapshot.py:500` đã except;
  `industry_peers` đổi sang ném trung thực (có chủ ý, P-1).
- Docstring lịch sử của `RateLimitError` đã xác minh lại là đúng (không stale).

## Verdict: AGREE (không phải PASS)

`confidence: medium` — auditor và người code là một (solo), dù đã bù bằng
full-suite xanh, fail-before bằng code thật, traversal thay vì đọc lướt, và
2 lần tự bắt lỗi (test xanh giả S1, citation stale của chính mình).
Bước audit độc lập thật sự là review của Owner trên PR — mọi residual risk
đã liệt kê ở trên và trong PR body để reviewer tick.

Gate 6→7 theo skill cần TEST_REPORT toàn Pass (có, trừ 2 KNOWN-RED đã ghi)
+ AUDIT 0 blocker/major (có) — đủ điều kiện mở PR, KHÔNG tự merge vào main
(vào main cần tag + Release theo luật repo, thuộc Owner — Q7).
