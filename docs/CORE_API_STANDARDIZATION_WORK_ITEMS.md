# Work Items - Danh sách ticket sẵn sàng cho đội code

> Mỗi mục dưới đây là một ticket có thể đưa thẳng vào board (Jira/Linear/GitHub Projects).

---

## Epic E1 - Insider Standardization

### E1-T1: Chuẩn hoá method surface Insider

Mục tiêu:
- Đảm bảo API công khai dùng một method chuẩn: insider_deals.

Phạm vi:
- Alias provider có method insider_trading.
- Đồng bộ facade gọi method chuẩn.

Acceptance:
- Source cố định và AUTO đều gọi insider_deals thành công.

### E1-T2: Insider normalization mapping

Mục tiêu:
- Chuẩn hoá cột đầu ra insider theo schema chuẩn.

Phạm vi:
- Mapping raw -> normalized.
- Null-safe cho field thiếu.

Acceptance:
- Output có đủ cột bắt buộc, không drop cột.

### E1-T3: Insider test suite

Mục tiêu:
- Chặn regression và schema drift.

Phạm vi:
- Unit + contract + integration.

Acceptance:
- Pass toàn bộ test insider.

---

## Epic E2 - Financial Core Standardization

### E2-T1: Period harmonization

Mục tiêu:
- Đồng nhất period year/quarter/annual.

Acceptance:
- Annual được map nhất quán sang year theo contract.

### E2-T2: Normalize 4 financial methods

Mục tiêu:
- Chuẩn hoá output cho balance_sheet, income_statement, cash_flow, ratio.

Acceptance:
- Schema hợp lệ cho mọi provider có capability.

### E2-T3: Add fundamental_snapshot

Mục tiêu:
- Thêm API tổng hợp nhanh metrics tài chính.

Acceptance:
- Có source/source_used, chạy được với source cố định và AUTO.

### E2-T4: Financial test suite

Acceptance:
- Contract tests pass 100%.

---

## Epic E3 - Industry Comparison API

### E3-T1: industry_peers

Mục tiêu:
- Trả danh sách peer theo ngành của symbol.

Acceptance:
- Peer list hợp lệ, không trùng.

### E3-T2: industry_benchmark

Mục tiêu:
- Tính benchmark median/mean theo metric.

Acceptance:
- Kết quả đúng với sample kiểm chứng.

### E3-T3: industry_rank

Mục tiêu:
- Tính rank/percentile/zscore.

Acceptance:
- Rank trong [1..N], percentile trong [0..100].

### E3-T4: Industry test suite

Acceptance:
- Unit + contract + integration pass.

---

## Epic E4 - Provider Extensibility

### E4-T1: Capability manifest template

Acceptance:
- Có template chuẩn cho provider mới.

### E4-T2: Mapping template

Acceptance:
- Có template raw -> normalized cho insider/financial.

### E4-T3: Onboarding dry-run mock provider

Acceptance:
- Onboard provider mock không sửa logic lõi.

---

## Epic E5 - Hardening and Release

### E5-T1: Regression full suite

Acceptance:
- Không còn regression critical.

### E5-T2: Docs and migration finalize

Acceptance:
- Docs đầy đủ, đồng bộ index.

### E5-T3: Release readiness signoff

Acceptance:
- QA + Tech Lead approve.

---

## Trường thông tin bắt buộc cho mỗi ticket

- Owner
- Estimate
- Dependency
- Risk level
- Acceptance criteria
- Test evidence link
- Docs updated
- Audit updated
