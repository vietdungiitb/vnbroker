# SSI Broker Lane — Hướng dẫn sử dụng

> Native FastConnect v3, **không cần cài `ssi-sdk`**. Đăng ký API tại
> https://developers.ssi.com.vn/ rồi đặt 4 biến môi trường
> `VNBROKER_BROKER_SSI_CLIENT_ID/_API_KEY/_API_SECRET/_PRIVATE_KEY`
> (xem `.env.example`). **Không bao giờ commit secret.**

## 1. Market data không OTP

`authenticate()` không tham số = xác thực market-data-only (không cần OTP).

```python
from vnbroker import Vnbroker

vn = Vnbroker()
ssi = vn.broker(
    provider="ssi",
    api_key="YOUR_SSI_API_KEY",
    api_secret="YOUR_SSI_API_SECRET",
)
ssi.authenticate()  # market-only

ohlc = ssi.get_ohlc("SSI", timeframe="1d",
                    from_date="2026/01/01", to_date="2026/01/31")
print(ohlc[["trading_date", "close", "volume"]].tail())

master = ssi.get_master_data()  # trần/sàn/TC toàn sàn
print(master[["symbol", "ceiling", "floor", "ref_price"]].head())
```

## 2. Auth đầy đủ + đọc danh mục

```python
ssi = vn.broker(
    provider="ssi",
    client_id="YOUR_CLIENT_ID",
    api_key="YOUR_SSI_API_KEY",
    api_secret="YOUR_SSI_API_SECRET",
    private_key="YOUR_PRIVATE_KEY",
)
ssi.authenticate(otp="123456")  # hoặc request_otp() + Smart OTP push

accounts = ssi.list_accounts()
balance = ssi.get_balance("1234561")
holdings = ssi.get_holdings("1234561")
orders = ssi.get_orders("1234561")
snapshot = ssi.portfolio_snapshot("1234561", market_prices={"SSI": 26000.0})
```

## 3. Lệnh điều kiện FCO an toàn (dry-run trước)

Mọi write `dry_run=True` mặc định. Bật write thật bằng
`ssi.session.enable_write()` sau khi đã authenticate.

```python
# 3.1. Chạy khô trước — không gửi gì lên server
dry = ssi.place_fco_gtd(
    "1234561", "SSI", "BUY", 100, 25000, 0.5,
    "2026/01/05 00:00:00", "2026/01/12 23:00:00",
)
assert dry["dry_run"] is True

# 3.2. Pattern đặt GTD rồi hủy ngay (an toàn khi kiểm tra live)
ssi.session.enable_write()
placed = ssi.place_fco_gtd(
    "1234561", "SSI", "BUY", 100, 25000, 0.5,
    "2026/01/05 00:00:00", "2026/01/12 23:00:00",
    dry_run=False,
)
print(ssi.cancel_fco(placed["fco_id"], dry_run=False))
```

## 4. Streaming realtime

```python
ssi.authenticate(otp="123456")

def on_tick(tick):
    print(tick.symbol, tick.price, tick.quantity)

ssi.stream.on_data = on_tick
ssi.stream.connect()
ssi.stream.subscribe_symbol(["SSI", "HPG"])
ssi.stream.subscribe_order_status("1234561")
ssi.stream.wait(timeout=60)
ssi.stream.disconnect()
```

## Lưu ý

- Date query `YYYY/MM/DD`; FCO place `YYYY/MM/DD HH:MM:SS`.
- Giá VND giữ nguyên (không chia 1000). `raw=True` trả payload gốc.
- SSI không có fundamentals/news — dùng KBS/VCI cho các module đó.
- Chi tiết kỹ thuật: `docs/SSI_INTEGRATION_PLAN.md`.
