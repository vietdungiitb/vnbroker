# HANDOFF — Corporate actions Slice 4 + fix P0 (2026-11-20)

- **Repo/branch**: `vnbroker@main` · HEAD `a2b6ffb` · base `99dabbe` (3.8.1)
- **Trạng thái**: `done` — code + PyPI 3.8.2 publish/verify xong (15:03Z)
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

## Release (đã xong 15:03Z)

- Blocker billing cũ đã hết: `gh run rerun 44758095521` → **success** (build + publish).
- PyPI: `vnbroker==3.8.2`, wheel `628137 B` + sdist `521899 B`, yanked=false,
  upload `2026-11-20T15:03:56Z`. Wheel sha256 `899946f9…a3ab`, chứa `exrightDate`
  và `_is_event_row`; METADATA `Version: 3.8.2`.
- Mirror pip nội bộ còn lag (chỉ thấy tới 3.8.1) — dùng `--index-url https://pypi.org/simple`
  nếu bump pin bị "No matching distribution".

## Next steps (owner vninvest)

- Bump pin `3.8.1 → 3.8.2` + re-probe (kỳ vọng VNM 57 / FPT 79 / VCB 23), full BE/FE
  + deploy staging; sau đó mới đổi ingest sang field số (`FIELD_MAPPING_VNBROKER.md`).
  Giữ `CORPORATE_ACTIONS_ENABLED=False` tới khi xong.
- Evidence đầy đủ: `docs/REPORT_FINAL_CORPORATE_ACTIONS_20261120.md` §8,
  `docs/evidence/CORPORATE_ACTIONS_FIX_381_EVIDENCE_20261120.md`.
