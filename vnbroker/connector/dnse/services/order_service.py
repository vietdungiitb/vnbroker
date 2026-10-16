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
        page_index: int = 1,
        page_size: int | None = None,
        dry_run: bool = False,
    ):
        """Danh sách lệnh đang hoạt động.

        ⚠ **`pageIndex` là bắt buộc ở production.** Đo 2026-10-16:
        `GET /accounts/{no}/orders` không kèm `pageIndex` ⇒
        `400 pageIndex is required`. **Sandbox thì không đòi** — đó là lý do
        không thể dùng sandbox làm chuẩn, và cũng là lý do mặc định ở đây là `1`
        thay vì `None`: gửi `None` là trả về đúng cái lỗi 400 đó.

        `page_size` vẫn tuỳ chọn — không có bằng chứng server bắt buộc.
        """
        query: dict[str, object] = {
            "marketType": market_type,
            "pageIndex": page_index,
        }
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
        """Lịch sử lệnh. `from_date`/`to_date` là **date string `yyyy-MM-dd`**.

        ⚠ **Format khác hẳn price endpoints.** `quotes`/`trades`/`market-index`
        nhận unix **giây**; endpoint này nhận chuỗi ngày. Trộn hai loại là nguồn
        lỗi rất dễ rơi vào (D4).

        Production đòi **cả hai** vế: thiếu cả hai ⇒ `400 from is required`, chỉ
        có `from` ⇒ `400 to is required`. Sandbox thì gọi được với cả hai vế
        trống, nên cặp thiếu bị chặn ngay ở đây (L-R01) thay vì để server trả
        400 buộc người gọi đoán.

        Raises:
            DNSEValidationError: khi có đúng một vế. ``error_code ==
                "ORDER_HISTORY_RANGE_INCOMPLETE"``.
        """
        if (from_date is None) != (to_date is None):
            missing = "to" if to_date is None else "from"
            raise DNSEValidationError(
                message=(
                    f"get_order_history cần CẢ `from_date` và `to_date`, hoặc "
                    f"không truyền vế nào. Bạn đang thiếu `{missing}_date`. "
                    f"Định dạng là chuỗi ngày `yyyy-MM-dd` — ví dụ "
                    f"from_date='2026-10-01', to_date='2026-10-05' (KHÁC unix "
                    f"giây của price endpoints)."
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
