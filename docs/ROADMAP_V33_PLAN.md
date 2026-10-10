# Kế hoạch v3.3+ — Độc lập hoàn toàn từ vnbroker 3.5.0

> Trạng thái: vnbroker 3.5.0 đã hoàn thành kiến trúc hai tầng (Direct Provider + Broker Lane). Codebase độc lập, không phụ thuộc nguồn ngoại.

## Mục tiêu tiếp theo

1. Hoàn thiện tài liệu người dùng (`docs/` nội bộ repo).
2. Đóng gói v3.5.0 với CI sạch (lint / type / test 0 lỗi).
3. Xóa triệt để các tham chiếu cũ đến dự án khác (đã hoàn thành qua kế hoạch `PLAN_CLEAR_VNSTOCK_REFERENCES.md`).

## Phạm vi

- `docs/` — tài liệu người phát triển và người dùng.
- `tests/unit/` — mở rộng phủ kín cho broker lane (SSI, TCBS, DNSE).
- `vnbroker/config.py` — cập nhật `VERSION_NOTICES` và `release_url` cho các phiên bản mới.

> Không còn phụ thuộc kiến trúc hay bản quyền từ bất kỳ dự án ngoại nào. Mọi tính năng được thiết kế và triển khai nội bộ từ vnbroker 3.5.0.
