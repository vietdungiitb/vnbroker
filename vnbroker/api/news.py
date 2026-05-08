"""Unified News adapter for multi-source stock news."""

from typing import Any, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from vnbroker.base import BaseAdapter, dynamic_method
from vnbroker.config import Config
from vnbroker.core.source_router import AUTO_SOURCE


class News(BaseAdapter):
    _module_name = "news"

    def __init__(
        self,
        source: str = "auto",
        symbol: Optional[str] = None,
        random_agent: bool = False,
        show_log: bool = False,
        auth_token: Optional[str] = None,
    ):
        # Ensure provider modules are loaded.
        from vnbroker import _ensure_explorer_modules_loaded

        _ensure_explorer_modules_loaded()

        self.source = source
        self.symbol = symbol if symbol else ""
        self.random_agent = random_agent
        self.show_log = show_log
        self.auth_token = auth_token

        valid_sources = [
            "kbs",
            "vci",
            "tcbs",
            "rss_cafef",
            "rss_vneconomy",
            AUTO_SOURCE,
        ]
        if source.lower() not in valid_sources:
            raise ValueError(
                "Lop News chi nhan source: 'KBS', 'VCI', 'TCBS', 'RSS_CAFEF', 'RSS_VNECONOMY' hoac 'AUTO'."
            )

        super().__init__(
            source=source,
            symbol=symbol,
            random_agent=random_agent,
            show_log=show_log,
            auth_token=auth_token,
        )

    @retry(
        stop=stop_after_attempt(Config.RETRIES),
        wait=wait_exponential(
            multiplier=Config.BACKOFF_MULTIPLIER,
            min=Config.BACKOFF_MIN,
            max=Config.BACKOFF_MAX,
        ),
    )
    @dynamic_method
    def latest(self, *args: Any, **kwargs: Any) -> Any:
        """Get latest normalized news records."""
        pass

    @retry(
        stop=stop_after_attempt(Config.RETRIES),
        wait=wait_exponential(
            multiplier=Config.BACKOFF_MULTIPLIER,
            min=Config.BACKOFF_MIN,
            max=Config.BACKOFF_MAX,
        ),
    )
    @dynamic_method
    def search(self, *args: Any, **kwargs: Any) -> Any:
        """Search normalized news records by query text."""
        pass

    @retry(
        stop=stop_after_attempt(Config.RETRIES),
        wait=wait_exponential(
            multiplier=Config.BACKOFF_MULTIPLIER,
            min=Config.BACKOFF_MIN,
            max=Config.BACKOFF_MAX,
        ),
    )
    @dynamic_method
    def by_symbol(self, *args: Any, **kwargs: Any) -> Any:
        """Get normalized news records by stock symbol."""
        pass

    def _delegate_to_provider(self, method_name: str, symbol: Optional[str] = None, **kwargs: Any) -> Any:
        original_symbol = None
        try:
            if symbol:
                original_symbol = self.symbol
                self.symbol = symbol.upper()
                self._update_provider()

            method = getattr(self.provider, method_name)
            return method(symbol=self.symbol, **kwargs)
        finally:
            if original_symbol:
                self.symbol = original_symbol
                self._update_provider()
