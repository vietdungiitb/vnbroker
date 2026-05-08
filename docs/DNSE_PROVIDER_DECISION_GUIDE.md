# DNSE Provider Decision Guide

> Mục tiêu: biến ma trận so sánh provider thành khuyến nghị ra quyết định.
>
> Dùng khi bạn cần chốt một trong ba hướng: (1) chỉ làm public market-data, (2) làm broker-integrated app với DNSE, hoặc (3) làm kiến trúc hybrid vừa portable vừa có DNSE OpenAPI riêng.
>
> Ngày: 2026-05-08

---

## 1. Kết luận ngắn trước khi đi vào bảng

Nếu mục tiêu của bạn là **một ứng dụng có thể đọc thị trường, xem tài khoản, đặt/sửa/hủy lệnh và đi sâu vào toàn bộ dịch vụ DNSE**, thì DNSE phải là **broker layer chính** của hệ thống.

Nếu mục tiêu của bạn là **một lớp API public portable cho market-data** mà đổi provider ít phải sửa code, thì VCI và KBS vẫn là hai lựa chọn rất mạnh. TCBS nên được xem là lựa chọn tương thích/fallback hơn là lựa chọn primary cho một kiến trúc mới.

Quan điểm thực dụng:

- **DNSE**: chọn khi cần broker integration.
- **VCI/KBS**: chọn khi cần public market-data coverage tốt và portable.
- **TCBS**: chọn khi đã phụ thuộc hệ sinh thái đó hoặc cần KBS-backed public behavior.

---

## 2. Bối cảnh ra quyết định

Tài liệu này không cố gắng trả lời câu hỏi “provider nào hay nhất tuyệt đối”. Nó trả lời câu hỏi thực tế hơn:

1. App của bạn có cần account/trading OpenAPI không?
2. App có chỉ cần public market-data không?
3. App có cần đổi provider qua lại mà không lệch schema không?
4. App có chấp nhận khác biệt semantics giữa `intraday`/`price_depth` không?

Chỉ khi trả lời xong bốn câu này thì mới chọn provider hợp lý.

---

## 3. Điểm số tương đối theo mục tiêu

Điểm bên dưới là **tương đối** trên thang 1-5, dùng để ra quyết định. Đây không phải benchmark tuyệt đối của toàn thị trường, mà là tổng hợp từ kiến trúc hiện có, contract live, và benchmark/smoke hiện có trong repo.

| Tiêu chí | DNSE | VCI | KBS | TCBS | Ý nghĩa |
|---|---|---|---|---|---|
| Public market-data portability | 4 | 5 | 5 | 3 | Đổi provider mà ít phải sửa code |
| Listing / taxonomy coverage | 3 | 5 | 5 | 3 | Độ giàu của danh sách mã, nhóm, ngành, chỉ số |
| Intraday stability / readability | 3 | 4 | 4 | 3 | Mức ổn định và dễ dùng cho luồng trong ngày |
| `price_depth` semantics rõ ràng | 2.5 | 4 | 4 | 1 | Độ gần với mô hình sổ lệnh/depth truyền thống |
| Broker account / trading capability | 5 | 0 | 0 | 0 | Có tài khoản, lệnh, OTP, trading token, đối soát |
| Fit cho app broker-integrated | 5 | 1 | 1 | 1 | Phù hợp cho product cần vừa đọc vừa giao dịch |
| Fit cho app market-data-only | 3.5 | 4.5 | 4.5 | 2.5 | Phù hợp cho app chỉ đọc dữ liệu |

### Cách đọc nhanh

- **DNSE** thắng rõ khi bạn cần broker functionality.
- **VCI/KBS** thắng rõ khi bạn cần market-data coverage và portability.
- **TCBS** không phải lựa chọn primary cho một kiến trúc mới nếu mục tiêu chính là portability và breadth.

---

## 4. Chọn provider theo use case

| Use case | Nên chọn | Provider phụ / fallback | Vì sao |
|---|---|---|---|
| Chỉ xem chart, lịch sử giá, backtest nhẹ | VCI hoặc KBS | DNSE | Public market-data portable, ít ràng buộc account/trading |
| Screener / listing / taxonomy rộng | KBS hoặc VCI | DNSE | Listing coverage và taxonomy của VCI/KBS mạnh hơn |
| Một ứng dụng vừa đọc thị trường vừa đặt lệnh | DNSE | VCI/KBS cho public data fallback | DNSE là provider duy nhất trong bộ này có broker OpenAPI đầy đủ |
| Portfolio / account sync / trading automation | DNSE | Không có provider tương đương | Đây là vùng DNSE-only |
| Multi-provider analytics / failover | VCI + KBS | DNSE extension cho broker layer | Tối ưu portability và tránh lock-in |
| Dùng TCBS vì legacy ecosystem | TCBS | KBS fallback | TCBS public layer nên được xem là compatibility path |

---

## 5. Những điểm dễ gây hiểu nhầm khi ra quyết định

### 5.1 `history()` không phải vấn đề lớn nhất

`history()` là hàm portable nhất giữa các provider. Nếu app của bạn chỉ cần lịch sử giá, bạn có thể đổi provider tương đối an toàn miễn là normalize schema.

### 5.2 `intraday()` khác nhau ở độ ổn định live

Trong live smoke hiện tại của workspace này, DNSE có thể trả gap ở `get_trades` nên `intraday()` được xử lý best-effort. VCI và KBS cho luồng intraday ổn định hơn trong lần chạy này. Vì vậy, nếu intraday là ưu tiên số một, hãy xem VCI/KBS là public-data default, còn DNSE là broker layer.

### 5.3 `price_depth()` không giống nhau giữa providers

DNSE đang trả security definition, không phải order book level-2 theo nghĩa truyền thống. VCI/KBS thiên về depth/order-book hơn. Nếu app của bạn đọc `price_depth()` như một sổ lệnh, hãy cẩn thận khi đổi provider.

### 5.4 Account/trading không có provider thay thế

Nếu bạn muốn đi qua tài khoản DNSE thật để tạo trading token, đặt/sửa/hủy lệnh, hoặc đối soát trạng thái, thì không có provider nào khác trong bộ này thay thế 1:1 được.

---

## 6. Khuyến nghị quyết định theo mục tiêu dự án

### 6.1 Nếu mục tiêu là app market-data-only

Chọn **VCI hoặc KBS** làm provider chính.

Lý do:

- Public API portable tốt.
- Listing/taxonomy mạnh.
- Không phải mang theo lớp account/trading phức tạp.

Khuyến nghị phụ:

- Dùng DNSE như provider bổ sung nếu muốn kiểm tra khả năng broker integration về sau.

### 6.2 Nếu mục tiêu là app broker-integrated

Chọn **DNSE** làm provider chính.

Lý do:

- Có account, orders, OTP, trading token, post/put/cancel order.
- Có thể xây một lớp cầu nối giữa ứng dụng và công ty chứng khoán.
- Hợp với kiến trúc mà vnbroker chỉ cung cấp API chung, còn DNSE là extension riêng cho người dùng có tài khoản DNSE.

Khuyến nghị phụ:

- Giữ VCI/KBS làm market-data fallback nếu cần portability hoặc taxonomy rộng hơn.

### 6.3 Nếu mục tiêu là kiến trúc hybrid lâu dài

Chọn mô hình sau:

- Public market-data layer: VCI/KBS làm chuẩn portable.
- Broker layer: DNSE làm extension riêng cho account/trading.

Đây là mô hình cân bằng nhất nếu bạn muốn vừa dễ đổi provider ở phần đọc dữ liệu, vừa khai thác được toàn bộ dịch vụ DNSE cho người dùng có tài khoản thật.

---

## 7. Quy tắc ra quyết định nhanh

1. Nếu cần trading/account thật → chọn DNSE.
2. Nếu chỉ cần public market-data → chọn VCI hoặc KBS.
3. Nếu cần breadth listing/taxonomy → nghiêng về KBS/VCI.
4. Nếu cần một lớp public portable + broker riêng → chọn hybrid: VCI/KBS + DNSE.
5. Nếu đang cân nhắc TCBS làm primary cho kiến trúc mới → chỉ nên chọn khi bạn đã có ràng buộc legacy rõ ràng.

---

## 8. Khuyến nghị cho chính project này

Với bối cảnh hiện tại của dự án VN stock tracker / robo-advisor và việc bạn đã có tài khoản DNSE:

- **DNSE nên là broker platform chính** cho phần account/trading.
- **VCI/KBS nên là lớp public market-data cân bằng** nếu bạn cần portability hoặc taxonomy mạnh hơn.
- **TCBS chỉ nên là compatibility path**, không nên là provider chính cho kiến trúc mới nếu mục tiêu của bạn là tích hợp broker lâu dài.

Nói ngắn gọn: nếu bạn phải chọn một provider để làm nền cho app giao dịch thật, chọn DNSE. Nếu bạn phải chọn một provider để chỉ đọc thị trường và giữ code portable, chọn VCI/KBS.

---

## 9. Kết luận cuối

Không nên ra quyết định chỉ dựa trên câu hỏi “provider nào có nhiều hàm nhất”. Câu hỏi đúng là:

- Bạn có cần broker integration không?
- Bạn có cần đổi provider ít sửa code không?
- Bạn có cần taxonomy/listing rộng hơn không?
- Bạn có chấp nhận trade-off semantics giữa providers không?

Nếu câu trả lời là **có cần broker integration**, thì DNSE là lựa chọn đúng. Nếu câu trả lời là **chỉ cần public market-data portable**, thì VCI/KBS hợp lý hơn. TCBS phù hợp chủ yếu khi bạn đã bị ràng buộc bởi hệ sinh thái đó hoặc muốn dùng nó như lớp compatibility.
