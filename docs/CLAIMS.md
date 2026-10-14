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
Lesson ap dung: [L-E01, L-E02, L-E03, L-E05, L-E06, L-E07, L-R01, L-R04, L-P01, L-P03, L-P04, L-P05, L-P06].
