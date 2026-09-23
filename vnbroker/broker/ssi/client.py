"""
vnbroker.broker.ssi.client — SSIBrokerClient: unified facade cho SSI broker lane.

Usage:
    from vnbroker.broker.ssi.client import SSIBrokerClient

    client = SSIBrokerClient(api_key="...", api_secret="...")
    client.authenticate()                          # market-data-only (không OTP)
    ohlc = client.get_ohlc("SSI", timeframe="1d")  # DataFrame
    client.authenticate(otp="123456")              # full trading auth
    balance = client.get_balance("A1")

    client = SSIBrokerClient(client_id="...", api_key="...", api_secret="...",
                             private_key="...")    # write cần private_key (ký RSA)

SECURITY RULES:
  - KHÔNG log api_key/api_secret/otp/transaction_id/token/private_key/signature.
  - dry_run=True mặc định cho mọi write (place/modify/cancel, FCO).
  - 1 SSIHttpClient dùng chung cả lane (1 Bearer header + 1 rate-limiter).
  - Dùng requests trực tiếp qua _transport — KHÔNG dùng core/utils/client.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from vnbroker.broker.base import BaseBrokerClient
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession, SessionState
from vnbroker.broker.ssi.account import SSIAccountService
from vnbroker.broker.ssi.auth import SSIAuthService
from vnbroker.broker.ssi.equity import SSIEquityService
from vnbroker.broker.ssi.fco import SSIFCOService
from vnbroker.broker.ssi.market import SSIMarketService
from vnbroker.broker.ssi.money import SSIMoneyService
from vnbroker.broker.ssi.portfolio import SSIPortfolioService
from vnbroker.broker.ssi.stream import SSIStreamManager
from vnbroker.broker.ssi._transport import SSIHttpClient
from vnbroker.broker.tcbs.portfolio import TCBSPortfolioEngine

_logger = logging.getLogger("vnbroker.broker.ssi.client")


class SSIBrokerClient(BaseBrokerClient):
    """
    Unified facade cho toàn bộ SSI broker lane (native FastConnect v3).

    Tổng hợp:
      - SSIAuthService      → authenticate, request_otp, refresh, ensure_authenticated
      - SSIAccountService   → list_accounts
      - SSIMoneyService     → get_balance, PPMMR, maxBuySell
      - SSIEquityService    → place/modify/cancel (dry_run default)
      - SSIFCOService       → 7 lệnh điều kiện + query vòng đời
      - SSIMarketService    → OHLC, index, securities, master data
      - SSIPortfolioService → positions, orders, snapshot
      - SSIStreamManager    → WebSocket realtime (lazy, qua property .stream)

    Pattern:
        client = SSIBrokerClient(api_key="...", api_secret="...")
        client.authenticate()            # market-only
        client.authenticate(otp="...")   # full
        client.session.enable_write()    # trước mọi write dry_run=False
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        private_key: Optional[str] = None,
        api_url: Optional[str] = None,
        stream_url: Optional[str] = None,
    ) -> None:
        """
        Khởi tạo SSI broker client. Param None → đọc env VNBROKER_BROKER_SSI_*.

        Không raise khi thiếu creds ở construct (fail-sớm ở authenticate).
        """
        self._config = SSICredentialConfig(
            api_key=api_key or os.getenv("VNBROKER_BROKER_SSI_API_KEY") or "",
            api_secret=api_secret or os.getenv("VNBROKER_BROKER_SSI_API_SECRET") or "",
            client_id=client_id or os.getenv("VNBROKER_BROKER_SSI_CLIENT_ID") or "",
            private_key=private_key
            or os.getenv("VNBROKER_BROKER_SSI_PRIVATE_KEY")
            or "",
            api_url=(
                api_url
                or os.getenv("VNBROKER_BROKER_SSI_API_URL")
                or "https://api.ssi.com.vn"
            ).rstrip("/"),
            stream_url=(
                stream_url
                or os.getenv("VNBROKER_BROKER_SSI_STREAM_URL")
                or "wss://stream.ssi.com.vn/ws/v3"
            ),
        )
        self.session = BrokerSession(provider="SSI")
        self._transport = SSIHttpClient(
            base_url=self._config.api_url,
            timeout=self._config.timeout_seconds,
            rate_limit_rps=self._config.rate_limit_rps,
            max_retries=self._config.max_retries,
        )

        self._auth = SSIAuthService(self._config, self.session, self._transport)
        self._account = SSIAccountService(self._config, self.session, self._transport)
        self._money = SSIMoneyService(self._config, self.session, self._transport)
        self._equity = SSIEquityService(self._config, self.session, self._transport)
        self._portfolio = SSIPortfolioService(
            self._config, self.session, self._transport
        )
        self._market = SSIMarketService(self._config, self.session, self._transport)
        self._fco = SSIFCOService(self._config, self.session, self._transport)
        self._stream: Optional[SSIStreamManager] = None
        self.portfolio = TCBSPortfolioEngine  # pure compute — truy cập trực tiếp

    # ── Base interface ───────────────────────────────────────────────────

    @property
    def provider_name(self) -> str:
        """Tên nhà cung cấp broker."""
        return "SSI"

    def authenticate(
        self,
        otp: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> str:
        """
        Xác thực SSI. Không OTP → market-data-only; otp/transaction_id → full.

        Returns:
            access token string.
        """
        self._auth.authenticate(otp=otp, transaction_id=transaction_id)
        return self.session.token or ""

    def request_otp(self) -> Dict[str, Any]:
        """Yêu cầu gửi OTP / push Smart OTP."""
        return self._auth.request_otp()

    def refresh(self) -> str:
        """Refresh access token. Trả về token mới."""
        self._auth.refresh()
        return self.session.token or ""

    def ensure_authenticated(
        self,
        otp: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> str:
        """Đảm bảo token hợp lệ (refresh/poll tự động)."""
        return self._auth.ensure_authenticated(otp=otp, transaction_id=transaction_id)

    def is_token_valid(self) -> bool:
        """True nếu token còn hiệu lực. Không raise."""
        return self._auth.is_token_valid()

    def revoke(self) -> None:
        """Hủy session, xóa token."""
        self._auth.revoke()

    def close(self) -> None:
        """Đóng stream + transport + revoke session."""
        if self._stream is not None:
            try:
                self._stream.disconnect()
            except Exception as exc:
                _logger.debug("SSI close stream: %s", exc)
        try:
            self._transport.close()
        finally:
            self.revoke()

    def get_account_list(self) -> List[Dict[str, Any]]:
        """Danh sách tài khoản theo BaseBrokerClient (list dict)."""
        accounts = self.list_accounts(raw=True)
        return accounts if isinstance(accounts, list) else []

    def get_account_balance(self, account_no: str) -> Dict[str, Any]:
        """Số dư tài khoản theo BaseBrokerClient (dict)."""
        balance = self.get_balance(account_no=account_no, raw=True)
        return balance if isinstance(balance, dict) else {}

    # ── Account / Money ──────────────────────────────────────────────────

    def list_accounts(
        self, raw: bool = False
    ) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
        """Danh sách tài khoản (account_no masked khi raw=False)."""
        out = self._account.list_accounts(raw=raw)
        if raw:
            assert isinstance(out, list)
            return out
        assert isinstance(out, pd.DataFrame)
        return out

    def get_balance(
        self, account_no: str, raw: bool = False
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """Số dư equity."""
        return self._money.get_balance(account_no=account_no, raw=raw)

    def get_derivative_balance(
        self, account_no: str, raw: bool = False
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """Số dư phái sinh."""
        return self._money.get_derivative_balance(account_no=account_no, raw=raw)

    def get_ppmmr(
        self, account_no: str, raw: bool = False
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """PPMMR equity (full columns)."""
        return self._money.get_ppmmr(account_no=account_no, raw=raw)

    def get_derivative_ppmmr(
        self, account_no: str, raw: bool = False
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """PPMMR phái sinh (full columns)."""
        return self._money.get_derivative_ppmmr(account_no=account_no, raw=raw)

    def get_purchasing_power(
        self,
        account_no: str,
        symbol: str,
        price: Optional[Union[int, float]] = None,
        raw: bool = False,
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """Sức mua/bán (price=None → giá thị trường)."""
        return self._money.get_max_buy_sell(
            account_no=account_no, symbol=symbol, price=price, raw=raw
        )

    # ── Portfolio ────────────────────────────────────────────────────────

    def get_holdings(
        self, account_no: str, raw: bool = False
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """Vị thế equity."""
        return self._portfolio.get_equity_positions(account_no=account_no, raw=raw)

    def get_derivative_positions(
        self, account_no: str, open_only: bool = False, raw: bool = False
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """Vị thế phái sinh (open_only=True → chỉ vị thế mở)."""
        return self._portfolio.get_derivative_positions(
            account_no=account_no, open_only=open_only, raw=raw
        )

    def get_orders(
        self, account_no: str, raw: bool = False
    ) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
        """Sổ lệnh trong ngày."""
        out = self._portfolio.get_today_orders(account_no=account_no, raw=raw)
        if raw:
            assert isinstance(out, list)
            return out
        assert isinstance(out, pd.DataFrame)
        return out

    def get_order_history(
        self, account_no: str, from_date: str, to_date: str, raw: bool = False
    ) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
        """Lịch sử lệnh YYYY/MM/DD."""
        out = self._portfolio.get_historical_orders(
            account_no=account_no, from_date=from_date, to_date=to_date, raw=raw
        )
        if raw:
            assert isinstance(out, list)
            return out
        assert isinstance(out, pd.DataFrame)
        return out

    def portfolio_snapshot(
        self, account_no: str, market_prices: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Snapshot holdings + summary (giá thị trường qua market_prices map)."""
        return self._portfolio.portfolio_snapshot(
            account_no=account_no, market_prices=market_prices
        )

    # ── Equity write ─────────────────────────────────────────────────────

    def place_order(
        self,
        account_no: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: Union[int, float] = 0,
        request_id: Optional[str] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Đặt lệnh. dry_run=True mặc định (không pin_code — ký RSA)."""
        return self._equity.place_order(
            account_no=account_no,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            request_id=request_id,
            dry_run=dry_run,
        )

    def place_limit_order(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        price: Union[int, float],
        request_id: Optional[str] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Lệnh LO. dry_run=True mặc định."""
        return self._equity.place_limit_order(
            account_no=account_no,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            request_id=request_id,
            dry_run=dry_run,
        )

    def place_market_order(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        request_id: Optional[str] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Lệnh MTL. dry_run=True mặc định."""
        return self._equity.place_market_order(
            account_no=account_no,
            symbol=symbol,
            side=side,
            quantity=quantity,
            request_id=request_id,
            dry_run=dry_run,
        )

    def modify_order(
        self,
        account_no: str,
        quantity: Optional[int] = None,
        price: Optional[Union[int, float]] = None,
        order_id: str = "",
        client_request_id: str = "",
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Sửa giá HOẶC lượng. dry_run=True mặc định."""
        return self._equity.modify_order(
            account_no=account_no,
            quantity=quantity,
            price=price,
            order_id=order_id,
            client_request_id=client_request_id,
            dry_run=dry_run,
        )

    def cancel_order(
        self,
        account_no: str,
        order_id: str = "",
        client_request_id: str = "",
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Hủy lệnh. dry_run=True mặc định."""
        return self._equity.cancel_order(
            account_no=account_no,
            order_id=order_id,
            client_request_id=client_request_id,
            dry_run=dry_run,
        )

    # ── FCO ──────────────────────────────────────────────────────────────

    def place_fco_gtd(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        price: Union[int, float, str],
        price_slip: Union[int, float],
        from_date: str,
        to_date: str,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Đặt FCO GTD. dry_run=True mặc định."""
        return self._fco.place_fco_gtd(
            account_no,
            symbol,
            side,
            quantity,
            price,
            price_slip,
            from_date,
            to_date,
            dry_run=dry_run,
        )

    def place_fco_stop(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        stop_price: Union[int, float],
        operator: str,
        from_date: str,
        to_date: str,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Đặt FCO Stop. dry_run=True mặc định."""
        return self._fco.place_fco_stop(
            account_no,
            symbol,
            side,
            quantity,
            stop_price,
            operator,
            from_date,
            to_date,
            dry_run=dry_run,
        )

    def place_fco_stop_limit(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        price: Union[int, float],
        price_slip: Union[int, float],
        stop_price: Union[int, float],
        operator: str,
        from_date: str,
        to_date: str,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Đặt FCO Stop-Limit. dry_run=True mặc định."""
        return self._fco.place_fco_stop_limit(
            account_no,
            symbol,
            side,
            quantity,
            price,
            price_slip,
            stop_price,
            operator,
            from_date,
            to_date,
            dry_run=dry_run,
        )

    def place_fco_trailing_stop(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        active_price: Union[int, float],
        trailing_amount: Union[int, float],
        from_date: str,
        to_date: str,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Đặt FCO Trailing Stop. dry_run=True mặc định."""
        return self._fco.place_fco_trailing_stop(
            account_no,
            symbol,
            side,
            quantity,
            active_price,
            trailing_amount,
            from_date,
            to_date,
            dry_run=dry_run,
        )

    def place_fco_trailing_stop_limit(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        active_price: Union[int, float],
        trailing_amount: Union[int, float],
        price_slip: Union[int, float],
        from_date: str,
        to_date: str,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Đặt FCO Trailing Stop-Limit. dry_run=True mặc định."""
        return self._fco.place_fco_trailing_stop_limit(
            account_no,
            symbol,
            side,
            quantity,
            active_price,
            trailing_amount,
            price_slip,
            from_date,
            to_date,
            dry_run=dry_run,
        )

    def place_fco_oco(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        tp_active_price: Union[int, float],
        sl_active_price: Union[int, float],
        tp_price: Union[int, float, str] = "MP",
        sl_price: Union[int, float, str] = "MP",
        tp_slip: Union[int, float] = 0,
        sl_slip: Union[int, float] = 0,
        from_date: str = "",
        to_date: str = "",
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Đặt FCO OCO. dry_run=True mặc định."""
        return self._fco.place_fco_oco(
            account_no,
            symbol,
            side,
            quantity,
            tp_active_price,
            sl_active_price,
            tp_price,
            sl_price,
            tp_slip,
            sl_slip,
            from_date,
            to_date,
            dry_run=dry_run,
        )

    def place_fco_bull_bear(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        price: Union[int, float, str],
        price_slip: Union[int, float],
        tp_active_price: Union[int, float],
        sl_active_price: Union[int, float],
        tp_price: Union[int, float, str],
        sl_price: Union[int, float, str],
        tp_slip: Union[int, float],
        sl_slip: Union[int, float],
        from_date: str = "",
        to_date: str = "",
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Đặt FCO Bull-Bear. dry_run=True mặc định."""
        return self._fco.place_fco_bull_bear(
            account_no,
            symbol,
            side,
            quantity,
            price,
            price_slip,
            tp_active_price,
            sl_active_price,
            tp_price,
            sl_price,
            tp_slip,
            sl_slip,
            from_date,
            to_date,
            dry_run=dry_run,
        )

    def cancel_fco(self, fco_id: str, dry_run: bool = True) -> Dict[str, Any]:
        """Hủy FCO. dry_run=True mặc định."""
        return self._fco.cancel_fco(fco_id=fco_id, dry_run=dry_run)

    def get_fco_by_account_no(
        self,
        account_no: str,
        page_index: int = 1,
        page_size: int = 10,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
        """Query FCO theo tài khoản."""
        out = self._fco.get_fco_by_account_no(account_no, page_index, page_size, raw)
        return _narrow_fco_list(out, raw)

    def get_fco_by_symbol(
        self,
        account_no: str,
        symbol: str,
        page_index: int = 1,
        page_size: int = 10,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
        """Query FCO theo mã."""
        out = self._fco.get_fco_by_symbol(
            account_no, symbol, page_index, page_size, raw
        )
        return _narrow_fco_list(out, raw)

    def get_fco_by_status(
        self,
        account_no: str,
        process_status: str,
        page_index: int = 1,
        page_size: int = 10,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
        """Query FCO theo trạng thái."""
        out = self._fco.get_fco_by_status(
            account_no, process_status, page_index, page_size, raw
        )
        return _narrow_fco_list(out, raw)

    def get_fco_by_date(
        self,
        account_no: str,
        from_date: str,
        to_date: str,
        page_index: int = 1,
        page_size: int = 10,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
        """Query FCO theo khoảng ngày."""
        out = self._fco.get_fco_by_date(
            account_no, from_date, to_date, page_index, page_size, raw
        )
        return _narrow_fco_list(out, raw)

    def get_fco_by_id(self, account_no: str, fco_id: str) -> Optional[Dict[str, Any]]:
        """Chi tiết 1 FCO hoặc None."""
        return self._fco.get_fco_by_id(account_no=account_no, fco_id=fco_id)

    def get_fco_order_book(
        self,
        fco_id: str,
        page_index: int = 1,
        page_size: int = 10,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
        """Nhật ký khớp của 1 FCO."""
        out = self._fco.get_fco_order_book(fco_id, page_index, page_size, raw)
        return _narrow_fco_list(out, raw)

    # ── Market ───────────────────────────────────────────────────────────

    def get_ohlc(
        self,
        symbol: str,
        timeframe: str = "1d",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 1,
        size: int = 1000,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
        """Nến OHLCV (timeframe 1m–1M)."""
        out = self._market.get_ohlc(
            symbol, timeframe, from_date, to_date, page, size, raw
        )
        return _narrow_list(out, raw)

    def get_indexes(
        self, board: Optional[str] = None, raw: bool = False
    ) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
        """Danh sách chỉ số."""
        out = self._market.get_indexes(board, raw)
        return _narrow_list(out, raw)

    def get_index_summary(
        self,
        index: str,
        trading_date: Optional[str] = None,
        raw: bool = False,
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """Summary chỉ số."""
        return self._market.get_index_summary(index, trading_date, raw)

    def get_board_summary(
        self,
        board: str,
        trading_date: Optional[str] = None,
        raw: bool = False,
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """Summary sàn."""
        return self._market.get_board_summary(board, trading_date, raw)

    def get_securities_info(
        self,
        symbol: Optional[str] = None,
        board: Optional[str] = None,
        index: Optional[str] = None,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
        """Thông tin chứng khoán."""
        out = self._market.get_securities_info(symbol, board, index, raw)
        return _narrow_list(out, raw)

    def get_securities_summary(
        self,
        symbol: Optional[str] = None,
        index: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
        """Summary chứng khoán."""
        out = self._market.get_securities_summary(
            symbol, index, from_date, to_date, raw
        )
        return _narrow_list(out, raw)

    def get_master_data(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
        """Trần/sàn/TC toàn sàn (tự gom pages)."""
        out = self._market.get_master_data(from_date, to_date, raw)
        return _narrow_list(out, raw)

    # ── Stream (lazy) ────────────────────────────────────────────────────

    @property
    def stream(self) -> SSIStreamManager:
        """SSIStreamManager dùng chung session/config (tạo lazy)."""
        if self._stream is None:
            self._stream = SSIStreamManager(self._config, self.session)
        return self._stream

    # ── Session shortcuts ────────────────────────────────────────────────

    @property
    def is_authenticated(self) -> bool:
        """True nếu AUTHENTICATED_READ hoặc WRITE_ENABLED."""
        return self.session.state in (
            SessionState.AUTHENTICATED_READ,
            SessionState.AUTHENTICATED_WRITE_ENABLED,
        )

    def enable_write(self) -> None:
        """Cho phép write. Cần authenticated trước."""
        self.session.enable_write()

    def __repr__(self) -> str:
        return f"SSIBrokerClient(state={self.session.state.name!r})"


def _narrow_list(
    out: Union[pd.DataFrame, List[Dict[str, Any]]], raw: bool
) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
    if raw:
        assert isinstance(out, list)
        return out
    assert isinstance(out, pd.DataFrame)
    return out


def _narrow_fco_list(
    out: Union[pd.DataFrame, List[Dict[str, Any]]], raw: bool
) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
    return _narrow_list(out, raw)
