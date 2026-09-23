# Retail & Unified UI — Hướng dẫn sử dụng (v3.3)

> Không cần credentials. Nguồn: SJC/BTMC (vàng), Vietcombank (tỷ giá).

## 1. Giá vàng SJC

```python
from vnbroker import Vnbroker

retail = Vnbroker().retail()
sjc = retail.gold(source="sjc", date="2026-01-15")
print(sjc[["name", "branch", "buy_price", "sell_price"]].head())
# date None = hôm nay; SJC chỉ có dữ liệu từ 2016-01-02
```

## 2. Giá vàng BTMC (bỏ qua date)

```python
btmc = retail.gold(source="btmc")
print(btmc[["name", "karat", "buy_price", "sell_price"]].head())
# Schema khác SJC (có karat/gold_content/world_price/time) — giữ nguyên upstream
```

## 3. Tỷ giá Vietcombank

```python
fx = retail.exchange_rate(date="2026-01-15")
print(fx[["currency_code", "currency_name", "buy_cash", "sell"]].head())
# date None/"" = hôm nay
```

## 4. Unified UI (không cần biết source)

```python
from vnbroker.ui import Fundamental, Market, Reference, Retail, show_api

mkt = Market()  # default KBS
hist = mkt.equity("SSI").history(start="2026-01-01")
prof = Reference().company("SSI").profile()
bs = Fundamental().equity("SSI").balance_sheet(period="year")
show_api()  # in cây API
```

## Lưu ý

- Mọi read trả `pd.DataFrame` (rỗng đúng schema khi không dữ liệu, không `None`);
  `df.attrs["source"]` = `"SJC"|"BTMC"|"VCB"`.
- Lỗi mạng → `RuntimeError` prefix nguồn; date sai → `ValueError` fail-sớm.
- Key BTMC trong code là key public của upstream (giữ nguyên như nguồn).
- Chi tiết kỹ thuật: `docs/ROADMAP_V33_PLAN.md`.
