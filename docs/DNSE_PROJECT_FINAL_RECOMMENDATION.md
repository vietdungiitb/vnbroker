# DNSE Project Final Recommendation

> Mục tiêu: chốt hướng cho dự án trước khi ra quyết định cuối cùng.
>
> Trạng thái: Final recommendation
>
> Ngày: 2026-05-08

---

## 1. Quyết định chốt

**Khuyến nghị cuối cùng cho dự án này là mô hình hybrid:**

- **DNSE** là broker platform chính cho phần account, trading, token, và các nghiệp vụ mở rộng riêng cho người dùng có tài khoản DNSE.
- **VCI/KBS** là lớp public market-data portable chính cho những phần cần đổi provider ít thay đổi code.
- **TCBS** chỉ nên là compatibility path, không nên là provider chính cho kiến trúc mới.

Nói ngắn gọn:

- Nếu app cần **đọc + giao dịch** trên cùng một nền tảng, chọn **DNSE**.
- Nếu app chỉ cần **public market-data** và ưu tiên đổi provider dễ, chọn **VCI/KBS**.
- Nếu app cần **một kiến trúc bền vững lâu dài**, chọn **hybrid**: VCI/KBS cho lớp public, DNSE cho lớp broker.

---

## 2. Vì sao đây là quyết định đúng

### 2.1 DNSE là provider duy nhất trong bộ này có broker OpenAPI thật

DNSE không chỉ có market-data. DNSE còn có account, orders, OTP, trading token, post/put/cancel order và các nhánh nghiệp vụ liên quan. Điều này biến DNSE thành một broker layer thực thụ, không phải chỉ là một nguồn dữ liệu.

### 2.2 VCI/KBS mạnh hơn cho public market-data portable

VCI và KBS phù hợp hơn nếu bạn muốn:

- giữ API public portable;
- dễ đổi provider hơn;
- có listing/taxonomy rộng;
- tránh mang theo lớp account/trading phức tạp.

### 2.3 TCBS phù hợp hơn như compatibility path

TCBS public layer trong kiến trúc hiện tại chủ yếu nên được xem là đường tương thích/fallback, không phải lựa chọn chính cho một nền tảng broker mới.

### 2.4 Live contract DNSE đã đủ để đi theo hướng broker

Trong repo hiện tại:

- `history()` của DNSE đã khớp contract live.
- `price_depth()` của DNSE đã hoạt động, nhưng semantics là security definition chứ không phải sổ lệnh level-2 truyền thống.
- `get_trades()` vẫn có thể là gap live ở một số môi trường, nên intraday phải xử lý best-effort.

Điều này có nghĩa là DNSE đủ tốt để làm broker layer, nhưng không nên ép nó giả dạng hoàn toàn giống VCI/KBS ở lớp public market-data.

---

## 3. Kiến trúc chốt cho dự án

```text
Ứng dụng của bạn
  ├── Public Market Data Layer
  │     ├── VCI
  │     └── KBS
  ├── Broker Layer
  │     └── DNSE
  └── Compatibility Layer
        └── TCBS (chỉ khi cần legacy/fallback)
```

### 3.1 Public Market Data Layer

Layer này phục vụ:

- lịch sử giá;
- danh sách mã;
- lọc theo sàn/nhóm;
- phân tích thị trường;
- backtest nhẹ;
- dashboard market-data.

Khuyến nghị: dùng **VCI/KBS** làm default.

### 3.2 Broker Layer

Layer này phục vụ:

- tài khoản;
- số dư;
- margin;
- vị thế;
- OTP;
- trading token;
- đặt/sửa/hủy lệnh;
- đối soát trạng thái.

Khuyến nghị: dùng **DNSE** làm default.

### 3.3 Compatibility Layer

Layer này chỉ dùng khi:

- đang giữ code legacy;
- cần chạy thử đối chiếu;
- cần fallback tạm thời.

Khuyến nghị: **TCBS** chỉ ở đây.

---

## 4. Quy tắc ra quyết định cuối cùng

### 4.1 Nếu bạn muốn một app chỉ đọc thị trường

Chọn **VCI hoặc KBS**.

Lý do:

- portable tốt;
- coverage listing rộng;
- ít phụ thuộc broker account/trading.

### 4.2 Nếu bạn muốn một app vừa đọc vừa giao dịch thật

Chọn **DNSE**.

Lý do:

- có full broker OpenAPI;
- phù hợp làm cầu nối giữa app và công ty chứng khoán;
- hỗ trợ toàn bộ vòng đời từ account đến order.

### 4.3 Nếu bạn muốn một dự án bền vững lâu dài

Chọn **hybrid**.

Lý do:

- public data giữ portable;
- broker data giữ chuyên biệt;
- giảm lock-in;
- dễ mở rộng thành platform.

---

## 5. Tài liệu quyết định theo tình huống

| Tình huống | Quyết định khuyến nghị | Ghi chú |
|---|---|---|
| Chỉ xem chart / lịch sử giá | VCI hoặc KBS | Không cần broker layer |
| Screener / listing / taxonomy rộng | KBS hoặc VCI | Coverage mạnh hơn |
| Ứng dụng có account/trading thật | DNSE | Đây là vùng DNSE-only |
| Multi-provider analytics / failover | VCI + KBS, DNSE làm extension | Tối ưu portability |
| Legacy TCBS | TCBS nhưng chỉ như compatibility path | Không nên làm primary |

---

## 6. Điều không nên làm

1. Không nên ép DNSE phải giống VCI/KBS ở mọi semantics.
2. Không nên dùng `price_depth()` của DNSE như sổ lệnh level-2 truyền thống.
3. Không nên coi TCBS là provider chính nếu mục tiêu là kiến trúc mới.
4. Không nên trộn account/trading DNSE vào lớp public portable.
5. Không nên kỳ vọng đổi provider là dữ liệu y hệt tuyệt đối.

---

## 7. Nếu buộc phải chọn chỉ một provider

Nếu bạn bắt buộc chỉ được chọn **một** provider cho toàn dự án:

- **Chọn DNSE** nếu mục tiêu có account/trading thật, vì đây là nơi tạo ra giá trị sản phẩm cao nhất cho một app broker-integrated.
- **Chọn VCI hoặc KBS** nếu mục tiêu chỉ là market-data-only và bạn muốn tối đa hóa khả năng portable.

TCBS không phải lựa chọn tôi khuyến nghị làm primary cho dự án mới trong bối cảnh này.

---

## 8. Khuyến nghị hành động tiếp theo

### Phương án tôi khuyến nghị

1. Chốt **hybrid architecture**.
2. Chốt **DNSE** làm broker layer chính.
3. Chốt **VCI/KBS** làm public market-data default.
4. Chốt **TCBS** chỉ là compatibility path.
5. Bắt đầu bằng **Phase 0**: inventory capability, lock contract, và xác định route từng nhóm hàm.

### Vì sao nên bắt đầu bằng Phase 0

Phase 0 không phải để code nhiều. Phase 0 để tránh đổi hướng về sau:

- chốt endpoint nào portable;
- chốt endpoint nào DNSE-only;
- chốt endpoint nào fallback;
- chốt schema và error model;
- chốt nguyên tắc đổi provider.

Nếu Phase 0 được chốt đúng, các phase sau sẽ có đường đi rõ ràng và ít phải sửa ngược.

---

## 9. Kết luận cuối cùng

**Kết luận chốt cho dự án này:**

- **DNSE** là lựa chọn đúng cho broker integration và cho phần mở rộng riêng của người dùng DNSE.
- **VCI/KBS** là lựa chọn đúng cho lớp public market-data portable.
- **TCBS** chỉ nên giữ vai trò compatibility/fallback.
- **Hybrid** là kiến trúc cân bằng nhất cho dự án này.

Nếu bạn muốn một câu trả lời duy nhất để ra quyết định: **chọn hybrid, với DNSE làm broker chính và VCI/KBS làm public data default**.
