# TEST_REPORT — HANG1 Row 1 (S1–S4), branch `feat/hang1-row1`

Base đo: `main @ 662e2ef`. Mỗi hàng = một gate: tên và verdict cùng một dòng
(hazard 20). Lệnh tái lập đầy đủ; xem SUMMARY từng slice cho fail-before.

- `pytest tests/` (toàn bộ, không chỉ subfolder): **Pass** — 2071 passed, 26 skipped, 0 failed, 185s. Lệnh: `.venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider --basetemp=<tmp>` (basetemp vì thư mục Temp mặc định của máy báo PermissionError — flake hạ tầng, không liên quan code; xem REPORT_FINAL).
- `ruff check vnbroker scripts tests/unit tests/contract` (scope của check_all): **Pass** — clean.
- `ruff check tests` (toàn bộ): **KNOWN-RED** — đúng 13 lỗi có sẵn ở `tests/acceptance`, `tests/examples`, `tests/test_acb_all_providers.py`; không lỗi nào ở file của Hàng 1 (khớp baseline CLAUDE.md, không sửa — ngoài scope).
- `scripts/check_lessons.py`: **Pass** — exit 0 (24/40 lesson, 5 file sạch).
- `scripts/check_lessons.py --self-test`: **Pass** — 9 case.
- `scripts/verify_tcbs_coverage.py`: **Pass** — exit 0 (1 path chưa nối đã biết).
- `scripts/check_tcbs_bodies.py --baseline docs/tcbs_body_baseline.json`: **Pass** — 12 payload, 0 lệch mới.
- `scripts/check_tcbs_bodies.py --self-test`: **Pass** — 10 case.
- `scripts/check_provider_consistency.py`: **Pass** — exit 0.
- `scripts/check_provider_consistency.py --self-test`: **Pass** — exit 0 (có warning khôi phục env, không phải lỗi).
- `scripts/check_version_sync.py`: **Pass** — 3.7.0 khớp.
- `scripts/check_mypy_baseline.py` (gate type-check thật của repo): **Pass** — no new strict errors (baseline 1266, nay 1138). `mypy --strict` thô vẫn đỏ như baseline — KNOWN-RED, không phải gate.
- File-size ≤ 800L cho mọi file chạm: **Pass** — lớn nhất là test_cache_key 786L.
- Live integration (`vnbroker_RUN_LIVE_INTEGRATION=1`, cần credential/mạng): **CHƯA CHẠY**.
- CI GitHub Actions: **CHƯA CHẠY** (billing, đã ghi trong repo).
- Fail-before từng slice: **Pass** — S1 RuntimeError đúng chuỗi production; S2 key byte-identical + decorator cache oan; S3 probe trên code HEAD (ConnectionError + failover True + order đầy khi all-cooling); S4 10/12 DID NOT RAISE.
