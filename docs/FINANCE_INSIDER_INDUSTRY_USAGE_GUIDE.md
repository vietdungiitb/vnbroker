# Hướng dẫn sử dụng: Tài chính cơ bản, Giao dịch nội bộ, So sánh ngành

> Áp dụng cho nhánh code hiện tại của dự án vnstock-main.
> 
> Mục tiêu: dùng đúng 3 nhóm hàm đã chuẩn hóa để tích hợp vào service/API/dashboard.

---

## 1) Khởi tạo nhanh

Khuyến nghị đi qua client Vnstock để có đầy đủ component company/finance cho một mã cổ phiếu.

```python
from vnstock import Vnstock

client = Vnstock(show_log=False)
stock = client.stock(symbol="VCB", source="AUTO")

# stock.company -> nhóm giao dịch nội bộ
# stock.finance -> nhóm tài chính + so sánh ngành
```

Gợi ý source:
- Dùng AUTO cho môi trường production để có failover.
- Dùng KBS/VCI/TCBS khi cần truy vết cố định theo provider.

---

## 2) Tài chính cơ bản: fundamental_snapshot

Hàm:
- stock.finance.fundamental_snapshot(symbol=None, metrics=None, period=None, **kwargs)

Mục đích:
- Lấy snapshot chỉ số tài chính mới nhất theo schema chuẩn hóa dạng long-table.

Ví dụ cơ bản:

```python
df = stock.finance.fundamental_snapshot(
    period="quarter",
    metrics=["roe", "roa", "eps", "book_value_per_share"]
)

print(df.head())
```

Ví dụ tự chọn metric numeric (không truyền metrics):

```python
df_auto = stock.finance.fundamental_snapshot(period="year")
print(df_auto[["metric", "value"]].head(10))
```

Schema đầu ra:
- symbol
- period
- report_date
- metric
- value
- unit
- source
- source_used

Lưu ý:
- period nhận quarter/year/annual, trong đó annual được chuẩn hóa về year.
- Nếu provider trả rỗng, hàm trả DataFrame rỗng nhưng vẫn có đủ cột schema.

---

## 3) Giao dịch nội bộ: insider_deals

Hàm:
- stock.company.insider_deals(**kwargs)

Tham số thường dùng:
- page: trang dữ liệu, mặc định 1
- page_size: số dòng/trang, mặc định theo provider
- start_date, end_date: lọc theo thời gian
- actor_type: lọc nhóm đối tượng nội bộ
- standardize: True/False (mặc định True)

Ví dụ thực tế:

```python
df_insider = stock.company.insider_deals(
    page=1,
    page_size=50,
    start_date="2025-01-01",
    end_date="2025-12-31",
    actor_type=None,
    standardize=True
)

print(df_insider.head())
```

Nếu cần dữ liệu raw provider để debug mapping:

```python
df_raw = stock.company.insider_deals(page=1, page_size=20, standardize=False)
```

Schema chuẩn hóa (khi standardize=True):
- symbol
- announce_date
- deal_date
- actor_name
- actor_type
- action (BUY/SELL)
- quantity
- price
- ratio
- note
- source
- source_used

Lưu ý:
- Nên giữ standardize=True cho mọi luồng nghiệp vụ và API công khai.
- AUTO có thể failover giữa provider, nhưng schema đã giữ ổn định ở lớp normalization.

---

## 4) So sánh ngành

Nhóm này gồm 3 hàm:
- industry_peers
- industry_benchmark
- industry_rank

### 4.1 industry_peers

Hàm:
- stock.finance.industry_peers(symbol=None, level=4, include_exchanges=None, max_peers=100)

Ví dụ:

```python
df_peers = stock.finance.industry_peers(
    symbol="VCB",
    include_exchanges=["HOSE", "HNX", "UPCOM"],
    max_peers=30
)

print(df_peers.head())
```

Ý nghĩa:
- Trả danh sách mã đồng ngành của symbol mục tiêu.

### 4.2 industry_benchmark

Hàm:
- stock.finance.industry_benchmark(symbol=None, metrics=None, period="quarter", method="median")

Ví dụ:

```python
df_benchmark = stock.finance.industry_benchmark(
    symbol="VCB",
    metrics=["roe", "roa", "eps"],
    period="quarter"
)

print(df_benchmark.head())
```

Ý nghĩa:
- Tạo bảng benchmark theo từng peer và từng metric.
- Có sẵn industry_median, industry_mean, total_peers.

### 4.3 industry_rank

Hàm:
- stock.finance.industry_rank(symbol=None, metric="roe", period="quarter", method="percentile")

Ví dụ:

```python
df_rank = stock.finance.industry_rank(
    symbol="VCB",
    metric="roe",
    period="quarter"
)

target = df_rank[df_rank["peer_symbol"] == "VCB"]
print(target[["peer_symbol", "peer_value", "rank", "percentile", "zscore"]])
```

Ý nghĩa cột:
- rank: xếp hạng trong ngành (1 là cao nhất)
- percentile: vị trí tương đối trong dải [0..100]
- zscore: độ lệch chuẩn so với trung bình ngành

---

## 5) Luồng tích hợp khuyến nghị cho API backend

Thứ tự gọi điển hình cho endpoint phân tích 1 mã:
1. Gọi fundamental_snapshot để lấy chỉ số mới nhất.
2. Gọi industry_peers để xác định tập so sánh.
3. Gọi industry_benchmark cho nhóm metric cốt lõi.
4. Gọi industry_rank cho từng metric quan trọng.
5. Gộp thành payload JSON trả frontend.

Ví dụ hàm service:

```python
def build_finance_scorecard(symbol: str, source: str = "AUTO"):
    from vnstock import Vnstock

    stock = Vnstock(show_log=False).stock(symbol=symbol, source=source)

    snapshot = stock.finance.fundamental_snapshot(
        metrics=["roe", "roa", "eps", "book_value_per_share"],
        period="quarter"
    )
    peers = stock.finance.industry_peers(symbol=symbol, max_peers=50)
    benchmark = stock.finance.industry_benchmark(
        symbol=symbol,
        metrics=["roe", "roa", "eps"],
        period="quarter"
    )
    rank_roe = stock.finance.industry_rank(symbol=symbol, metric="roe", period="quarter")

    return {
        "symbol": symbol,
        "snapshot": snapshot.to_dict("records"),
        "peers": peers.to_dict("records"),
        "benchmark": benchmark.to_dict("records"),
        "rank_roe": rank_roe.to_dict("records"),
    }
```

---

## 6) Xử lý lỗi và dữ liệu thiếu

Trường hợp hay gặp:
- DataFrame rỗng do mã không có dữ liệu ở provider hiện tại.
- Một số metric không tồn tại với ngành/mã cụ thể.
- Upstream rate-limit ở test live.

Khuyến nghị:
- Dùng source="AUTO" ở runtime.
- Luôn guard DataFrame rỗng trước khi tính toán sâu.
- Chỉ render metric có dữ liệu khác null ở frontend.

Ví dụ guard:

```python
if snapshot.empty:
    return {"status": "warning", "message": "Chưa có dữ liệu snapshot cho mã này"}
```

---

## 7) Checklist dùng production

- Dùng chuẩn symbol in hoa, ví dụ VCB, FPT, HPG.
- Không tắt standardize cho insider trừ khi debug.
- Chốt danh sách metric chuẩn theo nghiệp vụ dashboard.
- Log source/source_used để dễ audit khi AUTO failover.
- Với test live integration, bật biến VNSTOCK_RUN_LIVE_INTEGRATION=1 theo lịch kiểm thử.

---

## 8) Tóm tắt nhanh

- Tài chính cơ bản: dùng fundamental_snapshot.
- Giao dịch nội bộ: dùng insider_deals với standardize=True.
- So sánh ngành: peers -> benchmark -> rank theo thứ tự.

Bộ 3 nhóm hàm này đã sẵn sàng để đưa vào service phân tích và API trả dữ liệu cho dashboard.
