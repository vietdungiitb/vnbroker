# vnbroker

Thư viện Python công khai cho dữ liệu, phân tích và tự động hóa nghiệp vụ chứng khoán Việt Nam.

> Tài liệu này phản ánh trạng thái hiện tại của repo: các adapter thị trường, tài chính, tin tức, snapshot, quỹ, bot nhắn tin và nhánh DNSE đã có trong cây mã nguồn.

## Tóm tắt

vnbroker cung cấp một lớp truy cập thống nhất để lấy dữ liệu từ nhiều nguồn khác nhau, chuẩn hóa đầu ra bằng `pandas` và giảm chi phí tích hợp cho ứng dụng phân tích, dashboard, backend và công cụ nghiên cứu.

Nếu bạn đang xem tài liệu cũ có tên `vnstock` hoặc `vnbroker3`, đó là dấu vết lịch sử. Tên gói hiện tại trong repo này là `vnbroker`.

## Thành phần chính

| Thành phần | Mục đích |
| --- | --- |
| `Vnbroker` | Client cấp cao để lấy stock, FX, crypto, world index và quỹ |
| `Quote` | Giá lịch sử, intraday, price depth |
| `Company` | Hồ sơ công ty, cổ đông, giao dịch nội bộ, ban lãnh đạo, công ty con, tin tức và sự kiện |
| `Finance` | Bảng cân đối kế toán, kết quả kinh doanh, lưu chuyển tiền tệ, chỉ số tài chính |
| `Listing` | Danh sách mã, nhóm ngành, nhóm chỉ số, futures, trái phiếu, covered warrant |
| `Trading` | Dữ liệu giao dịch và market board |
| `Screener` | Bộ lọc cổ phiếu TCBS, hiện là adapter riêng và phụ thuộc nguồn này |
| `News` | Tin tức chuẩn hóa từ nhiều nguồn |
| `MarketSnapshot` | Snapshot thị trường cho heatmap và dashboard danh mục |
| `Fund` | Dữ liệu quỹ từ FMarket |
| `Messenger` | Gửi cảnh báo qua Slack, Telegram, Discord, Lark |

## Nguồn dữ liệu hiện có

- `KBS`, `VCI`, `TCBS`, `DNSE`, `AUTO`: nhóm dữ liệu chứng khoán Việt Nam, công ty, tài chính, danh sách niêm yết và giao dịch.
- `MSN`: ngoại hối, crypto và một số chỉ số thế giới.
- `RSS_CAFEF`, `RSS_VNECONOMY`: nguồn tin tức RSS.
- `FMARKET`: dữ liệu quỹ.
- `FMP`, `Binance`: connector ngoài cho dữ liệu quốc tế và crypto.
- `AUTO`: cơ chế chọn nguồn và failover ở một số adapter.

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

### 1. Client thống nhất

```python
from vnbroker import Vnbroker

broker = Vnbroker(source="AUTO", show_log=False)
acb = broker.stock("ACB", source="AUTO")
history = acb.quote.history(start="2024-01-01", end="2024-12-31")
overview = acb.company.overview()
```

### 2. Adapter trực tiếp

```python
from vnbroker import Quote, Company, Finance, Listing, News, MarketSnapshot

quote = Quote(source="KBS", symbol="ACB")
df = quote.history(start="2024-01-01", end="2024-03-31")

company = Company(source="AUTO", symbol="ACB")
profile = company.overview()

finance = Finance(source="AUTO", symbol="ACB")
ratios = finance.ratio()

listing = Listing(source="AUTO")
vn30 = listing.symbols_by_group(group="VN30")

news = News(source="AUTO", symbol="ACB")
latest_news = news.latest()

snapshot = MarketSnapshot()
heatmap = snapshot.heatmap_data_by_group("VN30")
```

### 3. Gửi cảnh báo bot

```python
from vnbroker.bot.notify import Messenger

bot = Messenger("telegram", "-1001234567890", "BOT_TOKEN")
bot.send_message("ACB vượt ngưỡng cảnh báo")
```

## Lưu ý quan trọng

- Dữ liệu giá được chuẩn hóa theo contract riêng; hãy kiểm tra `df.attrs["price_unit"]` trước khi lưu hay so sánh.
- Nếu cần tương thích ngược, xem `docs/PRICE_UNIT_STANDARDIZATION.md` để bật `vnbroker_PRICE_UNIT=THOUSAND_VND`.
- `Screener` chỉ hỗ trợ TCBS.
- Một số nguồn live có thể bị giới hạn tốc độ hoặc thay đổi phía upstream; adapter của thư viện có retry và backoff, nhưng không thể đảm bảo 100% cho mọi thời điểm.

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
