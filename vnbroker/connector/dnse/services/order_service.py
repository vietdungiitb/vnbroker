from __future__ import annotations

from vnbroker.connector.dnse.core.errors import DNSEValidationError
from vnbroker.connector.dnse.core.http_client import DNSEHttpClient


class OrderService:
    def __init__(self, http: DNSEHttpClient):
        self._http = http

    def get_orders(
        self,
        account_no: str,
        market_type: str,
        order_category: str | None = None,
        page_index: int | None = 1,
        page_size: int | None = None,
        dry_run: bool = False,
    ):
        """Danh sÃ¡ch lá»‡nh Ä‘ang hoáº¡t Ä‘á»™ng.

        âš  **`pageIndex` lÃ  báº¯t buá»™c á»Ÿ production.** Äo 2026-10-16:
        `GET /accounts/{no}/orders` khÃ´ng kÃ¨m `pageIndex` â‡’
        `400 pageIndex is required`. **Sandbox thÃ¬ khÃ´ng Ä‘Ã²i** â€” Ä‘Ã³ lÃ  lÃ½ do
        khÃ´ng thá»ƒ dÃ¹ng sandbox lÃ m chuáº©n, vÃ  cÅ©ng lÃ  lÃ½ do máº·c Ä‘á»‹nh á»Ÿ Ä‘Ã¢y lÃ  `1`.

        Máº·c Ä‘á»‹nh lÃ  `1` chá»© khÃ´ng pháº£i `None` vÃ¬ gá»­i `pageIndex=None` sáº½ ra
        chuá»—i `pageIndex=None` trÃªn URL â€” má»™t lá»—i 400 khÃ¡c, khÃ³ Ä‘á»c hÆ¡n lá»—i cÅ©.
        Truyá»n `page_index=None` tÆ°á»ng minh váº«n Ä‘Æ°á»£c (bá» háº³n tham sá»‘) cho
        trÆ°á»ng há»£p cáº§n thá»­ trá»±c tiáº¿p.

        `page_size` váº«n tuá»³ chá»n â€” khÃ´ng cÃ³ báº±ng chá»©ng server báº¯t buá»™c.
        """
        query: dict[str, object] = {"marketType": market_type}
        if page_index is not None:
            query["pageIndex"] = page_index
        if order_category:
            query["orderCategory"] = order_category
        if page_size is not None:
            query["pageSize"] = page_size
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
        """Lá»‹ch sá»­ lá»‡nh. `from_date`/`to_date` lÃ  **date string `yyyy-MM-dd`**.

        âš  **Format khÃ¡c háº³n price endpoints.** `quotes`/`trades`/`market-index`
        nháº­n unix **giÃ¢y**; endpoint nÃ y nháº­n chuá»—i ngÃ y. Trá»™n hai loáº¡i lÃ  nguá»“n
        lá»—i ráº¥t dá»… rÆ¡i vÃ o (D4).

        Production Ä‘Ã²i **cáº£ hai** váº¿: thiáº¿u cáº£ hai â‡’ `400 from is required`, chá»‰
        cÃ³ `from` â‡’ `400 to is required`. Sandbox thÃ¬ gá»i Ä‘Æ°á»£c vá»›i cáº£ hai váº¿
        trá»‘ng, nÃªn cáº·p thiáº¿u bá»‹ cháº·n ngay á»Ÿ Ä‘Ã¢y (L-R01) thay vÃ¬ Ä‘á»ƒ server tráº£
        400 buá»™c ngÆ°á»i gá»i Ä‘oÃ¡n.

        Raises:
            DNSEValidationError: khi cÃ³ Ä‘Ãºng má»™t váº¿. ``error_code ==
                "ORDER_HISTORY_RANGE_INCOMPLETE"``.
        """
        if (from_date is None) != (to_date is None):
            missing = "to" if to_date is None else "from"
            raise DNSEValidationError(
                message=(
                    f"get_order_history cáº§n Cáº¢ `from_date` vÃ  `to_date`, hoáº·c "
                    f"khÃ´ng truyá»n váº¿ nÃ o. Báº¡n Ä‘ang thiáº¿u `{missing}_date`. "
                    f"Äá»‹nh dáº¡ng lÃ  chuá»—i ngÃ y `yyyy-MM-dd` â€” vÃ­ dá»¥ "
                    f"from_date='2026-10-01', to_date='2026-10-05' (KHÃC unix "
                    f"giÃ¢y cá»§a price endpoints)."
                ),
                error_code="ORDER_HISTORY_RANGE_INCOMPLETE",
                status_code=400,
            )
        query: dict[str, object] = {"marketType": market_type}
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

    def replace_order(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        payload: dict,
        trading_token: str,
        order_category: str | None = None,
        dry_run: bool = False,
    ):
        """Replace/modify an existing order."""
        query = {"marketType": market_type}
        if order_category:
            query["orderCategory"] = order_category
        return self._http.request(
            "PATCH",
            f"/accounts/{account_no}/orders/{order_id}",
            query=query,
            body=payload,
            headers={"trading-token": trading_token},
            dry_run=dry_run,
        )
