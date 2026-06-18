"""
vnbroker.broker.vndirect.client — VNDirectBrokerClient: unified facade cho VNDirect broker lane.

Usage:
    from vnbroker.broker.vndirect.client import VNDirectBrokerClient

    client = VNDirectBrokerClient(api_key="...")
    client.authenticate()               # Lấy token
    profile = client.get_profile("123456")       # Thông tin profile
    balance = client.get_balance("123456")       # Số dư tài khoản
    holdings = client.get_holdings("123456")     # Danh mục cổ phiếu

SECURITY RULES:
  - KHÔNG log api_key, token.
  - dry_run=True mặc định cho tất cả write methods.
  - Dùng requests trực tiếp — KHÔNG dùng vnbroker.core.utils.client.
"""

from __future__ import annotations

import logging
from typing import Optional, Union

import pandas as pd

from vnbroker.broker.security.credentials import VNDirectCredentialConfig, resolve_vndirect_credentials
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.vndirect.auth import VNDirectAuthService
from vnbroker.broker.vndirect.account import VNDirectAccountService
from vnbroker.broker.vndirect.equity import VNDirectEquityService
from vnbroker.broker.vndirect.market import VNDirectMarketService
from vnbroker.broker.vndirect.money import VNDirectMoneyService
from vnbroker.broker.vndirect.portfolio import VNDirectPortfolioEngine

_logger = logging.getLogger("vnbroker.broker.vndirect.client")


class VNDirectBrokerClient:
    """
    Unified facade cho toàn bộ VNDirect broker lane.

    Tổng hợp:
      - VNDirectAuthService        → authenticate, is_token_valid, revoke
      - VNDirectAccountService     → get_profile, get_balance, get_portfolio, get_purchasing_power
      - VNDirectMoneyService       → get_cash, get_margin
      - VNDirectEquityService      → orders, executions, holdings, place/modify/cancel
      - VNDirectMarketService      → ticker_info, snapshot, intraday, price_board, indices
      - VNDirectPortfolioEngine    → snapshot, PnL, reconcile (pure compute)

    Pattern:
        client = VNDirectBrokerClient(api_key="...")
        client.authenticate()
        # Sau authenticate → session.is_authenticated → True
        # Enable write: client.session.enable_write()
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """
        Khởi tạo VNDirect broker client.

        Args:
            api_key: VNDirect OpenAPI key. Nếu None → đọc từ env VNBROKER_BROKER_VNDIRECT_API_KEY.
            base_url: Override base URL. Nếu None → đọc từ env hoặc dùng mặc định.
        """
        self._config = resolve_vndirect_credentials(
            api_key=api_key,
            base_url=base_url,
        )
        self.session = BrokerSession()

        self._auth = VNDirectAuthService(config=self._config, session=self.session)
        self._account = VNDirectAccountService(config=self._config, session=self.session)
        self._money = VNDirectMoneyService(config=self._config, session=self.session)
        self._equity = VNDirectEquityService(config=self._config, session=self.session)
        self._market = VNDirectMarketService(config=self._config, session=self.session)
        self.portfolio = VNDirectPortfolioEngine  # Pure compute engine — truy cập trực tiếp

    # ── Auth ─────────────────────────────────────────────────────────────────

    def authenticate(
        self,
        api_key: Optional[str] = None,
    ) -> None:
        """
        Xác thực với VNDirect OpenAPI bằng API key.

        Args:
            api_key: VNDirect API key (optional, uses config if not provided)

        Raises:
            BrokerAuthError: Nếu xác thực thất bại.
        """
        self._auth.authenticate(api_key=api_key)

    def is_token_valid(self) -> bool:
        """Kiểm tra token hiện tại còn hợp lệ không."""
        return self._auth.is_token_valid()

    def revoke(self) -> None:
        """Hủy session và xóa token."""
        self._auth.revoke()

    # ── Account ──────────────────────────────────────────────────────────────

    def get_profile(self, account_no: str, raw: bool = False) -> Union[dict, pd.DataFrame]:
        """Lấy thông tin profile theo account_no."""
        return self._account.get_account_info(account_no=account_no, raw=raw)

    def get_balance(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """Lấy số dư tài khoản."""
        return self._account.get_balance(account_no=account_no, raw=raw)

    def get_portfolio(self, account_no: str, raw: bool = False) -> pd.DataFrame:
        """Lấy danh mục cổ phiếu (holdings)."""
        return self._account.get_portfolio(account_no=account_no, raw=raw)

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
        from_date: str = "",
        to_date: str = "",
        page: int = 0,
        size: int = 20,
        raw: bool = False,
    ) -> pd.DataFrame:
        """Lấy dữ liệu margin tài khoản."""
        return self._money.get_margin(
            account_no=account_no,
            from_date=from_date,
            to_date=to_date,
            page=page,
            size=size,
            raw=raw,
        )

    # ── Equity Trading ───────────────────────────────────────────────────────

    def place_order(
        self,
        account_no: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: Optional[float] = None,
        validity: str = "DAY",
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """
        Đặt lệnh mua/bán cổ phiếu.

        Args:
            account_no: Số tài khoản
            symbol: Mã cổ phiếu
            side: "BUY" hoặc "SELL"
            order_type: "LO" (Limit), "MP" (Market), "ATO", "ATC"
            quantity: Khối lượng
            price: Giá limit (bắt buộc cho LO)
            validity: "DAY", "IOC", "FOK"
            raw: Trả về dict thay vì DataFrame
        """
        return self._equity.place_order(
            account_no=account_no,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            validity=validity,
            raw=raw,
        )

    def modify_order(
        self,
        account_no: str,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """Sửa lệnh."""
        return self._equity.modify_order(
            account_no=account_no,
            order_id=order_id,
            quantity=quantity,
            price=price,
            raw=raw,
        )

    def cancel_order(
        self,
        account_no: str,
        order_id: str,
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """Hủy lệnh."""
        return self._equity.cancel_order(
            account_no=account_no,
            order_id=order_id,
            raw=raw,
        )

    def get_orders(
        self,
        account_no: str,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> pd.DataFrame:
        """Lấy lịch sử lệnh."""
        return self._equity.get_orders(
            account_no=account_no,
            symbol=symbol,
            status=status,
            from_date=from_date,
            to_date=to_date,
            page=page,
            size=size,
            raw=raw,
        )

    def get_executions(
        self,
        account_no: str,
        symbol: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> pd.DataFrame:
        """Lấy lịch sử khớp lệnh."""
        return self._equity.get_executions(
            account_no=account_no,
            symbol=symbol,
            from_date=from_date,
            to_date=to_date,
            page=page,
            size=size,
            raw=raw,
        )

    def get_holdings(
        self,
        account_no: str,
        raw: bool = False,
    ) -> pd.DataFrame:
        """Lấy danh mục cổ phiếu hiện tại."""
        return self._equity.get_holdings(account_no=account_no, raw=raw)

    # ── Market Data ──────────────────────────────────────────────────────────

    def get_ticker_info(
        self,
        tickers: Optional[Union[str, list[str]]] = None,
        raw: bool = False,
    ) -> pd.DataFrame:
        """Thông tin cơ bản về mã cổ phiếu."""
        return self._market.get_ticker_info(tickers=tickers, raw=raw)

    def get_market_snapshot(
        self,
        raw: bool = False,
    ) -> pd.DataFrame:
        """Snapshot giá hiện tại cho toàn bộ mã."""
        return self._market.get_market_snapshot(raw=raw)

    def get_intraday(
        self,
        symbol: str,
        page: int = 0,
        size: int = 100,
        raw: bool = False,
    ) -> pd.DataFrame:
        """Lịch sử khớp lệnh trong ngày theo mã."""
        return self._market.get_intraday(symbol=symbol, page=page, size=size, raw=raw)

    def get_price_board(
        self,
        symbols: list[str],
        raw: bool = False,
    ) -> pd.DataFrame:
        """Bảng giá cho nhiều mã."""
        return self._market.get_price_board(symbols=symbols, raw=raw)

    def get_indices(
        self,
        raw: bool = False,
    ) -> pd.DataFrame:
        """Chỉ số thị trường."""
        return self._market.get_indices(raw=raw)

    # ── Portfolio (pure compute) ──────────────────────────────────────────────

    def portfolio_snapshot(
        self, account_no: str, enrich_prices: bool = True, raw: bool = False
    ) -> dict:
        """
        Tổng hợp portfolio snapshot: holdings + balance → summary dict.

        Gọi get_holdings() và get_balance() nội bộ, sau đó tính toán qua VNDirectPortfolioEngine.
        """
        holdings_df = self.get_holdings(account_no=account_no, enrich_prices=enrich_prices, raw=raw)
        balance_df = self.get_balance(account_no=account_no, raw=raw)
        enriched = VNDirectPortfolioEngine.holdings_snapshot(holdings_df)
        return VNDirectPortfolioEngine.portfolio_summary(enriched, balance_df)

    # ── Session shortcuts ────────────────────────────────────────────────────

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
        return f"VNDirectBrokerClient(state={self.session.state.name!r})"


# Register with BrokerRegistry
from vnbroker.broker.registry import BrokerRegistry  # noqa: E402, F401
BrokerRegistry.register("vndirect", VNDirectBrokerClient)