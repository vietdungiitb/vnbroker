# CLAIMS — WP-CLEANUP-01

<!-- Mỗi agent ghi MỘT hàng TRƯỚC khi code. Script check-overlap.cjs chỉ so các
     hàng có status = in-progress. File set của các agent phải RỜI NHAU TUYỆT ĐỐI
     vì `worktree` chưa bật (mọi agent dùng chung working directory).

     Đường dẫn ghi ĐẦY ĐỦ từ gốc repo — tên trần (vd `LESSONS.md`) không kiểm
     chứng được và làm cổng đối chiếu hai chiều báo sai. -->

| agent | branch | files | status | since |
|---|---|---|---|---|
| agent-gate-core | dev | docs/_workflow/gate-01-plan-approved.sh, docs/_workflow/gate-02-plan-verified.sh, docs/_workflow/gate-03-claims-check.sh, docs/_workflow/gate-06-report-final.sh, docs/_workflow/README.md | done | 2026-10-07T21:10 |
| agent-gate-verify | dev | docs/_workflow/gate-04-audit-pass.sh, docs/_workflow/gate-05-test-pass.sh, docs/_workflow/gate-07-close.sh, docs/_workflow/gate-08-retro.sh, docs/_workflow/gate-07-close.md, docs/_workflow/gate-08-retro.md, docs/_workflow/gates.json | done | 2026-10-07T21:10 |
| agent-repo-hygiene | dev | .gitignore | done | 2026-10-07T21:10 |
| agent-doc-env | dev | .env.example, .env.dnse.example, README.md | done | 2026-10-07T21:10 |
| agent-doc-refs | dev | docs/SSI_EXPLORER_IMPLEMENTATION_PLAN.md, docs/VNBROKER_IMPROVEMENT_PLAN.md, docs/_workflow/LESSONS.md, docs/_workflow/HOOK_CONFIG.template.md, docs/_workflow/VERIFICATION.md | done | 2026-10-07T21:10 |
| agent-connpool | feat/tier1-connpool | vnbroker/core/utils/client.py,vnbroker/core/utils/connection_pool.py,tests/unit/core/test_connection_pool.py | done | 2026-10-08T09:10:00Z |
| agent-failover | feat/tier1-failover | vnbroker/common/data.py,vnbroker/core/utils/normalizer.py,tests/contract/test_failover_integration.py,tests/unit/common/test_bulk_normalizer.py | done | 2026-10-08T09:10:00Z |
| agent-bulkrouter | feat/tier1-bulkrouter | vnbroker/core/bulk_router.py,vnbroker/core/health_router.py,tests/unit/core/test_bulk_router.py | done | 2026-10-08T09:10:00Z |
| agent-providerpool | feat/tier1-providerpool | vnbroker/core/provider_pool.py,tests/unit/core/test_provider_pool.py | done | 2026-10-08T09:10:00Z |
| agent-api | feat/tier1-api | vnbroker/ui/market.py,vnbroker/api/bulk.py,tests/unit/api/test_bulk_api.py | done | 2026-10-08T09:25:00Z |
| agent-cache | feat/fix-cache | vnbroker/core/utils/cache.py,tests/unit/core/test_cache_key.py | done | 2026-10-08T11:00:00Z |
| agent-router | feat/fix-router | vnbroker/core/source_router.py,vnbroker/common/data.py,tests/unit/core/test_source_router_fix.py | done | 2026-10-08T11:00:00Z |
| agent-tests | feat/add-tests | tests/unit/api/test_snapshot.py,tests/unit/api/test_stream.py,tests/unit/api/test_broker_api.py | done | 2026-10-08T11:00:00Z |
| agent-types | feat/fix-types | vnbroker/api/company.py,vnbroker/api/snapshot.py,vnbroker/api/broker.py,vnbroker/api/stream.py | done | 2026-10-08T11:00:00Z |
| agent-fetch | feat/fetch-multiple | vnbroker/explorer/dnse/quote.py,vnbroker/explorer/ssi/quote.py,tests/unit/explorer/test_dnse_fetch_multiple.py,tests/unit/explorer/test_ssi_fetch_multiple.py | done | 2026-10-08T11:00:00Z |
| agent-ratelimit | feat/rate-limit | vnbroker/core/utils/rate_limiter.py,vnbroker/core/utils/client.py,tests/unit/core/test_rate_limiter.py | done | 2026-10-08T11:00:00Z |
| leader-gates | feat/fix-gates | vnbroker/api/company.py,vnbroker/api/bulk.py,vnbroker/common/data.py,vnbroker/core/bulk_router.py,vnbroker/core/health_router.py,vnbroker/core/provider_pool.py,vnbroker/explorer/dnse/quote.py,tests/test_acb_all_providers.py,tests/unit/api/test_broker_api.py,tests/unit/api/test_snapshot.py,tests/unit/api/test_stream.py,tests/unit/common/test_bulk_normalizer.py,tests/unit/explorer/test_dnse_fetch_multiple.py | done | 2026-10-08T12:30:00Z |
| agent-t1-bulk | feat/tier1-bulk | vnbroker/core/registry.py,vnbroker/core/bulk_router.py,vnbroker/core/unified_registry.py,vnbroker/api/quote.py,vnbroker/api/bulk.py,tests/unit/core/test_bulk_router.py,tests/unit/api/test_bulk_api.py | done | 2026-10-08T13:00:00Z |
| agent-t1-failover | feat/tier1-failover | vnbroker/common/data.py,tests/contract/test_failover_integration.py,tests/contract/test_failover_tier1.py,tests/unit/common/test_bulk_normalizer.py | done | 2026-10-08T13:00:00Z |
| agent-t1-netpool | feat/tier1-netpool | vnbroker/core/utils/cache.py,vnbroker/core/utils/rate_limiter.py,vnbroker/core/utils/client.py,vnbroker/core/provider_pool.py,tests/unit/core/test_cache_key.py,tests/unit/core/test_rate_limiter.py,tests/unit/core/test_connection_pool.py,tests/unit/core/test_provider_pool.py | done | 2026-10-08T13:00:00Z |
| leader-t2-trade | dev | vnbroker/connector/dnse/trade.py,tests/unit/connector/dnse/test_trade_write_gate.py,tests/contract/test_dnse_endpoint_contract.py | done | 2026-10-08T15:00:00Z -> eeb1965 |
| leader-t2-secrecy | dev | vnbroker/broker/security/redaction.py,vnbroker/connector/dnse/core/http_client.py,tests/unit/broker/test_redaction.py | done | 2026-10-08T15:00:00Z -> b505766 |
| leader-t2-policy | dev | vnbroker/core/source_router.py,tests/unit/core/test_failover_parity.py | partial | 2026-10-08T15:00:00Z -> b505766 |
| leader-t2-ws | dev | vnbroker/connector/dnse/websocket.py,tests/unit/connector/dnse/test_websocket_protocol.py | done | 2026-10-09 -> 95f68e6 |
| pm-audit-doc | docs/pm-audit-2026-10-09 | docs/PM_AUDIT_REPORT_20261009.md | done | 2026-10-09 -> 2c67b3c |
| pm-gates-local | chore/local-gates-and-handoff | scripts/check_all.ps1,docs/HANDOFF_DNSE_ROUND2_20261009.md,CLAUDE.md,docs/CLAIMS.md | done | 2026-10-09 -> 2b76026 |
| pm-dnse-gate | feat/dnse-write-gate-layer | vnbroker/connector/dnse/client.py,vnbroker/connector/dnse/core/http_client.py,vnbroker/connector/dnse/trade.py,tests/unit/connector/dnse/test_write_gate_layer.py,tests/contract/test_dnse_endpoint_contract.py,CHANGELOG.md | done | 2026-10-09 -> 12cb29c |

| pm-ws-live | fix/dnse-subscribe-contract | vnbroker/connector/dnse/websocket.py,pyproject.toml,tests/unit/connector/dnse/test_subscribe_contract.py,docs/PM_AUDIT_REPORT_20261009.md,docs/HANDOFF_DNSE_ROUND2_20261009.md,CHANGELOG.md | done | 2026-10-09 -> 8efc03d |

<!-- ===== WAVE 3+4 (2026-10-10) ===== -->

| agent | branch | files | status | since | note |
|---|---|---|---|---|---|
| coordinator-w34 | (main) | docs/PLAN_TIER1_WAVE34.md, docs/PLAN_AUDIT_TIER1_WAVE34.md, docs/CLAIMS.md, docs/TEST_REPORT_TIER1_WAVE34.md, docs/AUDIT_TIER1_WAVE34.md, docs/HANDOFF_TIER1_WAVE34.md, docs/REPORT_FINAL_TIER1_WAVE34.md, CHANGELOG.md, CLAUDE.md | **in-progress** | 2026-10-10 | Plan + audit + claim + merge. Base `4cd0f2d` |
| w34-ratelimit | feat/w34-ratelimit | vnbroker/core/exceptions.py, vnbroker/core/utils/client.py, vnbroker/core/source_router.py, vnbroker/base.py, vnbroker/config.py, vnbroker/common/data.py, tests/unit/core/test_rate_limit_cooldown.py | **in-progress** | 2026-10-10 | worktree `../vnbroker-w34-ratelimit`. ⚠ `common/data.py` là đường người dùng THẬT (audit v2 blocker); chỉ sửa `_run_with_failover`, file đang 1823L ⇒ **không được dài thêm** |
| w34-logger | feat/w34-logger | vnbroker/core/utils/logger.py, tests/unit/core/test_logger_redaction.py | **in-progress** | 2026-10-10 | worktree `../vnbroker-w34-logger`. KHÔNG đụng `broker/security/` (money lane) |

<!-- Các claim `in-progress` ở trên (t-token, m-money, e-cond-sec, coordinator TCBS)
     đã STALE: cả 3 branch `feat/t-token`, `feat/m-money`, `feat/e-cond-sec` KHÔNG
     còn tồn tại (`git rev-parse` fail) và thư mục worktree tương ứng đã bị xoá.
     Không xoá hàng — chỉ chuyển status. Cột `files` của chúng KHÔNG giao với
     wave 3+4, nên không chặn. -->

| ~~t-token~~ (STALE) | feat/t-token (đã xoá) | — | **superseded** | 2026-10-10 | branch + worktree không còn; đã merge qua đợt trước |
| ~~m-money~~ (STALE) | feat/m-money (đã xoá) | — | **superseded** | 2026-10-10 | branch + worktree không còn; đã merge qua đợt trước |
| ~~e-cond-sec~~ (STALE) | feat/e-cond-sec (đã xoá) | — | **superseded** | 2026-10-10 | branch + worktree không còn; đã merge qua đợt trước |
| ~~coordinator~~ (TCBS, STALE) | dev | — | **superseded** | 2026-10-10 | claim của đợt TCBS trước; các file đã merge, còn `CHANGELOG.md` nay do coordinator-w34 giữ |
## Ghi chú

- `in-progress` = đang giữ. Đổi sang `done` ngay sau khi ghi xong file cuối cùng.
- **`leader-t2-policy` — ĐÃ SỬA GHI CHÚ SAI (2026-10-09).** Bản gốc ghi *"CHUA LAM:
  `async_client.py` (TokenBucketRateLimiter trùng lặp)"* kèm *"gate chưa đổi:
  `tests/unit/core/test_rate_limiter.py` chưa được tạo"*. Cả hai vế đều sai:
  - `tests/unit/core/test_rate_limiter.py` **đã tồn tại** — 174 dòng, 15 test, tạo ở `b2f43ff`.
  - Việc còn lại thật sự là hợp nhất class trùng trong `async_client.py`, và audit 2026-10-09
    đã hạ mức từ P0 xuống **minor** (đo: `capacity=300`, refill 5/s ⇒ không bao giờ treo).
  - `async_client.py` **không được claim ở đâu cả** — chỉ xuất hiện trong plan. Cần claim mới
    trước khi sửa.
- KHÔNG agent nào được claim: `CLAUDE.md` (Hermes bảo vệ), `vnbroker/**` (không có
  bug code), `~/.hermes/config.yaml` (hook toàn cục trỏ dự án khác), và các file
  thuộc việc dở của người dùng.
- `docs/PLAN_WORKFLOW_REPAIR.md`, `docs/PLAN_AUDIT.md`, `docs/CLAIMS.md` do
  **supervisor** viết, không agent nào claim.
- `docs/_workflow/STATE.json` chỉ bị **gitignore** (không sửa nội dung) ⇒ nằm
  trong scope mục 2 nhưng không cần claim file.

## Kiểm chồng lấn

```bash
SKILL="C:/Users/Pham Viet Dung/AppData/Local/hermes/skills/software-development/multi-agent-workflow"
node "$SKILL/scripts/check-overlap.cjs" --file docs/CLAIMS.md
```
Exit 0 = không chồng lấn. Exit 1 = có chồng lấn → DỪNG, không dispatch.

---

## 2026-10-09 — TCBS Rebuild (Mode A, 3 worker)

| agent | branch | worktree | scope | files | status | since | note |
|---|---|---|---|---|---|---|---|
| a1-bars | feat/a1-bars | ../tcbs-a1-bars | GĐ1 nối bars + bỏ NotImplementedError | explorer/tcbs/bars.py (mới), explorer/tcbs/quote.py, tests/unit/explorer/tcbs/test_tcbs_bars.py | **done** | 2026-10-09 | `6c88f4b`; quote.py 801→793L; AC 1-4 + 7 tự verify bằng payload thật |
| a2-ws | feat/a2-ws | ../tcbs-a2-ws | GĐ2 viết lại WebSocket protocol pipe | explorer/tcbs/websocket.py, ws_models.py, stream.py, tests/unit/explorer/tcbs/test_tcbs_ws_protocol.py | **done** | 2026-10-09 | `f2ba384`; +60 test offline; xoá bảng SIT; không có caller `stream_ohlc` bị đổi |
| a3-legacy | feat/a3-legacy | ../tcbs-a3-legacy | GĐ3 gỡ path không có trong 2 tài liệu | broker/tcbs/account.py, equity.py, client.py, 3 test file | **done** | 2026-10-09 | `de4c7f8`; gỡ **18/19** — `/aion/v1/accounts` giữ làm ngoại lệ (Owner chốt) |
| coordinator | docs/plan-tcbs | (main) | Plan + claim + audit + merge + verify | docs/PLAN_TCBS_REBUILD.md, CHANGELOG.md | **done** | 2026-10-09 | `a832a84`; tự verify độc lập bằng script, **không** tin lời agent |

**Rời nhau đã kiểm bằng script, không bằng mắt:** tập file của 3 agent giao nhau = ∅.

**Baseline gate @ bec8b82** (đo, không ước lượng):
- pytest tests/ -q --timeout=300 → exit 0, 1497 passed, 26 skipped
- 
uff check vnbroker → exit 0
- scripts/check_mypy_baseline.py → exit 0
- 
uff check tests → **exit 1, 13 lỗi KNOWN-RED có sẵn** — không đòi xanh, chỉ đòi không tăng
- 13 file vượt 800L (4 thuộc TCBS) — CLAUDE.md:15 "800 max"

**Gate sau merge @ a832a84** (`scripts/check_all.ps1`, đo local):
- pytest full → **1696 passed, 26 skipped** (baseline 1497 ⇒ **+199**)
- pytest-contract → 72 passed
- `check_mypy_baseline.py` → exit 0, baseline **1266 → 1161** (fix 105)
- `ruff check tests` → 13 KNOWN-RED, **không tăng**
- Ngân sách 800L khối TCBS: chỉ còn `derivatives.py` 852L (có sẵn, ngoài lát)

**Tự kiểm chứng của coordinator (không tin báo cáo agent):**
- AC S1 #1-4 + #7 — chạy `bars_to_frame` với payload thật Owner paste (có `dataT1: null`):
  6 cột chuẩn ✓, tz `Asia/Ho_Chi_Minh` ✓, ngày không dịch ✓, field lạ không lọt ✓, `D/W/M` ✓
- AC S2 — đọc code thật: `d|a|||` (`:194`), `d|p|||` (`:199`), `ping_interval=None`,
  không còn bảng `_WS_ENDPOINTS_SIT` (chỉ còn comment giải thích), `use_sit` giữ chữ ký + cảnh báo bỏ qua
- AC S3 — AST/regex có khoanh đúng khối `{}`: `_REMOVED_PATHS` = **18**, và **18/18 vắng
  trong spec** (đối chiếu `openapi-v1.0.0.json`). `_PATHS` còn **39** path.

> **ĐÍNH CHÍNH — lỗi của chính audit của tôi.** Ban đầu tôi ghi "19 path legacy là
> những path có tiền tố `erebos`/`aion`". **Tiêu chí đó sai**: spec chính thức có
> `/erebos/v2/digital/margin-info` và `/erebos/v2/digital/trans-hist-cashStatements`
> trong `money.py` (**có** trong cả spec lẫn Postman). Đã sửa tiêu chí thành
> "vắng ở path cụ thể" và xác minh lại từng cái. Nếu tin tiêu chí cũ thì đã xoá
> nhầm 2 path đang hoạt động.

**CHƯA CHẠY — KHÔNG ĐƯỢC GHI LÀ PASS:**
- **Probe server TCBS thật**: chưa có JWT (cần Smart OTP từ app TCInvest).
  ⇒ `countBack` + bản đồ resolution phút là **hệ số ước lượng**; mặc định 18 path
  là legacy **chưa** từng gọi server (401 chạy trước routing).
- **CI GitHub Actions**: job bị từ chối khởi động do billing.
- **GĐ4 TokenManager + GĐ5 13 endpoint**: chưa làm (ngoài phạm vi 3 lát).

**Cổng Giai đoạn 0 (probe 19 path) đã bị bỏ** — Owner quyết xoá theo tài liệu chính
thức, không cần probe. Ghi rõ: **xoá theo quyết định Owner, chưa verify bằng server.**

---

## 2026-10-10 — TCBS Round 2 (Mode A, 3 worker) · base `dev @ c8c4618`

| agent | branch | worktree | scope | files | status | since | note |
|---|---|---|---|---|---|---|---|
| t-token | feat/t-token | ../tcbs-t-token | GĐ4 TokenManager + 2 endpoint gaia | vnbroker/broker/tcbs/token_manager.py (mới), vnbroker/broker/tcbs/auth.py, tests/unit/broker/tcbs/test_tcbs_token_manager.py (mới) | **in-progress** | 2026-10-10 | Chặn bug 8 giờ bịa tại session.py:87-90 |
| m-money | feat/m-money | ../tcbs-m-money | GĐ5 4 endpoint tiền/vay (1 read + 3 write) | vnbroker/broker/tcbs/money.py, tests/unit/broker/tcbs/test_tcbs_money_endpoints.py (mới) | **in-progress** | 2026-10-10 | 3 write endpoint bắt buộc @write_gate |
| e-cond-sec | feat/e-cond-sec | ../tcbs-e-cond-sec | GĐ5 condition/cancel + ananke securities | vnbroker/broker/tcbs/condition_orders.py (mới), vnbroker/explorer/tcbs/listing.py, tests/unit/broker/tcbs/test_tcbs_condition_order.py (mới), tests/unit/explorer/tcbs/test_tcbs_ananke_securities.py (mới) | **in-progress** | 2026-10-10 | equity.py 798L nên KHÔNG thêm vào đó |
| coordinator | dev | (main) | Plan + audit + claim + merge + verify | docs/PLAN_TCBS_ROUND2.md, docs/PLAN_AUDIT_TCBS_ROUND2.md, docs/references/openapi-v1.0.0.json, scripts/verify_tcbs_coverage.py, .gitignore, vnbroker/broker/tcbs/client.py, vnbroker/broker/tcbs/__init__.py, CHANGELOG.md | **in-progress** | 2026-10-10 | `c8c4618` |

**Rời nhau kiểm bằng script, không bằng mắt:** tập file 3 agent giao nhau = ∅.

**Baseline gate @ b18e47b** (đo, không ước lượng):
- pytest tests/ -q --timeout=300 → **1696 passed, 26 skipped**. Lần chạy thứ nhất ra
  `1 failed, 1695 passed` — flake mạng `test_news_integration.py` gọi
  `kbbuddywts.kbsec.com.vn`. **Ghi cả hai lần.**
- pytest tests/contract → 72 passed · ruff check vnbroker → exit 0
- check_mypy_baseline.py → exit 0 (baseline 1266, now 1161)
- ruff check tests → **exit 1, 13 KNOWN-RED có sẵn** — không đòi xanh, chỉ đòi không tăng

**Phạm vi GĐ5 đo lại bằng script, không đọc từ proposal:**
`.venv\Scripts\python.exe scripts/verify_tcbs_coverage.py` → spec 48 · đã nối 39 ·
**còn 9** · `_REMOVED_PATHS` 18 key, **0 còn trong spec** (xác nhận lại lát a3 đợt 1).

**Cố ý hoãn, có lý do:**
- `/api/v1/derivatives/contracts` — spec tự mâu thuẫn (path REST, mô tả "over WebSocket",
  response không có `content`). Cần Owner chốt REST hay WS.
- `derivatives.py` (852L) **cấm chạm**. `equity.py` (798L) chỉ còn 2L dưới ngân sách.

**CHƯA CHẠY — KHÔNG ĐƯỢC GHI LÀ PASS:**
- **Probe server TCBS thật**: chưa có JWT (cần Smart OTP từ app TCInvest) ⇒ mọi AC về
  hành vi runtime chỉ dựa trên **spec**, chưa quan sát thực tế.
- **CI GitHub Actions**: job bị từ chối do billing.

## 2026-10-10 — TCBS Round 2 KẾT THÚC — cập nhật trạng thái claim

| agent | branch | worktree | status | commit | kết quả |
|---|---|---|---|---|---|
| t-token | feat/t-token | ../tcbs-t-token | **released** | `f056318` (merge `090034a`) | TokenManager 303L · AC T1-T10 10/10 · coverage 39→41 · chặn bug 8 giờ bịa |
| m-money | feat/m-money | ../tcbs-m-money | **released** | `6922d02` (merge `90ead64`) | 4 endpoint tiền/vay · AC M1-M9 9/9 · coverage 41→45 · money.py 791L |
| e-cond-sec | feat/e-cond-sec | ../tcbs-e-cond-sec | **released** | `2e48d99` (merge `8e4f959`) | condition/cancel + ananke · AC E1-E5 5/5 · coverage 45→47 |
| coordinator | dev | (main) | **released** | `f23786f` + fix F-1/F-2 | wire facade + `__init__` · audit fix |

**Phủ API:** spec 48 path · **đã nối 47** · còn **1** (`/api/v1/derivatives/contracts`)
· `_REMOVED_PATHS` 18 key, **0 còn trong spec** (xác nhận lại lát a3 đợt 1).

**Gate cuối ở `dev`:** pytest **1881 passed / 26 skipped** (baseline đợt 1: 1696 ⇒ +185) ·
contract 72 · ruff vnbroker exit 0 · mypy OK (baseline 1266→1161) ·
ruff tests **13 KNOWN-RED, không tăng** · `verify_tcbs_coverage.py` exit 0.

**Audit code độc lập:** `NEED_REVISION` — 0 blocker, 2 major, 13 minor, confidence high.
Cả 2 major đã sửa ở commit fix: F-1 (write 4xx) có bằng chứng fail-trước/pass-sau đo
được; F-2 (`rc`) ghi hợp đồng vào docstring + helper, phần raise tự động hoãn vì thiếu
tập mã.

**Chưa xử lý (chuyển session sau):** xem `docs/HANDOFF_TCBS_20261010.md`.

## 2026-10-10 — TCBS Round 3 (Mode B solo) · base `dev @ 5f7b83f` -> `c917399`

| agent | branch | scope | files | status | note |
|---|---|---|---|---|---|
| coordinator | dev (truc tiep) | Cong chan payload + tach derivatives + 2 fix nho + 5 lesson | scripts/check_tcbs_bodies.py, check_tcbs_bodies_selftest.py, docs/tcbs_body_baseline.json, broker/tcbs/derivative_orders.py, broker/tcbs/derivatives.py, broker/tcbs/auth.py, broker/security/guards.py, tests/unit/broker/tcbs/{test_tcbs_body_contract,test_tcbs_round3_fixes}.py, docs/LESSONS/*, docs/{PLAN_TCBS_ROUND3,REPORT_TCBS_ROUND3,HANDOFF_TCBS_20261010_R4}.md, scripts/check_all.ps1, CHANGELOG.md | **released** | `4654ff7` · `61ab18b` · `93a89e8` · `ee0fbc5` · `c917399` |

**Vi sao Mode B (tu tuan tu, khong song song):** ca 3 lat deu cham `vnbroker/broker/tcbs/`
=> file chong nhau. Chay song song se tai tao Hazard 1 (weld hunk).

**Phat hien:** spec 48 path · 47 da noi · 1 chua. Cong payload quet **12** write method →
**38 lech**; lon nhat la `_gated_change_derivative_order` thieu **6 field `required`**.
**CHUA SUA** — can Owner chot + JWT.

**Audit doc lap:** NEED_REVISION (1 blocker, 6 major) → sua xong tai `ee0fbc5`.
Tach `derivatives.py` xac nhan sach: 10/10 public method giu chu ky, khong import vong.

**Gate cuoi:** pytest 1918 passed / 26 skipped | contract 72 | ruff exit 0 |
mypy 1266->1148 | ruff tests 13 KNOWN-RED | tcbs-bodies lech moi 0 | lessons 24/40 |
self-test 9/9 + 10/10.

**CHUA CHAY:** probe server that (chua co JWT). Ba noi an toan la lane tien thuat
duoc sua bang `check_tcbs_bodies.py` + baseline, khong dua vao commit nao.

## 2026-10-10 — TCBS Round 4 (Mode B solo) · base `dev @ a843bae` -> `7aef6af`

| agent | branch | scope | status | note |
|---|---|---|---|---|
| coordinator | dev (truc tiep) | Sua 38 lech payload + do duoc server that + 3 lo hong cong + 2 bug co san + TTL 24h + DNSE skip | **released** | `2599872` · `ea55936` · `7aef6af` |

**Phat hien lon nhat:** `.env` **DA CO JWT** (1290 ky tu, con hieu luc den 19:10).
4 dot truo deu ghi "chua co JWT" — sai, chi la chua ai mo `.env` kiem.

**Do duoc (khong doan):** TTL = `exp - iat` = 86400s = **24 gio** (tai lieu ghi ~8 gio — sai) ·
`custodyID` trong claim · `scopes` **khong co derivative** => `/khronos/*` khong kiem chung duoc.

**Ket qua:** cong payload 12 write · **0 lech** (baseline rong) · `/api/v1/derivatives/contracts`
**404 ca GET lan POST** => khong noi, coverage giu 47/48 · 18 path da go: **17** chet that,
1 khong phan biet duoc voi wildcard · 3 endpoint bi server tu choi (2 hydros tung bao PASS bang mock).

**3 lo hong CUA CONG** do chinh tai tao ra khi sua: quet bo sot `payload["x"]=..`;
map toan cuc theo TEN key lam 5 method derivative quet nham (9 lech SAI);
`subprocess` khong khai `encoding` lam gate mypy **xanh gia**. Khong baseline 2 loi
dau — chung la loi cua cong.

**2 bug co san:** `client.modify_order()` + `cancel_order()` truyen `pin_code` cho
method khong co tham so do => TypeError moi lan goi.

**5 ket luan sai cua chinh toi** da dinh chinh tai cho (bao cao §6): 4 loi **do sai
do khong doan dung** (truyen `{ticker}` literal, gui header hoc, dem sai path da go,
nho quyen la sai dinh dang).

**Gate:** **8/8 PASS** — ruff 0 | mypy 1266->1138 | contract 72 | tcbs-bodies 0 lech |
lessons 24/40 | pytest 1919 passed / 30 skipped / **0 ERROR**.

**CHUA CHAY:** goi write endpoint that (chua duoc giao phep) · xac nhan `/khronos/*`
· do tap `rc` · CI (billing).

---

## 2026-10-11 — HANG1 Row 1 (Mode B solo) · base `main @ 662e2ef`

| agent | branch | worktree | scope | files | status | since | note |
|---|---|---|---|---|---|---|---|
| pm-hang1-s1 | feat/hang1-row1 | (main checkout) | S1 WP-01 async lock per-loop | vnbroker/core/utils/async_client.py,vnbroker/core/utils/__init__.py,tests/unit/core/test_async_client.py | released | 2026-10-11 | PR #5 merged `7aca907` |
| pm-hang1-s2 | feat/hang1-row1 | (main checkout) | S2 WP-02 cache key fallback | vnbroker/core/utils/cache.py,tests/unit/core/test_cache_key.py | released | 2026-10-11 | PR #5 merged `7aca907` |
| pm-hang1-s3 | feat/hang1-row1 | (main checkout) | S3 WP-03 loi vinh vien | vnbroker/core/exceptions.py,vnbroker/core/utils/client.py,vnbroker/core/source_router.py,vnbroker/base.py,tests/unit/core/test_rate_limit_cooldown.py | released | 2026-10-11 | PR #5 merged `7aca907` |
| pm-hang1-s4 | feat/hang1-row1 | (main checkout) | S4 WP-04 rong-vs-loi | vnbroker/explorer/kbs/listing.py,vnbroker/explorer/kbs/trading.py,vnbroker/explorer/vci/quote.py,vnbroker/common/data.py | released | 2026-10-11 | PR #5 merged `7aca907`; common/data.py khong can cham |

Tap file 4 slice giao nhau = ∅ (S4 giu `common/data.py` mot minh).
Lesson ap dung: [L-P01, L-P02, L-P03, L-P04, L-P05, L-P06, L-E01, L-E04, L-E06].

## 2026-10-14 - VNINVEST REQ 001..005 (doc-only de, code co) - base main @ fe76670

Van ban yeu cau: ninvest/docs/REQUESTS_TO_VNBROKER_20261014.md (5 REQ).

| agent | branch | worktree | scope | files | status | since | note |
|---|---|---|---|---|---|---|---|
| opencode-vninvest-req | feat/vninvest-req-20261014 | (main checkout) | REQ-001 BrokerRegistry.capabilities() 3 lane | vnbroker/broker/registry.py,vnbroker/broker/capabilities.py,vnbroker/broker/__init__.py,tests/unit/broker/test_capabilities.py,tests/contract/test_capability_contract.py | in-progress | 2026-10-14 | - |
| opencode-vninvest-req | feat/vninvest-req-20261014 | (main checkout) | REQ-003 watchlist capability | cung file REQ-001 | in-progress | 2026-10-14 | (a) khai bao unsupported; (b) ghi roadmap, khong code |
| opencode-vninvest-req | feat/vninvest-req-20261014 | (main checkout) | REQ-004 MARKET_TYPES + validate | vnbroker/connector/dnse/constants.py,vnbroker/connector/dnse/client.py,vnbroker/connector/dnse/trade.py,tests/unit/connector/dnse/test_market_type_validation.py | in-progress | 2026-10-14 | 24 method DNSEClient+Trade |
| opencode-vninvest-req | feat/vninvest-req-20261014 | (main checkout) | REQ-005 normalize + market_type aggregate | vnbroker/connector/dnse/client.py,tests/unit/connector/dnse/test_normalize_public_api.py | in-progress | 2026-10-14 | - |
| opencode-vninvest-req | feat/vninvest-req-20261014 | (main checkout) | REQ-002 TCBS order history nhieu ngay | docs-only (khong code) | in-progress | 2026-10-14 | AC alternative khong thien hanh duoc theo spec |
| opencode-vninvest-req | feat/vninvest-req-20261014 | (main checkout) | F-01 __version__ doc metadata cu | vnbroker/__init__.py,scripts/check_version_sync.py | in-progress | 2026-10-14 | do: 3.4.0 vs pyproject 3.7.2 |

Khong file docs/CLAIMS.md cua agent khac dang claim in-progress bi cham.

| corporate-actions-source | feat/corporate-actions-source | (main checkout) | Corporate action source: Slice 1-3 xong (parser + unified API + auth/docs), Slice 4 chờ owner release/bump pin | vnbroker/common/corporate_actions.py, vnbroker/explorer/vci/company.py, vnbroker/api/company.py, vnbroker/explorer/tcbs/IMPLEMENTATION_SUMMARY.md, vnbroker/explorer/tcbs/MIGRATION_GUIDE.md, vnbroker/explorer/tcbs/company.py, tests/unit/common/test_corporate_actions_parser.py, tests/unit/explorer/test_vci_corporate_actions.py, tests/unit/api/test_corporate_actions_api.py, tests/unit/explorer/tcbs/test_dividends_auth_message.py, docs/PLAN_CORPORATE_ACTION_SOURCE_20261120.md, docs/CLAIMS.md | done | 2026-11-20 | base main@eac374b; merge queue main; KHÔNG đụng common/data.py; gate check_all CHƯA CHẠY (thiếu .venv) |
Lesson ap dung: [L-E01, L-E02, L-E03, L-E05, L-E06, L-E07, L-R01, L-R04, L-P01, L-P03, L-P04, L-P05, L-P06].

### Trang thai cua claim tren (cap nhat khi dong)

Tat ca 6 dong da **released** tren branch eat/vninvest-req-20261014 (khong merge).
Gate do tai main tree tai commit nay: check_all.ps1 (khong -Quick) **exit 0** —
ruff-src PASS · version-sync PASS (3.7.2, kem dist metadata) · lessons PASS ·
tcbs-coverage PASS · tcbs-bodies PASS · provider-consistency PASS ·
mypy-baseline PASS · pytest-contract **117 passed** · pytest-full **2177 passed,
26 skipped**.

CHUA CHAY: CI GitHub Actions (job bi tu choi khoi dong do billing).
KHONG co baseline pytest-full TRUOC thay doi — vi vay KHONG bao cao delta so
test (chi bao cao so do tai commit nay). Day la L-E07.

Phan hoi chinh thuc 5 REQ: docs/RESPONSE_TO_VNINVEST_20261014.md.
Phan hoi REQ-002 co contract test khoa ket luan:
	ests/contract/test_tcbs_order_history_contract.py.

### Dinh chinh so lieu (L-E01 bat duoc chinh minh ta)

Ban nhap dau cua docs/RESPONSE_TO_VNINVEST_20261014.md va roadmap ghi **so dong
file sai**, do lenh Get-Content f | Measure-Object -Line cua PowerShell **khong
dem dong rong**. So dung (do bang len(text.splitlines())):

| File | Sai (non-empty) | Dung (tong dong) |
|---|---|---|
| nbroker/connector/dnse/client.py | 662 | **713** |
| nbroker/connector/dnse/trade.py | 1233 | **1352** |

Va dem lai bang AST/inspect: DNSEClient co **15** method cong khai nhan
market_type (khong phai 11), Trade co **12** (khong phai 13).

Ket qua khong doi gi ve quyet dinh tach MultiMarketMixin — client.py truoc khi
them la 707 dong, them 155 se thanh **862, VUOT** ngan sach 800 (truoc do chi
"sát"). Va 	rade.py con vuot ngan sach nhieu hon da ghi.

Da sua trong docs/RESPONSE_TO_VNINVEST_20261014.md, CLAUDE.md, CHANGELOG.md.
Bai hoc: L-E01 xay ra **ngay trong luc viet bao cao**, khong phai chi la tai lieu
cu bi hong. Day la lan thu hai trong dot nay (lan 1: docs/RESEARCH_WATCHLIST_
BROKER_20261014.md ma REQ danh chung khong ton tai o cay hien tai).

### R-W2: dinh nghia that + dinh chinh dien giai sai

R-W2 **khong phai quy tac chung cua he thong** — no la dong 121 cua
docs/RESEARCH_WATCHLIST_BROKER_20261014.md (vninvest, branch
eat/multibroker-plan-research, commit 1b5e455b5):

| # | Noi dung | Muc |
|---|---|---|
| R-W1 | Khai bao trung thuc WatchlistCapability = unsupported cho ca 3 lane trong roker/registry.py | P1 |
| **R-W2** | **KHONG reverse-engineer private web API (iBoard/EntradeX web) de lay watchlist** | Quy tac |
| R-W3 | Duong chinh thong duy nhat: de xuat provider mo API watchlist | P3 |
| R-W4 | Tai dung co san: get_holdings/get_positions 3 lane; ligo get_watchlist(filters) cho goi y ma (screener, **khong phai** watchlist user) | P0 |

**Hai loi cua ban nhap:**
1. **Tu mau thuan.** §7 row 9 cua van ban tra loi noi file nay "KHONG ton tai" o
   cay hien tai cua vninvest — roi §2 REQ-003b lai trich R-W1..R-W4 tu chinh file
   do lam can cu. Vua bao file khong ton tai vua dung no.
2. **Dien giai qua rong.** Ban nhap noi REQ-003b "bi chan" *theo R-W2*. That ra R-W2
   cam reverse-engineer **web private de lay watchlist**, KHONG cam vnbroker viet
   CRUD khi provider **co** API chinh thuc. Ly do that de chua viet la **chua co
   API nao de goi** — khong lien quan gi toi R-W2.

Da sua ca hai trong docs/RESPONSE_TO_VNINVEST_20261014.md §2 (them bang doi
chieu R-W1..R-W4 + khoi doan dinh chinh) va §7 row 9 (nen nguon + commit).

Ghi chu: R-W4 cua vninvest da phan loai get_watchlist(filters) cua
explorer/tcbs la screencer chu khong phai watchlist user — **dung bang cach
vnbroker gan nhan**, va get_watchlist(filters) do da co san trong repo nen
R-W4 khong ton tai viiec moi o vnbroker.
---

## 2026-10-16 - DNSE OPENAPI FIX (Mode B solo) - base `f6cf68b`

Plan: `docs/PLAN_DNSE_FIX_20261016.md` - Audit: `docs/PLAN_AUDIT_DNSE_FIX_20261016.md`
Verdict audit: **NEED_REVISION** (4 blocker, 7 major, 6 nho) -> plan ban 2 da sua het.

| agent | branch | worktree | scope | files | status | since | note |
|---|---|---|---|---|---|---|---|
| coordinator-dnse-fix | feat/dnse-openapi-fix | (main checkout) | Sua 11 defect client DNSE OpenAPI (D1-D11) | vnbroker/connector/dnse/services/{market_service,order_service,account_service,position_service}.py, vnbroker/connector/dnse/client.py, vnbroker/connector/dnse/core/time_utils.py (moi), vnbroker/connector/dnse/{trade_derivatives,trade_conditional,openapi_passthrough}.py (moi), vnbroker/explorer/dnse/quote.py, vnbroker/broker/capabilities.py, scripts/probe_dnse_readonly.py, tests/unit/connector/dnse/{test_market_time_units,test_order_read_params,test_position_id_guard}.py (moi), tests/contract/test_trade_public_surface.py (moi), tests/unit/connector/dnse/test_market_data_read_methods.py, tests/unit/connector/dnse/test_write_safety.py, tests/contract/test_dnse_endpoint_contract.py, docs/AGENT_PROTOCOL.md, docs/DNSE_API_CONTRACT.md, docs/REPORT_DNSE_LIVE_20261016.md, docs/LESSONS/provider-params.md | **merged** `v3.8.0` | 2026-10-16 | Mode B. 16 commit `0bc2d45`..`bdfd2cf` (10 commit REQ-001..005 truoc do da nam tren nhanh tu truoc); 11/11 defect dong, **da do lai live**. Merge vao `main`, tag `v3.8.0` |

**Vi sao Mode B:** lat A/B/D sua `market_service.py`; lat A/B/C/D sua `client.py`.
Tap file giao nhau => chay song song se tai tao Hazard 1 (weld hunk). Tien le:
TCBS Round 3 (`docs/CLAIMS.md:205-206`).

**KHONG claim:** `vnbroker/connector/dnse/core/http_client.py` (write gate la choke
point money lane). ~~`trade.py` (1352L, vuot ngan sach 800L)~~ — da tach ngay sau
do, xem muc "Tach trade.py" duoi day.

**Baseline gate @ f6cf68b** (do, khong suy tu CLAUDE.md - xem AGENT_PROTOCOL §2):
- pytest tests/ -q --timeout=300 -> exit 0, **2177 passed, 26 skipped**, 3 subtests
- pytest tests/contract -q -> exit 0, **117 passed** (do lai sau audit B1; ban
  nhap ghi "72" - chieu CLAUDE.md da loi thoi)
- pytest tests/unit/connector/dnse tests/contract -q -> exit 0, 332 passed
- ruff check vnbroker tests/unit tests/contract -> exit 0
- check_mypy_baseline.py -> exit 0 (baseline 1266, now 1138)
- ruff check tests -> **exit 1, 13 KNOWN-RED co san** - chi doi khong tang

**3 phat hien lam doi huong ke hoach (deu do duoc, khong doan):**
1. `/market/working-dates` -> **200, 257 workingDates**. Docstring trong code bao
   "DNSE khong co endpoint nay" -> **sai**. D1 la path bug, khong phai endpoint vong.
2. `/accounts/{a}/corporate-action-history` -> **200**. Code dung
   `/corporate-actions` -> `404 API ROUTE NOT FOUND`. D5 la path bug.
3. Kiem tra 24 gia tri boardId/marketId deu that bai. **KHONG them enum** (L-P06).

Lesson ap dung: [L-R01, L-R02, L-R03, L-R04, L-R06, L-E01, L-E02, L-E04, L-E06,
L-P03, L-P04, L-P05, L-P06].

### Trang thai claim tren (cap nhat khi dong)

**Da DONG.** 9 commit tren `feat/dnse-openapi-fix` (base `f6cf68b`):

| # | Commit | Noi dung |
|---|---|---|
| 1 | `0bc2d45` | Stage 0-3: AGENT_PROTOCOL, plan v2, audit, bao cao, probe |
| 2 | `3fbbb8b` | Slice A - D8/D9 don vi GIAY + chan market_index |
| 3 | `6f5fc98` | Slice B - D1 `/market/working-dates` |
| 4 | `069dfbe` | Slice C - D2/D3/D4 pageIndex + cap `from`/`to` |
| 5 | `9d37af4` | Slice D - D7 date string + board_id bat buoc |
| 6 | `393591e` | Slice E - D5 path + D6 chan position_id rac |
| 7 | `3e25b71` | Slice F - bang chung am tinh D10/D11 (hoa ra SAI, xem report §12) |
| 8 | `4746a8f` | Sua 1 blocker + 4 major cua audit ma nguon |
| 9 | `51f3e30` | **Khoi phuc mojibake** + them cong `check_encoding.py` |
| 10 | `d8fab65` | Mang ve: dong D10/D11 bang tu dien that + `pageSize` bat buoc |

**Audit ma nguon doc lap: 2 vong, ca 2 deu FAIL** (vong 1: 1 blocker/4 major;
vong 2: 1 blocker/1 major). Blocker vong 2 **do chinh toi gay ra** bang script
mutation-test: `Get-Content -Raw` doc UTF-8 bang CP1252 roi ghi lai ban hong.
Da them `scripts/check_encoding.py` vao `check_all.ps1` de loi nay tu do.

**Gate cuoi @ `d8fab65`:** `check_all.ps1` FULL **exit 0** · `pytest-full`
**2246 passed, 26 skipped** (baseline 2177 => **+69**) · contract 117 ·
mypy-baseline 1266->1133 · cong moi `encoding` PASS 449 file · `ruff check tests`
13 KNOWN-RED **khong tang**.

**Mutation-test 4/4**: bo tung fix lai lan luot thi test tuong ung do (6/1/1/5).
Khong con test xanh vi khang dinh sai.

**Do lai live (khong VPN):** `scripts/probe_dnse_readonly.py` => `PASS=40 FAIL=16`,
16 FAIL deu la probe phu dinh co chu dich. **11/11 defect da dong.**

**CHUA CHAY - KHONG DUOC GHI LA PASS:**
- **Mang DNSE production mat luc 16:40** (TLS handshake timeout 3/3 lan, 12.5s/lan).
  Bang chung D1/D5 thu o dau phien (khong VPN) van co gia tri nhung phai ghi kem
  dieu kien mang tai thoi diem do. Re-probe live Stage 6 => CHUA CHAY neu mang
  chua ve.
- Gia thuyet `boardId = "G1"` / `marketId` kieu `G*` (tu `websocket.py:19,278`) **chua
  kip thu** => Slice F chua chot duoc.
- Sandbox co chap nhan `pageIndex` khong -> chi biet "khong doi", chua biet "chap nhan".
- `Trade.login()` JWT: `.env` thieu `DNSE_USERNAME`/`DNSE_PASSWORD`.
- CI GitHub Actions: job bi tu choi khoi dong do billing.

---

## 2026-10-16 - SAU KHI DONG: 3 chi thi cua Owner

Owner chot 3 viec ngay sau khi dong task. Ca 3 da xong va **da merge** vao `main`.

### 1. `orderCategory` BAT BUOC (phuong an A) - `2c23984`

Hai yeu cau bat nguon tu luc do live: `get_orders` thieu `order_category` ->
`400 INVALID_ORDER_CATEGORY` tren production (sandbox khong doi).

Da can nhac 3 phuong an, Owner chot **A**:
- **A (chot):** `order_category: str` bat buoc trong chu ky. Go thieu ->
  `TypeError` ngay, khong co byte nao di ra.
- B (loai): giu tuy chon, chi validate gia tri.
- C (loai): mac dinh `"NORMAL"`.

**Vi sao loai C:** nguoi muon xem lenh `STOP` ma quen tham so se nhan danh sach
`NORMAL` day du trong mat va thieu. Do la **sai du lieu ma trong nhu dung** —
fail-open o tang ngu nghia du lieu, te hon han mot `TypeError` luc go.

### 2. Tach `trade.py` 1352L -> 4 file - `b4b386b` + `bdfd2cf`

Thu tu: **dong bang API truoc, tach sau**.

| File | Dong |
|---|---|
| `trade.py` (core: infra + auth + order/deal) | 622 |
| `trade_derivatives.py` (`DerivativeMixin`) | 180 |
| `trade_conditional.py` (`ConditionalOrderMixin`) | 180 |
| `openapi_passthrough.py` (`OpenApiPassthroughMixin`) | 354 |

`tests/contract/test_trade_public_surface.py` (moi): 47 method + 47 chu ky + 14
write-gated, xanh TRUOC (`b4b386b`) va xanh SAU (`bdfd2cf`).

**3 loi toi tu gay ra va bi cong cu bat (ghi lai de khong lap):**
1. Them `from __future__ import annotations` vao mixin -> `inspect.signature`
   doi dang -> freeze test bat. Da bo.
2. Script tu dong gan `-> Any` cho ca `__init__` (phai la `-> None`) -> mypy bat.
3. `test_write_safety.py` quet AST chi `class Trade` trong `trade.py` -> **bo sot
   2 method ghi tien that** sau khi tach. Money lane, quet hep = lo hong; da mo
   rong sang `TRADE_MODULES`.

**mypy-baseline 83 loi moi -> 0.** Nguyen nhan: baseline dem theo DUONG DAN file,
code chuyen file bi tinh la `new`. Sua that (khai bao hop dong mixin duoi
`TYPE_CHECKING`, return annotation, thu hop `dict`/`list`) chu **khong** dung
`--update` de giau. 1266 -> 1106.

### 3. Lesson moi - `73b8c99`

`docs/LESSONS/provider-params.md` -> `L-D01` (validator tu choi ma khong liet ke
tap hop -> doc response server, dung doan) va `L-D02` (mac dinh "cho chay duoc"
la tu che). ⚠ ID lesson regex la `^## L-[A-Z]\d+` — **mot chu cai**; `L-PP01` bi
gate bao DRIFT, da dung namespace `L-D`.

### Gate cuoi @ `bdfd2cf` (truoc merge)

`check_all.ps1` FULL **exit 0** · pytest **2281 passed, 26 skipped** (baseline
2177 => **+104**) · contract **149** · mypy-baseline 1266->1106 · encoding PASS
453 file · ruff-src/unit/contract sach · `ruff check tests` 13 KNOWN-RED khong tang.

### Con CHUA CHAY (chuyen tiep sang phien sau)

Xem `docs/HANDOFF_DNSE_FIX_20261016.md` — danh sach day du. Tom tat: STOP/OCO co
that su chay khong; `order_detail`/`executions`/`order_history` co doi
`order_category` khong; sandbox chap nhan `pageIndex`/`pageSize` khong; `403` tai
`position_id=999999` chua giai thich.

## 2026-11-20 — Fix P0 ex_date VCI corporate_actions (release 3.8.2)

| agent | branch | worktree | scope | files | status | since | note |
|---|---|---|---|---|---|---|---|
| corporate-actions-exrightdate | fix/corporate-actions-exrightdate | (main checkout) | Fix P0 từ re-probe vnbroker 3.8.1: `_pick` thiếu key thật `exrightDate` (ex_date=None 100%), lọc news rows (`isEvent=False`, không `eventCode`) khỏi contract, golden fixture VNM 57 events | vnbroker/common/corporate_actions.py, tests/unit/common/test_corporate_actions_parser.py, tests/fixtures/vci_news_events_vnm_20261120.json, docs/PLAN_FIX_CORPORATE_ACTIONS_EX_DATE_20261120.md, docs/REPORT_FINAL_CORPORATE_ACTIONS_20261120.md | done | 2026-11-20 -> 0da4df4 | base main@99dabbe; shared files bump version (`pyproject.toml`, `CHANGELOG.md`, `README.md`, `CLAUDE.md`, `vnbroker/config.py`) do coordinator sửa với trailer `Claim-Deny-List` |
| cafef-reference | feat/cafef-reference | (main checkout) | CafeF reference layer (XLSX primary+JSON fallback), Vnbroker.reference('cafef'), route KBS/VCI adjusted=False sang CafeF | vnbroker/explorer/kbs/quote.py,vnbroker/explorer/vci/quote.py,vnbroker/api/quote.py,vnbroker/common/client.py,vnbroker/reference/**,tests/unit/explorer/test_quote_adjusted_parameter.py,tests/unit/core/test_adjusted_failover.py,tests/unit/reference/**,tests/contract/test_cafef_reference_contract.py,docs/PLAN_CAFEF_REFERENCE_20261124.md,docs/evidence/CAFEF_REFERENCE_LAYER_DESIGN_20261124.md,docs/evidence/CAFEF_PROVIDER_FEASIBILITY_20261124.md,docs/PLAN_KBS_VCI_ADJUSTED_PARAM_20261124.md,docs/evidence/KBS_VCI_RAW_PRICE_PROBE_20261124.md,docs/handoffs/HANDOFF_2026-11-24_KBS_VCI_ADJUSTED.md,docs/handoffs/HANDOFF_2026-11-24_CAFEF_REFERENCE.md,CHANGELOG.md | done (merged main) | 2026-11-24 | base e996cb4; audit 4 vong -> PASS; 31 targeted test xanh; check_all.ps1 FULL PASS (10/10 gate; can 2 env var: DNSE_API_SECRET placeholder + PYTEST_DEBUG_TEMPROOT); khong dung base.py/common/data.py/source_router.py/exceptions.py/__init__.py (claim stale); khong dang ky CafeF vao AUTO pool |
