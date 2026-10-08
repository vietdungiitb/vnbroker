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

## Ghi chú

- `in-progress` = đang giữ. Đổi sang `done` ngay sau khi ghi xong file cuối cùng.
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
