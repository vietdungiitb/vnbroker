# DNSE API Contract For vnstock

## 1. Muc tieu contract

Tai lieu nay quy dinh API level cho team dev de code dong nhat va cho QA de test theo expected behavior.

## 2. Khoi tao client

```python
from vnstock.connector.dnse.client import DNSEClient

client = DNSEClient(
    api_key="your_api_key",
    api_secret="your_api_secret",
    base_url="https://openapi.dnse.com.vn",
    show_log=False,
)
```

## 3. Contract method bat buoc

### Account

- `get_accounts(dry_run: bool = False, raw: bool = False)`
- `get_balances(account_no: str, dry_run: bool = False, raw: bool = False)`
- `get_loan_packages(account_no: str, market_type: str, symbol: str | None = None, dry_run: bool = False, raw: bool = False)`
- `get_ppse(account_no: str, market_type: str, symbol: str, price: float, loan_package_id: int, dry_run: bool = False, raw: bool = False)`

### Orders

- `get_orders(account_no: str, market_type: str, order_category: str | None = None, dry_run: bool = False, raw: bool = False)`
- `get_order_detail(account_no: str, order_id: str, market_type: str, order_category: str | None = None, dry_run: bool = False, raw: bool = False)`
- `get_execution_detail(account_no: str, order_id: str, market_type: str, order_category: str = "NORMAL", dry_run: bool = False, raw: bool = False)`
- `get_order_history(account_no: str, market_type: str, from_date: str | None = None, to_date: str | None = None, page_size: int | None = None, page_index: int | None = None, dry_run: bool = False, raw: bool = False)`

### Trade actions

- `post_order(market_type: str, payload: dict, trading_token: str, order_category: str = "NORMAL", dry_run: bool = False, raw: bool = False)`
- `put_order(account_no: str, order_id: str, market_type: str, payload: dict, trading_token: str, order_category: str | None = None, dry_run: bool = False, raw: bool = False)`
- `cancel_order(account_no: str, order_id: str, market_type: str, trading_token: str, order_category: str | None = None, dry_run: bool = False, raw: bool = False)`

### Token va auth flow

- `send_email_otp(dry_run: bool = False, raw: bool = False)`
- `create_trading_token(otp_type: str, passcode: str, dry_run: bool = False, raw: bool = False)`

### Market data

- `get_security_definition(symbol: str, board_id: str | None = None, dry_run: bool = False, raw: bool = False)`
- `get_ohlc(bar_type: str, query: dict | None = None, dry_run: bool = False, raw: bool = False)`
- `get_trades(symbol: str, board_id: str | None = None, from_date: int | None = None, to_date: int | None = None, limit: int | None = None, order: str | None = None, next_page_token: str | None = None, dry_run: bool = False, raw: bool = False)`
- `get_instruments(symbol: str | None = None, market_id: str | None = None, security_group_id: str | None = None, index_name: str | None = None, limit: int | None = None, page: int | None = None, dry_run: bool = False, raw: bool = False)`

### 3.1 Live market-data notes

- `get_ohlc(...)` live smoke hiện dùng `bar_type="STOCK"` cho history chứng khoán. Raw body có thể là một OHLC dict top-level với các key `t/o/h/l/c/v`, hoặc là list nằm trong `bars`/`data`.
- `get_security_definition(...)` live smoke hiện trả về list các dict security-definition; `price_depth()` normalizes list này bằng `pd.json_normalize`.
- `get_trades(...)` hiện vẫn 404 page not found trong live smoke, kể cả khi thử thêm `boardId=HOSE`. `intraday()` cần được xem là best-effort và phải trả empty DataFrame khi endpoint chưa ổn định.
- `get_instruments(..., limit=1000)` là ceiling an toàn quan sát được trên live smoke hiện tại; limit cao hơn có thể bị từ chối.

## 4. Error contract

- `DNSEAuthError`: 401/403, signature sai, token het han.
- `DNSERateLimitError`: 429.
- `DNSEValidationError`: 400.
- `DNSEServerError`: 5xx.
- `DNSETransportError`: timeout, connection reset.

Moi exception phai co:

- `status_code` (neu co).
- `error_code` (neu DNSE tra ve).
- `message`.
- `request_id`.

## 5. Contract cho dry-run

- `dry_run=True` phai tra ve object debug de QA verify:
  - url
  - method
  - query
  - headers mask
  - body
- Khong duoc goi network that su.

## 6. Compatibility contract cho trade.py cu

- Cac method cu trong `trade.py` van goi duoc.
- Neu method cu co ten khac, phai map sang method moi.
- Bat `DeprecationWarning` voi huong dan migration ngan gon.
