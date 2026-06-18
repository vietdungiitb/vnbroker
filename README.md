# vnbroker

Thư viện Python cho dữ liệu, phân tích và tự động hóa nghiệp vụ chứng khoán Việt Nam.

> **v3.0.0** — Direct Provider Architecture, không phụ thuộc PAT/Gateway.

## Tóm tắt

vnbroker cung cấp một lớp truy cập thống nhất để lấy dữ liệu từ nhiều nguồn trực tiếp (VCI, KBS, TCBS, DNSE, MSN, FMP), chuẩn hóa đầu ra bằng `pandas` và giảm chi phí tích hợp cho ứng dụng phân tích, dashboard, backend và công cụ nghiên cứu.

**Điểm truy cập chính:** lớp `Vnbroker` (xem `vnbroker/common/client.py`).

## Thành phần chính

| Thành phần | Mục đích |
| --- | --- |
| `Vnbroker` | Client cấp cao để lấy stock, FX, crypto, world index và quỹ (Direct Providers) |
| `Quote` | Giá lịch sử, intraday, price depth (Multi-Source) |
| `Company` | Hồ sơ công ty, cổ đông, giao dịch nội bộ, ban lãnh đạo, công ty con, tin tức và sự kiện |
| `Finance` | Bảng cân đối kế toán, kết quả kinh doanh, lưu chuyển tiền tệ, chỉ số tài chính |
| `Listing` | Danh sách mã, nhóm ngành, nhóm chỉ số, futures, trái phiếu, covered warrant |
| `Trading` | Dữ liệu giao dịch và market board |
| `News` | Tin tức chuẩn hóa từ nhiều nguồn (VCI, KBS, TCBS + RSS) |
| `MarketSnapshot` | Snapshot thị trường cho heatmap và dashboard danh mục |
| `Fund` | Dữ liệu quỹ từ FMarket |
| `Messenger` | Gửi cảnh báo qua Slack, Telegram, Discord, Lark |
| `Broker` | **Giao dịch tài khoản cá nhân (Private Brokerage) — Direct Broker API: TCBS, DNSE, SSI** |

## Nguồn dữ liệu (Data Sources)

### Direct Provider Architecture

vnbroker hỗ trợ truy cập trực tiếp tới các provider mà **không cần PAT/Gateway**:

| Provider | Dữ liệu hỗ trợ | Credentials bổ sung |
| --- | --- | --- |
| `VCI` | Quote, Company, Finance, Listing, Trading, News | Không cần auth |
| `KBS` | Quote, Company, Finance, Listing, Trading | Không cần auth |
| `TCBS` | Quote, Company, Finance, Listing, Trading, News | Không cần auth |
| `DNSE` | Quote, Listing, Trading | Cần `DNSE_API_KEY` + `DNSE_API_SECRET` |
| `MSN` | Quote, Listing, FX, Crypto, World Index | Không cần auth |
| `FMP` | Quote, Listing, FX, Crypto, World Index | Cần `FMP_API_KEY` |
| `BINANCE` | Crypto (scaffolded) | Reserved for future |
| `SSI` | Broker (scaffolded) | Reserved for future |

### Private Brokerage (Direct Broker API)
- `TCBS`: Đặt/hủy/sửa lệnh, số dư, sức mua, vị thế nắm giữ, portfolio — **trực tiếp TCBS iFlash OpenAPI v1.0.0**
- `DNSE`: Đặt/hủy/sửa lệnh, số dư, vị thế — **trực tiếp VNDirect API**
- `SSI`: (Sắp ra mắt) Giao dịch chứng khoán — **trực tiếp SSI API**

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

### 1. Market Data — Direct Provider Mode

```python
from vnbroker import Vnbroker

# Khởi tạo đơn giản, không cần PAT
vn = Vnbroker(source="KBS")  # KBS là mặc định

acb = vn.stock("ACB")
history = acb.quote.history(start="2024-01-01", end="2024-12-31")
overview = acb.company.overview()
finance = acb.finance.ratio()
news = acb.news.latest()
```

### 2. Chọn provider cụ thể

```python
from vnbroker import Vnbroker

vn = Vnbroker()
acb_vci = vn.stock("ACB", source="VCI")
acb_kbs = vn.stock("ACB", source="KBS")
acb_tcbs = vn.stock("ACB", source="TCBS")
acb_dnse = vn.stock("ACB", source="DNSE")  # Cần DNSE_API_KEY + DNSE_API_SECRET
```

**Nguồn hợp lệ theo nhóm dữ liệu:**

| Nhóm | Nguồn hỗ trợ |
| --- | --- |
| `Quote` | `VCI`, `KBS`, `TCBS`, `MSN`, `DNSE`, `FMP` |
| `Company` | `VCI`, `KBS`, `TCBS`, `DNSE`, `MSN`, `FMP` |
| `Finance` | `VCI`, `KBS`, `TCBS`, `DNSE`, `FMP` |
| `Listing` | `VCI`, `KBS`, `TCBS`, `DNSE`, `FMP` |
| `Trading` | `VCI`, `KBS`, `TCBS`, `DNSE` |
| `News` | `VCI`, `KBS`, `TCBS` |
| `FX/Crypto/World Index` | `MSN`, `FMP` |
| `Fund` | `FMARKET` |

### 3. Private Brokerage (trực tiếp API Broker)

```python
from vnbroker import Vnbroker

vn = Vnbroker()

# TCBS Broker Client
client = vn.broker(provider="tcbs", api_key="your_tcbs_openapi_key")
client.authenticate(otp="123456")

profile = client.get_profile(custody_code="105C334455")
balance = client.get_balance(account_no="0123456789")
holdings = client.get_holdings(account_no="0123456789")

# Write operations (dry_run=True mặc định)
client.enable_write()
order = client.place_order(
    account_no="0123456789",
    symbol="ACB",
    side="BUY",
    order_type="LO",
    quantity=100,
    price=25000,
    request_id="unique-idempotency-key"
)
```

### 4. Gửi cảnh báo bot

```python
from vnbroker.bot.notify import Messenger

bot = Messenger("telegram", "-1001234567890", "BOT_TOKEN")
bot.send_message("ACB vượt ngưỡng cảnh báo")
```

### 5. FX, Crypto, World Index

```python
from vnbroker import Vnbroker

vn = Vnbroker(source="MSN")

usd_vnd = vn.fx("USDVND")
fx_history = usd_vnd.quote.history(start="2024-01-01", end="2024-12-31")

btc = vn.crypto("BTC")
btc_history = btc.quote.history(start="2024-01-01", end="2024-12-31")

dji = vn.world_index("DJI")
dji_history = dji.quote.history(start="2024-01-01", end="2024-12-31")
```

### 6. Fund (Quỹ mở)

```python
from vnbroker import Vnbroker

vn = Vnbroker()
funds = vn.fund()
all_funds = funds.listing()
```

## Biến môi trường

| Biến | Mô tả | Ví dụ |
| --- | --- | --- |
| `DNSE_API_KEY` | DNSE API Key | `your_dnse_key` |
| `DNSE_API_SECRET` | DNSE API Secret | `your_dnse_secret` |
| `FMP_API_KEY` | Financial Modeling Prep API Key | `your_fmp_key` |
| `VNBROKER_BROKER_TCBS_API_KEY` | TCBS OpenAPI Key cho Broker Lane | `your_tcbs_key` |

## Lưu ý quan trọng

- **Market Data:** Truy cập trực tiếp provider (VCI, KBS, TCBS, DNSE, MSN, FMP) — **không cần PAT/Gateway**.
- **Broker Lane:** Gọi trực tiếp API Broker với API Key + OTP.
- Dữ liệu giá được chuẩn hóa theo contract riêng; kiểm tra `df.attrs["price_unit"]` trước khi lưu hay so sánh.
- Một số nguồn live có thể bị giới hạn tốc độ hoặc thay đổi phía upstream; adapter của thư viện có retry và backoff.

## Đóng góp và hỗ trợ

Nếu bạn đang dùng vnbroker trong nghiên cứu, dashboard, hoặc công cụ nội bộ, vui lòng trích dẫn dự án và giữ nguyên thông báo giấy phép đi kèm.

## Giấy phép

Xem [LICENSE.md](LICENSE.md) để biết điều khoản đầy đủ.
