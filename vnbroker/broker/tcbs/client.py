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
"""
from __future__ import annotations

import logging
from typing import Optional, Union

import pandas as pd

from vnbroker.broker.exceptions import BrokerValidationError
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.security.guards import write_gate
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.tcbs.account import TCBSAccountService
from vnbroker.broker.tcbs.auth import TCBSAuthService
from vnbroker.broker.tcbs.equity import TCBSEquityService
from vnbroker.broker.tcbs.derivatives import TCBSDerivativesService
from vnbroker.broker.tcbs.market import TCBSMarketService
from vnbroker.broker.tcbs.money import TCBSMoneyService
from vnbroker.broker.tcbs.portfolio import TCBSPortfolioEngine

_logger = logging.getLogger("vnbroker.broker.tcbs.client")


class TCBSBrokerClient:
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
        from vnbroker.broker.security.credentials import TCBSCredentialConfig  # noqa: PLC0415

        self._config = TCBSCredentialConfig(
            api_key=api_key or _resolve_api_key(),
            base_url=base_url or _resolve_base_url(),
            custody_code=custody_code or _resolve_custody_code(),
        )
        self.session = BrokerSession()

        self._auth = TCBSAuthService(config=self._config, session=self.session)
        self._account = TCBSAccountService(config=self._config, session=self.session)
        self._money = TCBSMoneyService(config=self._config, session=self.session)
        self._equity = TCBSEquityService(config=self._config, session=self.session)
        self._derivatives = TCBSDerivativesService(config=self._config, session=self.session)
        self._market = TCBSMarketService(config=self._config, session=self.session)
        self.portfolio = TCBSPortfolioEngine  # Pure compute engine — truy cập trực tiếp

    # ── Auth ─────────────────────────────────────────────────────────────────

    def authenticate(self, otp: str) -> None:
        """
        Xác thực với TCBS OpenAPI bằng OTP.

        Args:
            otp: OTP nhận từ TCBS (6 số).

        Raises:
            BrokerAuthError: Nếu xác thực thất bại.
        """
        self._auth.authenticate(otp=otp)

    def is_token_valid(self) -> bool:
        """Kiểm tra token hiện tại còn hợp lệ không."""
        return self._auth.is_token_valid()

    def revoke(self) -> None:
        """Hủy session và xóa token."""
        self._auth.revoke()

    # ── Account ──────────────────────────────────────────────────────────────

    def get_profile(self, custody_code: str, raw: bool = False) -> Union[dict, pd.DataFrame]:
        """Lấy thông tin profile theo custody_code (105C format)."""
        return self._account.get_profile(custody_code=custody_code, raw=raw)

    def get_balance(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """Lấy số dư tài khoản (CashInvestmentResponse)."""
        return self._account.get_balance(account_no=account_no, raw=raw)

    def get_purchasing_power(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """Lấy sức mua tài khoản."""
        return self._account.get_purchasing_power(account_no=account_no, raw=raw)

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

    # ── Equity ───────────────────────────────────────────────────────────────

    def get_orders(
        self, account_no: str, page: int = 0, page_size: int = 50, raw: bool = False
    ) -> pd.DataFrame:
        """Lấy danh sách lệnh đang có."""
        return self._equity.get_orders(account_no=account_no, page=page, size=page_size, raw=raw)

    def get_order_history(
        self, account_no: str, page: int = 0, page_size: int = 50,
        start_date: Optional[str] = None, end_date: Optional[str] = None, raw: bool = False,
    ) -> pd.DataFrame:
        """Lấy lịch sử lệnh."""
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
        self, account_no: str, raw: bool = False
    ) -> pd.DataFrame:
        """Lấy danh mục cổ phiếu đang nắm giữ."""
        return self._equity.get_holdings(account_no=account_no, raw=raw)

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
            pin_code=pin_code, request_id=request_id, dry_run=dry_run,
        )

    def modify_order(
        self,
        account_no: str,
        order_id: str,
        quantity: int,
        price: float,
        pin_code: str,
        dry_run: bool = True,
    ) -> dict:
        """Sửa lệnh. dry_run=True mặc định."""
        return self._equity.modify_order(
            account_no=account_no, order_id=order_id,
            quantity=quantity, price=price, pin_code=pin_code, dry_run=dry_run,
        )

    def cancel_order(
        self,
        account_no: str,
        order_id: str,
        pin_code: str,
        dry_run: bool = True,
    ) -> dict:
        """Hủy lệnh. dry_run=True mặc định."""
        return self._equity.cancel_order(
            account_no=account_no, order_id=order_id,
            pin_code=pin_code, dry_run=dry_run,
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
