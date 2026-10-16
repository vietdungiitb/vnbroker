import warnings

from typing import TYPE_CHECKING, Any, Dict, Optional

from vnbroker.connector.dnse.client import DNSEClient


"""20 method của `Trade` chỉ làm một việc: gọi thẳng `DNSEClient`.

Tách khỏi `trade.py` ngày 2026-10-16 (1352 dòng, vượt trần 800L). Đây là nửa
"bầu trời xanh" của `Trade`: phần lõi nói chuyện API private cũ (JWT + OTP),
còn phần này nói chuyện OpenAPI mới, và 20 method kia là **bọc thẳng, không có
logic nào**.

Vì sao để chúng ở `Trade` mà không bỏ hẳn
-----------------------------------------
Vì `Trade` là bề mặt đã được người gọi tin: ai đó đang dùng
`Trade.get_positions(...)` thì không được bắt họ đổi sang `DNSEClient`. Giữ
lại bọc ở đây là một quyết định tương thích, và nó là lý do file này tồn tại
riêng thay vì bị xoá.

Hàng rào tiền thật
-----------------
`post_order`, `put_order`, `cancel_order_openapi`, `close_position`,
`create_trading_token` gọi `self._require_write` — hàm đó nằm ở `Trade`, và
ngoài ra chúng còn đi qua `DNSEHttpClient.request`, nơi write gate thứ hai
đóng lại ở tầng HTTP (`core/http_client.py:31-45`). Lát tách này phải để cả hai
nguyên vẹn.
"""


class OpenApiPassthroughMixin:
    """Bọc thẳng `DNSEClient`. Cần `Trade` cung cấp `_get_openapi_client`
    và `_require_write`.
    """
    # --- Hop dong voi `Trade` ------------------------------------------------
    # 2 thanh vien nay KHONG duoc dinh nghia o day. Chúng thuoc `Trade`
    # (xem `trade.py`), va chi co gia tri khi class nay duoc ghep vao no.
    # Khai bao duoi `TYPE_CHECKING` de mypy biet ma **khong** tao them bat ky
    # attribute nao luc chay — neu khai bao o cap class thi se gan gia tri That
    # va che mat `_require_write` cua `Trade`, tuc lam hoang rao tien that.
    if TYPE_CHECKING:
        TIMEOUT: int
        _api_base_url: str

        def _get_openapi_client(self) -> DNSEClient: ...
        def _require_write(
            self, operation: str, dry_run: bool
        ) -> Optional[Dict[str, Any]]: ...



    def get_accounts(self, dry_run: bool = False, raw: bool = False) -> Any:
        warnings.warn(
            "Trade OpenAPI bridge is active. Prefer using vnbroker.connector.dnse.DNSEClient directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._get_openapi_client().get_accounts(dry_run=dry_run, raw=raw)

    def get_balances(self, account_no: str, dry_run: bool = False, raw: bool = False) -> Any:
        return self._get_openapi_client().get_balances(
            account_no=account_no,
            dry_run=dry_run,
            raw=raw,
        )

    def get_loan_packages(
        self,
        account_no: str,
        market_type: str,
        symbol: Optional[str] = None,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        return self._get_openapi_client().get_loan_packages(
            account_no=account_no,
            market_type=market_type,
            symbol=symbol,
            dry_run=dry_run,
            raw=raw,
        )

    def get_ppse(
        self,
        account_no: str,
        market_type: str,
        symbol: str,
        price: float,
        loan_package_id: int,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        return self._get_openapi_client().get_ppse(
            account_no=account_no,
            market_type=market_type,
            symbol=symbol,
            price=price,
            loan_package_id=loan_package_id,
            dry_run=dry_run,
            raw=raw,
        )

    def get_orders(
        self,
        account_no: str,
        market_type: str,
        order_category: str,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        return self._get_openapi_client().get_orders(
            account_no=account_no,
            market_type=market_type,
            order_category=order_category,
            dry_run=dry_run,
            raw=raw,
        )

    def get_order_detail(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        order_category: Optional[str] = None,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        return self._get_openapi_client().get_order_detail(
            account_no=account_no,
            order_id=order_id,
            market_type=market_type,
            order_category=order_category,
            dry_run=dry_run,
            raw=raw,
        )

    def get_execution_detail(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        order_category: str = "NORMAL",
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        return self._get_openapi_client().get_execution_detail(
            account_no=account_no,
            order_id=order_id,
            market_type=market_type,
            order_category=order_category,
            dry_run=dry_run,
            raw=raw,
        )

    def get_order_history(
        self,
        account_no: str,
        market_type: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page_size: Optional[int] = None,
        page_index: Optional[int] = None,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        return self._get_openapi_client().get_order_history(
            account_no=account_no,
            market_type=market_type,
            from_date=from_date,
            to_date=to_date,
            page_size=page_size,
            page_index=page_index,
            dry_run=dry_run,
            raw=raw,
        )

    def post_order(
        self,
        market_type: str,
        payload: Dict[str, Any],
        trading_token: str,
        order_category: str = "NORMAL",
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        _dry = self._require_write("post_order", dry_run)
        if _dry is not None:
            return _dry

        return self._get_openapi_client().post_order(
            market_type=market_type,
            payload=payload,
            trading_token=trading_token,
            order_category=order_category,
            dry_run=dry_run,
            raw=raw,
        )

    def put_order(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        payload: Dict[str, Any],
        trading_token: str,
        order_category: Optional[str] = None,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        _dry = self._require_write("put_order", dry_run)
        if _dry is not None:
            return _dry

        return self._get_openapi_client().put_order(
            account_no=account_no,
            order_id=order_id,
            market_type=market_type,
            payload=payload,
            trading_token=trading_token,
            order_category=order_category,
            dry_run=dry_run,
            raw=raw,
        )

    def cancel_order_openapi(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        trading_token: str,
        order_category: Optional[str] = None,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        _dry = self._require_write("cancel_order_openapi", dry_run)
        if _dry is not None:
            return _dry

        return self._get_openapi_client().cancel_order(
            account_no=account_no,
            order_id=order_id,
            market_type=market_type,
            trading_token=trading_token,
            order_category=order_category,
            dry_run=dry_run,
            raw=raw,
        )

    def send_email_otp(self, dry_run: bool = False, raw: bool = False) -> Any:
        return self._get_openapi_client().send_email_otp(dry_run=dry_run, raw=raw)

    def create_trading_token(
        self,
        otp_type: str,
        passcode: str,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        _dry = self._require_write("create_trading_token", dry_run)
        if _dry is not None:
            return _dry

        return self._get_openapi_client().create_trading_token(
            otp_type=otp_type,
            passcode=passcode,
            dry_run=dry_run,
            raw=raw,
        )

    def get_positions(
        self,
        account_no: str,
        market_type: str,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        return self._get_openapi_client().get_positions(
            account_no=account_no,
            market_type=market_type,
            dry_run=dry_run,
            raw=raw,
        )

    def get_position_by_id(
        self,
        market_type: str,
        position_id: str,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        return self._get_openapi_client().get_position_by_id(
            market_type=market_type,
            position_id=position_id,
            dry_run=dry_run,
            raw=raw,
        )

    def close_position(
        self,
        position_id: str,
        market_type: str,
        trading_token: str,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        _dry = self._require_write("close_position", dry_run)
        if _dry is not None:
            return _dry

        return self._get_openapi_client().close_position(
            position_id=position_id,
            market_type=market_type,
            trading_token=trading_token,
            dry_run=dry_run,
            raw=raw,
        )

    def get_security_definition(
        self,
        symbol: str,
        board_id: Optional[str] = None,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        return self._get_openapi_client().get_security_definition(
            symbol=symbol,
            board_id=board_id,
            dry_run=dry_run,
            raw=raw,
        )

    def get_ohlc(
        self,
        bar_type: str,
        query: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        return self._get_openapi_client().get_ohlc(
            bar_type=bar_type,
            query=query,
            dry_run=dry_run,
            raw=raw,
        )

    def get_trades(
        self,
        symbol: str,
        board_id: Optional[str] = None,
        from_date: Optional[int] = None,
        to_date: Optional[int] = None,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        next_page_token: Optional[str] = None,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        return self._get_openapi_client().get_trades(
            symbol=symbol,
            board_id=board_id,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            order=order,
            next_page_token=next_page_token,
            dry_run=dry_run,
            raw=raw,
        )

    def get_instruments(
        self,
        symbol: Optional[str] = None,
        market_id: Optional[str] = None,
        security_group_id: Optional[str] = None,
        index_name: Optional[str] = None,
        limit: Optional[int] = None,
        page: Optional[int] = None,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        return self._get_openapi_client().get_instruments(
            symbol=symbol,
            market_id=market_id,
            security_group_id=security_group_id,
            index_name=index_name,
            limit=limit,
            page=page,
            dry_run=dry_run,
            raw=raw,
        )
