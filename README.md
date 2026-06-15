# vnbroker

Thư viện Python công khai cho dữ liệu, phân tích và tự động hóa nghiệp vụ chứng khoán Việt Nam.

> Tài liệu này phản ánh trạng thái hiện tại của repo: các adapter thị trường, tài chính, tin tức, snapshot, quỹ, bot nhắn tin và nhánh DNSE đã có trong cây mã nguồn.

## Tóm tắt

vnbroker cung cấp một lớp truy cập thống nhất để lấy dữ liệu từ nhiều nguồn khác nhau, chuẩn hóa đầu ra bằng `pandas` và giảm chi phí tích hợp cho ứng dụng phân tích, dashboard, backend và công cụ nghiên cứu.

Nếu bạn đang xem tài liệu cũ có tên `vnstock` hoặc `vnbroker3`, đó là dấu vết lịch sử. Tên gói hiện tại trong repo này là `vnbroker`.

## Thành phần chính

| Thành phần | Mục đích |
| --- | --- |
| `Vnbroker` | Client cấp cao để lấy stock, FX, crypto, world index và quỹ (qua Gateway PAT) |
| `Quote` | Giá lịch sử, intraday, price depth (qua Gateway PAT) |
| `Company` | Hồ sơ công ty, cổ đông, giao dịch nội bộ, ban lãnh đạo, công ty con, tin tức và sự kiện (qua Gateway PAT) |
| `Finance` | Bảng cân đối kế toán, kết quả kinh doanh, lưu chuyển tiền tệ, chỉ số tài chính (qua Gateway PAT) |
| `Listing` | Danh sách mã, nhóm ngành, nhóm chỉ số, futures, trái phiếu, covered warrant (qua Gateway PAT) |
| `Trading` | Dữ liệu giao dịch và market board (qua Gateway PAT) |
| `News` | Tin tức chuẩn hóa từ nhiều nguồn (qua Gateway PAT) |
| `MarketSnapshot` | Snapshot thị trường cho heatmap và dashboard danh mục (qua Gateway PAT) |
| `Fund` | Dữ liệu quỹ từ FMarket (qua Gateway PAT) |
| `Messenger` | Gửi cảnh báo qua Slack, Telegram, Discord, Lark |
| `Broker` | **Giao dịch tài khoản cá nhân (Private Brokerage) — Bypass Gateway, trực tiếp TCBS/DNSE** |

## Nguồn dữ liệu hiện có

### Market Data (qua vninvest SaaS Gateway — yêu cầu PAT Key)
- `GATEWAY`, `AUTO`: Tất cả dữ liệu thị trường (Quote, Company, Finance, Listing, Trading, News, MarketSnapshot, Fund, FX, Crypto, World Index) đều đi qua Gateway.
- **Không còn hỗ trợ Direct Mode** (KBS, VCI, TCBS, DNSE, MSN, FMP, Binance) cho dữ liệu thị trường.

### Private Brokerage (Bypass Gateway — trực tiếp API Broker)
- `TCBS`: Đặt/hủy/sửa lệnh, số dư, sức mua, vị thế nắm giữ, portfolio — **trực tiếp API TCBS iFlash OpenAPI**.
- `DNSE`: (Sắp ra mắt) Đặt/hủy/sửa lệnh, số dư, vị thế — **trực tiếp API DNSE**.

> **Lý do bypass Gateway cho Broker Lane:**
> - **Bảo mật tối đa (Zero-Knowledge):** OTP, mật khẩu, PIN, API Key/Secret không bao giờ đi qua Gateway trung gian.
> - **Độ trễ thấp (Low Latency):** Lệnh giao dịch gửi thẳng từ client local → API CTCK để khớp lệnh nhanh nhất.
> - **Hạn mức do CTCK quản lý:** Gateway không điều phối hạn mức đặt lệnh/số dư tài khoản cá nhân.

## Cài đặt

```bash
pip install -U vnbroker
```

Phát triển cục bộ:

```bash
pip install -e ".[test]"
```

Dự án yêu cầu Python `>=3.10`.

## Bắt đầu nhanh

### 1. Market Data (qua Gateway — yêu cầu PAT Key)

```python
from vnbroker import Vnbroker

# DEV: Gateway chạy local (http://localhost:8000)
vn = Vnbroker(
    pat_key="vninvest_pat_dev_free_default_unregistered_key",  # Default PAT
    gateway_url="http://localhost:8000"
)

# PRODUCTION: Gateway production (https://saas.edusuccess.vn)
vn = Vnbroker(
    pat_key="vninvest_pat_your_production_token",  # PAT từ vninvest
    gateway_url="https://saas.edusuccess.vn"
)

# Hoặc dùng biến môi trường:
# export VNBROKER_PAT_KEY="vninvest_pat_..."
# export VNBROKER_GATEWAY_URL="https://saas.edusuccess.vn"
# vn = Vnbroker()

acb = vn.stock("ACB")
history = acb.quote.history(start="2024-01-01", end="2024-12-31")
overview = acb.company.overview()
finance = acb.finance.ratio()
news = acb.news.latest()
```

> **Lưu ý:** Chỉ hỗ trợ `source="GATEWAY"` hoặc `source="AUTO"`. Các nguồn trực tiếp cũ (KBS, VCI, TCBS, DNSE, MSN) đã bị loại bỏ cho dữ liệu thị trường.
> 
> **Gateway URLs:**
> - **Dev:** `http://localhost:8000` (mặc định)
> - **Production:** `https://saas.edusuccess.vn`

### 2. Private Brokerage (Bypass Gateway — trực tiếp API Broker)

```python
from vnbroker import Vnbroker

vn = Vnbroker()  # PAT Key không bắt buộc cho broker lane

# TCBS Broker Client
client = vn.broker(provider="tcbs", api_key="your_tcbs_openapi_key")
client.authenticate(otp="123456")  # OTP 6 số từ TCBS

# Read operations
profile = client.get_profile(custody_code="105C334455")
balance = client.get_balance(account_no="0123456789")
holdings = client.get_holdings(account_no="0123456789")
margin = client.get_margin(account_no="0123456789")

# Write operations (dry_run=True mặc định)
client.enable_write()  # Bật chế độ write sau khi authenticated
order = client.place_order(
    account_no="0123456789",
    symbol="ACB",
    side="BUY",
    order_type="LO",
    quantity=100,
    price=25000,
    request_id="unique-idempotency-key"  # Bắt buộc
)
```

### 3. Gửi cảnh báo bot

```python
from vnbroker.bot.notify import Messenger

bot = Messenger("telegram", "-1001234567890", "BOT_TOKEN")
bot.send_message("ACB vượt ngưỡng cảnh báo")
```

## Lưu ý quan trọng

- **Market Data:** Tất cả yêu cầu PAT Key (vninvest_pat_...). Chỉ hỗ trợ `GATEWAY` và `AUTO`.
- **Broker Lane:** Bypass Gateway hoàn toàn. Sử dụng API Key + OTP trực tiếp với TCBS/DNSE.
- Dữ liệu giá được chuẩn hóa theo contract riêng; hãy kiểm tra `df.attrs["price_unit"]` trước khi lưu hay so sánh.
- Nếu cần tương thích ngược, xem `docs/PRICE_UNIT_STANDARDIZATION.md` để bật `vnbroker_PRICE_UNIT=THOUSAND_VND`.
- `Screener` đã bị loại bỏ (phụ thuộc TCBS direct).
- Một số nguồn live có thể bị giới hạn tốc độ hoặc thay đổi phía upstream; adapter của thư viện có retry và backoff, nhưng không thể đảm bảo 100% cho mọi thời điểm.
- **Emergency Fallback:** Khi Gateway down, tự động fallback sang direct explorer (tối đa 10 calls/ngày).

## Tài liệu liên quan

- `module_tree_full.md`
- `docs/VNBROKER_USAGE_GUIDE.md`
- `docs/DNSE_INDEX.md`
- `docs/DNSE_TAPE_API_GUIDE.md`
- `docs/PRICE_UNIT_STANDARDIZATION.md`
- `docs/STOCK_NEWS_INDEX.md`
- `docs/STOCK_NEWS_USAGE_GUIDE.md`
- `docs/PORTFOLIO_ROBOADVISOR_GUIDE.md`
- `docs/MARKET_SNAPSHOT_GUIDE.md`
- `docs/FINANCE_INSIDER_INDUSTRY_USAGE_GUIDE.md`

## Đóng góp và hỗ trợ

Nếu bạn đang dùng vnbroker trong nghiên cứu, dashboard, hoặc công cụ nội bộ, vui lòng trích dẫn dự án và giữ nguyên thông báo giấy phép đi kèm. Nếu muốn dùng cho mục đích thương mại, hãy liên hệ tác giả trước khi tích hợp.

## Giấy phép

Xem [LICENSE.md](LICENSE.md) để biết điều khoản đầy đủ.
