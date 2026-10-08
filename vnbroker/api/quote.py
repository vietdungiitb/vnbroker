"""
vnbroker/api/quote.py

Unified Quote adapter with dynamic method detection and parameter filtering.
Module quản lý dữ liệu giá chứng khoán với phát hiện phương thức động và lọc tham số.
"""

from typing import Any, Callable, Optional, Union
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential
from vnbroker.config import Config
from vnbroker.base import BaseAdapter, dynamic_method
from vnbroker.core.types import (
    ParameterNames as P,
    MethodNames as M,
    DataSource,
    TimeFrame,
)

# Backward compatibility aliases
DataSources = DataSource
TimeResolutions = TimeFrame


def call_provider_sync(func: Callable[..., Any], /, **kwargs: Any) -> Any:
    """Call a provider callable that may be sync or async, from sync code.

    Single source of truth for the sync/async bridge. ``VCI.fetch_multiple`` is
    an ``async classmethod`` while ``KBS.fetch_multiple`` is a sync one, so any
    caller that invokes it blindly gets a coroutine back instead of frames.
    Callers MUST reuse this instead of writing a second bridge.

    Args:
        func: Bound method or classmethod to invoke.
        **kwargs: Forwarded verbatim to ``func``.

    Returns:
        Whatever ``func`` returns, with coroutines already awaited.

    Raises:
        RuntimeError: If an async callable is invoked from inside a running
            event loop, where ``asyncio.run`` cannot be used.
    """
    import asyncio
    import inspect

    if inspect.iscoroutinefunction(func):
        try:
            return asyncio.run(func(**kwargs))
        except RuntimeError as exc:
            raise RuntimeError(
                "Cannot call async provider method inside an active event loop. "
                "Use await provider.method(...) directly."
            ) from exc
    return func(**kwargs)


class Quote(BaseAdapter):
    _module_name = "quote"
    """
    Adapter for historical and intraday quote data.
    Bộ điều hợp dữ liệu giá lịch sử và trong ngày.

    Usage/Cách sử dụng:
        q = Quote(source="vci", symbol="VCI", random_agent=False, show_log=True)
        df = q.history(start_date="2024-01-01", end_date="2024-04-18", resolution=TimeResolutions.DAILY)
        df2 = q.intraday(page_size=100)
        depth = q.price_depth()
    """
    def __init__(
        self,
        source: str = DataSources.KBS,
        symbol: str = "",
        random_agent: bool = False,
        show_log: bool = False,
        auth_token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ):
        """
        Initialize a Quote instance.
        Khởi tạo một đối tượng Quote.

        Args:
            source (str): Data source (VCI, KBS). Nguồn dữ liệu (VCI, KBS).
            symbol (str): Stock symbol. Mã chứng khoán.
            random_agent (bool): Use random user agent for requests. Sử dụng user agent ngẫu nhiên cho các yêu cầu.
            show_log (bool): Show log messages. Hiển thị thông báo nhật ký.
        """
        # Ensure explorer modules are loaded (lazy load to avoid deadlock)
        from vnbroker import _ensure_explorer_modules_loaded
        _ensure_explorer_modules_loaded()
        
        # Store parameters for later use
        self.source = source
        self.symbol = symbol if symbol else ""
        self.random_agent = random_agent
        self.show_log = show_log
        self.auth_token = auth_token
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Validate the source to only accept vci or msn
        all_sources = DataSources.all_sources()
        if source.lower() not in [s.lower() for s in all_sources]:
            sources_str = ', '.join(all_sources)
            raise ValueError(
                f"Lớp Quote chỉ nhận giá trị tham số source là {sources_str}."
            )
        
        # BaseAdapter will discover vnbroker.explorer.<real_source>.quote
        # and pass only the kwargs its __init__ accepts (symbol, random_agent, show_log).
        super().__init__(
            source=source,
            symbol=symbol,
            random_agent=random_agent,
            show_log=show_log,
            auth_token=auth_token,
            api_key=api_key,
            api_secret=api_secret,
        )

    @retry(
        stop=stop_after_attempt(Config.RETRIES),
        wait=wait_exponential(
            multiplier=Config.BACKOFF_MULTIPLIER,
            min=Config.BACKOFF_MIN,
            max=Config.BACKOFF_MAX
        )
    )
    @dynamic_method
    def history(self, symbol: Optional[str] = None, start: str = None, end: str = None, 
               interval: str = TimeResolutions.DAILY, **kwargs: Any) -> pd.DataFrame:
        """
        Load historical OHLC data for the symbol.
        Tải dữ liệu OHLC lịch sử cho mã chứng khoán.

        Args:
            symbol (str, optional): Stock symbol. Mã chứng khoán.
            start (str): Start time in format YYYY-MM-DD or YYYY-MM-DD HH:MM:SS.
                        Thời gian bắt đầu định dạng YYYY-MM-DD hoặc YYYY-MM-DD HH:MM:SS.
            end (str): End time in format YYYY-MM-DD or YYYY-MM-DD HH:MM:SS.
                      Thời gian kết thúc định dạng YYYY-MM-DD hoặc YYYY-MM-DD HH:MM:SS.
            interval (str, optional): Data interval (1m, 5m, 15m, 30m, 1H, D, 1W, 1M).
                                     Khoảng thời gian dữ liệu (1m, 5m, 15m, 30m, 1H, D, 1W, 1M).

        Returns:
            pandas.DataFrame: Historical price data. Dữ liệu giá lịch sử.
            
        Examples:
            >>> quote = Quote(symbol="VCI", source="vci")
            >>> df = quote.history(start="2024-01-01", end="2024-04-18")
            >>> df = quote.history(symbol="FPT", start="2024-01-01", end="2024-04-18", interval=TimeResolutions.WEEKLY)
            >>> df = quote.history(symbol="FPT", start="2024-01-01 09:00:00", end="2024-01-01 14:30:00", interval=TimeResolutions.MINUTE_5)
        """
        # Support for backward compatibility with old parameter names
        if 'resolution' in kwargs:
            interval = kwargs.pop('resolution')
            
        # Prepare parameters
        params = {}
        if start:
            params[P.START] = start
        if end:
            params[P.END] = end
        if interval:
            params[P.INTERVAL] = interval
            
        # Add any remaining kwargs
        params.update(kwargs)
            
        return self._delegate_to_provider(M.HISTORY, symbol, **params)

    @retry(
        stop=stop_after_attempt(Config.RETRIES),
        wait=wait_exponential(
            multiplier=Config.BACKOFF_MULTIPLIER,
            min=Config.BACKOFF_MIN,
            max=Config.BACKOFF_MAX
        )
    )
    @dynamic_method
    def intraday(self, symbol: Optional[str] = None, page_size: int = 100, page: int = 1, **kwargs: Any) -> pd.DataFrame:
        """
        Load intraday trade data for the symbol.
        Tải dữ liệu giao dịch trong ngày cho mã chứng khoán.

        Args:
            symbol (str, optional): Stock symbol. Mã chứng khoán.
            page_size (int, optional): Number of records to return. Số lượng bản ghi trả về.
            page (int, optional): Page number. Số trang.

        Returns:
            pandas.DataFrame: Intraday trade data. Dữ liệu giao dịch trong ngày.
            
        Examples:
            >>> quote = Quote(symbol="VCI", source="vci")
            >>> df = quote.intraday()
            >>> df = quote.intraday(symbol="FPT", page_size=200)
        """
        # Prepare parameters
        params = {
            P.PAGE_SIZE: page_size,
            P.PAGE: page
        }
        
        # Add any remaining kwargs
        params.update(kwargs)
        
        return self._delegate_to_provider(M.INTRADAY, symbol, **params)

    @retry(
        stop=stop_after_attempt(Config.RETRIES),
        wait=wait_exponential(
            multiplier=Config.BACKOFF_MULTIPLIER,
            min=Config.BACKOFF_MIN,
            max=Config.BACKOFF_MAX
        )
    )
    @dynamic_method
    def price_depth(self, symbol: Optional[str] = None, **kwargs: Any) -> pd.DataFrame:
        """
        Load price depth (order book) data for the symbol.
        Tải dữ liệu độ sâu giá (sổ lệnh) cho mã chứng khoán.

        Args:
            symbol (str, optional): Stock symbol. Mã chứng khoán.

        Returns:
            pandas.DataFrame: Price depth data. Dữ liệu độ sâu giá.
            
        Examples:
            >>> quote = Quote(symbol="VCI", source="vci")
            >>> df = quote.price_depth()
            >>> df = quote.price_depth(symbol="FPT")
        """
        return self._delegate_to_provider(M.PRICE_DEPTH, symbol, **kwargs)
        
    def _delegate_to_provider(self, method_name: str, symbol: Optional[str] = None, **kwargs: Any) -> Any:
        """
        Delegate method call to the provider with symbol update if needed.
        Ủy thác cuộc gọi phương thức cho nhà cung cấp với cập nhật mã chứng khoán nếu cần.

        Args:
            method_name (str): Method name to call. Tên phương thức cần gọi.
            symbol (str, optional): Symbol to use. Mã chứng khoán cần sử dụng.
            **kwargs: Additional parameters. Các tham số bổ sung.

        Returns:
            Any: Result from the provider. Kết quả từ nhà cung cấp.
        """
        # Standard vnbroker implementation
        original_symbol = None
        try:
            if symbol:
                original_symbol = self.symbol
                self.symbol = symbol.upper()
                self._update_provider()
                
            # Get the method from the provider
            method = getattr(self.provider, method_name)
            return method(**kwargs)
        finally:
            if original_symbol:
                self.symbol = original_symbol
                self._update_provider()

    @retry(
        stop=stop_after_attempt(Config.RETRIES),
        wait=wait_exponential(
            multiplier=Config.BACKOFF_MULTIPLIER,
            min=Config.BACKOFF_MIN,
            max=Config.BACKOFF_MAX
        )
    )
    def fetch_multiple(
        self,
        symbols: list[str],
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: str = TimeResolutions.DAILY,
        show_log: bool = False,
        count_back: Optional[int] = None,
        floating: int = 2,
        length: Optional[Union[str, int]] = None,
        max_concurrency: int = 24,
        adaptive_concurrency: Optional[bool] = None,
    ) -> list[pd.DataFrame]:
        """
        Fetch historical data for multiple symbols in parallel.
        
        Lấy dữ liệu lịch sử cho nhiều mã chứng khoán song song.
        
        This method uses the provider's native parallel fetching capability
        (async for VCI, thread pool for KBS) for optimal performance.
        
        Args:
            symbols: List of stock symbols to fetch
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            interval: Data interval (1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M)
            show_log: Show log messages
            count_back: Number of bars to fetch
            floating: Decimal places for prices
            length: Time period string (e.g., '1M', '3M') or number of days
            max_concurrency: Maximum concurrent requests
            adaptive_concurrency: Enable adaptive concurrency control
            
        Returns:
            List of DataFrames, one per symbol (in same order as input)
            
        Examples:
            >>> quote = Quote(source="vci")
            >>> dfs = quote.fetch_multiple(["VNM", "VCB", "FPT"], start="2024-01-01", end="2024-12-31")
            >>> for symbol, df in zip(["VNM", "VCB", "FPT"], dfs):
            ...     print(f"{symbol}: {len(df)} rows")
        """
        if not symbols:
            return []
        
        # Check if provider has fetch_multiple method
        if not hasattr(self.provider, 'fetch_multiple'):
            raise NotImplementedError(
                f"Provider {self.source} does not support parallel multi-symbol fetching. "
                f"Use VCI or KBS for this feature."
            )
        
        # Call provider's fetch_multiple (handles both sync and async)
        return call_provider_sync(
            self.provider.fetch_multiple,
            symbols=symbols,
            start=start,
            end=end,
            interval=interval,
            show_log=show_log,
            count_back=count_back,
            floating=floating,
            length=length,
            max_concurrency=max_concurrency,
            adaptive_concurrency=adaptive_concurrency,
        )
