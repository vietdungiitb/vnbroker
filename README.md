# vnbroker

Thư viện Python cho dữ liệu, phân tích và tự động hóa nghiệp vụ chứng khoán Việt Nam.

> **v3.7.0** — Rate-limit thật + logger không rò token. Server trả `429` nay **không bị retry 3 lần** nữa mà chuyển provider ngay, và cooldown theo **đúng `Retry-After`** của server thay vì con số 5s suy đoán. `logger` bịt 4 đường rò token (`Authorization: Bearer <JWT>`, token trần, OTP trần) và vá lỗi `log.info("%s", dict)` **mất trọn dòng log**. ⚠️ Có **Breaking changes** (xem [Phiên bản 3.7.0](#phiên-bản-370--2026-10-10--rate-limit-thật--logger-không-rò-token)).
>
> **v3.6.0** — Hợp đồng dữ liệu tầng 1: **mọi provider trả cùng một schema**. Sửa 3 lỗi đang sai âm thầm: `match_type` lệch casing giữa provider (`df[df.match_type=='Buy']` trả **0 dòng** từ KBS, 67 từ VCI), cột `time` lệch đơn vị lưu trữ khiến `pd.concat` ra `object`, và `market_cap` phóng đại **1000 lần**. Nối TCBS vào `AUTO` và thêm cổng `check_provider_consistency.py`. ⚠️ Có **Breaking changes** (xem [Phiên bản 3.6.0](#phiên-bản-360-2026-10-10--hợp-đồng-dữ-liệu-tầng-1)).
>
> **v3.5.0** — Kiến trúc hai tầng: dữ liệu thị trường ẩn danh (`auto=True`) tự chọn và xoay vòng provider; broker chọn provider tường minh. Kèm chặn double-submit lệnh SSI + hàng rào `dry_run` cho `connector/dnse`. ⚠️ Có **Breaking changes** (xem [Breaking Changes 3.5.0](#phiên-bản-350--2026-10-02--kiến-trúc-hai-tầng--an-toàn-đường-giao-dịch)) — `history()` trả `time` tz-aware.
>
> **Độc lập hoàn toàn từ v3.5.0:** `vnbroker` không phải fork hay phụ thuộc bất kỳ dự án ngoại nào. Mọi kiến trúc, bản quyền và mã nguồn được phát triển nội bộ từ đầu (`Direct Provider Architecture` — tầng 1 dữ liệu ẩn danh, tầng 2 broker lane). Xem `docs/PLAN_CLEAR_VNSTOCK_REFERENCES.md` để biết chi tiết các tham chiếu cũ đã được xóa sạch.

## Tóm tắt

vnbroker cung cấp một lớp truy cập thống nhất để lấy dữ liệu từ nhiều nguồn trực tiếp (VCI, KBS, TCBS, DNSE), chuẩn hóa đầu ra bằng `pandas` và giảm chi phí tích hợp cho ứng dụng phân tích, dashboard, backend và công cụ nghiên cứu.

**Điểm truy cập chính:** lớp `Vnbroker` (xem `vnbroker/common/client.py`).

## Thành phần chính

| Thành phần | Mục đích |
| --- | --- |
| `Vnbroker` | Client cấp cao để lấy stock, crypto (Binance), quỹ và Retail (FX/world index chưa hỗ trợ) |
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

[![PyPI](https://img.shields.io/pypi/v/vnbroker)](https://pypi.org/project/vnbroker/)
[![Python](https://img.shields.io/pypi/pyversions/vnbroker)](https://pypi.org/project/vnbroker/)
[![License](https://img.shields.io/pypi/l/vnbroker)](https://pypi.org/project/vnbroker/)

Cài trực tiếp từ GitHub (bản `main`):

```bash
pip install "git+https://github.com/vietdungiitb/vnbroker.git@v3.6.0"
```

Phát triển cục bộ:

```bash
git clone https://github.com/vietdungiitb/vnbroker.git
cd vnbroker
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
| `DNSE_USERNAME` | DNSE Username (JWT Trading) — **CHƯA HỖ TRỢ**, code không đọc | `your_dnse_username` |
| `DNSE_PASSWORD` | DNSE Password (JWT Trading) — **CHƯA HỖ TRỢ**, code không đọc | `your_dnse_password` |
| `VNBROKER_BROKER_TCBS_API_KEY` | TCBS OpenAPI Key cho Broker Lane (iFlash) | `your_tcbs_key` |

> **Lưu ý:** `DNSE_USERNAME` và `DNSE_PASSWORD` dành cho phần DNSE JWT/Trading chưa implement; xem `docs/PUBLISHING.md` để biết trạng thái phát hành.

## Lưu ý quan trọng

- **Market Data:** Truy cập trực tiếp provider (VCI, KBS, TCBS, DNSE) — **không cần PAT/Gateway**.
- **Broker Lane:** Gọi trực tiếp API Broker với API Key + OTP.
- Dữ liệu giá được chuẩn hóa theo contract riêng; kiểm tra `df.attrs["price_unit"]` trước khi lưu hay so sánh.
- Một số nguồn live có thể bị giới hạn tốc độ hoặc thay đổi phía upstream; adapter của thư viện có retry và backoff.
- **FX/World Index:** Không được hỗ trợ bởi các provider hiện tại (KBS, VCI, TCBS,
  DNSE). `fx()` và `world_index()` raise `NotImplementedError`.
  Riêng **`crypto()` đã hoạt động** từ v3.4 qua provider `BINANCE` (spot public,
  không cần key).

## Phiên bản 3.7.0 (2026-10-10) — Rate-limit thật, logger không rò token

Đợt này sửa hai lỗi **đo được bằng số**, mỗi lỗi có lệnh tái lập (mã `TCB`, 2026-10-10).

### Breaking Changes (3.7.0)

1. **HTTP 429 giờ ném `RateLimitError`, không phải `ConnectionError`.**
   - **Trước:** `send_request_direct` coi mọi status ≠ 200 là `ConnectionError`,
     nên `429` không mang theo `Retry-After` của server.
   - **Sau:** `429` → `vnbroker.core.exceptions.RateLimitError`, có thuộc tính
     `retry_after: float | None` và `provider`.
   - **`except ConnectionError` của bạn vẫn bắt được** (đã kiểm chứng MRO:
     `RateLimitError ⊂ ConnectionError ⊂ OSError`). Nhưng nếu bạn dùng
     `type(e) is ConnectionError` thì **phải đổi** sang `isinstance`.

2. **429 không còn bị retry 3 lần.**
   - **Trước:** một lệnh `history()` gặp 429 gửi **3** request (source cố định)
     hoặc **6** request (AUTO, 2 provider) rồi mới xoay vòng — tức bắn thêm vào
     một provider vừa bảo "chậm lại".
   - **Sau:** **1** request mỗi provider, rồi chuyển provider ngay.

3. **Cooldown theo `Retry-After` của server, không còn 5 giây suy đoán.**
   - **Trước:** `5 × 2^(lần lỗi − 1)`, tối đa 90 giây, **bỏ qua** header server.
   - **Sau:** `max(suy đoán, Retry-After)`, kẹp trong `[1, 900]` giây
     (`Config.RETRY_AFTER_MAX_SECONDS`). `Retry-After: 120` ⇒ cooldown **120s**.

### Thay đổi khác

- **`logger` bịt 4 đường rò token.** Đo trước/sau trên cùng 10 chuỗi:
  `Authorization: Bearer <JWT>`, `repr({'Authorization': 'Bearer <JWT>'})`,
  JWT trần không tên biến, `otp 123456` — trước **4/10 rò**, sau **0/10**.
- **Vá lỗi `log.info("%s", {...})` làm mất dòng log.** Filter cũ duyệt dict như
  iterable nên ra **key**; dict 2 khóa còn gây `TypeError` và **mất trọn dòng log**.
  Nay giá trị được hiển thị đúng và đã redact.
- **Vá lỗi redact quá rộng:** `monkey=abc` trước đây ra `'monkey: "***REDACTED***"'`
  vì regex không có word boundary.
- `bearer of the bond coupon` (tiếng Anh thường) **không** còn bị bóp méo.

### Thứ **CHƯA** chạy (đừng đọc như đã xong)

- **CI GitHub Actions không chạy** (billing). Mọi gate trong mục này chạy **LOCAL**
  qua `pwsh -File scripts/check_all.ps1`.
- Chưa đo live với traffic TCBS/DNSE thật trong lần sửa này.

---

## Phiên bản 3.6.0 (2026-10-10) — Hợp đồng dữ liệu tầng 1

Ba lỗi dưới đây **đang xảy ra với người dùng** và đều sai **âm thầm** — không
ném lỗi, chỉ cho ra số sai. Toàn bộ số liệu dưới đây đo được trên dữ liệu thật
(mã `TCB`, `VCB`, ngày 2026-10-10), trước và sau khi sửa.

### Breaking Changes (3.6.0)

1. **`match_type` dùng chung một tập giá trị.**
   - **Trước:** KBS trả `'buy'/'sell'/'atc'`, VCI trả `'Buy'/'Sell'/'ATC'`.
     `df[df.match_type == "Buy"]` trả **0 dòng** từ KBS và **67 dòng** từ VCI cho
     cùng một phiên.
   - **Sau:** mọi provider trả `{Buy, Sell, ATO, ATC, unknown}`.
   - **Nếu bạn lọc `== 'buy'` (chữ thường): đổi thành `'Buy'`.**

2. **`market_cap` của `MarketSnapshot` đúng bằng 1000 lần.**
   - **Trước:** `heatmap_data()` / `heatmap_df()` nhân `×1000` khi `price_unit=None`
     (mặc định), trong khi provider thật sự trả giá **VND**. VCB ra
     `473 766 777.83` tỷ thay vì `473 766.78` tỷ.
   - **Sau:** đơn vị giá đọc từ `df.attrs['price_unit']` do chính provider dán.
   - **Nếu bạn tự nhân 1000 ở lớp trên: bỏ đi**, dữ liệu đã đúng.

3. **Cột `time` có một đơn vị lưu trữ duy nhất: `datetime64[ns, Asia/Ho_Chi_Minh]`.**
   - **Trước:** KBS `[us]` và VCI `[s]`; `pd.concat` hai frame cho **`object`** và
     mọi phép tính thời gian hỏng mà không báo lỗi.
   - **Sau:** cả hai về `[ns, Asia/Ho_Chi_Minh]`.
   - **Nếu bạn so `dtype` cứng:** dùng `str(df['time'].dtype)`.

### Thay đổi khác

- **TCBS vào `source="AUTO"`** (nối **cuối**, sau VCI/KBS) khi có `TCBS_JWT_TOKEN`.
  Trước đây nó không bao giờ vào AUTO dù có token hợp lệ. Dùng biến
  `TCBS_JWT_TOKEN`; `TCBS_AUTH_TOKEN` **không phải JWT** và server trả
  `401 validate.token.error`.
- Cổng mới `scripts/check_provider_consistency.py` chạy trong `check_all.ps1`:
  phát hiện ba danh sách provider lệch nhau trước khi chúng lệch.
- `screener` không còn trả danh sách rỗng trong `AUTO`.
- Thêm `tests/isolation.py`: test đơn vị không còn phụ thuộc `.env` của máy.

### Biết trước

- **TCBS `intraday()` không có thông tin mua/bán.** Server trả `"a": ""` cho mọi
  bản ghi nên `match_type` là `unknown`; KBS/VCI vẫn có `Buy`/`Sell`. Nếu `AUTO`
  chọn TCBS cho `intraday`, đó là kết quả đúng theo nguồn, không phải lỗi.
- **DNSE chưa được xác nhận chạy được.** TLS handshake tới `openapi.dnse.com.vn`
  timeout ở máy đo ngày 2026-10-10. Hãy đo lại trước khi kết luận.
- **Thư viện không tự nạp `.env`.** Hãy `export` biến môi trường, hoặc truyền
  `auth_token` / `api_key` tường minh.

Bằng chứng đầy đủ: `docs/REPORT_FINAL_TIER1_WAVE12.md`,
`docs/TEST_REPORT_TIER1_WAVE12.md`, `docs/AUDIT_TIER1_WAVE12.md`.

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
