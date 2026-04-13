# DNSE Test Plan

## 1. Muc tieu test

- Dam bao module DNSE moi dung contract.
- Dam bao khong gay regression cho API cu.
- Dam bao flow trade thuc thi duoc o dry-run va integration environment.

## 2. Pham vi test

### Unit tests (bat buoc)

- `signature.py`:
  - Format chu ky.
  - Header list.
  - Nonce on/off.
- `http_client.py`:
  - Retry theo policy.
  - Timeout handling.
  - Mapping status code sang exceptions.
- `client.py`:
  - Query/body builder dung.
  - raw/DataFrame output mode.

### Integration tests (uu tien cao)

- Account endpoints:
  - get_accounts, get_balances, get_loan_packages, get_ppse.
- Order endpoints:
  - get_orders, get_order_detail, get_execution_detail, get_order_history.
- Token/trade endpoints:
  - send_email_otp, create_trading_token, post/put/cancel order.

### Regression tests

- Cac method cu trong `connector/dnse/trade.py`.
- So sanh output shape voi facade moi.

## 3. Test data va moi truong

- ENV can co:
  - `DNSE_API_KEY`
  - `DNSE_API_SECRET`
  - `DNSE_BASE_URL` (prod/uat)
  - `DNSE_ACCOUNT_NO` (neu can)
- Tuyet doi khong commit credentials.

## 4. Lenh test de chay ngay

```bash
# Unit cho DNSE
pytest tests/unit/connector/dnse -v

# Integration DNSE
pytest tests/integration/test_dnse_integration.py -v

# Regression API cu
pytest tests/unit/connector/dnse/test_trade_compat.py -v

# Full DNSE suite
pytest tests/unit/connector/dnse tests/integration/test_dnse_integration.py -v
```

## 5. KPI chat luong

- Unit pass rate: 100%.
- Integration pass rate: >= 95% (phan fail phai co ly do moi truong).
- Thoi gian suite unit DNSE: <= 20s.
- Coverage DNSE module moi: >= 80%.

## 6. Bug severity guideline

- Sev-1: Sai order action, sai side/quantity/price.
- Sev-2: Sai auth/signature, khong trade duoc.
- Sev-3: Sai mapping data hoac log khong day du.
- Sev-4: Van de docstring/tai lieu.
