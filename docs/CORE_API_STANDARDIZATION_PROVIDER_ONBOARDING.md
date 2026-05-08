# Provider Onboarding Guide - Chuẩn mở rộng không sửa lõi

> Mục tiêu: thêm provider mới cho core modules với thay đổi tối thiểu.

---

## 1) Triết lý onboarding

Provider mới không được yêu cầu sửa business logic lõi.

Bắt buộc chỉ thêm:
1. Provider class implement method theo protocol.
2. Register vào ProviderRegistry.
3. Capability manifest.
4. Schema mapping file.
5. Test contract tương ứng.

---

## 2) Checklist onboarding bắt buộc

1. Tạo class provider trong `vnbroker/explorer/<provider>/` hoặc `vnbroker/connector/<provider>/`.
2. Implement method chuẩn theo nhóm module được hỗ trợ.
3. Register provider bằng `ProviderRegistry.register(module, source, class)`.
4. Khai báo capability:
- supports_financial_core
- supports_insider_deals
- supports_industry_peers
- supports_industry_benchmark
- supports_industry_rank
5. Tạo schema mapping cho output raw -> normalized.
6. Viết test:
- unit test method
- contract test schema
- integration smoke test
7. Cập nhật docs + audit file.

---

## 3) Cấu trúc file khuyến nghị

- `vnbroker/explorer/<provider>/company.py`
- `vnbroker/explorer/<provider>/financial.py`
- `vnbroker/explorer/<provider>/listing.py`
- `vnbroker/explorer/<provider>/mappings/insider_mapping.py`
- `vnbroker/explorer/<provider>/mappings/financial_mapping.py`
- `vnbroker/explorer/<provider>/capabilities.py`

---

## 4) Chuẩn capability manifest

Ví dụ cấu trúc:

```python
CAPABILITIES = {
    "company": {
        "supports_insider_deals": True,
    },
    "financial": {
        "supports_financial_core": True,
    },
    "industry": {
        "supports_industry_peers": True,
        "supports_industry_benchmark": False,
        "supports_industry_rank": False,
    },
}
```

Quy tắc:
- Thiếu capability xem như `False`.
- Router chỉ chọn provider có capability phù hợp.

---

## 5) Chuẩn schema mapping

Mỗi provider có map riêng, ví dụ insider:

```python
INSIDER_MAP = {
    "raw_announce_date": "announce_date",
    "raw_actor": "actor_name",
    "raw_action": "action",
    "raw_qty": "quantity",
    "raw_price": "price",
}
```

Quy tắc:
- Sau rename phải đảm bảo đủ cột bắt buộc.
- Cột thiếu phải được tạo với giá trị null.

---

## 6) Quy tắc tương thích ngược

- Nếu provider đã có method tên cũ, thêm alias method chuẩn.
- Không xoá method cũ ngay; đánh dấu deprecate.

---

## 7) Definition of Done cho provider mới

1. Có thể gọi qua source cố định.
2. Có thể tham gia AUTO nếu capability cho phép.
3. Pass contract test cho module tương ứng.
4. Docs + audit cập nhật đầy đủ.
