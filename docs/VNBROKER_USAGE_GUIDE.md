# Hướng dẫn sử dụng vnbroker theo phiên bản

> Mục tiêu của tài liệu này là bám sát API đang có trong code hiện tại và chia theo phiên bản để lần nâng cấp sau chỉ cần thêm một mục mới.

## Cách đọc tài liệu

- Mỗi phiên bản bên dưới mô tả đúng trạng thái public API tại thời điểm đó.
- Nếu code thay đổi nhưng chưa bump `pyproject.toml`, ghi thêm một mục theo ngày ở cuối tài liệu.
- Ví dụ trong tài liệu luôn ưu tiên tên lớp và tên phương thức đang tồn tại trong repo.

## Phiên bản hiện tại

### 1.0.2 - Nền tảng public API hiện tại

Đây là mốc package đang khai báo trong [pyproject.toml](../pyproject.toml) và là trạng thái phù hợp nhất để dùng làm tài liệu chính.

#### Những gì dùng được ngay

- `Vnbroker` là client cấp cao để lấy stock, FX, crypto, world index và quỹ.
- `Quote`, `Company`, `Finance`, `Listing`, `Trading`, `News`, `MarketSnapshot`, `Fund`, `Messenger` là các entrypoint công khai chính.
- `source='AUTO'` có thể dùng ở các adapter chính để tự chọn nguồn phù hợp.
- `StockComponents` hỗ trợ `DNSE` bên cạnh các nguồn VN truyền thống.
- Giá thị trường có chuẩn đơn vị riêng; hãy kiểm tra `df.attrs["price_unit"]` trước khi lưu hoặc so sánh.
- Nếu cần dữ liệu quốc tế, repo đã có nhánh FMP riêng; xem notebook `docs/6_quickstart_fmp_international.ipynb`.

#### Khởi tạo nhanh

```python
from vnbroker import Vnbroker, Quote, Company, Finance, Listing, Trading, News, MarketSnapshot, Fund
from vnbroker.bot.notify import Messenger

broker = Vnbroker(source="AUTO", show_log=False)
stock = broker.stock("ACB", source="AUTO")
```

#### Ví dụ theo nhóm chức năng

##### 1) Giá và doanh nghiệp

```python
from vnbroker import Quote, Company, Finance

quote = Quote(source="AUTO", symbol="ACB")
history = quote.history(start="2024-01-01", end="2024-12-31")
intraday = quote.intraday(page_size=100, page=1)
depth = quote.price_depth()

company = Company(source="AUTO", symbol="ACB")
overview = company.overview()
shareholders = company.shareholders()
insider = company.insider_deals(page=1, page_size=20)
officers = company.officers(filter_by="all")

finance = Finance(source="AUTO", symbol="ACB")
balance_sheet = finance.balance_sheet(period="quarter", lang="vi")
income_statement = finance.income_statement(period="year", lang="vi")
cash_flow = finance.cash_flow(period="quarter", lang="vi")
ratio = finance.ratio(period="year", lang="vi")
```

##### 2) Danh sách mã, giao dịch và snapshot

```python
from vnbroker import Listing, Trading, MarketSnapshot

listing = Listing(source="AUTO")
all_symbols = listing.all_symbols()
vn30 = listing.symbols_by_group(group="VN30")
future = listing.all_future_indices()
bonds = listing.all_bonds()

trading = Trading(source="AUTO", symbol="ACB")
price_board = trading.price_board(symbols_list=["ACB", "VCB", "VNM"])
trade_stats = trading.trading_stats()
side_stats = trading.side_stats()

snapshot = MarketSnapshot()
heatmap = snapshot.heatmap_data_by_group("VN30")
```

##### 3) Tin tức, quỹ và cảnh báo

```python
from vnbroker import News, Fund
from vnbroker.bot.notify import Messenger

news = News(source="AUTO", symbol="ACB")
latest = news.latest()
search = news.search(query="ngân hàng")

fund = Fund()
funds = fund.listing()
detail = fund.details.top_holding(symbol="SSISCA")

bot = Messenger("telegram", "-1001234567890", "BOT_TOKEN")
bot.send_message("ACB vượt ngưỡng cảnh báo")
```

#### Nguồn hợp lệ theo nhóm

| Nhóm | Nguồn hợp lệ |
| --- | --- |
| `Quote` | `KBS`, `VCI`, `TCBS`, `MSN`, `DNSE`, `FMP`, `AUTO` |
| `Company` | `KBS`, `VCI`, `TCBS`, `AUTO` |
| `Finance` | `KBS`, `VCI`, `TCBS`, `AUTO` |
| `Listing` | `KBS`, `VCI`, `MSN`, `DNSE`, `AUTO` |
| `Trading` | `KBS`, `VCI`, `TCBS`, `AUTO` |
| `News` | `KBS`, `VCI`, `TCBS`, `RSS_CAFEF`, `RSS_VNECONOMY`, `AUTO` |
| `StockComponents` | `AUTO`, `KBS`, `VCI`, `TCBS`, `MSN`, `FMP`, `DNSE` |
| `Fund` | `FMARKET` |

#### Những lưu ý cần nhớ

- `Screener` hiện chỉ hỗ trợ TCBS.
- Nếu đang dùng notebook cũ, đổi các ví dụ `from vnbroker import vnbroker` sang `from vnbroker import Vnbroker`.
- `DNSE` cần `api_key` và `api_secret` khi đi qua `Vnbroker.stock(..., source="DNSE")`.
- `FMP` là connector ngoài, thường cần API key của nhà cung cấp.
- Nhiều adapter có retry/backoff sẵn, nhưng upstream vẫn có thể thay đổi hoặc giới hạn tốc độ.

## Phiên bản trước đó

### 3.4.0 - Giai đoạn ổn định nguồn và chuẩn hóa điều hướng

Mốc này chủ yếu bao gồm:

- cơ chế `AUTO` routing,
- chuẩn hóa luồng dữ liệu giá,
- củng cố public adapter cho các nguồn VN cốt lõi,
- các bộ tài liệu vận hành và kiểm thử đi kèm.

Tài liệu liên quan:

- [AUTO Source Guide](AUTO_SOURCE_GUIDE.md)
- [Price Unit Standardization](PRICE_UNIT_STANDARDIZATION.md)
- [MarketSnapshot Guide](MARKET_SNAPSHOT_GUIDE.md)
- [Stock News Usage Guide](STOCK_NEWS_USAGE_GUIDE.md)

## Cách thêm phiên bản mới

Khi repo được nâng cấp, chỉ cần làm 3 việc:

1. Thêm một mục phiên bản mới ngay dưới phần này.
2. Cập nhật ví dụ theo đúng public API hiện tại.
3. Ghi thay đổi vào [docs/CENTRAL_MODIFIED_FILES_AUDIT.md](CENTRAL_MODIFIED_FILES_AUDIT.md).

### Mẫu khung cho version mới

Mỗi phiên bản mới nên giữ cấu trúc này:

- `### X.Y.Z - Tên thay đổi chính`
- `#### Điểm mới` với các gạch đầu dòng mô tả thay đổi
- `#### Ví dụ dùng nhanh` với một hoặc nhiều block Python ngắn
- `#### Ghi chú tương thích` nếu có thay đổi hành vi hoặc nguồn dữ liệu

Ví dụ tối thiểu:

```python
from vnbroker import Quote

quote = Quote(source="AUTO", symbol="ACB")
history = quote.history(start="2024-01-01", end="2024-12-31")
```

## Liên kết nhanh

- [README](../README.md)
- [Changelog](../CHANGELOG.md)
- [Module tree](../module_tree_full.md)
