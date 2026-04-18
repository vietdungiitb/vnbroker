# RFC - Chuẩn hoá Core API cho Financial, Insider, Industry Comparison

> Mã RFC: VNSTOCK-RFC-CORE-2026-04
>
> Trạng thái: Implemented and verified
>
> Ngày: 2026-04-18
>
> Ngày chốt thực thi: 2026-04-18

---

## 1) Bối cảnh và mục tiêu

Thư viện hiện đã có nền adapter/provider tốt, nhưng contract API chưa đồng nhất hoàn toàn giữa các provider (đặc biệt nhóm Insider và dữ liệu ngành).

Mục tiêu RFC:
- Chuẩn hoá API công khai cho 3 nhóm:
  - Tài chính cơ bản
  - Giao dịch nội bộ
  - So sánh ngành
- Giữ tương thích kiến trúc hiện tại (`BaseAdapter`, `ProviderRegistry`, `AUTO` routing).
- Đảm bảo mở rộng provider mới với thay đổi tối thiểu.

Non-goals:
- Không thay đổi toàn bộ hệ thống router hiện tại.
- Không ép provider trả dữ liệu giống hệt từ raw layer; chuẩn hoá thực hiện tại normalization layer.

---

## 2) Nguyên tắc thiết kế

1. Contract-first: chốt signature, schema và error trước khi code.
2. Backward-compatible: duy trì API cũ, dùng alias/deprecation có thời gian chuyển đổi.
3. Provider-agnostic: business logic không hard-code vào từng provider.
4. Pluggable capability: feature được kích hoạt theo năng lực provider.
5. Deterministic schema: output cột chuẩn, metadata nhất quán.

---

## 3) API public chuẩn đề xuất

### 3.1 Financial (chuẩn hoá)

- `balance_sheet(symbol: str, period: str = "quarter", lang: str = "vi", dropna: bool = True, show_log: bool = False)`
- `income_statement(symbol: str, period: str = "quarter", lang: str = "vi", dropna: bool = True, show_log: bool = False)`
- `cash_flow(symbol: str, period: str = "quarter", lang: str = "vi", dropna: bool = True, show_log: bool = False)`
- `ratio(symbol: str, period: str = "quarter", dropna: bool = True, get_all: bool = True, show_log: bool = False)`
- `fundamental_snapshot(symbol: str, period: str = "quarter", metrics: list[str] | None = None, source_priority: list[str] | None = None)`

### 3.2 Insider (chuẩn hoá)

- `insider_deals(symbol: str, page: int = 1, page_size: int = 20, start_date: str | None = None, end_date: str | None = None, actor_type: str | None = None, show_log: bool = False)`

Ghi chú alias bắt buộc:
- Provider có method `insider_trading` phải expose alias `insider_deals`.

### 3.3 Industry Comparison (mới)

- `industry_peers(symbol: str, level: int = 4, include_exchanges: list[str] | None = None, max_peers: int = 100)`
- `industry_benchmark(symbol: str, metrics: list[str], period: str = "quarter", method: str = "median")`
- `industry_rank(symbol: str, metric: str, period: str = "quarter", method: str = "percentile")`

---

## 4) Schema chuẩn đầu ra

### 4.1 Financial normalized schema

Tối thiểu gồm:
- `symbol`
- `period`
- `report_date`
- `metric`
- `value`
- `unit`
- `source`
- `source_used`

### 4.2 Insider normalized schema

Tối thiểu gồm:
- `symbol`
- `announce_date`
- `deal_date`
- `actor_name`
- `actor_type`
- `action` (`BUY`/`SELL`)
- `quantity`
- `price`
- `ratio`
- `note`
- `source`
- `source_used`

### 4.3 Industry comparison schema

Tối thiểu gồm:
- `symbol`
- `industry_code`
- `industry_name`
- `peer_symbol`
- `metric`
- `peer_value`
- `industry_median`
- `industry_mean`
- `percentile`
- `zscore`
- `rank`
- `total_peers`
- `source`
- `source_used`

---

## 5) Capability matrix

Provider cần khai báo capability rõ ràng theo module:

- `supports_financial_core`
- `supports_insider_deals`
- `supports_industry_peers`
- `supports_industry_benchmark`
- `supports_industry_rank`

Router `AUTO` sử dụng capability để:
1. Chọn candidate phù hợp chức năng.
2. Failover sang provider khác có cùng capability.

---

## 6) Error contract

Chuẩn hoá error code theo nhóm:
- `PROVIDER_001`: provider không hỗ trợ
- `PROVIDER_002`: method không hỗ trợ
- `DATA_001`: fetch lỗi
- `DATA_002`: schema mapping lỗi
- `DATA_003`: thiếu trường bắt buộc

Quy tắc:
- Exception phải chứa: `error_code`, `message`, `details`.
- Khi failover thất bại toàn bộ, trả lỗi có danh sách provider đã thử.

---

## 7) Backward compatibility

1. Giữ method cũ trong 2 release cycle.
2. Method cũ gọi vào method chuẩn qua alias.
3. Gắn warning deprecate có deadline loại bỏ.

---

## 8) Tích hợp với kiến trúc hiện có

Các điểm tích hợp chính:
- Adapter dispatch: `vnstock/base.py`
- Provider registration: `vnstock/core/registry.py`
- AUTO routing/failover: `vnstock/core/source_router.py`
- Public API lớp data facade: `vnstock/common/data.py`

Không thay đổi lớn ở các lớp này; chỉ mở rộng theo nguyên tắc plug-in.

---

## 9) Tiêu chí hoàn tất RFC implementation

- API contract được implement đầy đủ cho KBS/VCI/TCBS (mức hỗ trợ tuỳ capability).
- Schema output đồng nhất cho mọi provider có hỗ trợ.
- AUTO failover không phá schema.
- Bộ test contract + integration + regression pass.
