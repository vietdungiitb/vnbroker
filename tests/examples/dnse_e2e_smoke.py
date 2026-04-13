"""DNSE E2E smoke script.

Usage:
- python -m tests.examples.dnse_e2e_smoke
"""

from __future__ import annotations

import os
from typing import Any

from vnstock.connector.dnse.client import DNSEClient


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(name)
    return value


def _print_check(name: str, payload: Any) -> None:
    print(f"{name}: {'OK' if payload is not None else 'EMPTY'}")


def main() -> int:
    missing: list[str] = []
    try:
        api_key = _require_env("DNSE_API_KEY")
    except ValueError as exc:
        missing.append(str(exc))
        api_key = ""
    try:
        api_secret = _require_env("DNSE_API_SECRET")
    except ValueError as exc:
        missing.append(str(exc))
        api_secret = ""
    try:
        account_no = _require_env("DNSE_ACCOUNT_NO")
    except ValueError as exc:
        missing.append(str(exc))
        account_no = ""

    if missing:
        print("Missing required environment variables:")
        for name in missing:
            print(f"- {name}")
        return 2

    base_url = os.getenv("DNSE_BASE_URL", "https://openapi.dnse.com.vn")
    market_type = os.getenv("DNSE_MARKET_TYPE", "STOCK")

    client = DNSEClient(
        api_key=api_key,
        api_secret=api_secret,
        base_url=base_url,
        show_log=False,
    )

    accounts = client.get_accounts(raw=True)
    _print_check("get_accounts", accounts)

    balances = client.get_balances(account_no=account_no, raw=True)
    _print_check("get_balances", balances)

    secdef = client.get_security_definition(symbol="HPG", raw=True)
    _print_check("get_security_definition", secdef)

    orders = client.get_orders(account_no=account_no, market_type=market_type, raw=True)
    _print_check("get_orders", orders)

    print("DNSE smoke completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
