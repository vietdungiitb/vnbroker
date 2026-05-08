# Price Unit Standardization - Quick Reference

## 🎯 Nhanh chóng sử dụng

### Mặc định VND
```python
from vnbroker import Stock
stock = Stock(source='VCI')
df = stock.quote.history(symbol='ACB', length='1M')
# Tất cả giá ở VND, df.attrs['price_unit'] == 'VND'
```

### Yêu cầu THOUSAND_VND
```python
df = stock.quote.history(symbol='ACB', length='1M', price_unit='THOUSAND_VND')
# df.attrs['price_unit'] == 'THOUSAND_VND'
```

### Bảng giao dịch (Price Board)
```python
from vnbroker.explorer.vci.trading import Trading
vci = Trading(symbol='ACB')
df = vci.price_board()  # VND mặc định
df_t = vci.price_board(price_unit='THOUSAND_VND')
```

## 📋 Hàm được cập nhật

| Module | Hàm | Tham số mới |
|--------|-----|-----------|
| Quote (all sources) | `history()` | `price_unit='VND'` |
| Quote (all sources) | `intraday()` | `price_unit='VND'` |
| Quote (VCI) | `price_depth()` | `price_unit='VND'` |
| Trading (VCI/KBS/TCBS) | `price_board()` | `price_unit='VND'` |

## 🔧 Điều khiển mặc định toàn cục

```bash
# Linux/macOS
export vnbroker_PRICE_UNIT=THOUSAND_VND

# Windows PowerShell
$env:vnbroker_PRICE_UNIT = "THOUSAND_VND"

# Python
import os
os.environ['vnbroker_PRICE_UNIT'] = 'THOUSAND_VND'
```

## 🔍 Kiểm tra đơn vị

```python
df = stock.quote.history(symbol='ACB', length='1M')
unit = df.attrs['price_unit']  # 'VND' or 'THOUSAND_VND'
```

## ✅ Tương thích ngược

- Không có break changes
- Code cũ vẫn chạy bình thường (mặc định VND)
- Optional parameter `price_unit` không bắt buộc

## 📚 Tài liệu đầy đủ

Xem: [PRICE_UNIT_API_GUIDE.md](./PRICE_UNIT_API_GUIDE.md)
