# RFC - DNSE Broker Platform: từ nguồn dữ liệu thành cầu nối giao dịch

> Mã RFC: VNSTOCK-RFC-DNSE-BROKER-2026-05
>
> Trạng thái: Proposal
>
> Ngày: 2026-05-08

---

## 1. Tóm tắt điều hành

Đề xuất này không xem DNSE là một provider market-data đơn lẻ nữa. Mục tiêu là nâng DNSE thành một **broker platform layer** cho vnstock: một lớp cầu nối thống nhất giữa ứng dụng và công ty chứng khoán, bao phủ đọc dữ liệu thị trường, quản lý tài khoản, đặt/sửa/hủy lệnh, theo dõi vị thế, đối soát trạng thái và mở rộng các tác vụ vận hành.

Điểm cốt lõi của đề xuất:

- Giữ nguyên tương thích với vnstock hiện tại, đặc biệt là `Vnstock`, `StockComponents`, `Quote`, `Listing` và `Trade`.
- Dùng DNSE làm broker backend chuẩn cho ứng dụng của bạn, thay vì chỉ dùng DNSE để xem giá.
- Tách rõ hai lớp: **connector** để nói chuyện với OpenAPI, và **broker bridge** để điều phối nghiệp vụ cho ứng dụng.
- Thiết kế theo hướng capability-based: endpoint nào DNSE hỗ trợ thật thì public, endpoint nào chưa ổn định thì cô lập, không để làm gãy các luồng khác.
- Tạo một chuẩn phát triển lâu dài để sau này có thể gắn thêm broker khác mà không phải viết lại kiến trúc.

Một câu ngắn gọn để chốt định hướng: nếu chỉ dừng ở provider, DNSE chỉ là nguồn dữ liệu; nếu đi theo broker platform, DNSE trở thành hạ tầng giao dịch của sản phẩm.

---

## 2. Vì sao đề xuất này đáng làm ngay

### 2.1 Ta đã có đủ tín hiệu thực tế

Trong repo hiện tại, DNSE không còn là ý tưởng trên giấy:

- Market data đã có explorer layer, contract docs, test spec, audit, và live smoke.
- `history()` và `price_depth()` đã khớp contract live theo quan sát thực tế.
- `all_symbols()` đã hoạt động sau khi hạ limit an toàn xuống `1000`.
- `get_security_definition()` trả về `list[dict]`, nên có thể normalize rõ ràng thành DataFrame.
- `get_trades()` hiện vẫn có gap live ở một số môi trường, nên phải xử lý best-effort thay vì fail cứng.
- Account/trading surface của `DNSEClient` và `Trade` đã có nền để bridge tiếp.

Nói cách khác, nền móng đã đủ để chuyển từ “kết nối được” sang “xây nền tảng sử dụng được thật”.

### 2.2 Vì sao chỉ làm provider market-data là chưa đủ

Nếu DNSE chỉ dừng ở provider market-data, bạn sẽ có một thư viện xem giá tốt hơn, nhưng vẫn phải làm các việc cốt lõi ở nhiều chỗ khác nhau:

- Tài khoản phải đọc ở một lớp.
- Vị thế phải tính ở lớp khác.
- Lệnh phải gửi ở layer riêng.
- Đối soát trạng thái lại thành một job khác.
- Mỗi khi DNSE thêm endpoint mới, app phải tự nối lại từ đầu.

Kết quả là ứng dụng của bạn sẽ phân mảnh: đọc dữ liệu thì qua vnstock, đặt lệnh thì qua script riêng, kiểm tra vị thế thì qua một API khác, đối soát thì lại viết thêm một pipeline khác.

Đó là cách rất nhanh để tạo ra chi phí bảo trì cao và contract drift.

### 2.3 Tại sao đây là thời điểm phù hợp

Bạn đã có tài khoản DNSE thật, nghĩa là có thể xác minh live contract và không phải đoán theo spec.

Bạn cũng đang có một dự án lớn hơn vnstock thuần túy: tracker, robo-advisor, tác vụ đọc thị trường, quản trị danh mục và tự động hóa giao dịch. Những use case này cần một broker bridge, không chỉ một quote provider.

---

## 3. Đề xuất chiến lược

### 3.1 Mục tiêu

Biến DNSE thành lớp cầu nối chuẩn giữa ứng dụng và công ty chứng khoán, với ba vai trò cùng lúc:

1. **Market gateway**: đọc dữ liệu thị trường chuẩn hóa.
2. **Account/trading gateway**: quản lý tài khoản, lệnh, vị thế, token.
3. **Platform bridge**: đưa các nghiệp vụ DNSE vào một contract duy nhất để app sử dụng.

### 3.2 Phạm vi đúng

Đề xuất này không yêu cầu “làm mọi thứ ngay lập tức”. Nó yêu cầu:

- Chốt contract theo capability thật.
- Làm bridge trên nền connector hiện có.
- Mở public API ở mức đủ cho app sử dụng, không tạo fat file.
- Dùng audit và test để bảo đảm mọi thay đổi có thể kiểm soát.

Quan điểm thiết kế ở đây là: **vnstock có một lớp API chung cho mọi provider cho các public functions đã được chuẩn hóa**, còn DNSE được mở thêm một lớp mở rộng riêng cho người dùng có tài khoản DNSE để đi sâu vào OpenAPI account/trading/portfolio.

### 3.3 Mô hình lớp

```text
Ứng dụng của bạn
  └── Broker Bridge (API thống nhất cho app)
       ├── Market layer: lịch sử giá, intraday, secdef, instruments
       ├── Account layer: số dư, margin, gói vay, PPSE
       ├── Trading layer: OTP, trading token, đặt/sửa/hủy lệnh
       ├── Portfolio layer: vị thế, lãi/lỗ, exposure, rủi ro
       └── Ops layer: audit log, retry, đối soát, idempotency
            └── DNSE Connector (OpenAPI, ký request, lỗi, raw response)
```

Nếu đi theo mô hình này, `vnstock` không bị khóa vào một broker duy nhất, nhưng DNSE lại đủ sâu để dùng như hạ tầng giao dịch thật.

---

## 4. Những chức năng nên bao phủ

Mục tiêu là bao phủ toàn bộ nhóm chức năng DNSE đã public qua OpenAPI và đã đủ điều kiện kiểm chứng bằng tài khoản thật. Các nhóm sau nên được đưa vào capability registry.

| Nhóm năng lực | Ví dụ chức năng | Vai trò trong sản phẩm |
|---|---|---|
| Market data | `get_ohlc`, `get_trades`, `get_security_definition`, `get_instruments` | Cung cấp giá, lịch sử, danh mục mã, dữ liệu giao dịch intraday |
| Account | `get_accounts`, `get_balances`, `get_loan_packages`, `get_ppse` | Quản lý tài khoản, số dư, margin, sức mua |
| Orders | `get_orders`, `get_order_detail`, `get_execution_detail`, `get_order_history` | Theo dõi trạng thái lệnh và lịch sử thực thi |
| Trading | `send_email_otp`, `create_trading_token`, `post_order`, `put_order`, `cancel_order` | Tạo luồng giao dịch đầy đủ từ xác thực đến đặt lệnh |
| Portfolio | `get_positions` và các chỉ số phát sinh từ danh mục | Hiển thị vị thế, lãi/lỗ, phân bổ tài sản, risk guard |
| Ops | dry-run, audit, retry, idempotency, request tracing | Vận hành an toàn, debug nhanh, giảm lỗi trùng lệnh |

### 4.1 Lưu ý quan trọng về contract live

Tài liệu contract hiện tại đã ghi nhận các quan sát live sau:

- OHLC history cần dùng `bar_type="STOCK"` cho cổ phiếu.
- OHLC body có thể là một `dict` top-level hoặc list trong `bars`/`data`.
- `get_security_definition()` có thể trả về `list[dict]`.
- `get_instruments(..., limit=1000)` là ngưỡng an toàn hiện tại.
- `get_trades()` có thể là gap live tạm thời, nên bridge phải dùng semantics best-effort.

Đây là điểm mấu chốt: bridge phải dựa trên **năng lực xác minh được**, không dựa trên giả định.

### 4.2 Bảng tương thích với kiến trúc hiện có của vnstock

#### 4.2.1 Lớp API chung cho mọi provider

| API / nhóm chức năng | Vai trò trong vnstock | Mức tương thích với DNSE | Chuyển provider an toàn? | Ghi chú thiết kế |
|---|---|---|---|---|
| `Quote.history()` | Lấy lịch sử giá chuẩn hóa | Cao | Có | DNSE dùng `bar_type="STOCK"`; output chuẩn hóa `time/open/high/low/close/volume` |
| `Listing.all_symbols()` | Danh sách mã chứng khoán | Cao | Có | DNSE đã chuẩn hóa output và hạ limit an toàn về `1000` |
| `Listing.symbols_by_exchange()` | Lọc danh sách theo sàn | Cao | Có | Chỉ cần map `exchange`/`market_id` đúng taxonomy |
| `Listing.indices()` | Danh sách chỉ số | Trung bình - cao | Có, nhưng nên đối chiếu taxonomy | DNSE có thể fallback khi data list không đủ đầy |
| `Quote.intraday()` | Giao dịch khớp trong ngày | Trung bình | Có điều kiện | DNSE live trades có thể 404; bridge phải trả empty thay vì fail cứng |
| `Quote.price_depth()` | Dữ liệu security definition / thông tin mã | Trung bình | Có điều kiện | Semantics khác order book; app không nên giả định đây là level-2 depth |

#### 4.2.2 Lớp mở rộng riêng cho người dùng DNSE

| DNSE OpenAPI function family | Có trong lớp API chung vnstock? | DNSE support | Khi chuyển provider | Ghi chú |
|---|---|---|---|---|
| Account: `get_accounts`, `get_balances`, `get_loan_packages`, `get_ppse` | Không | Có | Không áp dụng | Chỉ mở cho người dùng có DNSE credentials |
| Orders: `get_orders`, `get_order_detail`, `get_execution_detail`, `get_order_history` | Không | Có | Không áp dụng | Nên đi qua broker bridge riêng của DNSE |
| Trading: `send_email_otp`, `create_trading_token`, `post_order`, `put_order`, `cancel_order` | Không | Có | Không áp dụng | Đây là lớp giao dịch riêng, không nên giả lập như market-data |
| Portfolio / position / reconciliation | Không chuẩn hóa chung | Có thể mở rộng | Không áp dụng | Dùng cho app giao dịch thực, đồng bộ trạng thái và đối soát |

Kết luận thực dụng của bảng tương thích: **người dùng có thể đổi provider khá an toàn nếu code chỉ bám vào lớp API chuẩn hóa của vnstock và schema đã normalize**. Còn nếu họ dùng các hàm DNSE extension, đó là năng lực riêng của DNSE và không thể kỳ vọng provider khác có cùng hành vi 1:1.

---

## 5. Vì sao cách này tốt hơn các lựa chọn khác

| Lựa chọn | Ưu điểm | Nhược điểm | Kết luận |
|---|---|---|---|
| Chỉ giữ DNSE ở mức provider market-data | Dễ hiểu, ít thay đổi | Bỏ lỡ tài khoản, lệnh, vị thế, đối soát | Không đủ cho ứng dụng giao dịch thực |
| Viết script/endpoint riêng trong app | Nhanh lúc đầu | Phân tán logic, khó test, khó audit | Chỉ hợp demo ngắn hạn |
| **DNSE Broker Platform (đề xuất)** | Một contract, một audit trail, một lớp tích hợp | Cần thiết kế tốt hơn ban đầu | **Phù hợp nhất cho sản phẩm lâu dài** |

Lý do mạnh nhất để chọn phương án này là chi phí bảo trì. Mỗi endpoint DNSE mới sau này chỉ cần đi vào capability registry và một service nhỏ; không cần tái thiết kế cả ứng dụng.

---

## 6. Giá trị thực tế với sản phẩm của bạn

Đề xuất này không chỉ tốt về mặt kiến trúc. Nó tạo ra giá trị rất cụ thể cho VN stock tracker / robo-advisor của bạn:

- Có thể đọc dữ liệu, kiểm tra tài khoản và đặt lệnh trong cùng một luồng nghiệp vụ.
- Có thể xây risk guard tự động trước khi gửi lệnh.
- Có thể tạo cảnh báo margin, sức mua, vị thế và rủi ro danh mục.
- Có thể chuẩn hóa lịch sử giao dịch để làm back-office hoặc báo cáo nội bộ.
- Có thể chuyển từ “một app xem dữ liệu” thành “một app vận hành với broker”.

Đó là bước nhảy từ consumer app sang broker-integrated product.

---

## 7. Kiến trúc đề xuất

### 7.1 Connector layer

Giữ `vnstock.connector.dnse` là lớp thấp nhất, chuyên:

- Ký request.
- Gọi HTTP.
- Map lỗi.
- Trả raw body hoặc DataFrame khi hợp lý.
- Không chứa nghiệp vụ app.

### 7.2 Bridge layer

Thêm một lớp broker bridge ở trên connector, ví dụ theo domain như:

- account bridge
- trading bridge
- portfolio bridge
- reconciliation bridge

Bridge layer sẽ làm nhiệm vụ:

- chuẩn hóa contract;
- gom nhiều endpoint thành một use case;
- che đi khác biệt nhỏ giữa các response shape;
- trả lại API dễ dùng cho application layer.

### 7.3 App integration layer

Ứng dụng của bạn chỉ nên gọi bridge, không gọi endpoint DNSE raw trực tiếp.

Điều này giúp:

- đổi broker sau này ít đau hơn;
- dễ test hơn;
- dễ audit hơn;
- dễ thêm job sync bằng Celery/Redis;
- dễ làm observability và alerting.

---

## 8. Lộ trình triển khai được khuyến nghị

### Phase 0 - Chốt contract và inventory capability

Mục tiêu:

- Lập danh mục endpoint thực sự có thể dùng.
- Đánh dấu endpoint nào ổn định, endpoint nào best-effort, endpoint nào tạm thời gap.
- Chốt schema output tối thiểu và error model.

Đầu ra:

- capability matrix
- live contract inventory
- risk register
- acceptance criteria

### Phase 1 - Hoàn thiện connector và normalization

Mục tiêu:

- Giữ `DNSEClient` làm façade low-level ổn định.
- Chuẩn hóa raw/DataFrame mode.
- Đảm bảo retry/timeout/error mapping/logging nhất quán.

Đầu ra:

- raw response contract rõ ràng
- dry-run cho QA/dev
- request tracing
- test contract cho response shape

### Phase 2 - Xây broker bridge public

Mục tiêu:

- Tạo lớp public để app gọi account, trading, portfolio, market data qua cùng một contract.
- Ẩn bớt khác biệt giữa các endpoint DNSE.
- Thêm alias/deprecation nếu cần để không phá code cũ.

Đầu ra:

- một public API duy nhất cho app
- capability-based dispatch
- backward compatibility

### Phase 3 - Đồng bộ ứng dụng và vận hành

Mục tiêu:

- Tích hợp Celery/Redis cho sync trạng thái lệnh và vị thế.
- Thêm audit trail và reconciliation.
- Thêm cảnh báo cho margin, cash, order status.

Đầu ra:

- app có thể vận hành qua DNSE mà không cần thao tác tay
- logs và audit đầy đủ

### Phase 4 - Nâng thành platform thật

Mục tiêu:

- Bao phủ lifecycle đầy đủ của tài khoản và giao dịch.
- Thêm eventing/webhook nếu DNSE cung cấp.
- Chuẩn bị khả năng mở rộng sang broker khác mà không phải viết lại app.

Đầu ra:

- broker platform ổn định
- dễ mở rộng
- dễ bảo trì

---

## 9. Rủi ro và cách giảm thiểu

| Rủi ro | Tác động | Cách giảm thiểu |
|---|---|---|
| Endpoint live không ổn định, đặc biệt là trades | Làm gãy intraday nếu fail cứng | Best-effort semantics, fallback empty DataFrame, circuit breaker |
| Contract drift giữa docs và live | Dễ sinh bug ngầm | Contract tests, live smoke, audit file bắt buộc |
| Rò rỉ secret hoặc trading token | Rủi ro bảo mật nghiêm trọng | Mask log, env-only config, không ghi raw secret |
| Gửi lệnh trùng | Rủi ro tài chính | Idempotency key, request_id, kiểm tra trạng thái trước khi retry |
| Nở scope quá nhanh | Kéo dài delivery | Phased rollout, capability registry, no-go cho endpoint chưa chốt |

Điểm quan trọng là rủi ro không nằm ở việc làm bridge, mà nằm ở việc không có bridge nhưng vẫn phải vận hành nhiều luồng rời rạc.

---

## 10. Tiêu chí thành công

Đề xuất này chỉ nên được coi là thành công khi các điều kiện sau đều đạt:

- Ứng dụng chỉ cần một contract để đọc thị trường, xem tài khoản, đặt lệnh và theo dõi trạng thái.
- Mọi endpoint DNSE hỗ trợ thật đều được ánh xạ vào capability matrix.
- Mọi lỗi đều có `request_id`, `status_code` và message có ý nghĩa.
- Market-data path vẫn chạy được kể cả khi trading path tạm thời lỗi.
- Thêm endpoint DNSE mới không làm vỡ code cũ.
- QA có thể chạy live smoke và audit độc lập.

---

## 11. Đề nghị phê duyệt

Tôi đề nghị bạn phê duyệt theo nguyên tắc sau:

1. Chấp thuận DNSE là **broker platform** của vnstock, không chỉ là data provider.
2. Chấp thuận xây dựng một **broker bridge layer** ở trên connector hiện có.
3. Chấp thuận làm theo **phase-based rollout**, bắt đầu từ capability inventory và contract lock.
4. Chấp thuận nguyên tắc: mọi logic app với DNSE phải đi qua bridge, không gọi raw endpoint rải rác.

Nếu bạn chỉ muốn chốt một việc để bắt đầu, hãy chốt Phase 0 trước. Phase 0 không phải là code nhiều; nó là bước giúp toàn bộ các phase sau đi đúng hướng và không phải sửa ngược.
