# DNSE / VCI / KBS / TCBS Provider Comparison Matrix

> Mục tiêu: so sánh 4 provider theo từng public function để xác định chỗ nào có thể thay thế lẫn nhau, chỗ nào chỉ là DNSE-only, và chỗ nào cần hiểu như fallback của adapter chứ không phải support native.
>
> Phạm vi: public market-data functions trong lớp API chuẩn hóa của vnbroker, cộng thêm phần mở rộng riêng cho DNSE OpenAPI.
>
> Ngày: 2026-05-08

---

## 1. Quan điểm thiết kế

vnbroker có một lớp API chung cho các provider khác nhau để người dùng lấy các public functions chuẩn hóa của thị trường chứng khoán. Trên lớp này, mục tiêu là:

- Giữ cách gọi thống nhất.
- Chuẩn hóa schema đầu ra.
- Cho phép đổi provider mà không phải sửa lại toàn bộ ứng dụng.

Riêng DNSE được thiết kế thêm một lớp mở rộng dành cho người dùng có tài khoản DNSE, để đi sâu vào toàn bộ OpenAPI của công ty chứng khoán: account, orders, trading token, và các nghiệp vụ vận hành liên quan.

Điểm quan trọng là phải tách rõ:

- **Cùng một contract public**: các hàm chuẩn hóa cho market-data.
- **DNSE-only extension**: các API tài khoản/giao dịch chỉ áp dụng cho DNSE.

---

## 2. Cách đọc bảng

- **Native**: provider đó có implementation trực tiếp cho hàm public.
- **Fallback**: lớp public vẫn gọi được nhưng implementation thực tế đi qua provider khác hoặc cơ chế dự phòng.
- **Partial**: support được nhưng semantics hoặc payload shape có khác biệt cần lưu ý.
- **No**: không có native support trong provider đó.

Khuyến nghị sử dụng:

- Nếu code chỉ dùng các dòng đánh dấu **Native/Portable**, việc chuyển provider là khá an toàn.
- Nếu code đụng vào **Partial** hoặc **Fallback**, phải normalize schema và test lại semantics.
- Nếu code đụng vào **DNSE-only**, không được kỳ vọng provider khác thay thế 1:1.

---

## 3. Bảng tương thích - Quote / market data

| Public function | DNSE | VCI | KBS | TCBS (public layer) | Mức thay thế | Ghi chú |
|---|---|---|---|---|---|---|
| `Quote.history()` | Native | Native | Native | Native | Cao | Đây là hàm portable nhất giữa 4 provider nếu code bám vào schema chuẩn hóa. |
| `Quote.intraday()` | Native, best-effort | Native | Native | Native | Trung bình | DNSE live trades có thể 404 trong một số môi trường; VCI/KBS ổn định hơn cho intraday. |
| `Quote.price_depth()` | Native, nhưng semantics là security definition | Native, order-book/depth | Native, order-book/depth | Không có native support | Thấp - trung bình | DNSE không trả order book level-2 theo nghĩa truyền thống; app không nên hiểu đây là sổ lệnh giống VCI/KBS. |

### Diễn giải ngắn

- `history()` là hàm an toàn nhất để đổi provider.
- `intraday()` thay được, nhưng phải chấp nhận sự khác nhau về độ ổn định live.
- `price_depth()` là nơi dễ lệch semantics nhất: DNSE trả security definition, VCI/KBS thiên về order-book/depth, còn TCBS hiện không có native support trong lớp public này.

---

## 4. Bảng tương thích - Listing / danh sách mã

| Public function | DNSE | VCI | KBS | TCBS (public layer) | Mức thay thế | Ghi chú |
|---|---|---|---|---|---|---|
| `Listing.all_symbols()` | Native | Native | Native | KBS fallback | Cao | TCBS public layer hiện phụ thuộc fallback KBS; không nên xem là native TCBS listing. |
| `Listing.symbols_by_exchange()` | Native | Native | Native | KBS fallback | Cao | Chuyển provider an toàn nếu chỉ cần lọc theo sàn. |
| `Listing.symbols_by_industries()` | Fallback | Native | Native | KBS fallback | Trung bình - cao | DNSE không có native ICB/industry explorer riêng; trả fallback để không làm gãy API. |
| `Listing.industries_icb()` | Fallback empty | Native | Native | KBS fallback | Trung bình | DNSE không có hierarchy ICB native; VCI/KBS mạnh hơn ở lớp này. |
| `Listing.symbols_by_group()` | Native | Native | Native | KBS fallback | Cao | Portable tốt nếu code chỉ quan tâm danh mục nhóm mã. |
| `Listing.all_future_indices()` | Fallback alias | Native | Native | KBS fallback | Trung bình | DNSE map qua nhóm chỉ số tương ứng; TCBS vẫn dựa KBS fallback ở layer public. |
| `Listing.all_covered_warrant()` | Fallback empty | Native | Native | KBS fallback | Trung bình | DNSE hiện chưa có native covered warrant listing. |
| `Listing.all_bonds()` | Fallback empty | Native | Native | KBS fallback | Trung bình | DNSE bond listing chưa được map native trong scope hiện tại. |
| `Listing.all_government_bonds()` | Fallback empty | Native | Native | KBS fallback | Trung bình | DNSE government bond listing chưa có native support. |

### Diễn giải ngắn

- VCI và KBS là hai provider mạnh nhất nếu mục tiêu của bạn là listing coverage rộng và giàu taxonomy.
- DNSE đủ tốt cho các luồng listing phổ biến, nhưng một số danh mục chuyên sâu sẽ là fallback hoặc empty.
- TCBS ở lớp listing public hiện nên được xem là **KBS-backed public behavior**, không phải listing native của TCBS.

---

## 5. Bảng DNSE-only extension

| DNSE OpenAPI function family | DNSE | VCI | KBS | TCBS | Mức thay thế | Ghi chú |
|---|---|---|---|---|---|---|
| `get_accounts`, `get_balances`, `get_loan_packages`, `get_ppse` | Có | Không | Không | Không | Không thay thế | Đây là năng lực tài khoản riêng của DNSE. |
| `get_orders`, `get_order_detail`, `get_execution_detail`, `get_order_history` | Có | Không | Không | Không | Không thay thế | Thuộc lớp account/order management của DNSE. |
| `send_email_otp`, `create_trading_token` | Có | Không | Không | Không | Không thay thế | Bước xác thực để đi vào luồng giao dịch DNSE. |
| `post_order`, `put_order`, `cancel_order` | Có | Không | Không | Không | Không thay thế | Đây là hoạt động giao dịch trực tiếp, không có tương đương trong lớp public market-data của 3 provider còn lại. |
| Portfolio / reconciliation / position bridge | Có thể mở rộng | Không | Không | Không | Không thay thế | Đây là lớp mở rộng riêng cho ứng dụng có tài khoản DNSE. |

Kết luận cho nhóm này: nếu app của bạn dùng các hàm DNSE-only, bạn đang đi vào vùng **broker integration**, không còn là vùng **provider portable** nữa.

---

## 6. Kết luận về tính thay thế

### 6.1 Có thể chuyển provider tương đối an toàn khi:

- App chỉ dùng `Quote.history()` và `Listing.all_symbols()` / `symbols_by_exchange()` / `symbols_by_group()`.
- App đã normalize schema, không phụ thuộc vào payload gốc của từng provider.
- App chấp nhận rằng một số provider có coverage rộng hơn hoặc khác taxonomy.

### 6.2 Cần cẩn thận khi:

- App dùng `intraday()` vì ổn định live khác nhau giữa provider.
- App dùng `price_depth()` vì semantics giữa DNSE và VCI/KBS không giống nhau.
- App dùng các hàm listing chuyên sâu như `industries_icb()` hoặc các nhóm bond/warrant.

### 6.3 Không nên kỳ vọng thay thế 1:1 khi:

- Code gọi vào account/trading OpenAPI của DNSE.
- App cần số liệu hiển nhiên giống hệt giữa provider này và provider khác.
- Luồng nghiệp vụ có yếu tố xác thực, trading token, hoặc đối soát giao dịch.

---

## 7. Khuyến nghị triển khai trong code

1. Chỉ dùng lớp API chuẩn hóa của vnbroker cho những phần cần portability.
2. Với các hàm `Partial` hoặc `Fallback`, normalize output trước khi đưa vào nghiệp vụ.
3. Với DNSE-only flows, tách riêng service/module để tránh làm ô nhiễm lớp public chung.
4. Khi cần chuyển provider, ưu tiên đổi ở tầng adapter/config, không đổi logic nghiệp vụ ở tầng app.

---

## 8. Tóm tắt một dòng

- **Portable cao**: `history`, `all_symbols`, `symbols_by_exchange`, `symbols_by_group`.
- **Portable có caveat**: `intraday`, `price_depth`, `symbols_by_industries`, `industries_icb`, bond/warrant groups.
- **DNSE-only**: account, order, OTP, trading token, post/put/cancel order, reconciliation.
