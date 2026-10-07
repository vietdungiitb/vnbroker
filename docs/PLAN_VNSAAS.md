# PLAN — WP-VNSAAS-INTEGRATION: Xác thực & Quản lý quyền vnbroker qua vnsaas

- **Task ID:** `WP-VNSAAS-INTEGRATION`
- **Planner:** Hermes Agent
- **Ngày:** 2026-10-05
- **Workdir:** `C:/Mujoco Projects/vnbroker`
- **Trạng thái:** `DRAFT`
- **Quy trình:** Theo `skills/software-development/multi-agent-workflow` (9 giai đoạn, 6 Gate)
- **Ngôn ngữ kế hoạch:** Tiếng Việt (theo yêu cầu người dùng); tên file/code giữ tiếng Anh.

---

## 1. Mục tiêu

**Hiện trạng:** `vnbroker` (v3.5.0, repo `C:/Mujoco Projects/vnbroker`) là thư viện Python độc lập. `vnsaas` (repo `C:/Mujoco Projects/vnsaas`) là nền tảng SaaS B2B quản lý quyền phần mềm (tenant, PAT, entitlement, license, billing). Hai dự án chưa có cơ chế kết nối: `vnbroker` không có module xác thực qua `vnsaas`; `vnsaas` đã thiết kế 9 bảng dữ liệu (`Product`, `ProductTier`, `Capability`, `TierCapability`, `Meter`, `TierMeterLimit`, `Entitlement`, `EntitlementCapabilityGrant`, `UsageRecord`) và cơ chế PAT (`identity_access/models.py:28-100` — HMAC-SHA256 + pepper), nhưng chưa có adapter SDK cho `vnbroker`.

**Mục tiêu (đo được):** Xây dựng code tích hợp (`vnbroker-sdk-vnsaas`) cho phép:
1. `vnbroker` (khi là thư viện trong dự án khách) gọi `/api/v1/entitlements/verify` của `vnsaas` qua PAT để kiểm quyền (`allowed`, `reason_code`, `capability`);
2. `vnbroker` nhận License Key từ `vnsaas` (`Product.license_type`) và kiểm tra hết hạn trước khi khởi tạo adapter (`Quote`, `Broker`, `Brokerage`);
3. SDK tự động từ chối gọi broker API (`place_order`, `cancel_order`, `get_holdings`) khi `allowed == false` hoặc `approval_pending`, sử dụng lại `broker/security/guards.py` (`dry_run=True` mặc định, `enable_write()` opt-in);
4. **Rate limit cho Tier 1 (ẩn danh):** Nếu không có PAT/License Key (`VN_SAAS_PAT` hoặc `VN_SAAS_LICENSE_KEY` rỗng), SDK áp dụng rate limit `vnbroker_RATE_LIMIT_RPM` (mặc định 300, `vnbroker/config.py:26`) nhưng cắt giảm còn **giới hạn số request/ngày thấp** (ví dụ: 50 request/ngày hoặc 10 request/phút) để tạo khác biệt khuyến khích đăng ký `vnsaas`. Nếu có PAT hợp lệ (`identity_access/authentication.py`), rate limit dựa trên `Entitlement.tier` (`TierMeterLimit` từ `catalog/`) qua `QuotaHistory.meter_code`; nếu có License Key (`Product.license_type`), rate limit mở rộng hoặc không giới hạn theo `UsageRecord`.
5. Code mới không sửa `vnbroker` core ngoại trừ thêm một `sdk/` adapter; `brokerage/` phải được đóng `write_gate` trước (P1 gap đã phát hiện ở `docs/SAAS_PLATFORM_DESIGN_20261002.md:530`).

**Trạng thái đích kiểm chứng:** `pytest tests/unit/sdk/test_vnsaas_gate.py` pass; `docs/PLAN_AUDIT.md` có verdict `PASS`; không có file nào ngoài `vnbroker/sdk/` bị sửa (`git diff --name-only`).

---

## 2. In-scope (phạm vi sửa)

| # | Path (glob) | Mô tả thay đổi dự kiến |
|---|---|---|
| 1 | `vnbroker/sdk/` (mới) | Adapter SDK gọi `vnsaas` API: `client.py` (verify entitlement), `license.py` (đọc/kiểm License Key), `gate.py` (kết hợp `broker/security/guards.py`) |
| 2 | `vnbroker/sdk/vnsaas_client.py` | Gọi `POST /api/v1/entitlements/verify` (Bearer PAT) và xử lý `reason_code` (`ok`, `pat_invalid`, `tier_insufficient`, `approval_pending`, `license_expired`, `quota_exceeded`) |
| 3 | `vnbroker/sdk/license_validator.py` | Đọc `VN_SAAS_LICENSE_KEY` từ env khách, kiểm tra định dạng và hết hạn (`expires_at` từ `Entitlement`) |
|| 4 | `vnbroker/sdk/gate_adapter.py` | Adapter kết nối `Capability.requires_approval` (`catalog.Capability`) với `broker/security/guards.py`; thêm `dry_run` cho `brokerage/` (P1 gap) |
|| 4b | `vnbroker/sdk/rate_limit.py` (mới) | Rate limit cho Tier 1 ẩn danh (`vnbroker/config.py:26` `RATE_LIMIT_RPM` cắt giảm thành 10 req/phút hoặc 50/ngày); nếu có PAT → dùng `TierMeterLimit` (`catalog/`); nếu có License Key → mở rộng theo `UsageRecord` (`entitlement/`) |
| 5 | `tests/unit/sdk/` (mới) | Unit test mock `vnsaas` API; test `TC-ENT-09` (thu hồi quyền → chặn ngay), `TC-ENT-10` (đọc tenant khác → chặn) |
| 6 | `docs/PLAN_VNSAAS.md` (tài liệu này) | Bản kế hoạch; `docs/AUDIT_VNSAAS.md` (sau khi code) |

**Cụ thể file mới (dự kiến):**
- `vnbroker/sdk/__init__.py`
- `vnbroker/sdk/vnsaas_client.py`
- `vnbroker/sdk/license_validator.py`
- `vnbroker/sdk/gate_adapter.py`
- `vnbroker/sdk/rate_limit.py` (mới) — rate limit Tier 1
- `tests/unit/sdk/test_vnsaas_client.py`
- `tests/unit/sdk/test_license_validator.py`
- `tests/unit/sdk/test_gate_adapter.py`
- `docs/PLAN_AUDIT.md`
- `docs/CLAIMS.md` (cập nhật claim)

---

## 3. Non-goals (KHÔNG làm)

- **KHÔNG** sửa `vnbroker/core/`, `explorer/`, `broker/` (trừ `broker/security/guards.py` nếu cần mở rộng nhỏ); `vnsaas` giữ nguyên 13 920 LOC backend, 596 test pass.
- **KHÔNG** thêm sản phẩm thứ 4 (`vnsaas` đã có `Product` generic; không hardcode tên sản phẩm theo `D04:§8` và `AGENTS.md:§8`).
- **KHÔNG** viết lại billing (`Invoice.line_items`, `Subscription`, `QuotaHistory`) — tái sử dụng từ `vnsaas` (`packages/core/backend/src/commercial/`).
- **KHÔNG** thêm logic giao dịch tự động (`auto-trading loop`) — giữ `dry_run=True` mặc định (`guards.py:24`).
- **KHÔNG** sửa `vnbroker` `LICENSE.md` — Mục 0 (`licenses.md:9-16`) đã giải phóng chủ sở hữu; chỉ thêm văn bản cấp quyền thương mại cho khách (`docs/SAAS_PLATFORM_DESIGN_20261002.md:§6.4`).
- **KHÔNG** thêm WebSocket stream mới (`broker/ssi/stream.py`) cho `vnsaas` — chỉ dùng `SSIMarketService` read-only (`explorer/ssi/_auth.py:145`).
- **KHÔNG** viết UI (`packages/web/`) — `vnsaas` đã có 0 màn hình nghiệp vụ (`README.md:169`); SDK là backend.

---

## 4. Claim dự kiến

- `docs/PLAN_VNSAAS.md` (file này) — `done`
- `vnbroker/sdk/*` — `in-progress` (agent phụ trách SDK)
- `tests/unit/sdk/*` — `in-progress` (agent phụ trách test)
- `docs/CLAIMS.md` — cập nhật trước khi sửa dòng đầu tiên (`AGENTS.md:§6.3`)

**Không giao với claim khác:** Kiểm tra `docs/CLAIMS.md` trước dispatch (`node scripts/check-multi-agent.mjs` ở `vnsaas` hoặc `git status --short` ở `vnbroker`).

---

## 5. Tác động repo khác

| Hệ thống bị ảnh hưởng | Bản chất ảnh hưởng | Cần thông báo ai |
|---|---|---|
| `vnsaas` backend (`packages/core/backend/src/`) | SDK `vnbroker` sẽ gọi `/api/v1/entitlements/verify` và `PAT` authentication (`identity_access/`) | Dev `vnsaas` (chủ repo) |
| `vninvest` (`C:/Mujoco Projects/vninvest/`) | Port từ `vninvest` (`AGENTS.md:§16`) — cần xác nhận `verify-vninvest-port.mjs` trước commit (`docs/development/PORT_RULES.md`) | Dev `vninvest` |
| `vnbroker` CI (`.github/workflows/`) | Thêm test SDK (`tests/unit/sdk/`); không sửa `tests/unit/api/` hiện có (1001 test pass `CLAUDE.md`) | DevOps `vnbroker` |
| `vnbroker` `docs/` | Thêm `PLAN_AUDIT.md`, `CLAIMS.md`; không sửa `docs/audit/` hoặc `docs/references/` hiện có | Reviewer `vnbroker` |

---

## 6. Cách kiểm chứng (Gate lệnh cụ thể — bắt buộc)

| # | Lệnh | Exit code mong đợi | Ý nghĩa khi pass |
|---|---|---|---|
| G1 (Plan) | `cat docs/PLAN_VNSAAS.md \| grep -c "In-scope\|Non-goals\|Claim"` | `3` | Kế hoạch có đủ 3 mục bắt buộc |
| G2 (Audit Plan) | `grep -E "PASS\|FAIL\|REJECT" docs/PLAN_AUDIT.md` | `PASS` (exit 0) | Audit kế hoạch pass |
| G3 (Claim) | `node scripts/check-multi-agent.mjs` (nếu có ở `vnsaas`); hoặc `git status --short` rỗng | `0` | Không file chồng lấn |
| G4 (Code) | `git diff HEAD --name-only` có file mới `vnbroker/sdk/*` và `tests/unit/sdk/*` | `exit 0` (khác rỗng) | Code thực sự sửa file |
| G5 (Audit Code) | `node scripts/check-gates.cjs --test docs/TEST_REPORT.md --audit docs/AUDIT_VNSAAS.md` (hoặc tương đương) | `0` | 0 lỗi audit, confidence high |
| G6 (Test) | `pytest tests/unit/sdk/ -v --timeout=60` | `0` | Mọi test SDK pass |
| G7 (Report Final) | `cat docs/REPORT_FINAL.md \| grep -c "PASS\|Gate"` | `>= 6` | Report xác nhận đủ 6 gate |

**Lệnh phụ (không thay thế gate):**
- `python -m py_compile vnbroker/sdk/*.py` → `0` (kiểm cú pháp — thay thế `mypy` nếu môi trường không có `mypy` đầy đủ, theo `CLAUDE.md:§Dev Workflow`).
- `grep -n "print(" vnbroker/sdk/*.py` → `0` (cấm `print()` tiếng Việt — `AGENTS.md:§4`).
- `grep -n "core.utils.client" vnbroker/sdk/*.py` → `0` (cấm import `core.utils.client` trong SDK, theo `CLAUDE.md` checklist).

---

## 7. Rollback

- **Lệnh:** `git checkout -- vnbroker/sdk/ tests/unit/sdk/ docs/PLAN_VNSAAS.md` (nếu sửa sai); hoặc `git revert <sha>` cho commit claim.
- **Kiểm tra sau rollback:** `git status --porcelain` → rỗng; `git log --oneline -3` vẫn còn commit trước khi sửa.
- **Nếu sửa `docs/CLAIMS.md`:** Không dùng `git revert` cho file claim (append-only); sửa lại dòng `done` thành `blocked` hoặc `rejected` bằng tay, ghi lý do.

---

## 8. Rủi ro

| Rủi ro | Xác suất | Tác động | Giảm thiểu |
|---|---|---|---|
| **P1 gap `brokerage/` thiếu `write_gate`** (`docs/SAAS_PLATFORM_DESIGN_20261002.md:§10`) | Cao | Cao (ai implement `brokerage/` mới sẽ không có `dry_run`) | Trước khi SDK kết nối `brokerage/`, thêm `write_gate` vào `brokerage/base.py` và `brokerage/tcbs/client.py` — dùng lại `broker/security/guards.py` (`dry_run`, `is_write_enabled`) |
| **Rò rỉ dữ liệu tenant** (`TC-ENT-10`) | Trung bình | Rất cao (vi phạm ràng buộc `AGENTS.md:§2`) | Mọi truy vấn SDK phải lọc `tenant_id`; `test_gate_adapter.py` phải có `TC-ENT-10` mock |
| **Bí mật PAT/License Key lọt git** (`AGENTS.md:§2.1`, `P0-SEC-01`) | Thấp | Cao (thu hồi khóa → xoay khóa → lọc lịch sử) | `scripts/scan-secrets.mjs` (hoặc `grep -rni "token_urlsafe\|secret\|key" . --exclude-dir=*.env`) chạy trước commit; `.env` và `.env.*` đã bị loại trừ (`README.md:§13.5`) |
| **Port từ `vninvest` sai** (`AGENTS.md:§16.3`) — agent báo "xây mới" nhưng thực tế `vninvest` đã có (`packages/core/backend/src/commercial/urls.py`) | Trung bình | Cao (ước lượng sai ~7 ngày-công) | Trước khi lập kế hoạch chi tiết cho `SDK adapter`, chạy `node scripts/verify-vninvest-port.mjs --strict` và đọc `docs/development/PORT_RULES.md` |
| **Không sửa `Subscription.tenant` từ `OneToOneField` → `ForeignKey`** (`SAAS_PLATFORM_DESIGN_20261002.md:§7.3.1`) | Trung bình | Cao (mỗi tenant chỉ mua 1 sản phẩm → không thể bán `vnbroker-data` + `vnbroker-brokerage` cùng lúc) | SDK phải đọc `Subscription` đã sửa (`FK` + `product`); nếu `vnsaas` chưa sửa, SDK vẫn đọc đúng nhưng ghi log cảnh báo |

---

## 9. Điều kiện Done

- [ ] Tất cả lệnh mục 6 (`G1`–`G6`) trả exit code như mong đợi (`G6`: `pytest` exit `0`).
- [ ] `git status --porcelain` chỉ chứa file mới trong `vnbroker/sdk/`, `tests/unit/sdk/`, `docs/PLAN_VNSAAS.md`, `docs/AUDIT_VNSAAS.md`, `docs/CLAIMS.md` (không sửa core).
- [ ] `broker/security/guards.py` vẫn giữ `dry_run = kwargs.get("dry_run", True)` (`line 24`); nếu sửa `brokerage/` thì thêm `write_gate` và kiểm lại bằng `grep -n "write_gate\|dry_run" vnbroker/brokerage/*.py`.
- [ ] `docs/AUDIT_VNSAAS.md` có verdict `PASS` và liệt kê đủ `file_path:line_number` cho mọi khẳng định.
- [ ] `docs/CLAIMS.md` có dòng `in-progress` cho agent giữ `vnbroker/sdk/` và dòng `done` sau khi hoàn thành (`AGENTS.md:§6.4`).
- [ ] `docs/REPORT_FINAL.md` xác nhận 6 gate (`G1`–`G6`) và ghi rõ phần nào `CHƯA CHẠY` (nếu có `P7` — đóng `brokerage/` gap chưa hoàn thành).

---

## 10. Tài liệu tham chiếu (bắt buộc đọc trước khi sửa)

- `docs/SAAS_PLATFORM_DESIGN_20261002.md` (§1–§15) — đặc tả tích hợp, rủi ro pháp lý, mô hình dữ liệu 9 bảng.
- `AGENTS.md` (§1–§16) — quy trình multi-agent, 3 rủi ro chặn, port từ `vninvest`, cổng chất lượng.
- `docs/development/PORT_RULES.md` — quy tắc port từ `vninvest` (`vnsaas` đã có `packages/core/backend/src/commercial/`).
- `vnbroker/LICENSE.md` (§0–§6) — quyền chủ sở hữu, hạn chế bên thứ ba, văn bản cấp quyền thương mại.
- `vnbroker/broker/security/guards.py` (`line 24`, `60-69`) — `dry_run`, `is_write_enabled`, `enable_write()`.
- `vnbroker/brokerage/base.py` (`line 1-9`, `125`, `278`, `283`, `288`) — `BrokerageBase` thiếu `write_gate` (P1 gap).
- `packages/core/backend/src/identity_access/models.py` (`line 28-100`) — PAT hash `hmac_sha256`, `generate_pat()`, `verify_pat()`.
- `packages/core/backend/src/entitlement/models.py` (`line 40-282`) — `Entitlement`, `CapabilityGrant`, `fail-closed`.
- `CLAUDE.md` (§Tech Stack, §Architecture, §Testing, §Security) — yêu cầu TDD, `mypy --strict`, `pytest`, `dry_run`.

---

## 11. Lộ trình phát triển (đề xuất theo `SAAS_PLATFORM_DESIGN_20261002.md:§12`)

|| Giai đoạn | Nội dung | Phụ thuộc | Kiểm chứng |
|---|---|---|---|---|
| P0 | 9 bảng dữ liệu `vnsaas` + sửa `Subscription` | Không cần `vnbroker` | `pytest` `vnsaas` pass (`596 passed`) |
| P1 | Đóng `brokerage/` `write_gate` + `dry_run` | Độc lập (`P7`) | `grep -n "write_gate" vnbroker/brokerage/*.py` có kết quả |
| P2 | SDK `vnbroker/sdk/vnsaas_client.py` — verify entitlement | P0 + P1 | `tests/unit/sdk/test_vnsaas_client.py` pass |
| P3 | `license_validator.py` — kiểm `License Key` | P0 | `tests/unit/sdk/test_license_validator.py` pass |
| P4 | `gate_adapter.py` — kết nối `Capability` + `guards.py` | P1 | `tests/unit/sdk/test_gate_adapter.py` pass (`TC-ENT-09`, `TC-ENT-10`) |
| P5 | Tích hợp `vnbroker` (adapter) + viết `docs/AUDIT_VNSAAS.md` | P2–P4 | `pytest tests/unit/sdk/` exit `0` |
| P6 | Hợp đồng B2B + văn bản cấp quyền (`LICENSE.md` Mục 0) | Owner (`vnbroker`) | `docs/SAAS_PLATFORM_DESIGN_20261002.md:§6.4` — văn bản 1 trang |
| P7 | Audit + triển khai (`docs/REPORT_FINAL.md`) | P5 + P6 | 6 gate pass |

**Điều kiện tiên quyết cho P6 (owner):**
- [x] `LICENSE.md` Mục 0 đã xác nhận chủ sở hữu (`vnbroker/LICENSE.md:9-16`).
- [ ] Viết văn bản cấp giấy phép thương mại cho khách (`SAAS_PLATFORM_DESIGN_20261002.md:§6.3` — Cách B khuyến nghị).
- [ ] Xác nhận phạm vi hoạt động pháp lý với luật sư (nếu bán tier C — `brokerage.place_order` có `requires_approval=True`).

**Ghi chú `CHƯA CHẠY`:** `P1` (`brokerage/` `write_gate`) và `P6` (tư vấn luật) là `CHƯA CHẠY` — không phải `PASS`. `P0` (`vnsaas` backend) đã có `13 920 LOC`, `596 passed`; `P2–P5` là mục tiêu kế hoạch này.

---

## 12. Bằng chứng (đã đọc trực tiếp)

|| Nội dung | Nguồn (`file:line`) |
|---|---|---|
| `vnbroker` `LICENSE.md` Mục 0 | Chủ sở hữu không ràng buộc, sản phẩm nội bộ (`VNInvest`) không cần xin phép | `vnbroker/LICENSE.md:9-16` |
| `vnbroker` `broker/security/guards.py` | `dry_run = True` mặc định; `enable_write()` opt-in | `vnbroker/broker/security/guards.py:24`, `:60-69` |
| `vnbroker` `brokerage/` thiếu `write_gate` | `grep` 0 hit trên `brokerage/*.py` | `docs/SAAS_PLATFORM_DESIGN_20261002.md:§10.1`, `§5.2` |
| `vnsaas` PAT mechanism | `hash_pat()` HMAC-SHA256 + pepper (`PAT_PEPPER`) | `packages/core/backend/src/identity_access/models.py:28-56` |
| `vnsaas` `Entitlement` + `CapabilityGrant` | `fail-closed`, `revoke_requires_reason`, `legal_terms_version` | `packages/core/backend/src/entitlement/models.py:40-282` |
| `vnsaas` `Subscription` cần sửa | `OneToOneField` → `ForeignKey` (`product`) | `docs/SAAS_PLATFORM_DESIGN_20261002.md:§7.3.1` |
| `vnbroker` `broker/ssi/_auth.py` | Coupling chỉ ở tầng auth plumbing, không ở trading | `vnbroker/explorer/ssi/_auth.py:19-25`, `:145` |
| `vnbroker` 1001 test pass | `CLAUDE.md` — `pytest tests/unit -v` | `CLAUDE.md:§Testing` |
| `vnsaas` 596 test pass | `README.md` — `22 PASS / 0 FAIL / 0 NOT RUN` | `README.md:§State` (`line 164-166`) |
| `vnbroker` `brokerage/` mồ côi | `grep` chỉ ra `brokerage/tcbs/client.py:20` | `docs/SAAS_PLATFORM_DESIGN_20261002.md:§5.3` |

---

*Bản kế hoạch này được lập theo kỹ thuật công nghiệp (`SWEBOK v4`, `ISO/IEC/IEEE 29148`) và quy trình `multi-agent-workflow` (9 giai đoạn, 6 Gate). Nếu người dùng muốn chuyển sang `CODE` (giai đoạn 4) hoặc `AUDIT PLAN` (giai đoạn 2), vui lòng báo — kế hoạch này là `DRAFT` và sẽ được cập nhật `docs/CLAIMS.md` trước khi sửa dòng đầu tiên (`AGENTS.md:§6.3`).*
