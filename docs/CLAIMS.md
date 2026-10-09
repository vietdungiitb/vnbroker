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
| a1-bars | feat/a1-bars | ../tcbs-a1-bars | GĐ1 nối bars + bỏ NotImplementedError | explorer/tcbs/bars.py (mới), explorer/tcbs/quote.py, tests/unit/explorer/tcbs/test_tcbs_bars.py | in-progress | 2026-10-09 | quote.py đã 801L, phải tách module mới |
| a2-ws | feat/a2-ws | ../tcbs-a2-ws | GĐ2 viết lại WebSocket protocol pipe | explorer/tcbs/websocket.py, ws_models.py, tests/unit/explorer/tcbs/test_tcbs_ws_protocol.py | in-progress | 2026-10-09 | không network trong test |
| a3-legacy | feat/a3-legacy | ../tcbs-a3-legacy | GĐ3 xoá 19 path legacy | broker/tcbs/account.py, broker/tcbs/equity.py, tests/unit/broker/tcbs/test_tcbs_legacy_removed.py | in-progress | 2026-10-09 | xoá theo quyết định Owner, chưa verify server |
| coordinator | docs/plan-tcbs | (main) | Plan + claim + audit + merge | docs/PLAN_TCBS_REBUILD.md | in-progress | 2026-10-09 | giai đoạn 4-5 chưa cắt lát |

**Rời nhau đã kiểm bằng script, không bằng mắt:** tập file của 3 agent giao nhau = ∅.

**Baseline gate @ bec8b82** (đo, không ước lượng):
- pytest tests/ -q --timeout=300 → exit 0, 1497 passed, 26 skipped
- uff check vnbroker → exit 0
- scripts/check_mypy_baseline.py → exit 0
- uff check tests → **exit 1, 13 lỗi KNOWN-RED có sẵn** — không đòi xanh, chỉ đòi không tăng
- 13 file vượt 800L (4 thuộc TCBS) — CLAUDE.md:15 "800 max"

**Cổng Giai đoạn 0 (probe 19 path) đã bị bỏ** — Owner quyết xoá theo tài liệu chính
thức, không cần probe. Ghi rõ: **xoá theo quyết định Owner, chưa verify bằng server.**
