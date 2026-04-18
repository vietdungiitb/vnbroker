# Decision Log - Core API Standardization

> Ghi lại các quyết định kỹ thuật để tránh tranh luận lặp lại khi coding.

---

## D-001 - Contract-first implementation

Ngày: 2026-04-18

Quyết định:
- Chốt API contract và schema trước khi viết code.

Lý do:
- Giảm schema drift, giảm rework.

Hệ quả:
- Mọi task code phải tham chiếu RFC.

---

## D-002 - Method chuẩn cho insider là insider_deals

Ngày: 2026-04-18

Quyết định:
- API công khai chuẩn hoá dùng insider_deals.
- Provider khác tên method phải dùng alias.

Lý do:
- Tránh mismatch khi đổi source/AUTO.

Hệ quả:
- Cần backward compatibility cho method cũ.

---

## D-003 - Capability-driven routing

Ngày: 2026-04-18

Quyết định:
- Router ưu tiên provider có capability phù hợp.

Lý do:
- Không gọi nhầm provider thiếu tính năng.

Hệ quả:
- Bắt buộc có capability manifest cho provider.

---

## D-004 - Normalization sau fetch, trước return

Ngày: 2026-04-18

Quyết định:
- Mọi output public phải đi qua bước chuẩn hoá schema.

Lý do:
- Giữ output ổn định xuyên provider/failover.

Hệ quả:
- Tăng chi phí mapping, giảm regression dài hạn.

---

## D-005 - Provider extensibility without core rewrite

Ngày: 2026-04-18

Quyết định:
- Provider mới không được buộc sửa logic lõi.

Lý do:
- Giảm coupling và rủi ro khi mở rộng hệ thống.

Hệ quả:
- Cần template onboarding/mapping/capability chuẩn.

---

## D-006 - Mandatory centralized audit update

Ngày: 2026-04-18

Quyết định:
- Mọi task phải cập nhật file audit tập trung.

Lý do:
- Handoff và kiểm toán nhanh.

Hệ quả:
- PR thiếu audit update bị chặn merge.
