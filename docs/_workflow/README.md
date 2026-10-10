# Quy trình SDLC — dự án vnbroker (Python)

Tổng quan: 8 cổng G1–G8. G1–G6, G7, G8 đều là script `.sh` (G7/G8 do agent khác viết).

## Trạng thái

- `STATE.json`: trạng thái khởi tạo `CHUA CHAY` tất cả gate (G1–G8)
- `gates.json`: mô tả gate, chưa chạy
- `HOOK_CONFIG.template.md`: mẫu `hooks:` trong config.yaml
- `LESSONS.md`: ghi bài học cho G7

## Các cổng

| Cổng | Script | Mô tả |
|------|--------|-------|
| G1 | `gate-01-plan-approved.sh` | Chặn nếu không có `docs/PLAN_AUDIT*.md` chứa verdict `PASS` |
| G2 | `gate-02-plan-verified.sh` | Chặn nếu thiếu `docs/PLAN_*.md` hoặc thiếu mục bắt buộc |
| G3 | `gate-03-claims-check.sh` | Chặn nếu thiếu `docs/CLAIMS.md` hoặc `check-overlap.cjs` exit ≠ 0 |
| G4 | `gate-04-audit-pass.sh` | (do agent khác viết) |
| G5 | `gate-05-test-pass.sh` | Chạy `pytest tests/` — exit 2 nếu có lỗi |
| G6 | `gate-06-report-final.sh` | Chặn nếu thiếu `docs/REPORT_FINAL.md` hoặc không chứa `GATE` |
| G7 | `gate-07-close.md` | (do agent khác viết) |
| G8 | `gate-08-retro.md` | (do agent khác viết) |

## Lưu ý quan trọng

- **`CHUA CHAY` là trạng thái hợp lệ**, không phải `PASS`. Đây là trạng thái khởi tạo.
- Dự án này là **Python** nên lệnh kiểm thử là `pytest`, **không phải** `npm`.
- Mỗi script gate: exit 0 = cho qua, exit 2 = chặn.

## Để bật

Thêm `hooks:` vào `~/.hermes/config.yaml`, chạy `hermes hooks test`, `hermes hooks doctor`.
Không tự động bật — chỉ có mẫu chuẩn bị. Cần người dùng xác nhận trước khi kích hoạt.
