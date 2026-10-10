from __future__ import annotations

from typing import Any

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

    def get_loans(
        self,
        account_no: str,
        market_type: str,
        disbursement_from: int | None = None,
        disbursement_to: int | None = None,
        due_date_from: int | None = None,
        due_date_to: int | None = None,
        position_id: int | None = None,
        page_index: int | None = None,
        page_size: int | None = None,
        dry_run: bool = False,
    ) -> tuple[int | None, Any]:
        """Danh sách khoản vay (Lớp B — giữ nguyên định dạng DNSE).

        Path theo SDK `dnse-tech/openapi-sdk` `python/dnse/api/client.py:85`:
        `GET /accounts/{account_no}/loans`.

        `market_type` là bắt buộc — SDK đặt nó thẳng vào query gốc
        (`client.py:68`), không phải tham số tuỳ chọn.
        """
        query: dict[str, object] = {"marketType": market_type}
        if disbursement_from is not None:
            query["disbursementFrom"] = disbursement_from
        if disbursement_to is not None:
            query["disbursementTo"] = disbursement_to
        if due_date_from is not None:
            query["dueDateFrom"] = due_date_from
        if due_date_to is not None:
            query["dueDateTo"] = due_date_to
        if position_id is not None:
            query["positionId"] = position_id
        if page_index is not None:
            query["pageIndex"] = page_index
        if page_size is not None:
            query["pageSize"] = page_size
        return self._http.request(
            "GET",
            f"/accounts/{account_no}/loans",
            query=query,
            dry_run=dry_run,
        )

