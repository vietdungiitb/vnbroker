"""
vnbroker.broker.tcbs.client — TCBSBrokerClient: unified facade cho TCBS broker lane.

Usage:
    from vnbroker.broker.tcbs.client import TCBSBrokerClient

    client = TCBSBrokerClient(api_key="...")
    client.authenticate(otp="123456")               # Lấy token
    profile = client.get_profile("105C334455")       # Thông tin profile
    balance = client.get_balance("0123456789")       # Số dư tài khoản
    holdings = client.get_holdings("0123456789")     # Danh mục cổ phiếu

SECURITY RULES:
  - KHÔNG log api_key, otp, token.
  - dry_run=True mặc định cho tất cả write methods.
  - Dùng requests trực tiếp — KHÔNG dùng vnbroker.core.utils.client.
  - KHÔNG có pin_code trong API TCBS iFlash Open API v1.0.0.

18 WRAPPER ĐÃ GỠ (2026-10-09) — gọi path không có trong 2 tài liệu chính thức
`openapi-v1.0.0.json` + `tcbs-openapi-v1.0.0.postman_collection.json`
(mỗi tài liệu 48 REST endpoint, khớp 48/48): 13 wrapper Erebos v1/v2 account
+ 4 wrapper stop-limit + `get_order_history` (/aion/v1/accounts/{a}/orders/history).
Xoá theo quyết định Owner dựa trên 2 tài liệu chính thức, CHƯA probe server
(401 chạy trước routing). KHÔNG phải kết luận "path không tồn tại trên server".
Wrapper VẪN CÒN nhưng ném NotImplementedError từ service — xem
`vnbroker/broker/tcbs/account.py` và `.../equity.py`.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional, Union

import pandas as pd

from vnbroker.broker.base import BaseBrokerClient
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.tcbs.account import TCBSAccountService
from vnbroker.broker.tcbs.auth import TCBSAuthService
from vnbroker.broker.tcbs.equity import TCBSEquityService
from vnbroker.broker.tcbs.condition_orders import TCBSConditionOrderService
from vnbroker.broker.tcbs.derivatives import TCBSDerivativesService
from vnbroker.broker.tcbs.market import TCBSMarketService
from vnbroker.broker.tcbs.money import TCBSMoneyService
from vnbroker.broker.tcbs.portfolio import TCBSPortfolioEngine

_logger = logging.getLogger("vnbroker.broker.tcbs.client")


class TCBSBrokerClient(BaseBrokerClient):
    """
    Unified facade cho toàn bộ TCBS broker lane.

    Tổng hợp:
      - TCBSAuthService        → authenticate, is_token_valid, revoke
      - TCBSAccountService     → get_profile, get_balance, get_purchasing_power
      - TCBSMoneyService       → get_cash, get_margin
      - TCBSEquityService      → orders, executions, holdings, place/modify/cancel
      - TCBSDerivativesService → positions, orders, cash (phái sinh)
      - TCBSMarketService      → ticker_info, snaps, bsa, intraday, derivatives_info
      - TCBSPortfolioEngine    → snapshot, PnL, reconcile (pure compute)

    Pattern:
        client = TCBSBrokerClient(api_key="...")
        client.authenticate(otp="...")
        # Sau authenticate → session.is_authenticated → True
        # Enable write: client.session.enable_write()
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        custody_code: Optional[str] = None,
    ) -> None:
        """
        Khởi tạo TCBS broker client.

        Args:
            api_key: TCBS OpenAPI key. Nếu None → đọc từ env VNBROKER_BROKER_TCBS_API_KEY.
            base_url: Override base URL. Nếu None → đọc từ env hoặc dùng mặc định.
            custody_code: Mã lưu ký 105C format (tùy chọn). Nếu None → đọc từ env.
        """

        self._config = TCBSCredentialConfig(
            api_key=api_key or _resolve_api_key(),
            base_url=base_url or _resolve_base_url(),
        )
        self.session = BrokerSession()

        self._auth = TCBSAuthService(config=self._config, session=self.session)
        self._account = TCBSAccountService(config=self._config, session=self.session)
        self._money = TCBSMoneyService(config=self._config, session=self.session)
        self._equity = TCBSEquityService(config=self._config, session=self.session)
        self._condition_orders = TCBSConditionOrderService(
            config=self._config, session=self.session
        )
        self._derivatives = TCBSDerivativesService(config=self._config, session=self.session)
        self._market = TCBSMarketService(config=self._config, session=self.session)
        self.portfolio = TCBSPortfolioEngine  # Pure compute engine — truy cập trực tiếp

    @property
    def provider_name(self) -> str:
        """Tên nhà cung cấp broker."""
        return "TCBS"

    def authenticate(self, otp: str) -> str:
        """
        Xác thực với TCBS OpenAPI bằng OTP.

        Args:
            otp: OTP nhận từ TCBS (6 số).

        Returns:
            JWT token string nếu thành công.

        Raises:
            BrokerAuthError: Nếu xác thực thất bại.
        """
        self._auth.authenticate(otp=otp)
        return self.session.token or ""

    def is_token_valid(self) -> bool:
        """Kiểm tra token hiện tại còn hợp lệ không."""
        return self._auth.is_token_valid()

    def revoke(self) -> None:
        """Hủy session và xóa token."""
        self._auth.revoke()

    def close(self) -> None:
        """Đóng phiên và giải phóng tài nguyên."""
        self.revoke()

    def get_account_list(self) -> list[dict]:
        """Lấy danh sách tài khoản theo giao diện BaseBrokerClient.

        Đây là method @abstractmethod (`vnbroker/broker/base.py:55-58`) nên phải
        có implementation. Dùng `GET /aion/v1/accounts` — path này KHÔNG có
        trong 2 tài liệu chính thức nhưng được GIỮ LẠI như NGOẠI LỆ vì path
        thay thế trong spec `/aion/v1/customers/{custodyId}/accounts` cần
        custodyId, tức là cần chính thông tin mà method này sinh ra.
        """
        accounts = self.list_accounts(raw=True)
        if isinstance(accounts, list):
            return accounts
        if hasattr(accounts, "to_dict"):
            return accounts.to_dict(orient="records")
        return []

    def get_account_balance(self, account_no: str) -> dict:
        """Lấy số dư tài khoản theo giao diện BaseBrokerClient."""
        balance = self.get_balance(account_no=account_no, raw=True)
        if isinstance(balance, dict):
            return balance
        if hasattr(balance, "to_dict"):
            records = balance.to_dict(orient="records")
            return records[0] if records else {}
        return {}

    # ── Account ──────────────────────────────────────────────────────────────

    def get_profile(self, custody_code: str, raw: bool = False) -> Union[dict, pd.DataFrame]:
        """Lấy thông tin profile theo custody_code (105C format)."""
        return self._account.get_profile(custody_code=custody_code, raw=raw)

    def list_accounts(self, raw: bool = False) -> Union[pd.DataFrame, list]:
        """Lấy danh sách tài khoản."""
        return self._account.list_accounts(raw=raw)

    def get_balance(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """Lấy số dư tài khoản (CashInvestmentResponse)."""
        return self._account.get_balance(account_no=account_no, raw=raw)

    def get_purchasing_power(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """Lấy sức mua tài khoản."""
        return self._account.get_purchasing_power(account_no=account_no, raw=raw)

    # ── Erebos v1/v2 Account Endpoints — ĐÃ GỠ (13 path) ──────────────────────
    # Xoá theo quyết định Owner dựa trên 2 tài liệu chính thức, chưa probe server.
    # Mỗi wrapper ném lại lỗi từ service (NotImplementedError) — không trả rỗng.

    def get_erebos_v1_asset(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """ĐÃ GỠ — /erebos/v1/account/asset."""
        return self._account.get_erebos_v1_asset(account_no=account_no, raw=raw)

    def get_erebos_v1_available_balance(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """ĐÃ GỠ — /erebos/v1/account/available-balance."""
        return self._account.get_erebos_v1_available_balance(account_no=account_no, raw=raw)

    def get_erebos_v1_portfolio_asset(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """ĐÃ GỠ — /erebos/v1/portfolio-asset."""
        return self._account.get_erebos_v1_portfolio_asset(account_no=account_no, raw=raw)

    def get_erebos_v1_portfolio_asset_token(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """ĐÃ GỠ — /erebos/v1/portfolio-asset/token."""
        return self._account.get_erebos_v1_portfolio_asset_token(account_no=account_no, raw=raw)

    def get_erebos_v1_portfolio_stock_statistic(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """ĐÃ GỠ — /erebos/v1/portfolio/stock/{accountNo}/statistic."""
        return self._account.get_erebos_v1_portfolio_stock_statistic(account_no=account_no, raw=raw)

    def get_erebos_v2_asset(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/asset."""
        return self._account.get_erebos_v2_asset(account_no=account_no, raw=raw)

    def get_erebos_v2_available_balance(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/available-balance."""
        return self._account.get_erebos_v2_available_balance(account_no=account_no, raw=raw)

    def get_erebos_v2_stock_statistic(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/stock-statistic."""
        return self._account.get_erebos_v2_stock_statistic(account_no=account_no, raw=raw)

    def get_erebos_v2_orders_history(
        self, account_no: str, from_date: str = "", to_date: str = "",
        page: int = 0, size: int = 50, raw: bool = False,
    ) -> pd.DataFrame:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/orders/history."""
        return self._account.get_erebos_v2_orders_history(
            account_no=account_no, from_date=from_date, to_date=to_date,
            page=page, size=size, raw=raw,
        )

    def get_erebos_v2_orders_matching(
        self, account_no: str, from_date: str = "", to_date: str = "",
        page: int = 0, size: int = 50, raw: bool = False,
    ) -> pd.DataFrame:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/orders/matching."""
        return self._account.get_erebos_v2_orders_matching(
            account_no=account_no, from_date=from_date, to_date=to_date,
            page=page, size=size, raw=raw,
        )

    def get_erebos_v2_withdraw_history(
        self, account_no: str, from_date: str = "", to_date: str = "",
        page: int = 0, size: int = 50, raw: bool = False,
    ) -> pd.DataFrame:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/withdraw."""
        return self._account.get_erebos_v2_withdraw_history(
            account_no=account_no, from_date=from_date, to_date=to_date,
            page=page, size=size, raw=raw,
        )

    def get_erebos_v2_deposit_history(
        self, account_no: str, from_date: str = "", to_date: str = "",
        page: int = 0, size: int = 50, raw: bool = False,
    ) -> pd.DataFrame:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/deposit."""
        return self._account.get_erebos_v2_deposit_history(
            account_no=account_no, from_date=from_date, to_date=to_date,
            page=page, size=size, raw=raw,
        )

    def get_erebos_v2_dividend_history(
        self, account_no: str, from_date: str = "", to_date: str = "",
        page: int = 0, size: int = 50, raw: bool = False,
    ) -> pd.DataFrame:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/dividend."""
        return self._account.get_erebos_v2_dividend_history(
            account_no=account_no, from_date=from_date, to_date=to_date,
            page=page, size=size, raw=raw,
        )

    # ── Money ────────────────────────────────────────────────────────────────

    def get_cash(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """Lấy dữ liệu tiền mặt tài khoản."""
        return self._money.get_cash(account_no=account_no, raw=raw)

    def get_margin(
        self,
        account_no: str,
        custody_code: str = "",
        from_date: str = "",
        to_date: str = "",
        page: int = 0,
        size: int = 20,
        raw: bool = False,
    ) -> pd.DataFrame:
        """Lấy dữ liệu margin tài khoản."""
        return self._money.get_margin(
            account_no=account_no, custody_code=custody_code,
            from_date=from_date, to_date=to_date, page=page, size=size, raw=raw,
        )

    def get_purchasing_power_by_symbol(self, account_no: str, symbol: str, raw: bool = False) -> pd.DataFrame:
        """GET /aion/v1/accounts/{accountNo}/ppse/{symbol}"""
        return self._money.get_purchasing_power_by_symbol(account_no=account_no, symbol=symbol, raw=raw)

    def get_purchasing_power_by_symbol_price(
        self, account_no: str, symbol: str, price: float, raw: bool = False,
    ) -> pd.DataFrame:
        """GET /aion/v1/accounts/{accountNo}/ppse/{symbol}/{price}"""
        return self._money.get_purchasing_power_by_symbol_price(
            account_no=account_no, symbol=symbol, price=price, raw=raw,
        )

    def get_customer_accounts(self, custody_id: str, raw: bool = False) -> pd.DataFrame:
        """GET /aion/v1/customers/{custodyId}/accounts"""
        return self._money.get_customer_accounts(custody_id=custody_id, raw=raw)

    def get_margin_risk(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """GET /hydros/v1/account/{accountNo}/risk"""
        return self._money.get_margin_risk(account_no=account_no, raw=raw)

    def get_margin_subscription_detail(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """GET /campaign-management/v1/margin/subscription/{accountNo}/addons/detail"""
        return self._money.get_margin_subscription_detail(account_no=account_no, raw=raw)

    def get_loan_list(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """GET /khaos/v1/loan/{accountNo}"""
        return self._money.get_loan_list(account_no=account_no, raw=raw)

    def get_cash_statements(
        self, account_no: str, from_date: str, to_date: str,
        page: int = 0, size: int = 25, transaction_code: str = "", raw: bool = False,
    ) -> pd.DataFrame:
        """GET /erebos/v2/digital/trans-hist-cashStatements"""
        return self._money.get_cash_statements(
            account_no=account_no, from_date=from_date, to_date=to_date,
            page=page, size=size, transaction_code=transaction_code, raw=raw,
        )

    def get_pricing_policy(
        self, account_no: str, product_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """GET /hydros/v1/account/{accountNo}/pricing-policy"""
        return self._money.get_pricing_policy(
            account_no=account_no, product_id=product_id,
        )

    def deposit_margin(
        self, account_id: str, sub_account_id: str, amount: float,
        payment_content: str = "", *, dry_run: bool = True,
    ) -> dict[str, Any]:
        """POST /khronos/v1/cash/deposit/update — nộp tiền margin."""
        return self._money.deposit_margin(
            account_id=account_id, sub_account_id=sub_account_id, amount=amount,
            payment_content=payment_content, dry_run=dry_run,
        )

    def withdraw_margin(
        self, account_id: str, sub_account_id: str, amount: float,
        payment_content: str = "", *, dry_run: bool = True,
    ) -> dict[str, Any]:
        """POST /khronos/v1/cash/withdraw/update — rút tiền margin."""
        return self._money.withdraw_margin(
            account_id=account_id, sub_account_id=sub_account_id, amount=amount,
            payment_content=payment_content, dry_run=dry_run,
        )

    def transfer_between_sub_accounts(
        self, source_account_number: str, destination_account_number: str,
        amount: float, description: str, *, dry_run: bool = True,
    ) -> dict[str, Any]:
        """POST /physis/v1/stock/transfer — chuyển tiền giữa 2 sub-account."""
        return self._money.transfer_between_sub_accounts(
            source_account_number=source_account_number,
            destination_account_number=destination_account_number,
            amount=amount, description=description, dry_run=dry_run,
        )

    # �� Condition order (phái sinh) ������������������������������������������

    def cancel_condition_order(
        self, account_id: str, order_no: str,
        sub_account_id: str = "", *, dry_run: bool = True,
    ) -> dict[str, Any]:
        """POST /khronos/v1/order/condition/cancel — huỷ lệnh điều kiện."""
        return self._condition_orders.cancel_condition_order(
            account_id=account_id, sub_account_id=sub_account_id,
            order_no=order_no, dry_run=dry_run,
        )

    def get_api_key_expiration(self) -> Optional[datetime]:
        """POST /gaia/v1/oauth2/openapi/apikey/info — hạn API key."""
        return self._auth.get_api_key_expiration()

    def extend_api_key(self, otp: str) -> Optional[datetime]:
        """POST /gaia/v1/oauth2/openapi/apikey/extend — gia hạn API key (cần Smart OTP)."""
        return self._auth.extend_api_key(otp=otp)

    # ── Equity ───────────────────────────────────────────────────────────────

    def get_orders(
        self, account_no: str, raw: bool = False
    ) -> pd.DataFrame:
        """Lấy danh sách lệnh trong ngày."""
        return self._equity.get_orders(account_no=account_no, raw=raw)

    def get_order_history(
        self, account_no: str, page: int = 0, page_size: int = 50,
        start_date: Optional[str] = None, end_date: Optional[str] = None, raw: bool = False,
    ) -> pd.DataFrame:
        """ĐÃ GỠ — GET /aion/v1/accounts/{accountNo}/orders/history."""
        return self._equity.get_order_history(
            account_no=account_no, page=page, page_size=page_size,
            start_date=start_date, end_date=end_date, raw=raw,
        )

    def get_executions(
        self, account_no: str, page: int = 0, page_size: int = 50, raw: bool = False
    ) -> pd.DataFrame:
        """Lấy danh sách lệnh đã khớp."""
        return self._equity.get_executions(account_no=account_no, page=page, page_size=page_size, raw=raw)

    def get_holdings(
        self, account_no: str, enrich_prices: bool = True, raw: bool = False
    ) -> pd.DataFrame:
        """Lấy danh mục cổ phiếu đang nắm giữ."""
        return self._equity.get_holdings(account_no=account_no, enrich_prices=enrich_prices, raw=raw)

    def place_order(
        self,
        account_no: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float,
        pin_code: str,
        request_id: Optional[str] = None,
        dry_run: bool = True,
    ) -> dict:
        """
        Đặt lệnh mua/bán. dry_run=True mặc định (không gửi lệnh thật).

        Args:
            account_no: Số tài khoản.
            symbol: Mã chứng khoán (VNM, HPG...).
            side: "BUY" hoặc "SELL".
            order_type: "LO", "MP", "ATO", "ATC".
            quantity: Khối lượng.
            price: Giá đặt lệnh.
            pin_code: Mã PIN xác nhận.
            request_id: Mã định danh request (tùy chọn).
            dry_run: Nếu True → chỉ validate, không gửi. Mặc định True.
        """
        return self._equity.place_order(
            account_no=account_no, symbol=symbol, side=side,
            order_type=order_type, quantity=quantity, price=price,
            pin_code=pin_code,
            # `place_order` (equity_orders.py) validate `request_id` là bắt buộc
            # (nội bộ, idempotency key) dù spec không gửi nó lên TCBS. Facade
            # cho phép `None` ⇒ phải nâng lên str thay vì truyền None xuống.
            request_id=request_id or "",
            dry_run=dry_run,
        )

    def modify_order(
        self,
        account_no: str,
        order_id: str,
        quantity: int,
        price: float,
        request_id: str,
        dry_run: bool = True,
    ) -> dict:
        """
        Sửa lệnh. dry_run=True mặc định.

        ⚠ ĐỔI CHỮ KÝ 2026-10-10: `pin_code` → `request_id`.
        Bản cũ truyền `pin_code=...` cho `modify_order()`, hàm đó **không có**
        tham số này ⇒ `TypeError` mỗi lần gọi. Lỗi có sẵn từ trước, chỉ lộ ra
        khi mypy phân giải lại qua `EquityWriteMixin`. `request_id` là tham số
        thật mà method dưới vẫn yêu cầu (dù spec không gửi nó lên wire).
        """
        return self._equity.modify_order(
            account_no=account_no, order_id=order_id,
            quantity=quantity, price=price, request_id=request_id, dry_run=dry_run,
        )

    def cancel_order(
        self,
        account_no: str,
        order_id: str,
        request_id: str,
        dry_run: bool = True,
    ) -> dict:
        """
        Hủy lệnh. dry_run=True mặc định.

        ⚠ ĐỔI CHỮ KÝ 2026-10-10: `pin_code` → `request_id`, giống `modify_order`.
        """
        return self._equity.cancel_order(
            account_no=account_no, order_id=order_id,
            request_id=request_id, dry_run=dry_run,
        )

    # ── Stop-Limit Orders — ĐÃ GỠ (4 path) ────────────────────────────────────
    # Xoá theo quyết định Owner dựa trên 2 tài liệu chính thức, chưa probe server.

    def place_stop_limit_order(
        self,
        account_no: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float,
        stop_price: float,
        request_id: str,
        dry_run: bool = True,
    ) -> dict:
        """ĐÃ GỠ — POST /erebos/v2/order/stop-limit."""
        return self._equity.place_stop_limit_order(
            account_no=account_no, symbol=symbol, side=side,
            order_type=order_type, quantity=quantity, price=price,
            stop_price=stop_price, request_id=request_id, dry_run=dry_run,
        )

    def get_stop_limit_orders(self, account_no: str, status: str = "", raw: bool = False) -> pd.DataFrame:
        """ĐÃ GỠ — GET /erebos/v2/order/stop-limit/orders."""
        return self._equity.get_stop_limit_orders(account_no=account_no, status=status, raw=raw)

    def cancel_stop_limit_order(self, order_id: str, request_id: str, dry_run: bool = True) -> dict:
        """ĐÃ GỠ — PUT /erebos/v2/order/stop-limit/{orderId}/cancel."""
        return self._equity.cancel_stop_limit_order(order_id=order_id, request_id=request_id, dry_run=dry_run)

    def modify_stop_limit_order(
        self, order_id: str, quantity: int, price: float, stop_price: float,
        request_id: str, dry_run: bool = True,
    ) -> dict:
        """ĐÃ GỠ — PUT /erebos/v2/order/stop-limit/{orderId}."""
        return self._equity.modify_stop_limit_order(
            order_id=order_id, quantity=quantity, price=price,
            stop_price=stop_price, request_id=request_id, dry_run=dry_run,
        )

    # ── Derivatives ──────────────────────────────────────────────────────────

    def get_derivative_positions(
        self,
        account_id: str,
        sub_account_id: str = "",
        raw: bool = False,
    ) -> pd.DataFrame:
        """Lấy vị thế phái sinh. account_id là custody code 105C format."""
        return self._derivatives.get_positions(
            account_id=account_id, sub_account_id=sub_account_id, raw=raw
        )

    def get_derivative_orders(
        self,
        account_id: str,
        symbol: Optional[str] = None,
        page_no: int = 0,
        page_size: int = 50,
        raw: bool = False,
    ) -> pd.DataFrame:
        """Lấy lệnh phái sinh. account_id là custody code 105C format."""
        return self._derivatives.get_orders(
            account_id=account_id, symbol=symbol, page_no=page_no, page_size=page_size, raw=raw
        )

    def get_derivative_cash(
        self,
        account_id: str,
        sub_account_id: str = "",
        get_type: str = "",
        raw: bool = False,
    ) -> pd.DataFrame:
        """Lấy tiền mặt phái sinh (margin balance)."""
        return self._derivatives.get_cash(
            account_id=account_id, sub_account_id=sub_account_id, get_type=get_type, raw=raw
        )

    def get_derivative_closed_positions(
        self,
        account_id: str,
        sub_account_id: str,
        symbol: str = "",
        page_no: int = 1,
        page_size: int = 20,
        raw: bool = False,
    ) -> pd.DataFrame:
        """GET /khronos/v1/account/portfolio/position/close"""
        return self._derivatives.get_closed_positions(
            account_id=account_id, sub_account_id=sub_account_id,
            symbol=symbol, page_no=page_no, page_size=page_size, raw=raw,
        )

    def get_derivative_condition_orders(
        self,
        account_id: str,
        sub_account_id: str,
        order_status: str = "0",
        order_type: str = "ALL,ALL",
        symbol: str = "",
        page_no: int = 1,
        page_size: int = 25,
        raw: bool = False,
    ) -> pd.DataFrame:
        """GET /khronos/v1/order/condition/detail"""
        return self._derivatives.get_condition_orders(
            account_id=account_id, sub_account_id=sub_account_id,
            order_status=order_status, order_type=order_type, symbol=symbol,
            page_no=page_no, page_size=page_size, raw=raw,
        )

    def place_derivative_order(
        self,
        account_id: str,
        sub_account_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float,
        request_id: str,
        dry_run: bool = True,
    ) -> dict:
        """Đặt lệnh phái sinh thường. dry_run=True mặc định."""
        return self._derivatives.place_derivative_order(
            account_id=account_id, sub_account_id=sub_account_id,
            symbol=symbol, side=side, order_type=order_type,
            quantity=quantity, price=price, request_id=request_id, dry_run=dry_run,
        )

    def place_derivative_condition_order(
        self,
        account_id: str,
        sub_account_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float,
        trigger_price: float,
        request_id: str,
        dry_run: bool = True,
        *,
        callback_point: Optional[float] = None,
        activation_price: Optional[float] = None,
    ) -> dict:
        """Đặt lệnh phái sinh điều kiện. dry_run=True mặc định."""
        return self._derivatives.place_derivative_condition_order(
            account_id=account_id, sub_account_id=sub_account_id,
            symbol=symbol, side=side, order_type=order_type,
            quantity=quantity, price=price, trigger_price=trigger_price,
            request_id=request_id, dry_run=dry_run,
            callback_point=callback_point, activation_price=activation_price,
        )

    def change_derivative_order(
        self,
        account_id: str,
        sub_account_id: str,
        order_id: str,
        quantity: int,
        price: float,
        request_id: str,
        dry_run: bool = True,
    ) -> dict:
        """
        Sửa lệnh phái sinh thường. dry_run=True mặc định.

        ⚠ ĐỔI CHỮ KÝ 2026-10-10: thêm `account_id` + `sub_account_id`.
        Spec `/khronos/v1/order/change` liệt kê cả hai trong `required`; bản cũ
        không gửi ⇒ TCBS từ chối yêu cầu.
        """
        return self._derivatives.change_derivative_order(
            account_id=account_id, sub_account_id=sub_account_id,
            order_id=order_id, quantity=quantity, price=price,
            request_id=request_id, dry_run=dry_run,
        )

    def change_derivative_condition_order(
        self,
        account_id: str,
        order_id: str,
        trigger_price: float,
        request_id: str,
        dry_run: bool = True,
    ) -> dict:
        """
        Sửa lệnh phái sinh điều kiện. dry_run=True mặc định.

        ⚠ ĐỔI CHỮ KÝ 2026-10-10: bỏ `quantity` + `price`, thêm `account_id`.
        Spec `/khronos/v2/order/condition/change` không định nghĩa 2 field đã bỏ
        (lệnh điều kiện chỉ sửa được giá kích hoạt) và bắt buộc có `accountId`.
        """
        return self._derivatives.change_derivative_condition_order(
            account_id=account_id, order_id=order_id,
            trigger_price=trigger_price, request_id=request_id, dry_run=dry_run,
        )

    def cancel_derivative_order(
        self,
        account_id: str,
        order_id: str,
        request_id: str,
        dry_run: bool = True,
    ) -> dict:
        """
        Hủy lệnh phái sinh. dry_run=True mặc định.

        ⚠ ĐỔI CHỮ KÝ 2026-10-10: thêm `account_id` (spec yêu cầu `accountId`).
        """
        return self._derivatives.cancel_derivative_order(
            account_id=account_id, order_id=order_id,
            request_id=request_id, dry_run=dry_run,
        )

    # ── Market ─────────────────────────────────────────────────────────

    def get_ticker_info(
        self,
        tickers: Optional[str | list[str]] = None,
        index: Optional[int] = None,
        raw: bool = False,
    ) -> pd.DataFrame:
        """Thông tin cơ bản về mã cổ phiếu / chỉ số. Public endpoint."""
        return self._market.get_ticker_info(tickers=tickers, index=index, raw=raw)

    def get_ticker_snaps(self, index: int = 1, raw: bool = False) -> pd.DataFrame:
        """Snapshot giá hiện tại cho toàn bộ mã trong sàn. Public endpoint."""
        return self._market.get_ticker_snaps(index=index, raw=raw)

    def get_put_through_snaps(self, floor: int = 1, raw: bool = False) -> pd.DataFrame:
        """Snapshot giao dịch thỏa thuận. Public endpoint."""
        return self._market.get_put_through_snaps(floor=floor, raw=raw)

    def get_intraday_history(
        self,
        ticker: str,
        page: int = 0,
        size: int = 100,
        raw: bool = False,
    ) -> pd.DataFrame:
        """Lịch sử khớp lệnh trong ngày theo mã."""
        return self._market.get_intraday_history(ticker=ticker, page=page, size=size, raw=raw)

    def get_bsa(
        self,
        ticker: str,
        bsa_type: str = "all",
        raw: bool = False,
    ) -> pd.DataFrame:
        """Buy/Sell Analysis theo mã."""
        return self._market.get_bsa(ticker=ticker, bsa_type=bsa_type, raw=raw)

    def get_bsa_15m(
        self,
        ticker: str,
        time_window: int = 15,
        raw: bool = False,
    ) -> pd.DataFrame:
        """Buy/Sell Analysis theo từng phiên 15 phút."""
        return self._market.get_bsa_15m(ticker=ticker, time_window=time_window, raw=raw)

    def get_bsa_month(self, ticker: str, raw: bool = False) -> pd.DataFrame:
        """Buy/Sell Analysis tổng hợp theo tháng."""
        return self._market.get_bsa_month(ticker=ticker, raw=raw)

    def get_derivatives_market_info(self, raw: bool = False) -> pd.DataFrame:
        """Danh sách hợp đồng phái sinh đang niêm yết."""
        return self._market.get_derivatives_info(raw=raw)

    # ── Portfolio (pure compute) ──────────────────────────────────────────────

    def portfolio_snapshot(
        self, account_no: str, enrich_prices: bool = True, raw: bool = False
    ) -> dict:
        """
        Tổng hợp portfolio snapshot: holdings + balance → summary dict.

        Gọi get_holdings() và get_balance() nội bộ, sau đó tính toán qua TCBSPortfolioEngine.
        Nếu enrich_prices=True (mặc định), giá thị trường sẽ được bổ sung từ /tartarus/v1/tickerCommons.
        """
        holdings_df = self.get_holdings(account_no=account_no, enrich_prices=enrich_prices, raw=raw)
        balance_df = self.get_balance(account_no=account_no, raw=raw)
        enriched = TCBSPortfolioEngine.holdings_snapshot(holdings_df)
        return TCBSPortfolioEngine.portfolio_summary(enriched, balance_df)

    # ── Session shortcuts ─────────────────────────────────────────────────────

    @property
    def is_authenticated(self) -> bool:
        """True nếu session đang ở trạng thái AUTHENTICATED_READ hoặc WRITE_ENABLED."""
        from vnbroker.broker.session import SessionState  # noqa: PLC0415
        return self.session.state in (
            SessionState.AUTHENTICATED_READ,
            SessionState.AUTHENTICATED_WRITE_ENABLED,
        )

    def enable_write(self) -> None:
        """Cho phép write operations. Cần đã authenticated trước."""
        self.session.enable_write()

    def __repr__(self) -> str:
        return f"TCBSBrokerClient(state={self.session.state.name!r})"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_api_key() -> str:
    """Đọc API key từ biến môi trường."""
    import os
    return (
        os.getenv("VNBROKER_BROKER_TCBS_API_KEY")
        or os.getenv("vnbroker_TCBS_OPENAPI_API_KEY")
        or os.getenv("TCBS_API_KEY")
        or ""
    )


def _resolve_base_url() -> str:
    """Đọc base URL từ biến môi trường hoặc trả về mặc định."""
    import os
    return (
        os.getenv("VNBROKER_BROKER_TCBS_BASE_URL")
        or os.getenv("TCBS_OPENAPI_BASE_URL")
        or "https://openapi.tcbs.com.vn"
    )


def _resolve_custody_code() -> str | None:
    """Đọc custody code từ biến môi trường (tùy chọn)."""
    import os
    return (
        os.getenv("VNBROKER_BROKER_TCBS_CUSTODY_CODE")
        or os.getenv("TCBS_CUSTODY_CODE")
        or None
    )
