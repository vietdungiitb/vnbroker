# vnbroker — Bộ Tài Liệu Phân Tích & Thiết Kế Hệ Thống

> **Thư viện Python** tích hợp dữ liệu thị trường chứng khoán Việt Nam.
>
> **Ngày lập:** 2026-10-08 · **Phạm vi:** audit tĩnh toàn bộ `vnbroker/` (33.773 dòng Python)
> · **Phương pháp:** đọc code + probe runtime thật trên mạng thật.

---

## Đọc file này trước. Vài điều cần biết ngay

1. **Đây là bộ tài liệu MỚI, không phải bản nâng cấp của `docs/` cũ.**
   Tài liệu cũ ở `docs/*.md` được xem là **tài liệu lịch sử** — nó lệch so với
   source hiện tại. Xem [ADR-0001](00-GOVERNANCE/adr/ADR-0001-tai-lien-moi-thay-tien-lien-cu.md).

2. **Mọi khẳng định đều có nguồn.** Mỗi câu kết luận trích tới `file.py:DÒNG` đã đọc thật.
   Không có kết luận nào về hành vi runtime được bịa ra.

3. **Ba mức độ tin cậy được đánh dấu nhất quán:**

   | Ký hiệu | Nghĩa |
   |:--|:--|
   | ✅ **XÁC MINH** | Đã đọc code, đã chạy lệnh kiểm chứng |
   | ⚠ **SUY LUẬN** | Suy từ hành vi code, chưa chạy thật |
   | ❓ **CHƯA XÁC MINH** | Cần người dự án cung cấp thông tin |

4. **Tài liệu tự cập nhật được một phần.** Các mục số liệu định lượng do script sinh ra,
   nên không thể lạc hậu nếu chạy script. Phần còn lại cần người cập nhật — có quy trình
   riêng cho việc đó.

---

## Bắt đầu ở đâu

| Bạn là | Đọc theo thứ tự này | Mục tiêu |
|:--|:--|:--|
| **Lãnh đạo / người quyết định** | [`01.01 Tóm tắt điều hành`](01-SYSTEM-OVERVIEW/01.01-executive-summary.md) → [`13.01 Lộ trình`](13-ROADMAP/13.01-roadmap.md) | Biết hệ thống ở đâu, cần làm gì tiếp |
| **Người mới vào dự án** | [`00.02 Thuật ngữ`](00-GOVERNANCE/00.02-glossary.md) → [`01.01`](01-SYSTEM-OVERVIEW/01.01-executive-summary.md) → [`03.01 Sơ đồ`](03-DIAGRAMS/03.01-diagram-catalog.md) → [`11.01 Cài đặt`](11-DEVELOPMENT/11.01-development-environment-setup.md) | Chạy được dự án trong 1 giờ |
| **Python developer** | [`02.01 Kiến trúc`](02-ARCHITECTURE/02.01-architecture-overview.md) → [`02.03 Bản đồ module`](02-ARCHITECTURE/02.03-module-map.md) → dossier module liên quan → [`11.03 Chuẩn code`](11-DEVELOPMENT/11.03-coding-standards.md) | Biết viết code đúng kiểu dự án này |
| **Kiến trúc sư** | [`02.01`](02-ARCHITECTURE/02.01-architecture-overview.md) → [`06.01 Mô hình dữ liệu`](06-DATA-ARCHITECTURE/06.01-data-model-overview.md) → [`13.02 Nợ kỹ thuật`](13-ROADMAP/13.02-technical-debt-register.md) → `00-GOVERNANCE/adr/` | Hiểu quyết định & nợ kỹ thuật |
| **DevOps** | [`09.01 Triển khai`](09-DEPLOYMENT-OPS/09.01-deployment-and-toolchain.md) → [`12.01 Runbook`](12-OPERATIONS/12.01-operations-runbook.md) | Dựng & vận hành |
| **Chuyên gia bảo mật** | [`10.02 Kiến trúc bảo mật`](10-QUALITY-SECURITY/10.02-security-architecture.md) → [`10.03 Sổ phát hiện`](10-QUALITY-SECURITY/10.03-findings-register.md) | Đánh giá rủi ro bảo mật |

---

## Cấu trúc thư mục

```
docs/system-design/
├── 00-GOVERNANCE/          Quản trị tài liệu, thuật ngữ, ADR
├── 01-SYSTEM-OVERVIEW/     Tóm tắt điều hành, bối cảnh hệ thống
├── 02-ARCHITECTURE/        Kiến trúc tổng thể, module map
├── 03-DIAGRAMS/            Sơ đồ kiến trúc, luồng, dữ liệu
├── 04-FUNCTIONAL-SPEC/     Đặc tả chức năng, business rules
├── 05-WORKFLOW/            Luồng nghiệp vụ
├── 06-DATA-ARCHITECTURE/   Mô hình dữ liệu, schema
├── 07-API-SPEC/            API conventions, endpoint catalog
├── 08-TECH-STACK/          Công nghệ, dependencies
├── 09-DEPLOYMENT-OPS/      Triển khai, vận hành
├── 10-QUALITY-SECURITY/    Testing, bảo mật
├── 11-DEVELOPMENT/         Môi trường dev, SDLC, coding standards
├── 12-OPERATIONS/          Runbook vận hành
├── 13-ROADMAP/             Lộ trình, technical debt
├── MODULES/                Dossier từng module
└── _meta/                  Script tự động, inventory
```

---

## Quy ước

- **Mã tài liệu:** `SD-<NHÓM>-<SỐ>` (ví dụ: `SD-GOV-01`, `SD-ARCH-01`)
- **Mức độ tin cậy:** ✅ XÁC MINH / ⚠ SUY LUẬN / ❓ CHƯA XÁC MINH
- **Trích dẫn:** mọi khẳng định kèm `file.py:DÒNG`
- **Ngôn ngữ:** tiếng Việt (thuật ngữ kỹ thuật giữ nguyên tiếng Anh)
