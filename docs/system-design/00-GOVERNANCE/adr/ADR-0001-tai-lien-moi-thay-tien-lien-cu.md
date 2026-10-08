# ADR-0001: Tài liệu mới thay tài liệu cũ

| | |
|:--|:--|
| **Mã ADR** | `ADR-0001` |
| **Ngày** | 2026-10-08 |
| **Trạng thái** | Đã chấp nhận |
| **Người đề xuất** | Tech Lead |
| **Người phê duyệt** | Chủ dự án |

---

## 1. Bối cảnh

Bộ tài liệu cũ trong `docs/*.md` đã lệch so với codebase hiện tại:

- Mô tả 48 registration, thực tế có nhiều hơn
- Mô tả failover hoạt động, thực tế chỉ chạy trong test
- Mô tả bulk chuẩn hoá, thực tế bulk không qua chuẩn hoá
- Thiếu tài liệu về Tier 1 Data Engine (WP-1→5)

## 2. Quyết định

**Tạo bộ tài liệu mới** trong `docs/system-design/` theo chuẩn ISO/IEC/IEEE 29148:

- 13 nhóm tài liệu (00-GOVERNANCE → 13-ROADMAP)
- Mọi khẳng định truy vết `file.py:DÒNG`
- Script tự động kiểm tra đồng bộ
- Quy trình kiểm soát thay đổi

## 3. Hệ quả

### 3.1 Tích cực

- Tài liệu truy vết được tới mã nguồn
- Script tự động phát hiện lệch
- Quy trình rõ ràng cho việc cập nhật

### 3.2 Tiêu cực

- Tài liệu cũ không còn maintain (có thể gây nhầm lẫn)
- Cần thời gian để duy trì tài liệu mới

### 3.3 Rủi ro

| Rủi ro | Giảm thiểu |
|:--|:--|
| Tài liệu mới lạc hậu | Script `gen-inventory.py --check` |
| Tài liệu cũ gây nhầm lẫn | Ghi rõ trong README tài liệu mới |
