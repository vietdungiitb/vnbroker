# Hướng dẫn sử dụng Price Unit API - Chuẩn hóa Đơn vị Giá

## Tổng quan

Từ phiên bản này, vnstock chuẩn hóa tất cả các hàm trả về dữ liệu giá với đơn vị thống nhất. Mặc định, tất cả giá được trả về dưới **đơn vị VND (Việt Nam Đồng)**. Bạn có thể yêu cầu đơn vị khác bằng tham số `price_unit` nếu cần.

### Những thay đổi chính
- **Mặc định**: Tất cả hàm trả về giá sử dụng đơn vị **VND**
- **Tương thích ngược**: Hành vi cũ vẫn hỗ trợ qua biến môi trường `VNSTOCK_PRICE_UNIT`
- **Linh hoạt**: Bạn có thể yêu cầu đơn vị khác tại mỗi lệnh gọi hàm
- **Metadata**: Mỗi DataFrame trả về chứa thông tin đơn vị trong `df.attrs['price_unit']`

---

## Cách sử dụng

### 1. Lấy dữ liệu giá (Quote History)

#### VCI - Quote History với VND (mặc định)
```python
from vnstock import Stock

stock = Stock(source='VCI')
df = stock.quote.history(symbol='ACB', start='2024-01-01', end='2024-12-31')
print(df.attrs['price_unit'])  # Output: 'VND'
print(df.head())
# Các cột giá (open, high, low, close, volume) đều ở đơn vị VND
```

#### Yêu cầu đơn vị THOUSAND_VND (nếu cần)
```python
df_thousand = stock.quote.history(
    symbol='ACB',
    start='2024-01-01',
    end='2024-12-31',
    price_unit='THOUSAND_VND'
)
print(df_thousand.attrs['price_unit'])  # Output: 'THOUSAND_VND'
# Các cột giá được chia cho 1000 so với VND
```

#### KBS - Quote History
```python
stock_kbs = Stock(source='KBS')
df = stock_kbs.quote.history(symbol='VCB', length='3M')
# Mặc định VND, có thể yêu cầu THOUSAND_VND
```

#### TCBS - Quote History
```python
stock_tcbs = Stock(source='TCBS')
df = stock_tcbs.quote.history(symbol='HPG', count_back=60)
# Mặc định VND, hỗ trợ price_unit='THOUSAND_VND'
```

#### MSN - Quote History
```python
stock_msn = Stock(source='MSN')
df = stock_msn.quote.history(symbol='VNM', interval='1D', length='1M')
# Mặc định VND, có thể yêu cầu THOUSAND_VND
```

---

### 2. Bảng giá giao dịch (Price Board)

#### VCI Trading Price Board
```python
from vnstock.explorer.vci.trading import Trading

vci_trading = Trading(symbol='ACB')
df = vci_trading.price_board()
print(df.attrs['price_unit'])  # Output: 'VND' (mặc định)
# Chứa các cột giá như best_bid, best_offer, v.v.

# Yêu cầu THOUSAND_VND
df_thousand = vci_trading.price_board(price_unit='THOUSAND_VND')
```

#### KBS Trading Price Board
```python
from vnstock.explorer.kbs.trading import Trading as KBSTrading

kbs_trading = KBSTrading(symbol='VCB')
df = kbs_trading.price_board()
# Mặc định VND

df_thousand = kbs_trading.price_board(price_unit='THOUSAND_VND')
```

#### TCBS Trading Price Board
```python
from vnstock.explorer.tcbs.trading import Trading as TCBSTrading

tcbs_trading = TCBSTrading(symbol='TCB')
df = tcbs_trading.price_board()
# Mặc định VND, hỗ trợ price_unit

df_thousand = tcbs_trading.price_board(price_unit='THOUSAND_VND')
```

---

### 3. API Level (High-level Interface)

#### Sử dụng High-level Quote API
```python
from vnstock import quote

# Lấy lịch sử giá với VND (mặc định)
df = quote.history(symbol='ACB', source='VCI', length='1M')

# Lấy với THOUSAND_VND
df_thousand = quote.history(
    symbol='ACB',
    source='VCI',
    length='1M',
    price_unit='THOUSAND_VND'
)

# Trading price board
df_board = quote.price_board(symbol='ACB', source='KBS')
df_board_thousand = quote.price_board(
    symbol='ACB',
    source='KBS',
    price_unit='THOUSAND_VND'
)
```

---

## Điều khiển hành vi mặc định

### Biến môi trường (Environment Variable)

Để thay đổi đơn vị mặc định cho toàn bộ ứng dụng, đặt biến môi trường `VNSTOCK_PRICE_UNIT`:

**Windows (PowerShell)**
```powershell
$env:VNSTOCK_PRICE_UNIT = "THOUSAND_VND"
python your_script.py
```

**Windows (CMD)**
```cmd
set VNSTOCK_PRICE_UNIT=THOUSAND_VND
python your_script.py
```

**Linux/macOS**
```bash
export VNSTOCK_PRICE_UNIT=THOUSAND_VND
python your_script.py
```

**Python (trong code)**
```python
import os
os.environ['VNSTOCK_PRICE_UNIT'] = 'THOUSAND_VND'

# Sau đó gọi hàm như bình thường
from vnstock import Stock
stock = Stock(source='VCI')
df = stock.quote.history(symbol='ACB', length='1M')
# Sẽ trả về THOUSAND_VND vì env được đặt
```

### Giá trị hợp lệ
- `VND` (mặc định)
- `THOUSAND_VND`

Nếu bạn đặt giá trị không hợp lệ, hệ thống sẽ tự động fallback về `VND`.

---

## Kiểm tra đơn vị trong DataFrame

Mỗi DataFrame trả về từ vnstock đều có metadata về đơn vị giá:

```python
df = stock.quote.history(symbol='ACB', length='1M')

# Kiểm tra đơn vị
print(f"Đơn vị giá: {df.attrs['price_unit']}")

# Sử dụng để xử lý dữ liệu
if df.attrs['price_unit'] == 'THOUSAND_VND':
    # Nhân với 1000 để quy đổi về VND nếu cần
    df['close_vnd'] = df['close'] * 1000
```

---

## Hướng dẫn chuyển đổi đơn vị

### Từ THOUSAND_VND sang VND
```python
# Nếu bạn có dữ liệu ở THOUSAND_VND
if df.attrs['price_unit'] == 'THOUSAND_VND':
    price_cols = ['open', 'high', 'low', 'close']
    for col in price_cols:
        if col in df.columns:
            df[col] = df[col] * 1000
```

### Từ VND sang THOUSAND_VND
```python
if df.attrs['price_unit'] == 'VND':
    price_cols = ['open', 'high', 'low', 'close']
    for col in price_cols:
        if col in df.columns:
            df[col] = df[col] / 1000
```

---

## Ví dụ: Tích hợp trong ứng dụng

```python
from vnstock import Stock
import pandas as pd

class PriceAnalyzer:
    def __init__(self, symbol: str, source: str = 'VCI', price_unit: str = 'VND'):
        self.symbol = symbol
        self.stock = Stock(source=source)
        self.price_unit = price_unit
    
    def get_history(self, length: str = '1M'):
        """Lấy lịch sử giá"""
        df = self.stock.quote.history(
            symbol=self.symbol,
            length=length,
            price_unit=self.price_unit
        )
        return df
    
    def get_latest_price(self, length: str = '1D'):
        """Lấy giá mới nhất"""
        df = self.get_history(length)
        if df.empty:
            return None
        return {
            'symbol': self.symbol,
            'close': df.iloc[-1]['close'],
            'unit': df.attrs['price_unit'],
            'timestamp': df.index[-1]
        }

# Sử dụng
analyzer = PriceAnalyzer('ACB', source='VCI', price_unit='VND')
print(analyzer.get_latest_price())
```

---

## Migration Guide (Từ phiên bản cũ)

Nếu bạn có code cũ sử dụng vnstock:

**Trước (hành vi không xác định)**
```python
df = stock.quote.history(symbol='ACB', length='1M')
# Không biết đơn vị là gì
```

**Sau (rõ ràng và đầy đủ)**
```python
# Cách 1: Sử dụng mặc định VND
df = stock.quote.history(symbol='ACB', length='1M')
print(df.attrs['price_unit'])  # VND

# Cách 2: Yêu cầu THOUSAND_VND rõ ràng
df = stock.quote.history(symbol='ACB', length='1M', price_unit='THOUSAND_VND')
print(df.attrs['price_unit'])  # THOUSAND_VND
```

---

## Danh sách hàm được cập nhật

### Quote Functions (Lịch sử giá)
- `Stock.quote.history(..., price_unit=None)`
- `Stock.quote.intraday(..., price_unit=None)` (VCI)
- `Stock.quote.price_depth(..., price_unit=None)` (VCI)

### Trading Functions (Bảng giao dịch)
- `VCI.Trading.price_board(..., price_unit=None)`
- `KBS.Trading.price_board(..., price_unit=None)`
- `TCBS.Trading.price_board(..., price_unit=None)`
- `MSN.Trading.price_board(..., price_unit=None)` (if applicable)

### Core Utilities
- `vnstock.core.utils.transform.normalize_price_columns(..., target_unit=None)`
- `vnstock.core.utils.transform._parse_price_unit(raw)`

---

## Troubleshooting

### Q: Tôi nhận được lỗi "Invalid price_unit value"
**A**: Chỉ sử dụng `'VND'` hoặc `'THOUSAND_VND'`. Nếu bạn đặt giá trị khác, nó sẽ fallback về `VND`.

### Q: DataFrame của tôi không có metadata `price_unit`?
**A**: Nếu hàm trả về DataFrame trống (empty), metadata vẫn nên được đặt. Nếu không, hãy báo cáo issue.

### Q: Khi nào tôi nên dùng THOUSAND_VND?
**A**: Sử dụng khi bạn cần giá dưới dạng ngàn đơn vị (phổ biến để giảm kích thước dữ liệu hoặc tương thích với hệ thống cũ).

### Q: Tôi muốn mặc định toàn cầu là THOUSAND_VND?
**A**: Đặt biến môi trường: `export VNSTOCK_PRICE_UNIT=THOUSAND_VND` (Linux/macOS) hoặc `set VNSTOCK_PRICE_UNIT=THOUSAND_VND` (Windows).

---

## Changelog

### v2.4.0 (2026-04-16)
- ✨ Thêm tham số `price_unit` cho tất cả hàm trả về giá
- ✨ Chuẩn hóa mặc định về VND
- ✨ Thêm metadata `df.attrs['price_unit']` cho tất cả DataFrames
- 🔧 Hỗ trợ `VNSTOCK_PRICE_UNIT` env var
- ✅ Tương thích ngược 100%

---

## Liên hệ & Hỗ trợ

Nếu bạn gặp vấn đề với price_unit API, vui lòng:
1. Kiểm tra version vnstock: `python -c "import vnstock; print(vnstock.__version__)"`
2. Xem logs với `show_log=True`
3. Báo cáo issue trên GitHub với chi tiết reproduction steps
