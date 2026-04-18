# JSON Schema mẫu - Core API Standardization

> Mục tiêu: Cung cấp schema tham chiếu để đội backend, frontend, QA và data pipeline kiểm thử đồng nhất.

---

## 1) Nguyên tắc schema

- Tất cả output chuẩn hoá phải có `source` và `source_used`.
- Field thiếu từ provider phải có mặt và đặt `null`, không bỏ cột.
- Date field chuẩn ISO-8601 (`YYYY-MM-DD` hoặc datetime ISO nếu có giờ).

---

## 2) Schema mẫu - Insider Deals

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "InsiderDealsNormalized",
  "type": "object",
  "required": [
    "symbol",
    "announce_date",
    "deal_date",
    "actor_name",
    "actor_type",
    "action",
    "quantity",
    "price",
    "ratio",
    "note",
    "source",
    "source_used"
  ],
  "properties": {
    "symbol": { "type": "string", "minLength": 1 },
    "announce_date": { "type": ["string", "null"], "format": "date" },
    "deal_date": { "type": ["string", "null"], "format": "date" },
    "actor_name": { "type": ["string", "null"] },
    "actor_type": { "type": ["string", "null"] },
    "action": { "type": ["string", "null"], "enum": ["BUY", "SELL", null] },
    "quantity": { "type": ["number", "null"] },
    "price": { "type": ["number", "null"] },
    "ratio": { "type": ["number", "null"] },
    "note": { "type": ["string", "null"] },
    "source": { "type": "string" },
    "source_used": { "type": "string" }
  },
  "additionalProperties": true
}
```

---

## 3) Schema mẫu - Financial Normalized

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "FinancialNormalized",
  "type": "object",
  "required": [
    "symbol",
    "period",
    "report_date",
    "metric",
    "value",
    "unit",
    "source",
    "source_used"
  ],
  "properties": {
    "symbol": { "type": "string", "minLength": 1 },
    "period": { "type": "string", "enum": ["quarter", "year"] },
    "report_date": { "type": ["string", "null"], "format": "date" },
    "metric": { "type": "string" },
    "value": { "type": ["number", "null"] },
    "unit": { "type": ["string", "null"] },
    "source": { "type": "string" },
    "source_used": { "type": "string" }
  },
  "additionalProperties": true
}
```

---

## 4) Schema mẫu - Industry Comparison

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "IndustryComparisonNormalized",
  "type": "object",
  "required": [
    "symbol",
    "industry_code",
    "industry_name",
    "peer_symbol",
    "metric",
    "peer_value",
    "industry_median",
    "industry_mean",
    "percentile",
    "zscore",
    "rank",
    "total_peers",
    "source",
    "source_used"
  ],
  "properties": {
    "symbol": { "type": "string" },
    "industry_code": { "type": ["string", "number", "null"] },
    "industry_name": { "type": ["string", "null"] },
    "peer_symbol": { "type": "string" },
    "metric": { "type": "string" },
    "peer_value": { "type": ["number", "null"] },
    "industry_median": { "type": ["number", "null"] },
    "industry_mean": { "type": ["number", "null"] },
    "percentile": { "type": ["number", "null"], "minimum": 0, "maximum": 100 },
    "zscore": { "type": ["number", "null"] },
    "rank": { "type": ["integer", "null"], "minimum": 1 },
    "total_peers": { "type": ["integer", "null"], "minimum": 1 },
    "source": { "type": "string" },
    "source_used": { "type": "string" }
  },
  "additionalProperties": true
}
```

---

## 5) Payload mẫu để QA dùng smoke test

### Insider sample

```json
{
  "symbol": "VCB",
  "announce_date": "2026-04-10",
  "deal_date": "2026-04-12",
  "actor_name": "Nguyen Van A",
  "actor_type": "CO_DONG_NOI_BO",
  "action": "SELL",
  "quantity": 120000,
  "price": 88500,
  "ratio": 0.12,
  "note": null,
  "source": "KBS",
  "source_used": "KBS"
}
```

### Financial sample

```json
{
  "symbol": "VCB",
  "period": "quarter",
  "report_date": "2025-12-31",
  "metric": "roe",
  "value": 0.184,
  "unit": "ratio",
  "source": "VCI",
  "source_used": "VCI"
}
```

### Industry sample

```json
{
  "symbol": "VCB",
  "industry_code": 11,
  "industry_name": "Ngân hàng",
  "peer_symbol": "TCB",
  "metric": "roe",
  "peer_value": 0.172,
  "industry_median": 0.158,
  "industry_mean": 0.161,
  "percentile": 78.5,
  "zscore": 0.91,
  "rank": 3,
  "total_peers": 14,
  "source": "MIXED",
  "source_used": "AUTO"
}
```

---

## 6) Quy tắc versioning schema

- Mọi thay đổi breaking schema phải tăng major version tài liệu.
- Mọi thay đổi thêm field optional tăng minor.
- QA snapshot test phải pin theo version schema tương ứng.
