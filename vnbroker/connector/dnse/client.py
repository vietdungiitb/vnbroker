from __future__ import annotations

from typing import Any

import pandas as pd

from vnbroker.connector.dnse.core.config import DNSEConfig
from vnbroker.connector.dnse.core.http_client import DNSEHttpClient
from vnbroker.connector.dnse.multi_market import MultiMarketMixin
from vnbroker.connector.dnse.services import (
    AccountService,
    MarketService,
    OrderService,
    PositionService,
    TokenService,
)


def _list_to_frame(value: list, key: str) -> pd.DataFrame:
    """Dựng DataFrame từ một list phần tử của envelope.

    `pd.json_normalize` chỉ ăn được list-of-dict. DNSE cũng trả những list-of-
    scalar — `workingDates` là 257 chuỗi ngày. Gọi `json_normalize` lên đó ném
    `TypeError: All items in data must be of type dict`, tức là lời gọi hỏng vì
    **hình dạng**, không phải vì rỗng. Trường hợp đó thành một cột mang tên key.

    Rỗng thì trả DataFrame rỗng có đúng tên cột, để `df.columns` ổn định bất kể
    server trả gì.
    """
    items = [item for item in value if item is not None]
    if not items:
        return pd.DataFrame(columns=[key])
    if all(isinstance(item, dict) for item in items):
        return pd.json_normalize(items)
    return pd.DataFrame({key: items})


class DNSEClient(MultiMarketMixin):
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://openapi.dnse.com.vn",
        api_version: str = "2026-07-23",
        algorithm: str = "hmac-sha256",
        hmac_nonce_enabled: bool = True,
        timeout_seconds: float = 30.0,
        show_log: bool = False,
        write_enabled: bool = False,
    ):
        self._config = DNSEConfig(
            api_key=api_key,
            api_secret=api_secret,
            base_url=base_url,
            api_version=api_version,
            algorithm=algorithm,
            hmac_nonce_enabled=hmac_nonce_enabled,
            timeout_seconds=timeout_seconds,
            show_log=show_log,
        )
        # `write_enabled` is off by default and enforced inside
        # `DNSEHttpClient.request`, the one place every request passes through.
        self._http = DNSEHttpClient(self._config, write_enabled=write_enabled)
        self._account = AccountService(self._http)
        self._market = MarketService(self._http)
        self._order = OrderService(self._http)
        self._position = PositionService(self._http)
        self._token = TokenService(self._http)

    def enable_write(self, enabled: bool = True) -> None:
        """Allow (or forbid) state-changing requests.

        Required before ``post_order``, ``put_order``, ``cancel_order``,
        ``replace_order``, ``close_position`` or ``create_trading_token``
        actually reaches the provider. Reads and ``dry_run=True`` need no
        permission.

        Example:
            >>> client.enable_write()
            >>> client.post_order("STOCK", payload, trading_token)
        """
        self._http.enable_write(enabled)

    @staticmethod
    def _to_dataframe(payload: Any):
        if payload is None:
            return pd.DataFrame()
        if isinstance(payload, list):
            return pd.json_normalize(payload)
        if isinstance(payload, dict):
            for key in (
                "data", "items", "orders", "accounts", "loanPackages",
                "positions", "reports",
                # Market data keys
                "bars", "candles", "ohlc", "trades", "instruments", "securities",
                # `workingDates` phải có mặt ở đây, nếu không `get_working_dates`
                # sẽ trả DataFrame MỘT dòng chứa một cell là list — biểu hiện
                # khác của đúng bug "thành công rỗng" mà slice B đang chữa.
                "workingDates",
            ):
                value = payload.get(key)
                if isinstance(value, list):
                    df = _list_to_frame(value, key)
                    # The envelope's scalar siblings describe who the caller is,
                    # not what is in the list. Unwrapping dropped them silently -
                    # verified live on the sandbox: `get_accounts()` returned
                    # name / custodyCode / investorId at the top level and none of
                    # the three survived into the DataFrame. Repeat them on every
                    # row instead; a column per envelope, not per list item.
                    for sibling, scalar in payload.items():
                        if sibling == key or scalar is None:
                            continue
                        if isinstance(scalar, (list, dict)):
                            continue
                        if sibling not in df.columns:
                            df[sibling] = scalar
                    return df
            return pd.json_normalize(payload)
        return payload

    def _resolve_output(self, response: tuple[int | None, Any], raw: bool):
        _, body = response
        return body if raw else self._to_dataframe(body)

    # ── Chuẩn hoá + đọc nhiều market (VNBROKER-REQ-005) ───────────────────

    @staticmethod
    def normalize_payload(payload: Any, *, as_records: bool = False) -> Any:
        """Chuẩn hoá payload DNSE về một hình dạng duy nhất.

        Đây là hợp đồng công khai, không phải tiện ích nội bộ: phía tiêu thụ
        cần cùng một cách quy đổi thay vì tự viết lại — lý do chính thức của
        REQ-005 là vninvest đã tự chế ``vnbroker_dnse_compat.py`` và bên
        trong đó ``fetch_account_balance`` luôn trả 0 vì kiểm tra
        ``isinstance(raw, list)`` / ``isinstance(raw, dict)`` trong khi
        ``raw=False`` trả ``DataFrame``.

        Args:
            payload: ``DataFrame``, ``list[dict]``, ``dict`` (kể cả dict bọc
                trong envelope ``{"accounts": [...]}``), hoặc ``None``.
            as_records: ``True`` trả ``list[dict]`` thay vì ``DataFrame``.

        Returns:
            ``DataFrame`` (mặc định) hoặc ``list[dict]`` (``as_records=True``).
            Rỗng thì trả ``DataFrame`` rỗng — **không** trả ``[]`` để tránh
            chỗ gọi tưởng là "không có dữ liệu" trong khi thật ra là lỗi.

        Raises:
            Exception: lỗi từ ``to_dict("records")`` được để nổi lên. Nuốt nó
                thành ``[]`` chính là lỗi làm số dư về 0 mà vninvest gặp.
        """
        frame = (
            payload
            if isinstance(payload, pd.DataFrame)
            else DNSEClient._to_dataframe(payload)
        )
        if isinstance(frame, pd.DataFrame):
            return frame.to_dict("records") if as_records else frame
        return frame


    def get_accounts(self, dry_run: bool = False, raw: bool = False):
        return self._resolve_output(self._account.get_accounts(dry_run=dry_run), raw=raw)

    def get_balances(self, account_no: str, dry_run: bool = False, raw: bool = False):
        return self._resolve_output(self._account.get_balances(account_no=account_no, dry_run=dry_run), raw=raw)

    def get_loan_packages(
        self,
        account_no: str,
        market_type: str,
        symbol: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._account.get_loan_packages(
                account_no=account_no,
                market_type=market_type,
                symbol=symbol,
                dry_run=dry_run,
            ),
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
    ):
        return self._resolve_output(
            self._account.get_ppse(
                account_no=account_no,
                market_type=market_type,
                symbol=symbol,
                price=price,
                loan_package_id=loan_package_id,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_orders(
        self,
        account_no: str,
        market_type: str,
        order_category: str | None = None,
        page_index: int = 1,
        page_size: int | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        """Danh sách lệnh.

        `page_index` mặc định `1` vì **production bắt buộc** nó (thiếu ⇒
        `400 pageIndex is required`); sandbox thì không đòi.
        """
        return self._resolve_output(
            self._order.get_orders(
                account_no=account_no,
                market_type=market_type,
                order_category=order_category,
                page_index=page_index,
                page_size=page_size,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_order_detail(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        order_category: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._order.get_order_detail(
                account_no=account_no,
                order_id=order_id,
                market_type=market_type,
                order_category=order_category,
                dry_run=dry_run,
            ),
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
    ):
        return self._resolve_output(
            self._order.get_execution_detail(
                account_no=account_no,
                order_id=order_id,
                market_type=market_type,
                order_category=order_category,
                dry_run=dry_run,
            ),
            raw=raw,
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
        raw: bool = False,
    ):
        """Lịch sử lệnh.

        ⚠ `from_date`/`to_date` là **date string `yyyy-MM-dd`**, KHÁC unix giây
        của `quotes`/`trades`/`market-index`. Production đòi **cả hai** vế;
        truyền đúng một vế sẽ raise `DNSEValidationError` trước khi gửi.
        """
        return self._resolve_output(
            self._order.get_order_history(
                account_no=account_no,
                market_type=market_type,
                from_date=from_date,
                to_date=to_date,
                page_size=page_size,
                page_index=page_index,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def post_order(
        self,
        market_type: str,
        payload: dict,
        trading_token: str,
        order_category: str = "NORMAL",
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._order.post_order(
                market_type=market_type,
                payload=payload,
                trading_token=trading_token,
                order_category=order_category,
                dry_run=dry_run,
            ),
            raw=raw,
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
        raw: bool = False,
    ):
        return self._resolve_output(
            self._order.put_order(
                account_no=account_no,
                order_id=order_id,
                market_type=market_type,
                payload=payload,
                trading_token=trading_token,
                order_category=order_category,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def cancel_order(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        trading_token: str,
        order_category: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._order.cancel_order(
                account_no=account_no,
                order_id=order_id,
                market_type=market_type,
                trading_token=trading_token,
                order_category=order_category,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def send_email_otp(self, dry_run: bool = False, raw: bool = False):
        return self._resolve_output(self._token.send_email_otp(dry_run=dry_run), raw=raw)

    def create_trading_token(
        self,
        otp_type: str,
        passcode: str,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._token.create_trading_token(otp_type=otp_type, passcode=passcode, dry_run=dry_run),
            raw=raw,
        )

    def get_positions(
        self,
        account_no: str,
        market_type: str,
        dry_run: bool = False,
        raw: bool = False,
    ):
        """GET /accounts/{account_no}/positions?marketType={market_type}

        Args:
            account_no: Số tài khoản DNSE.
            market_type: Bắt buộc. Giá trị hợp lệ: ``STOCK``, ``DERIVATIVE``
                (hằng :data:`vnbroker.connector.dnse.constants.MARKET_TYPES`).
                Không phân biệt hoa/thường.
            dry_run: ``True`` chỉ trả envelope, không gọi ra server.
            raw: ``True`` trả body thô, ``False`` trả DataFrame.

        Raises:
            DNSEValidationError: ``market_type`` không thuộc
                :data:`~vnbroker.connector.dnse.constants.MARKET_TYPES`.
                ``error_code == "INVALID_MARKET_TYPE"``. Lỗi này ném ra
                **trước** khi có request nào đi ra — vì giá trị sai hay bị
                server trả HTTP 200 kèm body rỗng, tức lỗi kiểu "im lặng trả
                rỗng" thay vì lỗi có mã.

        Example:
            >>> client.get_positions("0123456789", MARKET_TYPES.STOCK)
        """
        return self._resolve_output(
            self._position.get_positions(account_no=account_no, market_type=market_type, dry_run=dry_run),
            raw=raw,
        )

    def get_position_by_id(
        self,
        market_type: str,
        position_id: str,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._position.get_position_by_id(market_type=market_type, position_id=position_id, dry_run=dry_run),
            raw=raw,
        )

    def close_position(
        self,
        position_id: str,
        market_type: str,
        trading_token: str,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._position.close_position(
                position_id=position_id,
                market_type=market_type,
                trading_token=trading_token,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_security_definition(
        self,
        symbol: str,
        board_id: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._market.get_security_definition(
                symbol=symbol,
                board_id=board_id,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_ohlc(self, bar_type: str, query: dict | None = None, dry_run: bool = False, raw: bool = False):
        return self._resolve_output(
            self._market.get_ohlc(bar_type=bar_type, query=query, dry_run=dry_run),
            raw=raw,
        )

    # --- Đợt 1 `docs/PLAN_DNSE_API_PARITY.md` ---------------------------------
    # 7 method read-only port từ SDK `dnse-tech/openapi-sdk`
    # (`python/dnse/api/client.py`). Tất cả là GET ⇒ không chạm write gate.
    # Path đã đối chiếu source SDK, xem `tests/.../test_market_data_read_methods.py`.

    def get_quotes(
        self,
        symbol: str,
        board_id: str | None = None,
        from_date: int | None = None,
        to_date: int | None = None,
        limit: int | None = None,
        order: str | None = None,
        next_page_token: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        """Nội giá (Lớp A). Cảnh báo `bid[].qtty` — xem NORMALISATION_POLICY §3.1.

        `from_date`/`to_date` là unix **GIÂY** (đo 2026-10-16: milliseconds ⇒
        `400 range exceeds maximum time range`).
        """
        return self._resolve_output(
            self._market.get_quotes(
                symbol=symbol,
                board_id=board_id,
                from_date=from_date,
                to_date=to_date,
                limit=limit,
                order=order,
                next_page_token=next_page_token,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_latest_quote(
        self,
        symbol: str,
        board_id: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        """Báo giá mới nhất (Lớp A)."""
        return self._resolve_output(
            self._market.get_latest_quote(
                symbol=symbol, board_id=board_id, dry_run=dry_run
            ),
            raw=raw,
        )

    def get_expected_price(
        self,
        symbol: str,
        board_id: str | None = None,
        from_date: int | None = None,
        to_date: int | None = None,
        limit: int | None = None,
        order: str | None = None,
        next_page_token: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        """Giá kỳ vọng (Lớp A).

        `from_date`/`to_date` là unix **GIÂY** (đo 2026-10-16: milliseconds ⇒
        `400 range exceeds maximum time range`).
        """
        return self._resolve_output(
            self._market.get_expected_price(
                symbol=symbol,
                board_id=board_id,
                from_date=from_date,
                to_date=to_date,
                limit=limit,
                order=order,
                next_page_token=next_page_token,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_foreign_trading(
        self,
        symbol: str,
        board_id: str | None = None,
        from_date: int | None = None,
        to_date: int | None = None,
        limit: int | None = None,
        order: str | None = None,
        next_page_token: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        """Giao dịch nước ngoài (Lớp B — giữ nguyên định dạng DNSE).

        `from_date`/`to_date` là unix **GIÂY** (đo 2026-10-16: milliseconds ⇒
        `400 range exceeds maximum time range`).
        """
        return self._resolve_output(
            self._market.get_foreign_trading(
                symbol=symbol,
                board_id=board_id,
                from_date=from_date,
                to_date=to_date,
                limit=limit,
                order=order,
                next_page_token=next_page_token,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_market_index(
        self,
        index_name: str,
        from_date: int | None = None,
        to_date: int | None = None,
        limit: int | None = None,
        order: str | None = None,
        next_page_token: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        """Chỉ số thị trường (Lớp A). Tham số là `index_name`, không phải `symbol`.

        `from_date`/`to_date` là unix **GIÂY**, và phải thuộc **cùng một ngày**
        lịch giờ VN — server trả `400 from and to must be in the same date` nếu
        không. Việc đó bị chặn sớm kèm cửa sổ hợp lệ (L-R01).
        """
        return self._resolve_output(
            self._market.get_market_index(
                index_name=index_name,
                from_date=from_date,
                to_date=to_date,
                limit=limit,
                order=order,
                next_page_token=next_page_token,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_trades_volume_profile(
        self,
        symbol: str,
        time: str,
        board_id: str,
        dry_run: bool = False,
        raw: bool = False,
    ) -> Any:
        """Phân bổ khối lượng theo giá (Lớp A).

        ⚠ `time` là **date string `yyyy-MM-dd`** (ví dụ `'2026-10-16'`), KHÔNG
        phải unix giây — đo 2026-10-16: `time=1700` ⇒ `400 invalid param
        'time', expected format yyyy-MM-dd`.
        ⚠ `board_id` bắt buộc — thiếu ⇒ `400 missing param 'boardId'`.
        """
        return self._resolve_output(
            self._market.get_trades_volume_profile(
                symbol=symbol, time=time, board_id=board_id, dry_run=dry_run
            ),
            raw=raw,
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
        raw: bool = False,
    ) -> Any:
        """Khoản vay (Lớp B — giữ nguyên định dạng DNSE)."""
        return self._resolve_output(
            self._account.get_loans(
                account_no=account_no,
                market_type=market_type,
                disbursement_from=disbursement_from,
                disbursement_to=disbursement_to,
                due_date_from=due_date_from,
                due_date_to=due_date_to,
                position_id=position_id,
                page_index=page_index,
                page_size=page_size,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_trades(
        self,
        symbol: str,
        board_id: str | None = None,
        from_date: int | None = None,
        to_date: int | None = None,
        limit: int | None = None,
        order: str | None = None,
        next_page_token: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        """Giao dịch khớp lệnh (Lớp B).

        `from_date`/`to_date` là unix **GIÂY** (đo 2026-10-16: milliseconds ⇒
        `400 range exceeds maximum time range`).
        """
        return self._resolve_output(
            self._market.get_trades(
                symbol=symbol,
                board_id=board_id,
                from_date=from_date,
                to_date=to_date,
                limit=limit,
                order=order,
                next_page_token=next_page_token,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_instruments(
        self,
        symbol: str | None = None,
        market_id: str | None = None,
        security_group_id: str | None = None,
        index_name: str | None = None,
        limit: int | None = None,
        page: int | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._market.get_instruments(
                symbol=symbol,
                market_id=market_id,
                security_group_id=security_group_id,
                index_name=index_name,
                limit=limit,
                page=page,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_close_price(self, symbol: str, dry_run: bool = False, raw: bool = False):
        return self._resolve_output(
            self._market.get_close_price(symbol=symbol, dry_run=dry_run), raw=raw
        )

    def get_latest_trade(self, symbol: str, dry_run: bool = False, raw: bool = False):
        return self._resolve_output(
            self._market.get_latest_trade(symbol=symbol, dry_run=dry_run), raw=raw
        )

    def get_working_dates(self, dry_run: bool = False, raw: bool = False):
        return self._resolve_output(
            self._market.get_working_dates(dry_run=dry_run), raw=raw
        )

    def get_corporate_action_history(
        self,
        account_no: str,
        market_type: str,
        from_date: str | None = None,
        to_date: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._account.get_corporate_action_history(
                account_no=account_no,
                market_type=market_type,
                from_date=from_date,
                to_date=to_date,
                dry_run=dry_run,
            ),
            raw=raw,
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
        raw: bool = False,
    ):
        return self._resolve_output(
            self._order.replace_order(
                account_no=account_no,
                order_id=order_id,
                market_type=market_type,
                payload=payload,
                trading_token=trading_token,
                order_category=order_category,
                dry_run=dry_run,
            ),
            raw=raw,
        )
