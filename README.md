# vnbroker

Thư viện Python cho dữ liệu, phân tích và tự động hóa nghiệp vụ chứng khoán Việt Nam.

> **v3.5.0** — Kiến trúc hai tầng: dữ liệu thị trường ẩn danh (`auto=True`) tự chọn và xoay vòng provider; broker chọn provider tường minh. Kèm chặn double-submit lệnh SSI + hàng rào `dry_run` cho `connector/dnse`. ⚠️ Có **Breaking changes** (xem [Breaking Changes 3.5.0](#phiên-bản-350--2026-10-02--kiến-trúc-hai-tầng--an-toàn-đường-giao-dịch)) — `history()` trả `time` tz-aware.

## Tóm tắt

vnbroker cung cấp một lớp truy cập thống nhất để lấy dữ liệu từ nhiều nguồn trực tiếp (VCI, KBS, TCBS, DNSE), chuẩn hóa đầu ra bằng `pandas` và giảm chi phí tích hợp cho ứng dụng phân tích, dashboard, backend và công cụ nghiên cứu.

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
| `Broker` | **Giao dịch tài khoản cá nhân (Private Brokerage) — Direct Broker API: TCBS, SSI, DNSE** |

## Nguồn dữ liệu (Data Sources)

### Direct Provider Architecture

vnbroker hỗ trợ truy cập trực tiếp tới các provider mà **không cần PAT/Gateway**:

| Provider | Dữ liệu hỗ trợ | Credentials bổ sung |
| --- | --- | --- |
| `VCI` | Quote, Company, Finance, Listing, Trading, News | Không cần auth |
| `KBS` | Quote, Company, Finance, Listing, Trading | Không cần auth |
| `TCBS` | Quote, Company, Finance, Listing, Trading, News | Không cần auth |
| `DNSE` | Quote, Listing, Trading | Cần `DNSE_API_KEY` + `DNSE_API_SECRET` |
| `SSI` | Quote, Listing, Trading | Cần `VNBROKER_BROKER_SSI_API_KEY` + `VNBROKER_BROKER_SSI_API_SECRET` |


> **Lưu ý:** DNSE/SSI không có Company/Finance/News endpoints ở upstream — provider trả
> DataFrame rỗng đúng schema và **facade tự fallback sang KBS/VCI**
> (`Finance` fallback cứng sang KBS; `Company` bỏ qua DF rỗng). Kiểm tra nguồn thật qua
> `df.attrs["source_used"]` / `source_requested`, đừng tin `source` yêu cầu.

### Private Brokerage (Direct Broker API)
- `TCBS`: Đặt/hủy/sửa lệnh, số dư, sức mua, vị thế nắm giữ, portfolio — **trực tiếp TCBS iFlash OpenAPI v1.0.0**
- `SSI`: Market data (OHLC 8 timeframe, master data), số dư/vị thế equity + phái sinh, đặt/hủy/sửa lệnh (ký RSA), **7 loại lệnh điều kiện FCO**, streaming WebSocket — **native FastConnect v3, không cần `ssi-sdk`** (xem `docs/SSI_USAGE_GUIDE.md`)
- `DNSE`: Đặt/hủy/sửa lệnh, số dư, vị thế — **trực tiếp VNDirect API**

```python
from vnbroker import Vnbroker

vn = Vnbroker()
ssi = vn.broker(provider="ssi", api_key="...", api_secret="...")
ssi.authenticate()  # market-data-only, không OTP
ohlc = ssi.get_ohlc("SSI", timeframe="1d")
```

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

### 1b. Retail & Unified UI (không cần biết source)

```python
from vnbroker import Vnbroker

retail = Vnbroker().retail()
sjc = retail.gold(source="sjc", date="2026-01-15")  # hoặc source="btmc"
fx = retail.exchange_rate()  # tỷ giá Vietcombank hôm nay

from vnbroker.ui import Fundamental, Market, Reference, show_api

mkt = Market()  # default KBS
hist = mkt.equity("SSI").history(start="2026-01-01")
prof = Reference().company("SSI").profile()
bs = Fundamental().equity("SSI").balance_sheet(period="year")
show_api()
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
| `Quote` | `VCI`, `KBS`, `TCBS`, `DNSE` |
| `Company` | `VCI`, `KBS`, `TCBS`, `DNSE` |
| `Finance` | `VCI`, `KBS`, `TCBS`, `DNSE` |
| `Listing` | `VCI`, `KBS`, `TCBS`, `DNSE` |
| `Trading` | `VCI`, `KBS`, `TCBS`, `DNSE` |
| `News` | `VCI`, `KBS`, `TCBS` |
| `Fund` | `FMARKET` |

### 3. Private Brokerage (trực tiếp API Broker)

vnbroker cung cấp **hai lane brokerage riêng biệt** cho TCBS:

#### 3a. TCBS iFlash OpenAPI v1.0.0 (Official - `vnbroker.broker.tcbs`)
API chính thức của TCBS, production-ready, test coverage đầy đủ.

```python
from vnbroker import Vnbroker

vn = Vnbroker()

# TCBS Official OpenAPI Client
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

#### 3b. TCBS Private API (Advanced - `vnbroker.brokerage.tcbs`)
API private của TCBS với HMAC-SHA256 + WebSocket streaming, dành cho advanced users.

```python
from vnbroker.brokerage.tcbs import TCBSClient

client = TCBSClient(
    api_key="your_api_key",
    secret="your_base64_secret",
    account_no="0123456789",
    otp_handler=lambda otp_type: input(f"Enter {otp_type} OTP: ")
)

balance = client.get_balance()
positions = client.get_positions()
orders = client.get_orders()

# Real-time streaming
async for tick in client.intratick_stream(["ACB", "VNM"]):
    print(f"{tick.symbol}: {tick.price} @ {tick.volume}")

# WebSocket order updates
async for order_update in client.order_updates_stream():
    print(f"Order {order_update.order_id}: {order_update.status}")
```

### 4. Gửi cảnh báo bot

```python
from vnbroker.bot.notify import Messenger

bot = Messenger("telegram", "-1001234567890", "BOT_TOKEN")
bot.send_message("ACB vượt ngưỡng cảnh báo")
```

### 5. Fund (Quỹ mở)

```python
from vnbroker import Vnbroker

vn = Vnbroker()
funds = vn.fund()
all_funds = funds.listing()
```

## Biến môi trường

| Biến | Mô tả | Ví dụ |
| --- | --- | --- |
| `DNSE_API_KEY` | DNSE API Key (HMAC OpenAPI) | `your_dnse_key` |
| `DNSE_API_SECRET` | DNSE API Secret (HMAC OpenAPI) | `your_dnse_secret` |
| `DNSE_USERNAME` | DNSE Username (JWT Trading) | `your_dnse_username` |
| `DNSE_PASSWORD` | DNSE Password (JWT Trading) | `your_dnse_password` |
| `VNBROKER_BROKER_TCBS_API_KEY` | TCBS OpenAPI Key cho Broker Lane (iFlash) | `your_tcbs_key` |

## Lưu ý quan trọng

- **Market Data:** Truy cập trực tiếp provider (VCI, KBS, TCBS, DNSE) — **không cần PAT/Gateway**.
- **Broker Lane:** Gọi trực tiếp API Broker với API Key + OTP.
- Dữ liệu giá được chuẩn hóa theo contract riêng; kiểm tra `df.attrs["price_unit"]` trước khi lưu hay so sánh.
- Một số nguồn live có thể bị giới hạn tốc độ hoặc thay đổi phía upstream; adapter của thư viện có retry và backoff.
- **FX/Crypto/World Index:** Không được hỗ trợ bởi các provider hiện tại (KBS, VCI, TCBS, DNSE). Các phương thức `fx()`, `crypto()`, `world_index()` sẽ raise `NotImplementedError` trong phiên bản tới.

## Phiên bản 3.5.0 (2026-10-02) — Kiến trúc hai tầng + an toàn đường giao dịch

### Breaking Changes (3.5.0)

1. **`history()` qua `Vnbroker` trả `time` tz-aware** (`Asia/Ho_Chi_Minh`) thay vì
   tz-naive, và được lọc theo `start`/`end`.
   - Lý do: provider trả tz khác nhau nên `pd.concat` sinh dtype `object`; VCI còn
     trả nến ngoài khoảng yêu cầu **không báo lỗi**.
   - Nếu bạn so `df["time"]` với timestamp naive: dùng `.dt.tz_localize(None)`.
   - Gọi provider trực tiếp (`VCIQuote(...).history()`) **không đổi**.
2. **`connector/dnse` cần `trade.enable_write()`** trước khi gửi lệnh thật.
   `place_order` / `cancel_order` / `deposit_derivative_margin` /
   `withdraw_derivative_margin` giờ có `dry_run=True` mặc định.
3. **SSI không retry tự động trên POST đặt lệnh** (chống double-submit — trước đây
   1 lời gọi có thể gửi **5 POST thật**). Hãy truyền `clientRequestId` khi định
   thử lại sau lỗi mạng.

### Tầng 1 — dữ liệu ẩn danh (không cần biết provider)

```python
from vnbroker.ui.market import Market

mkt = Market(auto=True)                      # tự chọn + tự xoay vòng provider
hist = mkt.equity("ACB").history(start="2026-01-01", end="2026-06-30")

# hoặc
from vnbroker import Vnbroker
vn = Vnbroker(source="AUTO")
```

Failover áp cho `history`, `intraday`, `price_depth`; kết quả có
`df.attrs["source_used"]` để biết provider nào đã phục vụ.
**Mặc định vẫn là `"KBS"`** — `auto=True` là tuỳ chọn, không phải mặc định.

### Tầng 2 — broker (chọn provider tường minh)

```python
vn.broker(provider="ssi").get_balance()      # mỗi broker theo OpenAPI riêng
```

## Phiên bản 3.1.0 (2026-06-18) — Cleanup Release

### Breaking Changes
- **Xóa hoàn toàn MSN explorer**: Không có dữ liệu thật.
- **Xóa hoàn toàn FMP connector**: Thiếu API key, không có module khác.
- **SUPPORTED_SOURCES thu hẹp**: Chỉ còn `KBS`, `VCI`, `TCBS`, `DNSE`. MSN, FMP, GATEWAY, AUTO đã bị loại.
- **Xóa `fx()`/`crypto()`/`world_index()` tests**: Các phương thức này chỉ hoạt động với MSN/FMP — đã bị xóa.

### Removed
- Toàn bộ file rác: test scratch, benchmark artifacts, planning docs, caches, vninvest-sdk.
- Toàn bộ planning/audit docs cũ.
- `GATEWAY`, `MSN`, `FMP` khỏi `DataSource` enum, `core/settings.py`, `dispatch.py`, `source_router.py`, `user_agent.py`.
- 4 orphan test fixtures gây ERROR.
- `GatewayHttpClient`, `launcher.py`.

### Testing
- **1001 passed**, 5 skipped — **0 failures** (tính 2026-10-02, `pytest tests/unit tests/contract`).

## Đóng góp và hỗ trợ

Nếu bạn đang dùng vnbroker trong nghiên cứu, dashboard, hoặc công cụ nội bộ, vui lòng trích dẫn dự án và giữ nguyên thông báo giấy phép đi kèm.

## Giấy phép

Xem [LICENSE.md](LICENSE.md) để biết điều khoản đầy đủ.
