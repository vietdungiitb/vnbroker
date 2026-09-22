# vnbroker - Audit Report: Historical Data Retrieval & Local DB Synchronization

**Date:** 2026-07-05  
**Scope:** Historical Data Adjustment, Trading Flows (Foreign, Proprietary, Insider), and Database Sync Integrity  
**Status:** Audit & Proposal Phase  

---

## Executive Summary

This audit evaluates the capabilities of `vnbroker` (v3.1.1) in handling **Historical stock & index data (OHLCV)** and **Detailed Trading Statistics (Foreign, Proprietary, Insider Flows)**. 

### Key Findings:
1. **Adjusted vs. Unadjusted Data Gap:** Current quote explorers do not allow switching between adjusted and unadjusted data. Data is returned in whatever format the default explorer endpoint serves (VCI uses adjusted gap-chart, TCBS computes from intraday ticks).
2. **Empty Trading Flow Methods:** In [vnbroker/api/trading.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/api/trading.py), methods for `foreign_trade`, `prop_trade`, and `insider_deal` exist only as placeholders (`pass`), creating a disconnect between the API layer and explorer capabilities.
3. **No Storage Persistence Layer:** `vnbroker` lacks local data caching or database synchronization utilities. Users attempting to cache historical data locally risk data corruption (broken price series) due to corporate action events (stock splits, stock dividends, rights issues) if using naive incremental updates.

---

## 1. Audit Findings: Data Coverage & Gaps

### 1.1 Price History: Adjusted vs. Unadjusted

Historical OHLCV price series are handled by the `history()` method in quote explorers.

| Provider Explorer | API Endpoint Used | Default Adjust State | Risk / Limitation |
|:---|:---|:---|:---|
| **VCI** ([vci/quote.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/explorer/vci/quote.py)) | `chart/OHLCChart/gap-chart` | **Adjusted** | Smoothed chart is ideal for technical analysis, but hides actual execution prices, breaking order book models. |
| **KBS** ([kbs/quote.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/explorer/kbs/quote.py)) | Internal KBS chart api | **Adjusted** | No option to toggle unadjusted data. |
| **TCBS** ([tcbs/quote.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/explorer/tcbs/quote.py)) | Computed from `/nyx/v1/intraday/his/paging` | **Unadjusted** (by nature of raw ticks) | Computes OHLC dynamically from intraday trades. If a corporate action happens, past historical calculations will not match the adjusted charts. |
| **DNSE** ([dnse/quote.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/explorer/dnse/quote.py)) | Internal DNSE chart api | **Adjusted** | Standard API behavior without toggle options. |

### 1.2 Detailed Trading Statistics: Placeholder Status

Lớp [Trading](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/api/trading.py#L127-L160) định nghĩa các phương thức lấy dữ liệu dòng tiền chuyên sâu nhưng chưa được liên kết tới bất kỳ Explorer thực tế nào:

```python
# vnbroker/api/trading.py (Trạng thái hiện tại)
@dynamic_method
def foreign_trade(self, *args: Any, **kwargs: Any) -> Any:
    """Retrieve foreign trade data for the given symbol."""
    pass  # Chưa có cài đặt dưới explorer

@dynamic_method
def prop_trade(self, *args: Any, **kwargs: Any) -> Any:
    """Retrieve property trade data for the given symbol."""
    pass  # Chưa có cài đặt dưới explorer

@dynamic_method
def insider_deal(self, *args: Any, **kwargs: Any) -> Any:
    """Retrieve insider deal data for the given symbol."""
    pass  # Chưa có cài đặt dưới explorer
```

---

## 2. Database Sync Pitfalls & Corporate Action Detection

Khi lưu trữ dữ liệu lịch sử OHLCV ở máy cục bộ (Local Database) nhằm tối ưu hiệu năng backtest và giảm số lượng cuộc gọi API, các nhà phát triển thường đối mặt với hai rủi ro lớn:

### 2.1 Các lỗi thường gặp
1. **Full Load (Tải lại toàn bộ hàng ngày):** 
   - *Hạn chế:* Gây quá tải băng thông, làm chậm tốc độ hệ thống khi quy mô danh mục tăng lên hàng trăm mã.
2. **Naive Append (Nối dữ liệu ngày mới trực tiếp):**
   - *Hạn chế:* Khi doanh nghiệp thực hiện quyền (chia cổ tức bằng cổ phiếu, chia tách, phát hành thêm), giá của các phiên giao dịch trong quá khứ trên máy chủ nguồn sẽ bị điều chỉnh giảm xuống. Nếu nối trực tiếp ngày mới, chuỗi giá sẽ bị gãy khúc (ví dụ: ngày hôm trước giá 50.000đ, ngày hôm sau giá điều chỉnh còn 35.000đ nhưng lịch sử cũ trong database vẫn giữ mốc 50.000đ).

### 2.2 Thuật toán Kiểm Tra Chéo (Cross-Validation Logic)
Giải pháp tối ưu là tải gối đầu $N$ phiên (thường là $N = 10$ ngày giao dịch gần nhất) và so sánh chéo giữa API nguồn và Local CSDL:

$$\Delta P\% = \frac{|P_{\text{local}} - P_{\text{api}}|}{P_{\text{api}}} \times 100\%$$

- **Nếu $\Delta P\% > \text{Threshold}$ (ví dụ $0.5\%$) xuất hiện đồng loạt trên các phiên đối chiếu:** 
  Có sự kiện điều chỉnh giá (Corporate Action). Cần kích hoạt tiến trình **Xóa lịch sử cũ và tải lại toàn bộ** (Full Overwrite).
- **Nếu $\Delta P\% \le \text{Threshold}$:**
  Không có sự kiện quyền. Chỉ cần lọc bỏ phần trùng lặp và tiến hành **Ghép nối lũy kế** (Incremental Append).

---

## 3. Bản Kế Hoạch Nâng Cấp Hệ Thống

### 3.1 Nâng Cấp API Lịch Sử Giá (`history()`)

**Thay đổi chữ ký hàm:**
Thêm tham số `adjusted: bool = True` tại [vnbroker/api/quote.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/api/quote.py) và các lớp Explorer.

```python
# Cập nhật trong vnbroker/api/quote.py
def history(self, symbol: Optional[str] = None, start: str = None, end: str = None, 
            interval: str = TimeResolutions.DAILY, adjusted: bool = True, **kwargs: Any) -> pd.DataFrame:
```

**Bản đồ Endpoint nâng cấp:**
- **VCI:** Mapping `adjusted=True` với `/OHLCChart/gap-chart` và `adjusted=False` với `/OHLCChart/raw-chart`.
- **TCBS:** Khi `adjusted=False`, sử dụng trực tiếp kết quả OHLC tính toán từ Tick. Khi `adjusted=True`, áp dụng hệ số điều chỉnh giá nhận được từ API lịch sử quyền.

### 3.2 Tích Hợp Thống Kê Dòng Tiền & Cung/Cầu

Hiện thực hóa các phương thức trống bằng cách khai thác API trực tiếp của KBS và TCBS:
1. **Dòng tiền ngoại (`foreign_trade`):**
   Khai thác `/rtranking/foreignTotal` của KBS. Normalization các cột: `foreign_buy_volume`, `foreign_sell_volume`, `foreign_net_volume`.
2. **Dòng tiền tự doanh (`prop_trade`):**
   Lấy báo cáo giao dịch tự doanh toàn thị trường từ HSX/HNX thông qua API tổng hợp của VCI hoặc KBS.
3. **Thống kê Cung/Cầu (Order Book Accumulation):**
   Tính toán tổng khối lượng đặt mua (Bid Volume) và tổng khối lượng đặt bán (Ask Volume) từ API sổ lệnh độ sâu khớp lệnh (Price Board / Depth).

### 3.3 Triển Khai Module Đồng Bộ `vnbroker.storage.SyncManager`

Dưới đây là mã nguồn đề xuất cho module lưu trữ `vnbroker/storage/sync.py` sử dụng cơ sở dữ liệu SQLite:

```python
# vnbroker/storage/sync.py
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from vnbroker import Vnbroker
from vnbroker.core.utils.logger import get_logger

logger = get_logger(__name__)

class SyncManager:
    """
    Quản lý đồng bộ dữ liệu lịch sử cổ phiếu và chỉ số vào Local Database.
    Tự động phát hiện và xử lý sự kiện quyền thông qua kiểm tra chéo (Cross-Validation).
    """
    
    def __init__(self, db_path: str = "vnbroker_data.db", provider: str = "AUTO"):
        self.db_path = db_path
        self.vn = Vnbroker(source=provider)
        self._init_db()

    def _init_db(self):
        """Khởi tạo cấu trúc bảng CSDL cục bộ."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_ohlcv (
                    symbol TEXT,
                    time TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    PRIMARY KEY (symbol, time)
                )
            """)
            conn.commit()

    def get_local_data(self, symbol: str) -> pd.DataFrame:
        """Đọc dữ liệu lịch sử đã có từ Local CSDL."""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT time, open, high, low, close, volume FROM daily_ohlcv WHERE symbol = ? ORDER BY time ASC"
            return pd.read_sql_query(query, conn, params=(symbol,))

    def save_full_history(self, symbol: str, df: pd.DataFrame):
        """Ghi đè toàn bộ lịch sử giá của mã chứng khoán."""
        df_to_save = df.copy()
        df_to_save["symbol"] = symbol
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM daily_ohlcv WHERE symbol = ?", (symbol,))
            df_to_save.to_sql("daily_ohlcv", conn, if_exists="append", index=False)
            conn.commit()
        logger.info(f"Đã lưu đè toàn bộ dữ liệu lịch sử cho {symbol} ({len(df)} phiên)")

    def append_new_records(self, symbol: str, df_new: pd.DataFrame):
        """Ghi lũy kế các phiên giao dịch mới vào CSDL."""
        if df_new.empty:
            return
        df_to_save = df_new.copy()
        df_to_save["symbol"] = symbol
        
        with sqlite3.connect(self.db_path) as conn:
            df_to_save.to_sql("daily_ohlcv", conn, if_exists="append", index=False)
            conn.commit()
        logger.info(f"Đã ghép nối (append) thêm {len(df_new)} phiên giao dịch mới cho {symbol}")

    def sync_symbol(self, symbol: str, overlap_days: int = 10, threshold_pct: float = 0.5) -> str:
        """
        Đồng bộ dữ liệu và áp dụng kiểm tra chéo (Cross-Validation).
        
        Args:
            symbol: Mã cổ phiếu hoặc chỉ số cần đồng bộ.
            overlap_days: Số ngày đối chiếu chéo gối đầu (Mặc định 10).
            threshold_pct: Ngưỡng phần trăm phát hiện sự thay đổi giá do sự kiện quyền.
            
        Returns:
            Kết quả hành động ('FULL_RELOADED' | 'INCREMENTAL_APPENDED' | 'UP_TO_DATE')
        """
        symbol = symbol.upper()
        df_local = self.get_local_data(symbol)
        
        # 1. Trường hợp DB trống: Tải từ 2015 đến hiện tại (Full Load)
        if df_local.empty:
            logger.info(f"CSDL cục bộ chưa có dữ liệu cho {symbol}. Đang thực hiện Full Load...")
            df_full = self.vn.stock(symbol).quote.history(start="2015-01-01")
            df_full["time"] = pd.to_datetime(df_full["time"]).dt.strftime("%Y-%m-%d")
            self.save_full_history(symbol, df_full)
            return "FULL_RELOADED"

        last_local_date_str = df_local["time"].max()
        last_local_date = datetime.strptime(last_local_date_str, "%Y-%m-%d")
        
        # 2. Lấy dữ liệu gối đầu (Overlap) để thực hiện đối chiếu chéo
        start_fetch_date = last_local_date - timedelta(days=overlap_days * 1.5)
        start_fetch_str = start_fetch_date.strftime("%Y-%m-%d")
        
        # Tải dữ liệu phiên mới từ API
        df_api = self.vn.stock(symbol).quote.history(start=start_fetch_str)
        df_api["time"] = pd.to_datetime(df_api["time"]).dt.strftime("%Y-%m-%d")

        if df_api.empty:
            logger.warning(f"Không lấy được dữ liệu mới từ API cho {symbol}")
            return "UP_TO_DATE"

        # 3. Tìm khoảng giao thoa thời gian để đối chiếu chéo
        common_dates = set(df_local["time"]).intersection(set(df_api["time"]))
        if not common_dates:
            logger.info(f"Không có khoảng giao thoa thời gian cho {symbol}. Tiến hành reload...")
            df_full = self.vn.stock(symbol).quote.history(start="2015-01-01")
            df_full["time"] = pd.to_datetime(df_full["time"]).dt.strftime("%Y-%m-%d")
            self.save_full_history(symbol, df_full)
            return "FULL_RELOADED"

        df_local_check = df_local[df_local["time"].isin(common_dates)].set_index("time")
        df_api_check = df_api[df_api["time"].isin(common_dates)].set_index("time")
        
        # 4. Tính sai lệch giá đóng cửa
        merged = df_local_check.join(df_api_check, lsuffix='_local', rsuffix='_api')
        merged['diff_pct'] = (abs(merged['close_local'] - merged['close_api']) / merged['close_api']) * 100
        
        significant_diffs = merged[merged['diff_pct'] > threshold_pct]
        
        # Phán quyết: Phát hiện sự kiện quyền nếu có từ 2 phiên trở lên bị lệch
        if len(significant_diffs) > 1:
            logger.warning(
                f"[CẢNH BÁO SỰ KIỆN QUYỀN] Giá lịch sử bị lệch vượt ngưỡng tại {len(significant_diffs)} phiên. "
                f"Tiến hành làm sạch CSDL cũ và tải lại toàn bộ..."
            )
            df_full = self.vn.stock(symbol).quote.history(start="2015-01-01")
            df_full["time"] = pd.to_datetime(df_full["time"]).dt.strftime("%Y-%m-%d")
            self.save_full_history(symbol, df_full)
            return "FULL_RELOADED"
        else:
            # Chỉ ghép nối dữ liệu mới
            df_new_records = df_api[df_api["time"] > last_local_date_str]
            if df_new_records.empty:
                logger.info(f"Dữ liệu {symbol} đã ở trạng thái mới nhất.")
                return "UP_TO_DATE"
            
            self.append_new_records(symbol, df_new_records)
            return "INCREMENTAL_APPENDED"
```

---

## 4. Khuyến Nghị Kỹ Thuật

> [!IMPORTANT]
> 1. **Đối với VNINDEX (Chỉ số thị trường):** VNINDEX không có sự kiện chia tách hoặc trả cổ tức làm điều chỉnh giá như cổ phiếu. Có thể áp dụng quy trình đồng bộ bỏ qua kiểm tra chéo sai số lớn để giảm thời gian xử lý.
> 2. **Lưu trữ tệp Parquet:** Đối với lượng dữ liệu lớn phục vụ backtesting định lượng, khuyến nghị cấu hình thêm Driver xuất dữ liệu ra file `.parquet` phân vùng (partitioned) theo cột `symbol` thay vì ghi trực tiếp vào một file SQLite duy nhất để tối đa hóa tốc độ tải dữ liệu bằng `pandas.read_parquet()`.
> 3. **Kiểm tra chéo định kỳ:** Có thể cấu hình cron job tự động chạy `SyncManager` vào lúc 16:30 hàng ngày sau khi phiên khớp lệnh hoàn tất.
