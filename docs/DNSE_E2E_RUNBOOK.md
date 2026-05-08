# DNSE E2E Runbook (Dev + QA)

## 1. Muc tieu

Runbook nay cho phep team tu verify flow thuc te tu account -> market -> trade ma khong can hoi lai.

## 2. Chuan bi

### 2.1 Environment

```bash
set DNSE_API_KEY=your_api_key
set DNSE_API_SECRET=your_api_secret
set DNSE_BASE_URL=https://openapi.dnse.com.vn
set DNSE_ACCOUNT_NO=0001xxxxxx
```

### 2.2 Cai dat

```bash
pip install -e .
pip install -r requirements.txt
```

### 2.3 Lenh chay nhanh

```bash
python -m pytest tests/integration/test_dnse_integration.py -v
python -m tests.examples.dnse_e2e_smoke
python -m tests.examples.dnse_qa_quickcheck
```

`dnse_qa_quickcheck` se chay lan luot:

1. Integration test DNSE.
2. Smoke script DNSE.

### 2.4 One-command cho Windows PowerShell

```powershell
Copy-Item .env.dnse.example .env.dnse
# Sua file .env.dnse voi gia tri thuc te truoc khi chay
.\tests\examples\run_dnse_quickcheck.ps1 -EnvFile .env.dnse
```

## 3. Kich ban E2E bat buoc

### Scenario A - Account health

Steps:

1. Goi `get_accounts`.
2. Chon 1 `account_no` hop le.
3. Goi `get_balances`.
4. Goi `get_loan_packages` va `get_ppse`.

Expected:

- Co du lieu account.
- Co so du/asset fields.
- PPSE tra ve gia tri hop le (> = 0).

### Scenario B - Market data read

Steps:

1. Goi `get_security_definition(symbol="HPG")`.
2. Goi `get_ohlc(bar_type="STOCK", query={...})`.
3. Goi `get_trades(symbol="HPG", limit=100)`.

Expected:

- Symbol hop le, schema field dung.
- OHLC co truong time/open/high/low/close.
- Trades co data hoac 404 page not found trong live smoke hien tai; neu 404 thi ghi nhan gap contract, khong fail market-data smoke khac.
- Security definition khi normalize co the thanh DataFrame nhieu dong.

### Scenario C - Trading flow (dry run first)

Steps:

1. `send_email_otp`.
2. `create_trading_token` bang OTP hop le.
3. `post_order` (dry_run=True).
4. `post_order` that su tren quantity nho (neu duoc phep).
5. `get_order_detail` + `get_execution_detail`.
6. `cancel_order` hoac `put_order` tuy trang thai.

Expected:

- Trading token tao thanh cong.
- Lenh duoc tao/cap nhat/huy dung contract.
- Khong lo thong tin nhay cam trong log.

## 4. Mau script smoke test

```python
import os
from vnbroker.connector.dnse.client import DNSEClient

client = DNSEClient(
    api_key=os.getenv("DNSE_API_KEY"),
    api_secret=os.getenv("DNSE_API_SECRET"),
    base_url=os.getenv("DNSE_BASE_URL", "https://openapi.dnse.com.vn"),
)

accounts = client.get_accounts(raw=True)
print("accounts_ok", bool(accounts))

acct = os.getenv("DNSE_ACCOUNT_NO")
balances = client.get_balances(account_no=acct, raw=True)
print("balances_ok", bool(balances))

secdef = client.get_security_definition(symbol="HPG", raw=True)
print("secdef_ok", bool(secdef))
```

## 5. Checklist bao cao sau khi run

- [ ] Log commit hash + branch.
- [ ] Danh sach scenario pass/fail.
- [ ] Attached output tom tat (khong kem secret).
- [ ] Neu fail: root cause + huong xu ly.
