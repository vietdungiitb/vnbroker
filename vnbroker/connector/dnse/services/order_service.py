from __future__ import annotations

from vnbroker.connector.dnse.core.http_client import DNSEHttpClient


class OrderService:
    def __init__(self, http: DNSEHttpClient):
        self._http = http

    def get_orders(
        self,
        account_no: str,
        market_type: str,
        order_category: str | None = None,
        dry_run: bool = False,
    ):
        query = {"marketType": market_type}
        if order_category:
            query["orderCategory"] = order_category
        return self._http.request(
            "GET",
            f"/accounts/{account_no}/orders",
            query=query,
            dry_run=dry_run,
        )

    def get_order_detail(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        order_category: str | None = None,
        dry_run: bool = False,
    ):
        query = {"marketType": market_type}
        if order_category:
            query["orderCategory"] = order_category
        return self._http.request(
            "GET",
            f"/accounts/{account_no}/orders/{order_id}",
            query=query,
            dry_run=dry_run,
        )

    def get_execution_detail(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        order_category: str = "NORMAL",
        dry_run: bool = False,
    ):
        return self._http.request(
            "GET",
            f"/accounts/{account_no}/executions/{order_id}",
            query={"marketType": market_type, "orderCategory": order_category},
            dry_run=dry_run,
        )

    def get_order_history(
        self,
        account_no: str,
        market_type: str,
        from_date: str | None = None,
        to_date: str | None = None,
        page_size: int | None = None,
        page_index: int | None = None,
        dry_run: bool = False,
    ):
        query = {"marketType": market_type}
        if from_date:
            query["from"] = from_date
        if to_date:
            query["to"] = to_date
        if page_size is not None:
            query["pageSize"] = page_size
        if page_index is not None:
            query["pageIndex"] = page_index
        return self._http.request(
            "GET",
            f"/accounts/{account_no}/orders/history",
            query=query,
            dry_run=dry_run,
        )

    def post_order(
        self,
        market_type: str,
        payload: dict,
        trading_token: str,
        order_category: str = "NORMAL",
        dry_run: bool = False,
    ):
        return self._http.request(
            "POST",
            "/accounts/orders",
            query={"marketType": market_type, "orderCategory": order_category},
            body=payload,
            headers={"trading-token": trading_token},
            dry_run=dry_run,
        )

    def put_order(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        payload: dict,
        trading_token: str,
        order_category: str | None = None,
        dry_run: bool = False,
    ):
        query = {"marketType": market_type}
        if order_category:
            query["orderCategory"] = order_category
        return self._http.request(
            "PUT",
            f"/accounts/{account_no}/orders/{order_id}",
            query=query,
            body=payload,
            headers={"trading-token": trading_token},
            dry_run=dry_run,
        )

    def cancel_order(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        trading_token: str,
        order_category: str | None = None,
        dry_run: bool = False,
    ):
        query = {"marketType": market_type}
        if order_category:
            query["orderCategory"] = order_category
        return self._http.request(
            "DELETE",
            f"/accounts/{account_no}/orders/{order_id}",
            query=query,
            headers={"trading-token": trading_token},
            dry_run=dry_run,
        )
