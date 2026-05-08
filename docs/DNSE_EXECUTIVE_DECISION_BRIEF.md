# DNSE Executive Decision Brief

> Mục tiêu: một trang để ra quyết định nhanh trước khi triển khai.
>
> Trạng thái: Chốt quyết định
>
> Ngày: 2026-05-08

---

## 1. Quyết định cuối cùng

**Chọn mô hình hybrid.**

- **DNSE** là broker platform chính cho account, trading, token và các nghiệp vụ mở rộng riêng.
- **VCI/KBS** là lớp public market-data portable mặc định.
- **TCBS** chỉ giữ vai trò compatibility/fallback path.

Nói ngắn gọn:

- Nếu app cần **đọc + giao dịch** trên cùng một nền tảng, chọn **DNSE**.
- Nếu app chỉ cần **public market-data** và ưu tiên đổi provider dễ, chọn **VCI/KBS**.
- Nếu app cần **một kiến trúc bền vững lâu dài**, chọn **hybrid**: VCI/KBS cho lớp public, DNSE cho lớp broker.

---

## 2. Vì sao chọn như vậy

| Nhu cầu | Nên chọn | Lý do |
|---|---|---|
| Market-data-only | VCI / KBS | Portable tốt, listing/taxonomy mạnh, ít ràng buộc trading |
| Broker-integrated app | DNSE | Có account, OTP, trading token, post/put/cancel order |
| Dự án dài hạn cần cả hai | Hybrid | Public data giữ portable, broker data giữ chuyên biệt |
| Legacy compatibility | TCBS | Chỉ nên dùng như fallback/compatibility path |

### Kết luận kỹ thuật ngắn

- `history()` là phần portable nhất.
- `intraday()` có thể khác nhau ở độ ổn định live.
- `price_depth()` của DNSE không đồng nghĩa với order book level-2 truyền thống.
- Account/trading DNSE là năng lực riêng, không có provider khác thay thế 1:1.

---

## 3. Quy tắc ra quyết định

1. Nếu app cần tài khoản thật, OTP, trading token, lệnh thật → chọn DNSE.
2. Nếu app chỉ cần xem thị trường, screener, listing, taxonomy → chọn VCI hoặc KBS.
3. Nếu app cần vừa portable vừa có broker extension → chọn hybrid.
4. Không chọn TCBS làm primary cho kiến trúc mới nếu mục tiêu là broker platform.

---

## 4. Kiến trúc chốt

```text
Public market-data layer  ->  VCI / KBS
Broker layer              ->  DNSE
Compatibility layer       ->  TCBS
```

### Mỗi layer dùng để làm gì

- Public market-data layer: lịch sử giá, danh sách mã, lọc theo sàn/nhóm, dashboard, backtest nhẹ.
- Broker layer: account, margin, vị thế, OTP, trading token, đặt/sửa/hủy lệnh, đối soát.
- Compatibility layer: legacy, fallback, đối chiếu tạm thời.

---

## 5. Rủi ro nếu chọn sai

- Chọn DNSE cho mọi thứ sẽ làm app gắn chặt vào broker semantics, nhưng đổi lại có năng lực giao dịch thật.
- Chọn VCI/KBS cho mọi thứ sẽ giữ portability tốt, nhưng mất account/trading integration.
- Chọn TCBS làm primary sẽ dễ biến kiến trúc mới thành đường tương thích thay vì nền tảng mới.

---

## 6. Hành động tiếp theo

**Bắt đầu bằng Phase 0:** inventory capability, lock contract, và route từng nhóm hàm.

Phải chốt sớm:

- endpoint nào portable;
- endpoint nào DNSE-only;
- endpoint nào fallback;
- schema và error model;
- nguyên tắc đổi provider.

---

## 7. Kết luận một câu

**Dự án nên đi theo mô hình hybrid, với DNSE làm broker chính và VCI/KBS làm public data default; TCBS chỉ giữ vai trò compatibility/fallback.**
