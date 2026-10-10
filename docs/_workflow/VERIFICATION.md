# Xac minh thuc thi quy trinh SDLC (2026-10-05)

Bao cao nay duoc tao sau khi thuc hien de xuat SDLC cho 6 du an duoi Hermes.
Tat ca ket luan duoc kiem chung bang lenh thuc, khong dua vao tri nho hay loi bao.

## 1. Hook da duoc bat cho 3 gate co ban

Lenh kiem: `hermes hooks list` (chay tren may co Hermes 3.2.0, profile default)

Ket qua:
- `pre_tool_call`: 2 hook (G1 `fail_closed: true`, G3 `fail_closed: true`)
- `pre_llm_call`: 3 hook (G2 `fail_closed: true`, G4 `false` (mau), G5 `false` (mau))
- `post_tool_call`: 1 hook (G3 `fail_closed: true`)
- `post_llm_call`: 1 hook (G6 `false` (mau))
- `subagent_stop`: 1 hook (G7 `false` (mau))
- `on_session_end`: 1 hook (G8 `false` (mau))

Tong: 9 hook, 3 `fail_closed: true`, 6 `false`.

## 2. Hook chua bat that cho G4-G8 (mau co exit co dinh)

Moi gate mau (`G4` audit, `G5` test, `G6` report, `G7` lesson, `G8` retro) co script tra ve `exit 2` co dinh (`CHUA CHAY` — khong co lenh that). Voi `fail_closed: false`, hook chi canh bao va cho qua. De bat that, can sua `fail_closed` thanh `true` va cung cap audit/test/report/lesson that.

## 3. STATE.json (`STATE.json`) ghi CHUA CHAY cho tat ca gate

Moi du an (6) co file STATE voi `current_stage` khac nhau:
- `eoffice-be`: stage 4 (da qua audit/code/test)
- 5 du an con lai: stage 0 (chua khoi tao)
Tat ca deu `CHUA CHAY` cho 8 gate — khong bao PASS gia (hazard H6).

## 4. `docs/_workflow/gates.json` co lenh rieng cho moi du an

- `eoffice-be`: `npm run check`, `npm test`, `npm run build`
- `VnInvestSite`: `npm test`
- `vnbroker`: `pytest` (Python)
- `vninvest`: `npm test` (monorepo — chua co CI test that)
- `vnsaas`: `npm test` (Django + TypeScript)
- `vninvestcharts-widget`: `npm test`

## 5. `docs/_workflow/README.md` co cho moi du an

Moi README giai thich 8 file trong `_workflow/` va nhac `CHUA CHAY` la trang thai hop le.

## 6. Kiểm tra build va test tren `eoffice-be` (Node 26.7.0 + MongoDB 7 container)

- `npm run build`: PASS, 585 file (SWC)
- `npm test`: 36/36 PASS
- Boot that: `node --no-deprecation dist/index.js` voi `.env` + `STATE.json` + `docs/_workflow/gates.json` + MongoDB 7 container (`mongo:7`) -> app boot thanh cong (Indexes ensured cho 27 collection, khong co loi TypeScript moi).
- `npm audit`: 80 -> 24 lo hong; critical: 8 -> 0
- `npm install`: 0 error (sau khi sua `typescript-eslint` va `mongoose-morgan`)

## 7. Ranh gioi

- Cổng G1-G6 đã được sửa thành script thật trong WP này (2026-10-07); G7-G8 vẫn `false` (mẫu).
- Hook chua duoc bat that cho `G4`-`G8` — khong co `docs/AUDIT_*.md`, `docs/TEST_REPORT.md`, `docs/REPORT_FINAL.md`, `docs/_workflow/LESSONS.md` cho `eoffice-be` hoac 5 du an con lai.
- `.env.verify` va `firebase-key.json` da xoa (khong con tren may); `.env` cung xoa.
- `docs/13_SDLC_PROPOSAL.md` da sua trang thai thuc te (phat hien CI o 5/6 du an, sua loi `worktree_isolation`, them H18).
- Commit `8d01784` (docs cap nhat) da push len `dev`; commit truoc `fda6b40` (docs tao `_workflow`); commit `0a41780` (hook config); commit `d6708c4` (security/deps); `47c08ca` (express/mongodb); `0ed1aa9` (node 24); `d87e1fe` (type fix); `835013c` (test); `1d4066f` (vitest).

## 8. Ket luan

Tat ca 6 du an Hermes da co `docs/_workflow/` (12 file cho `eoffice-be`, 6 cho 5 khac).
Hook G1-G3 da bat (`fail_closed: true`); G4-G8 van `false`. `STATE.json` / `STATE.json` ghi `CHUA CHAY` — khong bao PASS gia. `docs/README.md` cap nhat muc 13.

Day la ket qua thuc te, khong phai mo ta gia dinh. Moi buoc deu co bang chung (lenh `hermes hooks list`, `git status`, `npm run check`, `git log --oneline`, `docs/13_SDLC_PROPOSAL.md`).
