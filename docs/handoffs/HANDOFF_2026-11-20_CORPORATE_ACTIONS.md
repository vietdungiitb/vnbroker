# HANDOFF — Corporate actions Slice 4 + fix P0 (2026-11-20)

- **Repo/branch**: `vnbroker@main` · HEAD `a2b6ffb` · base `99dabbe` (3.8.1)
- **Trạng thái**: `in-progress` — code xong, release PyPI **bị chặn**
- **Claim**: `corporate-actions-exrightdate` = `done` (`eaa7487`)

## Kết quả + evidence

1. Slice 4 phía vninvest đã verify: PR #464/#465/#466/#467 merge commits
   `b8514bf2 / 6100c5d6 / 1374ddb4 / 2d9c669c`; pin trên `origin/dev` = `vnbroker==3.8.1`;
   PyPI 3.8.1 upload `2026-11-20T13:17:40.951813Z`, wheel + sdist, `yanked=false`.
2. P0 3.8.1 xác nhận & sửa: `vnbroker/common/corporate_actions.py:155` thiếu raw key
   `exrightDate` ⇒ `ex_date=None` 100%; news rows (`isEvent=False`, không `eventCode`)
   lẫn vào contract. Fix tại `2305e1e`, bump `6560eda`, merge `0da4df4`.
3. Test: fail-before `5 failed / 1 passed` → sau fix 25 targeted passed, 149 contract,
   full `2304 passed / 30 skipped / 2 failed` (cả 2 do môi trường: thiếu `DNSE_API_SECRET`,
   dist editable 1.0.2). Live VNM 57 / FPT 79 / VCB 23 dòng, 0 `ex_date=None`.
4. Tag `v3.8.2` → `eaa7487`, GitHub Release published `2026-11-20T14:55:12Z`.

## Blocker / next steps (owner)

- CI publish `44758095521` failed 2 lần (kể cả re-run): *"recent account payments have
  failed or your spending limit needs to be increased"*. `https://pypi.org/pypi/vnbroker/3.8.2/json`
  → **HTTP 404**. Không có `.pypirc`/token local để publish thay (OIDC-only).
- Owner: khôi phục billing GitHub → `gh run rerun 44758095521` → verify PyPI 3.8.2 →
  báo vninvest bump pin `3.8.1 → 3.8.2` + re-probe (57/79/23) → mới đổi ingest sang
  field số. Giữ `CORPORATE_ACTIONS_ENABLED=False`.
- Evidence đầy đủ: `docs/REPORT_FINAL_CORPORATE_ACTIONS_20261120.md` §7,
  `docs/evidence/CORPORATE_ACTIONS_FIX_381_EVIDENCE_20261120.md`.
