"""Probe read-only DNSE OpenAPI production (không VPN) — bằng chứng tái lập.

Chạy:
    .venv\\Scripts\\python.exe scripts\\probe_dnse_readonly.py

Đọc `DNSE_API_KEY` / `DNSE_API_SECRET` từ môi trường (hoặc `.env`).
KHÔNG in credential. KHÔNG gửi lệnh thật — chỉ GET + dry-run envelope.

Kết quả 2026-10-16 (không VPN) ghi tại `docs/REPORT_DNSE_LIVE_20261016.md`
§8-10 và kế hoạch fix tại `docs/PLAN_DNSE_FIX_20261016.md`.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

if not os.getenv("DNSE_API_KEY"):
    _env = _REPO / ".env"
    if _env.exists():
        for _raw in _env.read_text(encoding="utf-8").splitlines():
            _line = _raw.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

from vnbroker.connector.dnse.client import DNSEClient  # noqa: E402

PROD = "https://openapi.dnse.com.vn"
NOW_S = int(time.time())
DAY_S = NOW_S - 86400
TODAY0_S = NOW_S - (NOW_S % 86400)

_results: list[tuple[str, str, str]] = []


def _record(name: str, status: str, detail: str) -> None:
    _results.append((name, status, detail))
    print(f"[{status}] {name} — {detail}", flush=True)


def _probe(name: str, fn) -> None:
    try:
        out = fn()
        if hasattr(out, "shape"):
            detail = f"DataFrame shape={out.shape}"
        elif isinstance(out, dict):
            lists = {k: len(v) for k, v in out.items() if isinstance(v, list)}
            detail = f"keys={list(out.keys())[:6]} lists={lists}"
        elif isinstance(out, list):
            detail = f"list len={len(out)}"
        else:
            detail = type(out).__name__
        _record(name, "PASS", detail)
    except Exception as exc:  # noqa: BLE001 — probe ghi mọi lỗi, không nuốt
        code = getattr(exc, "status_code", None)
        _record(name, "FAIL", f"{type(exc).__name__} status={code}: {str(exc)[:120]}")


def main() -> int:
    client = DNSEClient(
        api_key=os.environ["DNSE_API_KEY"],
        api_secret=os.environ["DNSE_API_SECRET"],
        base_url=PROD,
        timeout_seconds=20.0,
    )

    print("=" * 70)
    print("DNSE production read-only probe (API key HMAC, không OTP)")
    print("=" * 70)

    accounts = client.get_accounts(raw=True)
    account_no = accounts["accounts"][0].get("accountNo") or accounts["accounts"][0].get("id", "")
    print(f"  account_no = {account_no}")

    _probe("get_balances", lambda: client.get_balances(account_no, raw=True))
    _probe("get_positions(STOCK)", lambda: client.get_positions(account_no, "STOCK", raw=True))
    _probe("get_loan_packages(HPG)", lambda: client.get_loan_packages(account_no, "STOCK", symbol="HPG", raw=True))
    _probe("get_loans(STOCK)", lambda: client.get_loans(account_no, "STOCK", raw=True))
    _probe("get_ppse(HPG,25000)", lambda: client.get_ppse(account_no, "STOCK", "HPG", 25000, 0, raw=True))
    _probe("get_orders(STOCK,NORMAL)", lambda: client.get_orders(account_no, "STOCK", "NORMAL", raw=True))
    _probe("get_order_history", lambda: client.get_order_history(account_no, "STOCK", from_date="2026-10-01", to_date="2026-10-16", raw=True))
    _probe("get_corporate_action_history", lambda: client.get_corporate_action_history(account_no, "STOCK", raw=True))
    _probe("get_position_by_id(fake)", lambda: client.get_position_by_id("STOCK", "fake", raw=True))

    _probe("get_security_definition(HPG)", lambda: client.get_security_definition("HPG", raw=True))
    _probe("get_instruments(HPG)", lambda: client.get_instruments(symbol="HPG", limit=5, raw=True))
    _probe("get_latest_quote(HPG)", lambda: client.get_latest_quote("HPG", raw=True))
    _probe("get_latest_trade(HPG)", lambda: client.get_latest_trade("HPG", raw=True))
    _probe("get_close_price(HPG)", lambda: client.get_close_price("HPG", raw=True))
    _probe("get_quotes(HPG, sec)", lambda: client.get_quotes("HPG", from_date=DAY_S, to_date=NOW_S, limit=5, raw=True))
    _probe("get_trades(HPG, sec)", lambda: client.get_trades("HPG", from_date=DAY_S, to_date=NOW_S, limit=5, raw=True))
    _probe("get_expected_price(HPG, sec)", lambda: client.get_expected_price("HPG", from_date=DAY_S, to_date=NOW_S, limit=5, raw=True))
    _probe("get_foreign_trading(HPG, sec)", lambda: client.get_foreign_trading("HPG", from_date=DAY_S, to_date=NOW_S, limit=5, raw=True))
    _probe("get_market_index(VNINDEX, same day)", lambda: client.get_market_index("VNINDEX", from_date=TODAY0_S, to_date=NOW_S, limit=5, raw=True))
    _probe("get_ohlc(1D, HPG)", lambda: client.get_ohlc("1D", query={"symbol": "HPG", "from": DAY_S, "to": NOW_S, "limit": 5}, raw=True))

    # D1: stub trả None im lặng — coi None là FAIL (L-R01: rỗng im lặng = thất bại,
    # không phải PASS). Server không có endpoint working-dates (§9 D1).
    wd = client.get_working_dates(raw=True)
    if wd is None:
        _record("get_working_dates", "FAIL", "D1 stub trả None im lặng (bug tuple-order, không gọi network)")
    else:
        _record("get_working_dates", "PASS", type(wd).__name__)

    print()
    print("=" * 70)
    passed = sum(1 for _, s, _ in _results if s == "PASS")
    print(f"SUMMARY: PASS={passed} FAIL={len(_results) - passed} TOTAL={len(_results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
