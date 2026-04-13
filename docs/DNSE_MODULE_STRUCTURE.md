# DNSE Module Structure Blueprint

## 1. Cau truc de xuat

```text
vnstock/
  connector/
    dnse/
      __init__.py
      client.py                      # Facade chinh
      trade.py                       # Compat layer (deprecate dan)
      core/
        __init__.py
        auth.py                      # Tao auth context
        signature.py                 # Build X-Signature/Date headers
        http_client.py               # Request wrapper + retry/timeout
        errors.py                    # Error classes + mapper
        config.py                    # Base URL, timeout, env
        models.py                    # Typed response payload (optional)
      services/
        __init__.py
        account_service.py           # accounts, balances, loan packages, ppse
        market_service.py            # instruments, secdef, ohlc, trades
        order_service.py             # orders, order_detail, execution, history
        position_service.py          # positions, position_by_id, close_position
        token_service.py             # email_otp, trading_token
```

## 2. Quy tac phan bo trach nhiem

- `core/*` khong chua business logic endpoint.
- `services/*` khong xu ly pandas phuc tap, chi mapping payload endpoint.
- `client.py` la diem vao duy nhat cho nguoi dung connector.
- `trade.py` chi delegate sang `client.py`, khong viet logic moi.

## 3. Quy tac naming

- Theo snake_case va giu dong bo voi SDK DNSE:
  - `get_accounts`, `get_balances`, `get_orders`, `get_order_history`...
- Tham so chuan:
  - `account_no`, `order_id`, `market_type`, `order_category`, `trading_token`.
- Enum string uu tien chu hoa theo DNSE:
  - `STOCK`, `DERIVATIVE`, `NORMAL`.

## 4. Quy tac output

- Tang service tra `dict/list` (raw response body).
- Tang facade co 2 mode:
  - `raw=True`: tra dict/list.
  - `raw=False` (default): tra DataFrame neu endpoint dang bang.

## 5. Logging va observability

- Bat/tat log qua `show_log`.
- Moi request gan request_id (uuid) de trace.
- Log toi thieu: method, path, status_code, elapsed_ms.
- Tuyet doi khong log api_secret, trading_token day du.
