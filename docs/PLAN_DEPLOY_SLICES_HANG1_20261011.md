# KẾ HOẠCH SLICE HÀNG 1 — S1–S4 claim-ready (2026-10-11)

Hàng 1 = "chặn sử dụng" (WP-01..04). Dispatch được ngay sau khi claim, không chờ
Q2–Q11. Hàng 3 bị chặn bởi B-1; Hàng 2+4 chưa slice được — xem §4.
Số dòng file đo ở `main @ 662e2ef`.

## §1. Bảng slice (file rời nhau tuyệt đối)

| Slice | WP | File viết (dòng hiện tại) | Test | Branch dự kiến |
|:--|:--|:--|:--|:--|
| S1 | WP-01 async lock | `vnbroker/core/utils/async_client.py` (434L), `vnbroker/core/utils/__init__.py` (162L, chỉ `:57-60`) | mở rộng `tests/unit/core/test_async_client.py` | `feat/h1-async-lock` |
| S2 | WP-02 cache key | `vnbroker/core/utils/cache.py` (507L, chỉ `:87-101` + call site) | mở rộng `tests/unit/core/test_cache_key.py` | `feat/h1-cache-key` |
| S3 | WP-03 lỗi vĩnh viễn | `vnbroker/core/utils/client.py` (493L, `:411-435`), `vnbroker/core/source_router.py` (517L, `:463-487` + `:301`) — một slice vì thay đổi cùng taxonomy lỗi | mở rộng `tests/unit/core/test_source_router_fix.py` | `feat/h1-permanent-errors` |
| S4 | WP-04 rỗng vs lỗi | `vnbroker/explorer/kbs/listing.py` (688L), `vnbroker/explorer/kbs/trading.py` (256L), `vnbroker/explorer/vci/quote.py` (700L, chỉ `:277-278` + lân cận), `vnbroker/common/data.py` (1823L — **chỉ** `:482` + docstring `:631-633`, không tăng dòng ròng, xem §2) | test mới cho KBS rỗng (tên file coordinator chốt bằng `ls`) | `feat/h1-empty-vs-error` |

`common/data.py` chỉ S4 được viết; S1–S3 coi là read-only (L-P04, đã ghi ở §2).

## §2. Quyết định L-P03 đã chốt trong plan (agent không tự quyết)

1. **S4 + `common/data.py` (1823L, vượt ngân sách 800L):** không refactor, không tách
   file giữa slice. Chỉ sửa predicate rỗng + docstring đã nêu. Nhu cầu tách file
   ghi thành nợ riêng, không làm trong S4.
2. **S1 + class `TokenBucketRateLimiter` trùng tên** (CLAIMS đã hạ minor): ngoài
   phạm vi — không hợp nhất trong S1. S1 chỉ tách lock theo loop
   (`WeakKeyDictionary` theo running loop + fallback sync).
3. **S2 + key encoding adversarial** ([1] §7 mục 10): giữ nguyên, chỉ sửa nhánh
   fallback `None`. Không viết lại đơn giản hơn.
4. **S3 một slice hai file:** `client.py` (phân loại lỗi) và `source_router.py`
   (failover) cùng một taxonomy — tách ra là mâu thuẫn thiết kế kiểu L-P03.
5. **Không symbol public mới** ở Hàng 1 ⇒ không chạm barrel/`__init__` nào ngoài
   `core/utils/__init__.py` của S1; verify bằng
   `python -c "from vnbroker.core.utils import fetch_multiple_requests"`.

## §3. AC (đo, fail-before/pass-sau bằng code thật)

- **S1:** adapter batch source=VCI gọi **2 lần liên tiếp** ⇒ lần 2 không còn
  `bound to a different event loop` (Q1 đã chốt chuỗi gọi); `RATE_LIMITER` không
  còn là biến module-level; test hồi quy trong gate.
- **S2:** 2 instance `VCIListing` proxy khác nhau ⇒ 2 key khác nhau; `show_log`
  True/False ⇒ 2 key; không key nào sụp về tên lớn khi instance có credential.
- **S3:** 400/401/403/404/422 ⇒ `should_failover=False`, không cooldown; 429/500/
  timeout/DNS giữ `True`; 1 lệnh `history()` pool 5 chết ⇒ ≤5 request, lần sau
  trong cooldown ⇒ 0 request tới provider đang cooldown.
- **S4:** mô phỏng KBS 500 ⇒ ném, không cache, không `record_success`; ngày nghỉ
  (200, 0 dòng, có cột) ⇒ vẫn trả frame rỗng, không failover; hết log "thành
  công" sau nhánh lỗi.

## §4. Hàng 2–4: chưa slice được + template

Chưa slice vì vi phạm L-P03/L-P06 nếu làm ngay: vị trí đặt chưa đọc (đặc biệt
`broker/` tiền thật cần nạp broker-risk trước), số B-2/B-3 còn ƯỚC LƯỢNG, B-1
chưa đo. Template slice tương lai: `slice | WP | file viết (kèm dòng) |
test | branch | Lesson áp dụng | AC đo (lệnh tái lập) | nợ ghi nhận`.

## §5. Luật chạy slice (L-P01/P02/P05, L-E04/E06)

- Claim trước khi code, đường dẫn đầy đủ từ gốc repo; overlap exit 0 mới dispatch.
- Worktree đo baseline riêng; gate cần `.env`/mạng ghi **CHƯA CHẠY**, không ép khớp
  main tree. Gate đỏ chạy lại lần 2, báo cáo ghi cả hai lần.
- Gỡ junction `.venv` (`rmdir` không `/s`) trước khi xoá worktree; xác nhận `.venv` chính còn nguyên.
- Coordinator tự chạy lại gate + đọc vùng rủi ro + auditor read-only riêng;
  câu hỏi bắt buộc: *"lỗi nào không agent nào nhắc tới?"*

## MANDATORY CHECKLIST (tick trước khi coi Hàng 1 xong)

- [ ] S1–S4 đã claim, overlap exit 0, file rời nhau (L-P04)?
- [ ] Số trong báo cáo kèm nơi đo + commit; thiếu môi trường ⇒ CHƯA CHẠY (L-P01)?
- [ ] AC ĐỎ trước/XANH sau bằng code thật, không assert hình thức (L-E06)?
- [ ] Gate đỏ chạy lại lần 2, ghi cả hai lần; test mạng không phải gate phát hành (L-E04)?
- [ ] `common/data.py` không tăng dòng ròng; không symbol public mới thiếu export (L-P03/P04)?
- [ ] Mỗi slice có dòng `Lesson áp dụng` + số ƯỚC LƯỢNG đã thay bằng số đo (L-E01)?

*Lessons áp dụng: [L-P01, L-P02, L-P03, L-P04, L-P05, L-P06, L-E01, L-E04, L-E06]*
*FILES READ: docs/LESSONS/process.md, docs/LESSONS/evidence.md (kỳ trước) —
bỏ sót có chủ ý: broker-risk.md, gate-integrity.md (docs-only, không chạm
`broker/`; bắt buộc nạp lại trước mọi slice Hàng 3).*
