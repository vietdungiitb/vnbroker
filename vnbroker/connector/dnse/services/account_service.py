from __future__ import annotations

from vnbroker.connector.dnse.core.http_client import DNSEHttpClient


class AccountService:
    def __init__(self, http: DNSEHttpClient):
        self._http = http

    def get_accounts(self, dry_run: bool = False):
        return self._http.request("GET", "/accounts", dry_run=dry_run)

    def get_balances(self, account_no: str, dry_run: bool = False):
        return self._http.request("GET", f"/accounts/{account_no}/balances", dry_run=dry_run)

    def get_loan_packages(
        self,
        account_no: str,
        market_type: str,
        symbol: str | None = None,
        dry_run: bool = False,
    ):
        query = {"marketType": market_type}
        if symbol:
            query["symbol"] = symbol
        return self._http.request(
            "GET",
            f"/accounts/{account_no}/loan-packages",
            query=query,
            dry_run=dry_run,
        )

    def get_ppse(
        self,
        account_no: str,
        market_type: str,
        symbol: str,
        price: float,
        loan_package_id: int,
        dry_run: bool = False,
    ):
        return self._http.request(
            "GET",
            f"/accounts/{account_no}/ppse",
            query={
                "marketType": market_type,
                "symbol": symbol,
                "price": str(price),
                "loanPackageId": str(loan_package_id),
            },
            dry_run=dry_run,
        )

    def get_corporate_action_history(
        self,
        account_no: str,
        market_type: str,
        from_date: str | None = None,
        to_date: str | None = None,
        dry_run: bool = False,
    ):
        """Get corporate action history for an account."""
        query = {"marketType": market_type}
        if from_date:
            query["from"] = from_date
        if to_date:
            query["to"] = to_date
        return self._http.request(
            "GET",
            f"/accounts/{account_no}/corporate-actions",
            query=query,
            dry_run=dry_run,
        )
