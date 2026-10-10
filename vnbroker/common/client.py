"""
Main entry point and orchestrator for vnbroker library.

This module provides the vnbroker class which acts as the primary interface
for accessing stock, forex, crypto, index, and fund data from various providers.

Architecture: Direct Provider Access Only
- VCI, KBS, TCBS, DNSE: Direct provider access with own credentials
- No PAT/Gateway required (v3.0+)
"""

import logging
import os
from typing import TYPE_CHECKING, Optional

from vnbroker.core.utils.logger import get_logger
from vnbroker.common.data import (
    StockComponents,
    Fund,
)

if TYPE_CHECKING:
    from vnbroker.common.retail import Retail

logger = get_logger(__name__)


class Vnbroker:
    """
    Main entry point for the vnbroker library (Direct Provider Architecture).

    Provides unified access to stock data, forex quotes, crypto prices,
    world indices, and fund information via direct provider access.

    Supported Sources:
    - "KBS": Korea Investment (KIS) - default
    - "VCI", "TCBS", "DNSE": Direct provider access

    Example:
        >>> # Direct provider mode (no PAT needed)
        >>> vn = Vnbroker()
        >>> acb = vn.stock('ACB')  # Uses default KBS
        >>> acb = vn.stock('ACB', source='VCI')  # Direct VCI access
        >>> acb = vn.stock('ACB', source='DNSE')  # Direct DNSE access (requires DNSE_API_KEY + DNSE_API_SECRET)
    """

    # AUTO = tầng 1 ẩn danh: hệ thống tự chọn provider ổn định và tự xoay vòng
    # khi gặp rate-limit / mất kết nối (xem Quote._run_with_failover).
    SUPPORTED_SOURCES = ["KBS", "VCI", "TCBS", "DNSE", "SSI", "AUTO"]
    DEFAULT_SOURCE = "KBS"

    def __init__(
        self,
        symbol: Optional[str] = None,
        source: str = "KBS",
        show_log: bool = True,
    ):
        """
        Initialize vnbroker client with direct provider support.

        Args:
            symbol (str, optional): Default symbol for stock queries.
                Defaults to None.
            source (str): Default data source.
                - "KBS", "VCI", "TCBS": Direct provider access (no auth)
                - "DNSE": Direct provider access (requires DNSE_API_KEY + DNSE_API_SECRET env vars)
                Defaults to "KBS".
            show_log (bool): Whether to display log messages.
                Defaults to True.

        Raises:
            ValueError: If source is not in SUPPORTED_SOURCES
        """
        self.symbol = symbol
        self.source = source.upper()
        self.show_log = show_log

        if self.source not in self.SUPPORTED_SOURCES:
            raise ValueError(
                f"Supported sources: {', '.join(self.SUPPORTED_SOURCES)}. Got: {source}"
            )

        if not show_log:
            logger.setLevel(logging.CRITICAL)

    def stock(
        self, symbol: Optional[str] = None, source: Optional[str] = None
    ) -> StockComponents:
        """
        Get stock data components for a symbol.

        Args:
            symbol (str, optional): Stock symbol (e.g., 'ACB', 'VNM').
                Defaults to 'VN30F1M' if not specified.
            source (str, optional): Data source override.
                - "KBS", "VCI", "TCBS", "DNSE": Direct provider access
                Defaults to instance source if not specified.

        Returns:
            StockComponents: Object with quote, company, finance, etc.

        Example:
            >>> # Direct provider mode
            >>> vn = Vnbroker()
            >>> acb = vn.stock('ACB')  # Uses default KBS
            >>> acb = vn.stock('ACB', source='VCI')  # Direct VCI access
            >>> acb = vn.stock('ACB', source='DNSE')  # Direct DNSE access (requires DNSE_API_KEY + DNSE_API_SECRET)
        """
        if symbol is None:
            symbol = "VN30F1M"
            if self.show_log:
                logger.info("Symbol not specified, using default: VN30F1M")
        else:
            self.symbol = symbol

        # Determine effective source
        effective_source = (source or self.source).upper()

        if effective_source not in self.SUPPORTED_SOURCES:
            raise ValueError(
                f"Source '{effective_source}' is not supported. "
                f"Supported: {', '.join(self.SUPPORTED_SOURCES)}"
            )

        # API keys per authenticated source (TCBS / SSI read their own env).
        if effective_source == "SSI":
            key = os.getenv("VNBROKER_BROKER_SSI_API_KEY")
            secret = os.getenv("VNBROKER_BROKER_SSI_API_SECRET")
        else:
            key = None
            secret = None

        # Bearer token cho TCBS phải do MỘT chỗ quyết định.
        #
        # Bản cũ đọc thẳng `TCBS_AUTH_TOKEN` ở đây và truyền xuống làm
        # `auth_token`, **ghi đè** mọi thứ provider tự giải quyết — kể cả khi
        # provider đã chọn đúng. Đo 2026-10-10: `TCBS_AUTH_TOKEN` là mã 48 ký
        # tự mà server từ chối (`401 validate.token.error`), còn `TCBS_JWT_TOKEN`
        # là JWT thật; truyền thẳng mã 48 ký tự xuống làm
        # `Vnbroker(source="TCBS").stock("TCB").quote.history()` ném
        # `ConnectionError` trong khi `explorer.tcbs.quote.Quote` gọi trực tiếp
        # với cùng `.env` thì chạy được (20 dòng).
        if effective_source == "TCBS":
            from vnbroker.explorer.tcbs.auth import resolve_auth_token

            tcbs_auth_token = resolve_auth_token()
        else:
            tcbs_auth_token = None

        return StockComponents(
            self.symbol,
            effective_source,
            show_log=self.show_log,
            auth_token=tcbs_auth_token,
            api_key=(
                os.getenv("vnbroker_TCBS_OPENAPI_API_KEY")
                or os.getenv("TCBS_OPENAPI_API_KEY")
                or os.getenv("vnbroker_TCBS_API_KEY")
                or os.getenv("TCBS_API_KEY")
                if effective_source == "TCBS"
                else key
            ),
            api_secret=secret,
        )

    def fx(self, symbol: Optional[str] = "EURUSD", source: Optional[str] = None):
        """
        Get forex (currency) data.

        Args:
            symbol (str): Currency pair (e.g., 'EURUSD', 'GBPUSD').
                Defaults to 'EURUSD'.
            source (str): Data source (not used - FX not supported).

        Raises:
            NotImplementedError: FX data is not supported by current providers
                (KBS, VCI, TCBS, DNSE). These providers only cover Vietnamese equities.
        """
        raise NotImplementedError(
            "FX/forex data is not supported by current Vietnamese market data providers "
            "(KBS, VCI, TCBS, DNSE). These providers only cover Vietnamese equities. "
            "FX support requires integration with international providers (planned for future release)."
        )

    def crypto(self, symbol: Optional[str] = "BTC", source: Optional[str] = None):
        """
        Get cryptocurrency data (Binance spot, public, no API key needed).

        Args:
            symbol (str): Crypto symbol (e.g., 'BTC', 'ETH', 'BTCUSDT').
                Defaults to 'BTC'.
            source (str): Data source. Only 'BINANCE' is currently supported.
                Defaults to 'BINANCE'.

        Returns:
            BinanceClient: Bound client with ``history()`` / ``intraday()``
                returning OHLCV DataFrames priced in USDT
                (``df.attrs["price_unit"] == "USDT"``).

        Example:
            >>> vn = Vnbroker()
            >>> btc = vn.crypto("BTC")
            >>> df = btc.history(start="2024-01-01", end="2024-12-31", interval="1D")
        """
        from vnbroker.connector.binance import BinanceClient

        src = (source or "BINANCE").upper()
        if src != "BINANCE":
            raise ValueError(
                f"Crypto source '{source}' is not supported. "
                f"Available: ['BINANCE']."
            )
        return BinanceClient(symbol=symbol or "BTC", show_log=self.show_log)

    def world_index(self, symbol: Optional[str] = "DJI", source: Optional[str] = None):
        """
        Get world market index data.

        Args:
            symbol (str): Index symbol (e.g., 'DJI', 'IXIC').
                Defaults to 'DJI' (Dow Jones).
            source (str): Data source (not used - world indices not supported).

        Raises:
            NotImplementedError: World index data is not supported by current providers
                (KBS, VCI, TCBS, DNSE). These providers only cover Vietnamese equities.
        """
        raise NotImplementedError(
            "World market index data is not supported by current Vietnamese market data providers "
            "(KBS, VCI, TCBS, DNSE). These providers only cover Vietnamese equities. "
            "World index support requires integration with international providers (planned for future release)."
        )

    def fund(self, source: str = "FMARKET") -> Fund:
        """
        Get fund/mutual fund data.

        Args:
            source (str): Data source. Only FMARKET is currently supported.
                Defaults to "FMARKET".

        Returns:
            Fund: Object with fund data and methods.

        Example:
            >>> funds = stock.fund()
            >>> all_funds = funds.listing()
        """
        return Fund(source)

    def retail(self) -> "Retail":
        """
        Get retail data (gold prices, exchange rates).

        Returns:
            Retail: Object with gold() and exchange_rate() methods.

        Example:
            >>> vn = Vnbroker()
            >>> retail = vn.retail()
            >>> sjc = retail.gold(source="sjc", date="2026-01-15")
            >>> fx = retail.exchange_rate()
        """
        from vnbroker.common.retail import Retail

        return Retail(show_log=self.show_log)

    def broker(self, provider: str = "tcbs", **kwargs):
        """
        Khởi tạo client giao dịch chứng khoán (Broker Lane).

        Args:
            provider (str): Tên broker ('tcbs', 'ssi'). Mặc định 'tcbs'.
            **kwargs: Tham số cấu hình xác thực tương ứng.
                - tcbs: api_key, base_url, custody_code, ...
                - ssi: client_id, api_key, api_secret, private_key,
                  api_url, stream_url, ...

        Returns:
            Broker client instance (TCBSBrokerClient hoặc SSIBrokerClient).

        Example:
            >>> vn = Vnbroker()
            >>> client = vn.broker(provider="tcbs", api_key="...")
            >>> client.authenticate(otp="123456")
            >>> balance = client.get_balance("0123456789")
            >>> ssi = vn.broker(provider="ssi", api_key="...", api_secret="...")
            >>> ssi.authenticate()  # market-data-only, không OTP
        """
        # Registration happens once at import (vnbroker.broker.__init__);
        # lookup goes through the UnifiedRegistry single entry point.
        import vnbroker.broker  # noqa: F401 - ensures register-once at import
        from vnbroker.core.unified_registry import UnifiedRegistry

        client_class = UnifiedRegistry.get_broker(provider)
        return client_class(**kwargs)
