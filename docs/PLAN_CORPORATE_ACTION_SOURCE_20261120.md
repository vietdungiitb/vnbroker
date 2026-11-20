# Corporate Action Source — Implementation Plan (rev2, 4 slice)

> **Trạng thái**: DRAFT — chưa khai claim, chưa code. Chờ owner chốt §F (5 câu) + re-audit vòng 2.
> **Nguồn**: phản biện độc lập `vninvest@252435379:docs/AUDIT_VNBROKER_PLAN_CRITIQUE_20261120.md` (PR #460, ledger vninvest Entry 571).
> **Base đo lường**: `vnbroker@main:eac374b` (`pyproject.toml:7` = 3.8.0), git status sạch. Không đọc file tiếng Việt qua console.

**Goal:** Cung cấp field số + API corporate-action ổn định trong package, để consumer (vninvest) bỏ được regex và bật flag `CORPORATE_ACTIONS_ENABLED` — kèm đường release tới đúng phiên bản consumer đang pin.

**Architecture:** 3 slice code (parser → unified API → auth/docs) + **Slice 4 release/bump pin** (blocker C-01). `events()` additive, không đổi contract cũ. Không đưa `adj_close` vào package.

**Tech Stack:** Python 3.10+, pandas, pytest, `@dynamic_method`, `ProviderAuthError`.

**Lessons áp dụng**: `[L-R04, L-E01, L-E02, L-E06, L-P03, L-P04, L-P05]`
- L-R04: không khẳng định runtime `dividends()` khi chưa có JWT thật (§F.5).
- L-E01/E02: mọi số kèm lệnh tái tạo tại đúng commit; spec/pin phải nằm trong repo.
- L-E06: fail-before phải gọi hàm thật, test ĐỎ trên code cũ (không assert hình thức).
- L-P03: chốt phương án trong plan — KHÔNG đụng `common/data.py` (claim `w34-ratelimit`, `docs/CLAIMS.md:47`).
- L-P04: bảng chủ file kể cả `__init__.py` barrel export.
- L-P05: auditor độc lập read-only ở B3 + B8, tự chạy lại gate.

**MANDATORY CHECKLIST (từ 3 nhóm lesson)** — tick trước khi coi slice xong:
- [ ] Số trong plan/report có lệnh tái tạo + chạy ở đúng commit; worktree đo riêng (L-P01, L-E01)
- [ ] Không khẳng định runtime TCBS khi chưa JWT; ghi `CHƯA XÁC MINH` (L-R04)
- [ ] Test fail-before gọi hàm thật, ĐỎ trước / XANH sau, có lệnh + output (L-E06)
- [ ] Bảng chủ file gồm cả `__init__.py`/export; không đụng file claim in-progress (L-P04, L-P03)
- [ ] Auditor read-only tự chạy lại gate, không tin số self-report (L-P05)
- [ ] Gate đỏ → chạy lại lần 2, ghi cả hai; test mạng đánh dấu flaky (L-E04)

---

## Global Constraints (mọi slice kế thừa)

- Không commit thẳng `main`; branch `feat/corporate-actions-source`, khai claim 1 dòng trong `docs/CLAIMS.md` TRƯỚC dòng code đầu tiên; tên agent = `corporate-actions-source` (bỏ tiền tố `feat/`).
- **Cấm đụng** `vnbroker/common/data.py` (claim `w34-ratelimit` in-progress, `docs/CLAIMS.md:47`).
- `events()` giữ nguyên; method mới additive. `adj_close`/`adj_factor` KHÔNG vào package.
- KHÔNG sửa KBS mù (`kbs/company.py:605-619`) khi chưa có response payload thật.
- KHÔNG gửi token qua doc; mọi kết luận auth ghi rõ nguồn: source hay runtime-probe.
- Golden: VNM 3 cặp cùng ex_date thật (`2023-08-03`, `2024-09-24`, `2025-10-16`) — nguồn `vninvest@252435379:docs/AUDIT_VNBROKER_PLAN_CRITIQUE_20261120.md` §TÓM TẮT #3 / C-03; **VCB KHÔNG cùng ex_date** (`2025-03-12` vs `2025-10-03`). Khi code phải thêm lệnh probe tái tạo 3 cặp này (L-E01).
- `group_id` = string `f"{symbol}:{ex_date}"` (JSON-serializable), KHÔNG tuple.
- `source_event_id` = VCI `id` pass-through + phơi raw; KHÔNG dedup theo `raw_title`.

## Ma trận REQ → slice → test (cập nhật từ audit)

| Finding audit | Xử lý | Test ghim |
|---|---|---|
| C-01 BLOCKER version trap | Slice 4 | `test_release_pin_contract.py` (assert pin == released version) |
| C-02 ESOP nhầm thành thưởng | Slice 1 + slice sửa song song vninvest | `test_esop_pct_is_unparsed` (FPT `0.5%`/`0.2%`) |
| C-03 Golden VCB sai | Slice 1 | `test_vnm_same_ex_date_pairs` (3 cặp) + `test_vcb_different_ex_dates` |
| C-04 TCBS docs/message | Slice 3 | `test_dividends_error_mentions_jwt` + grep 2 doc files |
| C-05 ID/group_id | Slice 2 | `test_group_id_string`, `test_two_div_same_ex_date_kept` |
| C-06 AUTO fallback | Slice 2 | `test_auto_fallback_to_vci`, `test_explicit_kbs_raises` |
| C-07 claim stale | §Phase 0 | kiểm `docs/CLAIMS.md` trước khai |
| C-08 lessons | header plan | `check_lessons.py` exit 0 |
| C-09 record_date/payment_date null | Slice 1 | `test_vci_null_dates_not_derived` |
| C-10 tuple không serialize | Slice 2 | `test_group_id_string` |

## Bảng chủ file (L-P04)

| File | Slice | Chủ | Ghi chú |
|---|---|---|---|
| `vnbroker/common/corporate_actions.py` (mới) | 1 | agent này | parser + normalize, ~150L |
| `vnbroker/explorer/vci/company.py` | 1 | agent này | thêm `corporate_actions()`, additive |
| `vnbroker/explorer/vci/__init__.py` | 1 | agent này | export nếu cần |
| `vnbroker/api/company.py` | 2 | agent này | thêm `@dynamic_method corporate_actions()` |
| `vnbroker/core/exceptions.py` | 3 | agent này | chỉ nếu cần mã lỗi mới (đã có PROVIDER_AUTH) |
| `vnbroker/explorer/tcbs/IMPLEMENTATION_SUMMARY.md`, `vnbroker/explorer/tcbs/MIGRATION_GUIDE.md` | 3 | agent này | sửa 4 dòng `TCBS_AUTH_TOKEN` (`:146`, `:36/:44/:47`) |
| `explorer/tcbs/company.py:468-499` | 3 | agent này | message dividends() nhắc JWT |
| `pyproject.toml` | 4 | owner | release version (không tự sửa) |
| `vninvest requirements.txt:38` | 4 | vninvest owner | bump pin (không tự sửa) |
| `vnbroker/common/data.py` | — | w34-ratelimit (in-progress) | **CẤM ĐỤNG** |

---

## Phase 0 — 5 câu §F cần owner chốt TRƯỚC KHI CODE

| # | Câu hỏi | Khuyến nghị mặc định (an toàn, không tự áp nếu owner chốt khác) | Ai chốt |
|---|---|---|---|
| F1 | Slice 4 ai làm, khi nào? | Owner vnbroker release 3.8.x; vninvest owner bump pin + re-probe. Không có F1 ⇒ 3 slice chỉ có giá trị tương lai. | vnbroker + vninvest owner |
| F2 | Thu hẹp `stock_ratio_pct` cho ISS? | **CÓ** — chỉ `Cổ phiếu thưởng` / `Trả Cổ tức bằng Cổ phiếu` mới set ratio; ESOP/CBCNV ⇒ `unparsed`. Sửa song song vninvest PR #458. | owner |
| F3 | 950+1.500 (3 cặp VNM) có thật? | Coi là 2 dòng riêng **để dedup**, nhưng KHÔNG assert tổng 2.450 là sự thật kinh tế cho tới đối chiếu disclosure/TCBS (giữ flag False). | vninvest owner |
| F4 | VCI `id` ổn định dài hạn? | Không có tài liệu ⇒ pass-through + expose raw + fallback hash, không dedup theo title. | vnbroker owner |
| F5 | Có JWT TCBS staging? | Nếu có → probe dividends runtime + đối chiếu VCB; nếu không → ghi `CHƯA XÁC MINH`, không khẳng định runtime. | owner |

Gate: auditor read-only verdict `PASS`/`AGREE` mới khai claim.

---

## Slice 1 — Parser + field số (R1, R6, C-02, C-03, C-09)

**Files:** Create `vnbroker/common/corporate_actions.py`; Modify `vnbroker/explorer/vci/company.py` (+ method mới); Modify `vnbroker/explorer/vci/__init__.py` (export).

**Interfaces:**
- Consumes: raw payload `news-events-for-chart` (`vci/company.py:104-119`).
- Produces: `ParsedAmount(cash_amount: Decimal|None, stock_ratio_pct: Decimal|None, parse_status: str, ambiguous_cash_pct: bool)`; `parse_event_title(title: str, action_type: str) -> ParsedAmount`; `normalize_events(rows: list[dict]) -> pd.DataFrame` với cột contract.

- [ ] **Step 1 — fail-before, hàm thật (L-E06)**: viết test gọi `parse_event_title()` trực tiếp; assert ĐỎ trên code cũ (`ImportError`/hàm chưa có), dán lệnh + output.
- [ ] **Step 2 — test golden + edge (C-02/C-03)**:
  - `test_two_div_same_ex_date`: VNM 950 + 1.500 cùng `2024-09-24` ⇒ 2 dòng riêng, `group_id='VNM:2024-09-24'`, KHÔNG gộp.
  - `test_vnm_same_ex_date_pairs`: 3 cặp `2023-08-03/2024-09-24/2025-10-16`.
  - `test_vcb_different_ex_dates`: 49.5% `2025-03-12`, 450 VND `2025-10-03` ⇒ 2 group_id khác nhau.
  - `test_esop_pct_is_unparsed`: FPT `Phát hành cho CBCNV tỉ lệ 0.5%` / `0.2%` ⇒ `stock_ratio_pct=None`, `parse_status='unparsed'`, `ambiguous_cash_pct=False`.
  - `test_bonus_pct_parsed`: `Cổ phiếu thưởng tỉ lệ 15%` ⇒ `stock_ratio_pct=15`.
  - `test_div_pct_ambiguous`: DIV + `20%` ⇒ `unparsed`, không coi là ratio.
  - `test_vci_null_dates_not_derived`: `record_date`/`payment_date` = None (VCI chỉ có `public_date`/`exright_date`/`display_date`).
- [ ] **Step 3 — implement parser**: regex `(?P<amt>\d[\d.,]*)\s*VND` + `(?P<pct>\d+(?:\.\d+)?)\s*%`; normalize dấu nghìn; `Decimal`. Chỉ set `stock_ratio_pct` khi title chứa `Cổ phiếu thưởng` hoặc `Trả Cổ tức bằng Cổ phiếu`.
- [ ] **Step 4 — implement `VCI.corporate_actions(from_date, to_date, event_codes='DIV,ISS')`**: gọi `_fetch_news_events`, map cột, giữ `id`, thêm `source='VCI'`, `fetched_at`, `group_id=str`.
- [ ] **Step 5 — chạy test XANH**; `git diff --numstat` khớp; commit `feat: add corporate action parser with ESOP guard`.

## Slice 2 — API thống nhất + semantics (R2, R3, C-05, C-06, C-10)

**Files:** Modify `vnbroker/api/company.py` (+ `@dynamic_method corporate_actions()`).

- [ ] **Step 1 — fail-before**: test gọi `Company(source='AUTO').corporate_actions(...)` ⇒ ĐỎ trước khi có method.
- [ ] **Step 2 — test**: `test_auto_fallback_to_vci` (KBS trả rỗng ⇒ AUTO dùng VCI, field `source='VCI'`); `test_explicit_kbs_raises` (`NotImplementedError` rõ, KHÔNG trả rỗng); `test_group_id_string`; `test_two_div_same_ex_date_kept` (2 dòng, không dedup theo title); `test_idempotent_same_id`.
- [ ] **Step 3 — implement**: `@dynamic_method` (`base.py:44-65`) để đi fallback từ `AUTO` (`core/source_router.py:493`). KHÔNG đụng `common/data.py`.
- [ ] **Step 4 — XANH + commit** `feat: add unified corporate_actions API`.

## Slice 3 — Auth/docs (R5, C-04)

**Files:** Modify `vnbroker/explorer/tcbs/IMPLEMENTATION_SUMMARY.md:146`, `vnbroker/explorer/tcbs/MIGRATION_GUIDE.md:36,44,47`, `vnbroker/explorer/tcbs/company.py:468-499`.

- [ ] **Step 1**: grep `TCBS_AUTH_TOKEN` trong **2 file doc**, kỳ vọng **4 hit** (`MIGRATION_GUIDE.md:36` = `your-jwt-token`, `:44` = `old_token`, `:47` = `new_jwt_token`; `IMPLEMENTATION_SUMMARY.md:146` = `your-jwt-token`) + xác nhận message `dividends()` (`company.py:468-499`) thiếu JWT. Lấy số bằng lệnh, không đếm tay (L-E01).
- [ ] **Step 2**: sửa thành `TCBS_JWT_TOKEN`; thêm message trong `dividends()` nhắc `ProviderAuthError.PROVIDER_AUTH` + env đúng.
- [ ] **Step 3**: test `test_dividends_error_mentions_jwt` (assert chuỗi `TCBS_JWT_TOKEN`); grep lại 0 hit sai.
- [ ] **Step 4 — runtime (F5)**: nếu có JWT ⇒ probe `dividends()` thật + đối chiếu VCB; nếu không ⇒ ghi `CHƯA XÁC MINH`, KHÔNG báo PASS runtime.
- [ ] **Step 5 — commit** `docs: fix TCBS token env guidance`.

## Slice 4 — Release + bump pin (C-01, BLOCKER)

**Files:** `pyproject.toml` (owner vnbroker), `vninvest/packages/core/backend/requirements.txt:38` (owner vninvest).

- [ ] **Step 1**: owner release `3.8.x` (từ `3.8.0` hiện tại) sau khi merge slice 1–3 + CHANGELOG.
- [ ] **Step 2**: vninvest owner bump pin `vnbroker==3.7.2` → `3.8.x`, re-probe 3 mã VNM/FPT/VCB trên container.
- [ ] **Step 3**: contract test `test_release_pin_contract` — assert pin == released version (L-E02: pin nằm trong repo).
- [ ] **Step 4**: ghi rõ timeline vào plan; KHÔNG tự sửa pin/version (owner).

---

## Gate & bàn giao

- Trước code: `check_lessons.py` exit 0; auditor verdict PASS/AGREE.
- Sau code: `scripts/check_all.ps1`, `pytest` targeted (ghi cả 2 lần nếu flaky – L-E04), `git status`, `git diff --numstat`.
- Re-audit vòng 2: 0 blocker + 0 major; merge commit; sync system-design/docs; đóng claim; ledger Entry tiếp theo.
- Không merge khi còn `CHƯA XÁC MINH` chưa được owner chấp nhận (đặc biệt F5 runtime dividends).

---

## BẢN GHI THỰC THI (2026-11-20) — Slice 1–3 xong, Slice 4 chờ owner

**Branch**: `feat/corporate-actions-source` · base `main@eac374b` · claim `corporate-actions-source`.

| Commit | Nội dung |
|---|---|
| `2a953a3` | claim + plan rev2 |
| `3cfebb9` | Slice 1 — parser + `VCI.corporate_actions` (ESOP guard, golden VNM/VCB) |
| `78009ab` | Slice 2 — facade `@dynamic_method corporate_actions` |
| `c3c028e` | Slice 3 — 4 dòng doc TCBS + message `dividends()` → `TCBS_JWT_TOKEN` |
| `6020aac` | ruff F401 |
| `a410e14` | bổ sung test AUTO fallback (auditor B8 F1) |

**Gates đã chạy thật**
- `python -m pytest <4 file slice> -q` → **23 passed** (lệnh nằm ở §Slice tương ứng).
- `python -m ruff check <8 file đổi>` → `All checks passed!`.
- `python scripts/check_lessons.py` → exit 0 (26/40 lesson, sạch).
- `git diff --numstat` khớp; `git status` sạch trước mỗi commit.
- Fail-before ĐỎ bằng chứng: Slice 1 `ModuleNotFoundError: vnbroker.common.corporate_actions`; VCI method `AttributeError`; Slice 3 docs/message RED trước khi sửa.

**Gate KHÔNG chạy được / CHƯA CHẠY (trung thực)**
- `scripts/check_all.ps1 -Quick` → exit 2 `[FATAL] Khong tim thay .venv\Scripts\python.exe` — env issue, KHÔNG tự cài.
- `scripts/check_version_sync.py` → FAIL do dist editable cài 1.0.2 vs pyproject 3.8.0 — env issue, không phải code đổi.
- Full suite / contract suite — CHƯA CHẠY.
- Runtime `dividends()` với JWT thật (§F.5) — CHƯA XÁC MINH.
- Regression `test_company_auto_failover_insider.py` → 1 failed **giống hệt trên code cũ** (`2a953a3` worktree) ⇒ pre-existing, KHÔNG tính regression.

**Audit trail**
- vòng 2 plan: AGREE (13/13 citation, 3 minor đã sửa).
- B8 code: AGREE (0 blocker/0 major), 3 minor — F1 đã đóng bằng `a410e14`; F2/F3 là diễn đạt plan (giữ nguyên code).

**Slice 4 (chờ owner — KHÔNG tự làm)**
- Owner vnbroker release `3.8.x` + CHANGELOG; vninvest owner bump pin `3.7.2 → 3.8.x` + re-probe. Trước đó 3 slice code chỉ có giá trị bản tương lai.

**Lessons áp dụng (đã tick)**: `[L-R04, L-E01, L-E02, L-E06, L-P01, L-P03, L-P04, L-P05]`.
