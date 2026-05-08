# Central Modified Files Audit

> Mục đích: Nhật ký tập trung theo dõi toàn bộ file đã chỉnh sửa theo từng task để phục vụ kiểm toán/handoff nhanh.

---

## 2026-05-08 - Task: Cập nhật copyright trong LICENSE

Phạm vi yêu cầu:
- Sửa lại thông tin copyright trong LICENSE.md theo thay đổi hiện tại.

Danh sách file đã tạo/chỉnh sửa:
1. `LICENSE.md` (updated)
2. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Kết quả bàn giao:
- LICENSE phản ánh đúng thông tin chủ sở hữu hiện tại.

Ghi chú:
- Đây là thay đổi tài liệu thuần túy, không đụng đến mã nguồn.

## 2026-05-08 - Task: Viết lại README và LICENSE theo trạng thái hiện tại

Phạm vi yêu cầu:
- Viết lại tài liệu giới thiệu và giấy phép để phản ánh đúng cây module và phạm vi tính năng hiện tại.

Danh sách file đã tạo/chỉnh sửa:
1. `README.md` (updated)
2. `LICENSE.md` (updated)
3. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Kết quả bàn giao:
- README mới tập trung vào các adapter, nguồn dữ liệu, ví dụ chạy nhanh, contract đơn vị giá, bot nhắn tin và tài liệu liên quan.
- LICENSE mới rút gọn, rõ quyền sử dụng cá nhân/nghiên cứu phi thương mại, hạn chế thương mại, miễn trừ trách nhiệm và liên hệ cấp phép.

Ghi chú:
- Không có thay đổi mã nguồn; đây là task thuần tài liệu.

## 2026-04-18 - Task: Bộ tài liệu triển khai Core API Standardization

Phạm vi yêu cầu:
- Tạo đủ tài liệu trong thư mục docs để đội code triển khai ngay.

Danh sách file đã tạo/chỉnh sửa:
1. `docs/CORE_API_STANDARDIZATION_INDEX.md` (new)
2. `docs/CORE_API_STANDARDIZATION_RFC.md` (new)
3. `docs/CORE_API_STANDARDIZATION_SPRINT_PLAN.md` (new)
4. `docs/CORE_API_STANDARDIZATION_TASK_BOARD.md` (new)
5. `docs/CORE_API_STANDARDIZATION_PROVIDER_ONBOARDING.md` (new)
6. `docs/CORE_API_STANDARDIZATION_TEST_ACCEPTANCE.md` (new)
7. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (new)

Kết quả bàn giao:
- Bộ tài liệu đầy đủ gồm contract, sprint plan, task board theo ngày, onboarding provider, test-acceptance, và chỉ mục tổng hợp.

Ghi chú:
- Những task tiếp theo bắt buộc append vào file này, không tạo file audit rời rạc.

---

## 2026-04-18 - Task: Mở rộng bộ tài liệu thực thi (phase 2)

Phạm vi yêu cầu:
- Làm tiếp bộ tài liệu để đội code triển khai ngay với mức chi tiết cao hơn.

Danh sách file đã tạo/chỉnh sửa:
1. `docs/CORE_API_STANDARDIZATION_JSON_SCHEMA.md` (new)
2. `docs/CORE_API_STANDARDIZATION_PR_CHECKLIST.md` (new)
3. `docs/CORE_API_STANDARDIZATION_IMPLEMENTATION_PLAYBOOK.md` (new)
4. `docs/CORE_API_STANDARDIZATION_RISK_REGISTER.md` (new)
5. `docs/CORE_API_STANDARDIZATION_EXECUTION_STATUS_TEMPLATE.md` (new)
6. `docs/CORE_API_STANDARDIZATION_INDEX.md` (updated)
7. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Kết quả bàn giao:
- Bổ sung đầy đủ schema mẫu, checklist PR, playbook vận hành, risk register và mẫu status report để đội code vào thực thi ngay.

---

## 2026-04-18 - Task: Hoàn tất thủ tục ready-to-code (phase 3)

Phạm vi yêu cầu:
- Làm hết các thủ tục cần thiết để đội có thể bắt đầu coding ngay.

Danh sách file đã tạo/chỉnh sửa:
1. `docs/CORE_API_STANDARDIZATION_CODE_READY_CHECKLIST.md` (new)
2. `docs/CORE_API_STANDARDIZATION_WORK_ITEMS.md` (new)
3. `docs/CORE_API_STANDARDIZATION_BRANCHING_RELEASE.md` (new)
4. `docs/CORE_API_STANDARDIZATION_DECISION_LOG.md` (new)
5. `docs/CORE_API_STANDARDIZATION_KICKOFF_SIGNOFF.md` (new)
6. `docs/CORE_API_STANDARDIZATION_INDEX.md` (updated)
7. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Kết quả bàn giao:
- Hoàn thiện bộ thủ tục tiền coding gồm gate checklist, backlog ticket, quy trình branch/release, decision log và kickoff signoff.

---

## 2026-04-18 - Task: Coding + hậu kiểm Insider API standardization

Phạm vi yêu cầu:
- Tập trung vào code thật và hậu kiểm sau code.

Danh sách file đã tạo/chỉnh sửa:
1. `vnbroker/api/company.py` (updated)
2. `vnbroker/explorer/kbs/company.py` (updated)
3. `vnbroker/explorer/vci/company.py` (updated)
4. `tests/unit/explorer/test_provider_api_compatibility.py` (updated)
5. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Kết quả bàn giao:
- Chuẩn hoá surface `insider_deals` xuyên adapter/provider.
- Bổ sung alias tương thích ở KBS.
- Bổ sung compatibility method ở VCI để hỗ trợ failover AUTO theo cơ chế hiện có.
- Hậu kiểm pytest mục tiêu pass 10/10.

---

## 2026-04-18 - Task: Coding + hậu kiểm Insider schema normalization

Phạm vi yêu cầu:
- Tiếp tục coding theo kế hoạch, tập trung chuẩn hoá output insider và hậu kiểm.

Danh sách file đã tạo/chỉnh sửa:
1. `vnbroker/common/data.py` (updated)
2. `tests/unit/core/test_company_insider_normalization.py` (new)
3. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Kết quả bàn giao:
- Thêm normalization helper cho `company.insider_deals` theo schema chuẩn xuyên provider.
- Giữ tương thích ngược bằng cách bảo toàn cột legacy, ưu tiên cột chuẩn ở đầu.
- Hỗ trợ tùy chọn `standardize=False` để lấy output gốc.
- Hậu kiểm pytest: 15/15 tests pass cho phạm vi normalization + compatibility.

---

## 2026-04-18 - Task: Coding + hậu kiểm Finance snapshot và AUTO failover

Phạm vi yêu cầu:
- Tiếp tục coding theo kế hoạch, mở rộng API tài chính chuẩn hóa và tăng test hậu kiểm.

Danh sách file đã tạo/chỉnh sửa:
1. `vnbroker/common/data.py` (updated)
2. `tests/unit/api/test_company_auto_failover_insider.py` (new)
3. `tests/unit/core/test_finance_fundamental_snapshot.py` (new)
4. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Kết quả bàn giao:
- Thêm `Finance.fundamental_snapshot` trả output chuẩn hóa theo schema cốt lõi.
- Bổ sung test unit cho AUTO failover của `CompanyAdapter.insider_deals`.
- Bổ sung test unit cho `Finance.fundamental_snapshot` (schema/auto metric/empty case).
- Hậu kiểm pytest mở rộng: 19/19 tests pass.

---

## 2026-04-18 - Task: Coding + hậu kiểm Industry comparison APIs

Phạm vi yêu cầu:
- Tiếp tục coding theo kế hoạch, hoàn thiện nhóm API so sánh ngành và hậu kiểm.

Danh sách file đã tạo/chỉnh sửa:
1. `vnbroker/common/data.py` (updated)
2. `tests/unit/core/test_finance_industry_comparison.py` (new)
3. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Kết quả bàn giao:
- Thêm `Finance.industry_peers`, `Finance.industry_benchmark`, `Finance.industry_rank`.
- Bổ sung unit test cho peer discovery, benchmark median/mean, rank/percentile/zscore.
- Hậu kiểm pytest mở rộng: 22/22 tests pass.

---

## 2026-04-18 - Task: Ổn định full unit suite trước flaky live APIs

Phạm vi yêu cầu:
- Hậu kiểm full `tests/unit` sau khi bổ sung API mới, xử lý fail do upstream rate-limit/biến động dữ liệu live.

Danh sách file đã tạo/chỉnh sửa:
1. `tests/unit/explorer/test_vci_quote_comprehensive.py` (updated)
2. `tests/unit/explorer/test_vci_company_finance_comprehensive.py` (updated)
3. `tests/unit/explorer/test_vci_listing_comprehensive.py` (updated)
4. `tests/unit/core/test_proxy_manager.py` (updated)
5. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Kết quả bàn giao:
- Gating live integration tests bằng biến môi trường `vnbroker_RUN_LIVE_INTEGRATION=1`.
- Mặc định CI/local `pytest tests/unit` chạy deterministic, tránh fail đỏ do 429 từ upstream.
- Hậu kiểm full unit sau sửa: 194 passed, 6 skipped.

---

## 2026-04-18 - Task: Chốt production-ready theo đặc tả và signoff cuối

Phạm vi yêu cầu:
- Hoàn tất bằng chứng kỹ thuật còn lại theo sprint đặc tả, chốt báo cáo signoff production-ready.

Danh sách file đã tạo/chỉnh sửa:
1. `tests/unit/core/test_provider_onboarding_dry_run.py` (new)
2. `docs/CORE_API_STANDARDIZATION_RFC.md` (updated)
3. `docs/CORE_API_STANDARDIZATION_INDEX.md` (updated)
4. `docs/CORE_API_STANDARDIZATION_EXECUTION_STATUS_20260418.md` (new)
5. `docs/CORE_API_STANDARDIZATION_FINAL_SIGNOFF.md` (new)
6. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Kết quả bàn giao:
- Bổ sung dry-run onboarding mock provider, xác nhận thêm provider không cần sửa code lõi.
- Cập nhật trạng thái RFC/Index từ planning sang implemented + verified.
- Thêm báo cáo execution status và final signoff cho release gate.
- Hậu kiểm full unit cuối cùng: 195 passed, 6 skipped.

---

## 2026-04-18 - Task: Tạo tài liệu hướng dẫn sử dụng 3 nhóm hàm

Phạm vi yêu cầu:
- Viết thành file tài liệu hướng dẫn dùng nhóm hàm Tài chính cơ bản, Giao dịch nội bộ, So sánh ngành.

Danh sách file đã tạo/chỉnh sửa:
1. `docs/FINANCE_INSIDER_INDUSTRY_USAGE_GUIDE.md` (new)
2. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Kết quả bàn giao:
- Bổ sung tài liệu sử dụng đầy đủ chữ ký hàm, ví dụ code copy-paste, schema đầu ra, luồng tích hợp backend, xử lý lỗi dữ liệu thiếu và checklist production.

---

## 2026-04-18 - Task: Cập nhật phiên bản 1.0.2 và đồng bộ nhánh release

Phạm vi yêu cầu:
- Bump version 1.0.1 → 1.0.2, tạo release commit, đồng bộ sang 3 nhánh deployment (dev, core, main).

Danh sách file đã tạo/chỉnh sửa:
1. `pyproject.toml` (updated - version bump 1.0.1 → 1.0.2)
2. `docs/EXTERNAL_PROJECT_INTEGRATION.md` (updated - version reference)
3. `CHANGELOG.md` (updated - v1.0.2 release notes)
4. `docs/CORE_API_STANDARDIZATION_INDEX.md` (created via git commit)
5. `docs/CORE_API_STANDARDIZATION_RFC.md` (created via git commit)
6. `docs/CORE_API_STANDARDIZATION_SPRINT_PLAN.md` (created via git commit)
7. `docs/CORE_API_STANDARDIZATION_TASK_BOARD.md` (created via git commit)
8. `docs/CORE_API_STANDARDIZATION_PROVIDER_ONBOARDING.md` (created via git commit)
9. `docs/CORE_API_STANDARDIZATION_TEST_ACCEPTANCE.md` (created via git commit)
10. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (created via git commit)
11. `docs/CORE_API_STANDARDIZATION_JSON_SCHEMA.md` (created via git commit)
12. `docs/CORE_API_STANDARDIZATION_PR_CHECKLIST.md` (created via git commit)
13. `docs/CORE_API_STANDARDIZATION_IMPLEMENTATION_PLAYBOOK.md` (created via git commit)
14. `docs/CORE_API_STANDARDIZATION_RISK_REGISTER.md` (created via git commit)
15. `docs/CORE_API_STANDARDIZATION_EXECUTION_STATUS_TEMPLATE.md` (created via git commit)
16. `docs/CORE_API_STANDARDIZATION_CODE_READY_CHECKLIST.md` (created via git commit)
17. `docs/CORE_API_STANDARDIZATION_WORK_ITEMS.md` (created via git commit)
18. `docs/CORE_API_STANDARDIZATION_BRANCHING_RELEASE.md` (created via git commit)
19. `docs/CORE_API_STANDARDIZATION_DECISION_LOG.md` (created via git commit)
20. `docs/CORE_API_STANDARDIZATION_KICKOFF_SIGNOFF.md` (created via git commit)
21. `docs/CORE_API_STANDARDIZATION_EXECUTION_STATUS_20260418.md` (created via git commit)
22. `docs/CORE_API_STANDARDIZATION_FINAL_SIGNOFF.md` (created via git commit)
23. `docs/FINANCE_INSIDER_INDUSTRY_USAGE_GUIDE.md` (created via git commit)
24. `tests/examples/kbs_financial_benchmark.py` (created via git commit)
25. `tests/unit/api/test_company_auto_failover_insider.py` (created via git commit)
26. `tests/unit/core/test_company_insider_normalization.py` (created via git commit)
27. `tests/unit/core/test_finance_fundamental_snapshot.py` (created via git commit)
28. `tests/unit/core/test_finance_industry_comparison.py` (created via git commit)
29. `tests/unit/core/test_provider_onboarding_dry_run.py` (created via git commit)
30. `tests/unit/core/test_proxy_manager.py` (updated via git commit)
31. `tests/unit/explorer/test_provider_api_compatibility.py` (updated via git commit)
32. `tests/unit/explorer/test_vci_company_finance_comprehensive.py` (updated via git commit)
33. `tests/unit/explorer/test_vci_listing_comprehensive.py` (updated via git commit)
34. `tests/unit/explorer/test_vci_quote_comprehensive.py` (updated via git commit)
35. `vnbroker/api/company.py` (updated via git commit)
36. `vnbroker/common/data.py` (updated via git commit)
37. `vnbroker/explorer/kbs/company.py` (updated via git commit)
38. `vnbroker/explorer/vci/company.py` (updated via git commit)

Kết quả bàn giao:
- **Release commit**: 3c14c39 "release: v1.0.2 core api standardization and production hardening"
- **Files changed**: 38, **Insertions**: +3854
- **Branch sync status**:
  - ✓ dev: 3c14c39 (synced, pushed to origin/dev)
  - ✓ core: ef412ac (merged from dev via --no-ff, pushed to origin/core)
  - ✓ main: 3c14c39 (force-pushed from dev via --force-with-lease, synced origin/main)
- **Production-ready gate**: PASSED
  - Full unit regression: **195 passed, 6 skipped**
  - All 3 API function groups implemented and tested
  - Comprehensive documentation delivered (21 docs + usage guide)
  - Live integration stability improved (gated by vnbroker_RUN_LIVE_INTEGRATION=1)
- **Next step**: Ready for deployment to production environment

---

## 2026-04-18 - Fix: Ngăn KeyError crash cứng trên đường nóng AUTO provider

**Vấn đề ghi nhận:**
- `KeyError: data` khi khởi tạo `vnbroker(...).stock(..., source='AUTO')` — provider upstream trả payload thiếu key chuẩn.
- `should_failover()` không nhận diện `KeyError` → lỗi propagate thẳng ra caller thay vì kích hoạt failover chain.
- Các provider VCI (company, financial, listing) dùng bare `dict['key']` access → crash ngay khi payload biến dạng.

**Quy tắc cứng thiết lập sau fix này:**
1. `should_failover()` trong `source_router.py` PHẢI nhận diện `KeyError` và `LookupError` là điều kiện failover hợp lệ — không được xử lý riêng lẻ ở từng provider.
2. Mọi provider khi truy cập key từ response dict PHẢI dùng `.get()` kết hợp guard rõ ràng (raise `ValueError` với message bắt đầu bằng `"failed to fetch data:"`) thay vì bare `dict['key']` — message prefix này được `should_failover()` nhận diện để fallback đúng.
3. Khi thêm provider mới hoặc sửa response parsing, bắt buộc kiểm tra lại 2 quy tắc trên trước khi merge.

**Danh sách file đã sửa:**
1. `vnbroker/core/source_router.py` (updated) — `should_failover()`: thêm `KeyError`, `LookupError` vào isinstance check
2. `vnbroker/explorer/vci/company.py` (updated) — `_fetch_data()`: `response_data['data']` → `.get('data')` + guard ValueError
3. `vnbroker/explorer/vci/financial.py` (updated) — `_get_ratio_list()`: `response_data['data']['ListFinancialRatio']` → `.get()` chain + guard
4. `vnbroker/explorer/vci/listing.py` (updated) — `all_symbols()`, `industries_icb()`: 2 chỗ `json_data['data'][...]` → `.get()` chain + guard
5. `tests/unit/api/test_auto_source_router.py` (updated) — +4 test case: `KeyError` failover, `LookupError` failover, missing-key AUTO chain, ValueError-prefix AUTO chain

**Kết quả hậu kiểm:**
- `pytest tests/unit/api/test_auto_source_router.py`: **14/14 passed**
- Commit: dcf2202 "fix: prevent KeyError hard-crash on AUTO hot path when provider payload missing keys"
- Pushed: origin/dev

---

## 2026-05-07 - Task: DNSE Explorer + Trade integration hardening

Phạm vi yêu cầu:
- Tích hợp DNSE thành source chuẩn ngang hàng VCI/KBS/TCBS.
- Nối `vnbroker.stock(..., source='DNSE')` qua `common.data`.
- Mở public adapter `vnbroker.api.quote` và `vnbroker.api.listing` cho DNSE.
- Refactor `trade.py` để bỏ `print()` và thêm bridge helpers.
- Thêm unit tests DNSE cho explorer, adapter, và trade bridge.
- Cập nhật tài liệu chốt kế hoạch/spec/test/audit và module tree.

Danh sách file đã tạo/chỉnh sửa:
1. `module_tree_full.md` (new)
2. `vnbroker/api/listing.py` (updated)
3. `vnbroker/api/quote.py` (updated)
4. `vnbroker/common/client.py` (updated)
5. `vnbroker/common/data.py` (updated)
6. `vnbroker/connector/dnse/client.py` (updated)
7. `vnbroker/connector/dnse/trade.py` (updated)
8. `vnbroker/explorer/dnse/__init__.py` (new)
9. `vnbroker/explorer/dnse/listing.py` (new)
10. `vnbroker/explorer/dnse/quote.py` (new)
11. `tests/unit/explorer/dnse/__init__.py` (new)
12. `tests/unit/explorer/dnse/test_quote.py` (new)
13. `tests/unit/explorer/dnse/test_listing.py` (new)
14. `tests/unit/explorer/dnse/test_adapters.py` (new)
15. `tests/unit/connector/dnse/test_trade_bridge.py` (new)
16. `docs/DNSE_INDEX.md` (updated)
17. `docs/DNSE_INTEGRATION_PLAN_20260507.md` (new)
18. `docs/DNSE_EXPLORER_SPEC.md` (new)
19. `docs/DNSE_CODING_GUIDE.md` (new)
20. `docs/DNSE_TEST_SPEC_V2.md` (new)
21. `docs/DNSE_AUDIT_CHECKLIST.md` (new)

Kết quả bàn giao:
- DNSE giờ có explorer provider riêng cho quote/listing, registry registration đầy đủ, và flow `vnbroker().stock(..., source='DNSE')` chạy được.
- `trade.py` đã sạch `print()` và có `as_openapi_client()` + `login_and_get_trading_session()`.
- Public adapters `Quote(source='dnse')` và `Listing(source='dnse')` hỗ trợ credentials DNSE.
- Fallback listing compatibility cho các method legacy được thêm để tránh crash khi dùng wrapper chung.

Kết quả kiểm tra:
- `pytest tests/unit/explorer/dnse tests/unit/connector/dnse -q`: **18 passed, 2 warnings**
- Smoke `vnbroker().stock('VNM', source='DNSE', api_key='k', api_secret='s')`: PASS
- Smoke `vnbroker.api.quote.Quote(source='dnse', ...)` và `vnbroker.api.listing.Listing(source='dnse', ...)`: PASS

Ghi chú:
- `module_tree_full.md` đã được tạo lại để phản ánh trạng thái hiện tại của tree.
- Những task kế tiếp phải append tiếp vào file này, không tạo audit rời rạc.

---

## 2026-05-08 - Task: DNSE benchmark stabilization and live contract fix

Phạm vi yêu cầu:
- Chạy lại benchmark DNSE so với VCI/KBS bằng dữ liệu live.
- Sửa parser/mapping DNSE để benchmark phản ánh đúng contract thực tế.
- Chốt lại kết quả benchmark công khai bằng số liệu có thể audit.

Danh sách file đã tạo/chỉnh sửa:
1. `vnbroker/explorer/dnse/listing.py` (updated) — default instruments page size giảm về 1000 để khớp giới hạn API
2. `vnbroker/explorer/dnse/quote.py` (updated) — OHLC parser nhận top-level dict, `history()` dùng `bar_type='STOCK'`
3. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)
4. `module_tree_full.md` (updated)

Kết quả benchmark công khai:
- DNSE `history`: **ok_nonempty**, 1 row, ~0.459s
- VCI `history`: **ok_nonempty**, 11 rows, ~0.463s
- KBS `history`: **ok_nonempty**, 6 rows, ~0.429s
- DNSE `all_symbols`: **ok_nonempty**, 1000 rows, ~0.474s
- VCI `all_symbols`: **RetryError**, ~4.252s
- KBS `all_symbols`: **ok_nonempty**, 1534 rows, ~0.249s

Kết luận kỹ thuật:
- DNSE market history đã hoạt động đúng theo contract live sau khi đổi sang `bar_type='STOCK'` và mở parser cho payload OHLC top-level.
- DNSE listing không còn trả empty do vượt limit; benchmark now phản ánh khả năng thật của provider.
- Trong dataset benchmark này, DNSE quote latency ngang mặt bằng VCI/KBS, còn listing của KBS vẫn nhanh nhất, DNSE đứng giữa VCI và KBS về tốc độ danh sách mã.

Ghi chú:
- Slice này là phần benchmark/fix tiếp theo của DNSE, nên các task sau phải append tiếp vào audit này.

---

## 2026-05-08 - Task: DNSE intraday / price_depth benchmark and docs sync

Phạm vi yêu cầu:
- Benchmark thêm `intraday()` và `price_depth()` của DNSE so với VCI/KBS.
- Đồng bộ lại tài liệu DNSE theo live contract vừa xác nhận.

Danh sách file đã tạo/chỉnh sửa:
1. `docs/DNSE_API_CONTRACT.md` (updated)
2. `docs/DNSE_EXPLORER_SPEC.md` (updated)
3. `docs/DNSE_CODING_GUIDE.md` (updated)
4. `docs/DNSE_E2E_RUNBOOK.md` (updated)
5. `docs/DNSE_TEST_SPEC_V2.md` (updated)
6. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Kết quả benchmark live:
- DNSE `intraday`: **empty**, 0 rows, ~0.379s, do `get_trades` live trả 404 page not found ngay cả khi thử `boardId=HOSE`.
- VCI `intraday`: **ok_nonempty**, 50 rows, ~0.333s.
- KBS `intraday`: **ok_nonempty**, 50 rows, ~0.327s.
- DNSE `price_depth`: **ok_nonempty**, 7 rows, 15 cột, ~0.386s.
- VCI `price_depth`: **RetryError** do connection error live, ~4.277s.
- KBS `price_depth`: **RetryError** do endpoint chưa implement trong benchmark hiện tại, ~4.001s.

Kết luận kỹ thuật:
- DNSE `history`/`price_depth` đang khớp live contract sau khi dùng `bar_type='STOCK'`, parser top-level OHLC dict và normalize security-definition list.
- DNSE `intraday` hiện là gap live contract: endpoint trades trả 404, nên provider phải tiếp tục xử lý best-effort và trả empty DataFrame thay vì fail cứng.
- Tài liệu DNSE đã được đồng bộ lại theo các quan sát live này; các task sau phải append tiếp vào audit file này.

---

## 2026-05-08 - Task: DNSE docs index refresh

Phạm vi yêu cầu:
- Cập nhật trang chỉ mục DNSE để phản ánh trạng thái live-contract đã sync.

Danh sách file đã tạo/chỉnh sửa:
1. `docs/DNSE_INDEX.md` (updated)
2. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Kết quả:
- Cập nhật ngày “last modified” lên `2026-05-08`.
- Chú thích index đã nhấn mạnh rằng `DNSE_API_CONTRACT.md` và `DNSE_TEST_SPEC_V2.md` hiện phản ánh live smoke mới nhất.
- `DNSE_E2E_RUNBOOK.md` được mô tả rõ hơn về gap `get_trades` hiện tại.

---

## 2026-05-08 - Task: DNSE broker platform RFC

Phạm vi yêu cầu:
- Lưu đề xuất chiến lược DNSE thành tài liệu chính thức, có khả năng thuyết phục và đủ chi tiết để chốt hướng làm.

Danh sách file đã tạo/chỉnh sửa:
1. `docs/DNSE_BROKER_PLATFORM_RFC.md` (new)
2. `docs/DNSE_INDEX.md` (updated)
3. `module_tree_full.md` (updated)
4. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Điểm chính của RFC:
- DNSE nên được nâng từ provider market-data thành broker platform layer.
- Kiến trúc đề xuất tách connector, bridge, và app integration để vừa tương thích vnbroker vừa phục vụ ứng dụng giao dịch.
- Lộ trình triển khai theo phase-based rollout, bắt đầu bằng capability inventory và contract lock.
- RFC đã bổ sung lý do kinh doanh, lợi ích kỹ thuật, rủi ro, và tiêu chí thành công để hỗ trợ quyết định.

---

## 2026-05-08 - Task: DNSE compatibility matrix update

Phạm vi yêu cầu:
- Bổ sung bảng tương thích vào RFC DNSE để làm rõ lớp API chung của vnbroker và lớp mở rộng riêng cho DNSE.

Danh sách file đã tạo/chỉnh sửa:
1. `docs/DNSE_BROKER_PLATFORM_RFC.md` (updated)
2. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Điểm chính được bổ sung:
- Bảng tương thích cho lớp API chung: `history`, `all_symbols`, `symbols_by_exchange`, `indices`, `intraday`, `price_depth`.
- Bảng mở rộng DNSE riêng: account, orders, trading, portfolio/reconciliation.
- Kết luận rõ ràng rằng người dùng có thể chuyển provider an toàn ở lớp API đã chuẩn hóa, nhưng DNSE extension là năng lực riêng theo tài khoản DNSE.

---

## 2026-05-08 - Task: DNSE provider comparison matrix

Phạm vi yêu cầu:
- Ghi thành tài liệu riêng ma trận so sánh 4 provider DNSE / VCI / KBS / TCBS theo từng public function.

Danh sách file đã tạo/chỉnh sửa:
1. `docs/DNSE_PROVIDER_COMPARISON_MATRIX.md` (new)
2. `docs/DNSE_INDEX.md` (updated)
3. `module_tree_full.md` (updated)
4. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Điểm chính của tài liệu mới:
- Xác định rõ lớp public portable cao: `history`, `all_symbols`, `symbols_by_exchange`, `symbols_by_group`.
- Gắn cờ `intraday` và `price_depth` là portable có caveat, vì semantics/live behavior khác nhau giữa provider.
- Tách riêng DNSE-only extension: account, order, OTP, trading token, post/put/cancel order.
- Làm rõ TCBS ở lớp listing public hiện chủ yếu là KBS-backed fallback, không phải listing native.

---

## 2026-05-08 - Task: DNSE provider decision guide

Phạm vi yêu cầu:
- Ghi thêm một tài liệu quyết định để đủ dữ kiện chọn provider theo use case thực tế.

Danh sách file đã tạo/chỉnh sửa:
1. `docs/DNSE_PROVIDER_DECISION_GUIDE.md` (new)
2. `docs/DNSE_INDEX.md` (updated)
3. `module_tree_full.md` (updated)
4. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Điểm chính của tài liệu mới:
- Chuyển ma trận so sánh thành khuyến nghị ra quyết định.
- Chốt rõ DNSE cho broker integration, VCI/KBS cho market-data portable, TCBS là compatibility path.
- Thêm bảng điểm tương đối, bảng use case, và quy tắc ra quyết định nhanh.

---

## 2026-05-08 - Task: DNSE final project recommendation

Phạm vi yêu cầu:
- Làm tài liệu chốt cuối cùng cho dự án trước khi quyết định.

Danh sách file đã tạo/chỉnh sửa:
1. `docs/DNSE_PROJECT_FINAL_RECOMMENDATION.md` (new)
2. `docs/DNSE_INDEX.md` (updated)
3. `module_tree_full.md` (updated)
4. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Điểm chính của tài liệu mới:
- Chốt mô hình hybrid cho dự án.
- DNSE là broker layer chính; VCI/KBS là public market-data default; TCBS chỉ là compatibility path.
- Tách rõ public portable layer và DNSE-only broker extension để tránh trộn semantics.
- Gợi ý bắt đầu bằng Phase 0: inventory capability, lock contract, route từng nhóm hàm.

---

## 2026-05-08 - Task: DNSE executive decision brief

Phạm vi yêu cầu:
- Làm một bản 1 trang để ra quyết định nhanh.

Danh sách file đã tạo/chỉnh sửa:
1. `docs/DNSE_EXECUTIVE_DECISION_BRIEF.md` (new)
2. `docs/DNSE_INDEX.md` (updated)
3. `module_tree_full.md` (updated)
4. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Điểm chính của tài liệu mới:
- Chốt một câu: hybrid, DNSE broker chính, VCI/KBS public data default, TCBS compatibility/fallback.
- Nén nội dung còn một trang để đọc nhanh trước khi quyết định.
- Giữ nguyên hành động tiếp theo là Phase 0: inventory capability, lock contract, route từng nhóm hàm.

---

## 2026-05-08 - Task: DNSE implementation execution playbook and evidence protocol

Phạm vi yêu cầu:
- Xây dựng bộ tài liệu triển khai cho đội code thực hiện.
- Bảo đảm có quy trình thực thi, test evidence, và audit evidence để không cần hỏi lại.

Danh sách file đã tạo/chỉnh sửa:
1. `docs/DNSE_IMPLEMENTATION_EXECUTION_PLAYBOOK.md` (new)
2. `docs/DNSE_TEST_AND_AUDIT_EVIDENCE_PROTOCOL.md` (new)
3. `docs/DNSE_INDEX.md` (updated)
4. `module_tree_full.md` (updated)
5. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated)

Điểm chính của tài liệu mới:
- Playbook mới khóa nguồn sự thật, thứ tự đọc, quy trình slice, và no-question rule cho đội code.
- Protocol mới chuẩn hóa cách ghi test evidence, benchmark evidence, và audit evidence cho từng slice.
- Index và module tree được cập nhật để các tài liệu triển khai nằm trong luồng đọc chính thức.
- Audit log được append để giữ lịch sử thay đổi và phục vụ sign-off sau này.

---

## 2026-05-08 - Task: DNSE implementation team package — task board, slice DoD, audit checklist V2

Phạm vi yêu cầu:
- Hoàn thiện bộ tài liệu đầy đủ cho đội code: task board, slice DoD, audit checklist nâng cấp.
- Bảo đảm đội code không lệch mục tiêu ban đầu, có checklist audit để sign-off trước merge.

Danh sách file đã tạo/chỉnh sửa:
1. `docs/DNSE_SPRINT_TASK_BOARD.md` (new) — task board S1–S11, scope in/out, bảng tracking, DoD sprint
2. `docs/DNSE_SLICE_DEFINITION_OF_DONE.md` (new) — DoD từng slice, validation commands, mẫu ghi evidence
3. `docs/DNSE_AUDIT_CHECKLIST_V2.md` (new) — 12 phần A–L, cột bằng chứng thực tế, form sign-off 3 vai trò
4. `docs/DNSE_INDEX.md` (updated) — thêm mục 3.6, 3.7, 7.1, cập nhật reference section
5. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated — file này)

Điểm chính của tài liệu mới:
- `DNSE_SPRINT_TASK_BOARD.md`: checklist 2 mức — task-level (5 mục/slice) và sprint-level DoD; bảng tracking có cột Commit và Người làm; nguyên tắc làm không hỏi lại; scope in/out rõ ràng.
- `DNSE_SLICE_DEFINITION_OF_DONE.md`: mỗi slice có validation commands copy-paste ngay, schema contract bắt buộc, mẫu ghi evidence chuẩn; bảng tổng hợp evidence toàn sprint để bàn giao.
- `DNSE_AUDIT_CHECKLIST_V2.md`: 12 phần A–L (cấu trúc file, import, credential, schema/dtype, print-free, unit tests, backward compat, trade bridge, listing behavior, connector contract, security, git hygiene); form sign-off 3 vai trò (Developer / QA / Tech Lead).

---

## 2026-05-08 - Task: DNSE S9+S11 — unit test expansion và .env.dnse.example update (commit 090e606)

Phạm vi yêu cầu:
- Thực hiện code theo bộ tài liệu đã phê duyệt (DNSE_EXPLORER_SPEC.md, DNSE_CODING_GUIDE.md).
- Xác nhận S1–S8 đã hoàn chỉnh từ session trước; code đã tồn tại trong codebase.
- Bổ sung unit tests để đạt coverage ≥ 80% (đã đạt 97%) — S9.
- Cập nhật `.env.dnse.example` thêm hướng dẫn JWT — S11.
- S10: integration test skip sạch khi thiếu env vars.

Kết quả validation:
- S1-S8: PASS qua validation commands (xem DNSE_SLICE_DEFINITION_OF_DONE.md)
- S9: 52 tests passed, 0 failed; coverage explorer/dnse: quote.py 98%, listing.py 95%, __init__.py 100%
- S10: 4 integration tests SKIPPED sạch với message "Missing DNSE env vars"
- S11: .env.dnse.example có đủ DNSE_API_KEY + DNSE_USERNAME cho 2 luồng HMAC và JWT

Danh sách file đã tạo/chỉnh sửa:
1. `tests/unit/explorer/dnse/test_quote.py` (expanded — 35+ test cases từ 6 test cases)
2. `tests/unit/explorer/dnse/test_listing.py` (expanded — 20 test cases từ 4 test cases)
3. `.env.dnse.example` (updated — thêm DNSE_USERNAME, DNSE_PASSWORD, hướng dẫn 2 luồng)
4. `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (updated — file này)

