"""
Data access layer providing unified interface to multiple data sources.

This module implements the facade pattern to access quote, company, finance,
trading, listing, and screener data from various sources (KBS, VCI, TCBS, DNSE).
"""

import logging
import importlib
import inspect
from typing import Optional, Any, Dict
from functools import lru_cache
import pandas as pd
import pytz
import requests
from tenacity import (
    Retrying,
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from pandas.api.types import is_numeric_dtype

from vnbroker.core.utils.logger import get_logger
from vnbroker.core.exceptions import UnsupportedMethodError

logger = get_logger(__name__)


PUBLIC_VN_SOURCES = {"KBS", "VCI", "TCBS", "DNSE", "SSI"}


_INSIDER_STANDARD_COLUMNS = [
    "symbol",
    "announce_date",
    "deal_date",
    "actor_name",
    "actor_type",
    "action",
    "quantity",
    "price",
    "ratio",
    "note",
    "source",
    "source_used",
]


def _pick_first_existing(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    for col in candidates:
        if col in df.columns:
            return df[col]
    return pd.Series([None] * len(df), index=df.index, dtype="object")


def _normalize_action_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    if text in {"BUY", "MUA", "0", "B"}:
        return "BUY"
    if text in {"SELL", "BAN", "BÁN", "B├üN", "1", "S"}:
        return "SELL"
    return text


def _normalize_company_insider_deals_df(df: pd.DataFrame, symbol: Optional[str] = None) -> pd.DataFrame:
    """Normalize insider deals output across providers while preserving original columns."""
    if df is None:
        base = pd.DataFrame()
    else:
        base = df.copy()

    if base.empty:
        normalized = pd.DataFrame(columns=_INSIDER_STANDARD_COLUMNS)
        return normalized

    normalized = base.copy()

    # Không dùng `.fillna(symbol)` khi symbol có thể None: pandas 2.x ném
    # ValueError ("Must specify a fill 'value' or 'method'") còn pandas 3.x bỏ
    # qua — cùng code, hai hành vi, chỉ máy có pandas mới chạy được.
    # (Phát hiện từ CI: test đỏ trên cả 3 OS ở Python 3.10.)
    symbol_col = _pick_first_existing(normalized, ["symbol", "ticker"])
    if symbol is not None:
        symbol_col = symbol_col.fillna(symbol)
    normalized["symbol"] = symbol_col

    normalized["announce_date"] = pd.to_datetime(
        _pick_first_existing(
            normalized,
            ["announce_date", "deal_announce_date", "an_date", "public_date", "date"],
        ),
        errors="coerce",
        dayfirst=True,
    ).dt.strftime("%Y-%m-%d")

    normalized["deal_date"] = pd.to_datetime(
        _pick_first_existing(
            normalized,
            ["deal_date", "trading_date", "transaction_date", "match_date"],
        ),
        errors="coerce",
        dayfirst=True,
    ).dt.strftime("%Y-%m-%d")

    normalized["actor_name"] = _pick_first_existing(
        normalized,
        [
            "actor_name",
            "insider_name",
            "owner_name",
            "full_name",
            "person_name",
            "share_holder",
        ],
    )

    normalized["actor_type"] = _pick_first_existing(
        normalized,
        ["actor_type", "deal_method", "dealing_method", "method", "holder_type"],
    )

    normalized["action"] = _pick_first_existing(
        normalized,
        ["action", "deal_action", "dealing_action", "transaction_type", "type"],
    ).map(_normalize_action_value)

    normalized["quantity"] = pd.to_numeric(
        _pick_first_existing(normalized, ["quantity", "deal_quantity", "volume", "deal_volume"]),
        errors="coerce",
    )

    normalized["price"] = pd.to_numeric(
        _pick_first_existing(normalized, ["price", "deal_price", "avg_price", "match_price"]),
        errors="coerce",
    )

    normalized["ratio"] = pd.to_numeric(
        _pick_first_existing(normalized, ["ratio", "deal_ratio", "ownership_ratio"]),
        errors="coerce",
    )

    normalized["note"] = _pick_first_existing(
        normalized,
        ["note", "description", "reason", "content"],
    )

    src = None
    if isinstance(getattr(df, "attrs", None), dict):
        src = df.attrs.get("source") or df.attrs.get("source_used")
    if src is None:
        src = getattr(df, "source", None)
    normalized["source"] = str(src).upper() if src is not None else None

    source_used = None
    if isinstance(getattr(df, "attrs", None), dict):
        source_used = df.attrs.get("source_used")
    normalized["source_used"] = str(source_used).upper() if source_used is not None else normalized["source"]

    # Ensure all standard columns exist and are first, while preserving legacy columns.
    for col in _INSIDER_STANDARD_COLUMNS:
        if col not in normalized.columns:
            normalized[col] = None
    ordered = _INSIDER_STANDARD_COLUMNS + [c for c in normalized.columns if c not in _INSIDER_STANDARD_COLUMNS]
    normalized = normalized[ordered]

    if isinstance(getattr(df, "attrs", None), dict):
        normalized.attrs.update(df.attrs)
    normalized.attrs["insider_schema_version"] = "1.0"
    return normalized


def _instantiate_supported(callable_obj, **kwargs):
    sig = inspect.signature(callable_obj)
    filtered_kwargs = {
        key: value for key, value in kwargs.items()
        if value is not None and key in sig.parameters
    }
    return callable_obj(**filtered_kwargs)

# Lazy import to avoid circular import
_get_asset_type = None

def _ensure_get_asset_type():
    """Lazy load get_asset_type to avoid circular import."""
    global _get_asset_type
    if _get_asset_type is None:
        from vnbroker.core.utils.parser import get_asset_type as _gat
        _get_asset_type = _gat
    return _get_asset_type

# Lazy import to avoid circular import deadlock

class Config:
    """Global configuration for data layer."""
    DEFAULT_SOURCE = "KBS"
    DEFAULT_TIMEOUT = 30  # seconds
    DEFAULT_RETRIES = 3
    CACHE_SIZE = 128
    LOG_LEVEL = logging.INFO

    @classmethod
    def setup(cls, **kwargs):
        """Update configuration settings."""
        for key, value in kwargs.items():
            if hasattr(cls, key):
                setattr(cls, key, value)
                logger.info(f"Config updated: {key}={value}")


class BaseComponent:
    """Base class for all data access components."""

    SUPPORTED_SOURCES = []
    FALLBACK_MAP: dict = {}

    def __init__(self, symbol: Optional[str] = None,
                 source: str = Config.DEFAULT_SOURCE):
        """
        Initialize base component.

        Args:
            symbol: Stock/asset symbol
            source: Data source (GATEWAY, AUTO)

        Raises:
            ValueError: If source not in SUPPORTED_SOURCES
        """
        self.symbol = symbol.upper() if symbol else None
        self.source = source.upper()
        self._fallback_cache: dict = {}
        self._validate_source()
        self.data_source = self._load_data_source()

    def _validate_source(self) -> None:
        """Validate that source is supported by this component.

        ``AUTO`` được chấp nhận ở mọi component: đó là tầng 1 ẩn danh, provider
        thật sự được chọn động bởi ``Quote._run_with_failover`` theo health store.
        Component chưa implement failover sẽ báo lỗi rõ ràng khi được gọi, thay
        vì từ chối ngay ở cửa — để người dùng vẫn dùng được các module đã hỗ trợ.
        """
        if self.source == "AUTO" and "AUTO" not in self.SUPPORTED_SOURCES:
            # Module chưa khai báo hỗ trợ AUTO: dùng provider đầu tiên của pool
            # ẩn danh làm mặc định ổn định. Module nào có failover động
            # (quote.history) sẽ tự chọn theo health store ở _run_with_failover.
            self.source = self._resolve_auto_source(self._auto_module_name())
        if self.source not in self.SUPPORTED_SOURCES and self.source != "AUTO":
            sources_str = ', '.join(self.SUPPORTED_SOURCES)
            raise ValueError(
                f"Supported sources: {sources_str}. Got: {self.source}"
            )

    def _auto_module_name(self) -> str:
        """Tên module trong source_router, suy ra từ tên class (vd Quote→quote)."""
        name = type(self).__name__.lower()
        # Tên class → tên module trong ProviderRegistry/source_router.
        alias = {
            "stockcomponents": "quote",
            "commonretail": "quote",
            "finance": "financial",
        }
        return alias.get(name, name)

    def _resolve_auto_source(self, module_name: str) -> str:
        """AUTO → provider cụ thể đầu tiên trong pool ẩn danh.

        Tầng 1: người dùng không cần biết provider nào đang phục vụ.
        """
        from vnbroker.core import source_router

        candidates = source_router.get_auto_candidates(module_name)
        if not candidates:
            raise ValueError(
                f"Không có provider ẩn danh khả dụng cho module {module_name!r}."
            )
        return candidates[0].upper()

    def _load_data_source(self):
        """Load and return the actual data source module instance."""
        raise NotImplementedError(
            "Subclasses must implement _load_data_source()"
        )

    def _load_fallback_provider(self, fb_source: str):
        """Load a fallback provider for the given source."""
        cache_key = f"{self.__class__.__name__}_{self.symbol}_{fb_source.upper()}"
        if cache_key in self._fallback_cache:
            return self._fallback_cache[cache_key]
        old_source = self.source
        self.source = fb_source.upper()
        provider = self._load_data_source()
        self.source = old_source
        self._fallback_cache[cache_key] = provider
        return provider

    def _call_with_fallback(self, method_name: str, *args, **kwargs):
        """Call method with auto-fallback across providers in FALLBACK_MAP."""
        provider = self.data_source
        sources = [self.source] + self.FALLBACK_MAP.get(self.source, [])
        last_error = None
        empty_result = None
        for source in sources:
            if source != self.source:
                try:
                    provider = self._load_fallback_provider(source)
                except Exception as e:
                    last_error = e
                    continue
            method = getattr(provider, method_name, None)
            if method is None:
                last_error = AttributeError(f"{source} has no method {method_name}")
                continue
            try:
                result = method(*args, **kwargs)
                if isinstance(result, pd.DataFrame) and result.empty:
                    # DNSE fallback providers return empty DF by design;
                    # keep trying fallbacks, remember empty to return if all empty.
                    if empty_result is None:
                        empty_result = result
                    continue
                return result
            except (NotImplementedError, AttributeError, UnsupportedMethodError) as e:
                last_error = e
                continue
            except Exception as e:
                if source != self.source:
                    last_error = e
                    continue
                raise
        if empty_result is not None:
            return empty_result
        if last_error:
            raise last_error
        raise NotImplementedError(
            f"No provider supports {method_name} for {getattr(self, 'symbol', 'N/A')}"
        )


class StockComponents(BaseComponent):
    """Unified access to stock data and related information.

    Direct Provider Architecture: VCI, KBS, TCBS, DNSE
    """

    # AUTO = tầng 1 ẩn danh: tự chọn provider ổn định, tự xoay vòng khi lỗi.
    SUPPORTED_SOURCES = ["VCI", "KBS", "TCBS", "DNSE", "SSI", "AUTO"]

    def __init__(self, symbol: str, source: str = "KBS",
                 show_log: bool = True,
                 auth_token: Optional[str] = None,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 gateway_client: Optional[Any] = None,
                 gateway_request_func: Optional[Any] = None):
        """
        Initialize stock components.

        Args:
            symbol: Stock symbol (e.g., 'ACB', 'VNM')
            source: Data source (VCI, KBS, TCBS, DNSE)
            show_log: Whether to display log messages
            auth_token: TCBS Bearer token (for direct TCBS access)
            api_key: API key for TCBS/DNSE (direct mode)
            api_secret: API secret for DNSE (direct mode)
            gateway_client: Deprecated, kept for backward compatibility
            gateway_request_func: Deprecated, kept for backward compatibility

        Raises:
            ValueError: If source is not supported
        """
        if source not in self.SUPPORTED_SOURCES:
            raise ValueError(f"Source '{source}' is not supported. Supported: {', '.join(self.SUPPORTED_SOURCES)}")

        self.auth_token = auth_token
        self.api_key = api_key
        self.api_secret = api_secret

        super().__init__(symbol, source)
        self.show_log = show_log

        get_asset_type_func = _ensure_get_asset_type()
        self.asset_type = get_asset_type_func(self.symbol)

        if not show_log:
            logger.setLevel(logging.CRITICAL)

        self._initialize_components()

    def _initialize_components(self):
        """Initialize quote, company, finance, trading components."""
        component_source = self.source

        self.company = Company(self.symbol, source=component_source, auth_token=self.auth_token,
                               api_key=self.api_key, api_secret=self.api_secret,
                               show_log=self.show_log)
        self.finance = Finance(self.symbol, source=component_source, auth_token=self.auth_token,
                               api_key=self.api_key, api_secret=self.api_secret,
                               show_log=self.show_log)
        self.news = News(self.symbol, source=component_source, auth_token=self.auth_token,
                         api_key=self.api_key, api_secret=self.api_secret,
                         show_log=self.show_log)
        self.trading = Trading(self.symbol, source=component_source, auth_token=self.auth_token,
                               api_key=self.api_key, api_secret=self.api_secret,
                               show_log=self.show_log)
        self.listing = Listing(source=component_source,
                               api_key=self.api_key, api_secret=self.api_secret,
                               show_log=self.show_log)
        self.screener = None
        self.quote = Quote(self.symbol, component_source, auth_token=self.auth_token,
                           api_key=self.api_key, api_secret=self.api_secret,
                           show_log=self.show_log)

    def _load_data_source(self):
        return self

    def update_symbol(self, symbol: str):
        self.symbol = symbol.upper()
        self._initialize_components()


class EmptyProviderResult(RuntimeError):
    """Provider trả về kết quả KHÔNG dùng được mà không ném lỗi.

    Cần loại riêng vì ``should_failover`` chỉ xét ``Exception``; quyết định
    "rỗng = không phục vụ được" thuộc về tầng data (``_run_with_failover``),
    không sửa ``core.source_router``.
    """


def _describe_empty(result: Any) -> str:
    """Mô tả ngắn kết quả rỗng để log/exception đọc được."""
    if isinstance(result, pd.DataFrame) or isinstance(result, pd.Series):
        return f"{type(result).__name__} khong co cot (schema={list(result.columns)!r})"
    return f"{type(result).__name__} rong: {result!r}"


def _is_unusable_provider_result(result: Any) -> bool:
    """Provider có trả về thứ gì **dùng được** không?

    Đây là chỗ hiện thực nguyên tắc đã ghi trong docstring của
    ``_run_with_failover``: "hết provider thì ném lỗi gốc, không bao giờ trả
    DataFrame rỗng". Provider im lặng trả rỗng là lỗi âm thầm nặng nhất vì
    người dùng tưởng "hôm nay không giao dịch" thay vì "provider chết".

    **"Không dùng được" khác "ngày giao dịch rỗng"** — ranh giới nằm ở *schema*,
    không phải ở số dòng:

    - ``pd.DataFrame()`` (0 cột) ⇒ provider không sinh ra cả cấu trúc. Hợp
      đồng tầng 1 quy định mọi provider trả cùng schema có cột ``time``
      (``_normalize_quote_result``), mà ``_normalize_quote_result` bỏ qua
      ngay ở ``if "time" not in result.columns`` ⇒ frame không cột lọt thẳng
      tới người dùng, vi phạm hợp đồng. ⇒ **không dùng được**.
    - ``pd.DataFrame(columns=["time", ...])`` với **0 dòng** ⇒ provider đã làm
      đúng việc, chỉ là trong khoảng yêu cầu không có phiên giao dịch (Tết,
      cuối tuần, mã chưa có dữ liệu). Chuẩn hoá vẫn chạy và trả frame tz-aware
      đúng hợp đồng. ⇒ **dùng được**, coi như thành công.

    Chọn mốc *schema* vì nó phân biệt được hai ca thật mà mốc "0 dòng" thì
    không: coi 0 dòng là thất bại sẽ biến mọi ngày nghỉ thành lỗi hệ thống —
    đủ provider cùng trả 0 dòng thì ``RuntimeError`` thay vì khung dữ liệu rỗng.

    Args:
        result: Giá trị provider trả về (DataFrame, dict, list, None, ...).

    Returns:
        ``True`` nếu kết quả không mang dữ liệu nào dùng được.
    """
    if result is None:
        return True
    if isinstance(result, (pd.DataFrame, pd.Series)):
        # Có cột = có schema = provider đã trả lời đúng hình thức, kể cả 0 dòng.
        return len(result.columns) == 0
    if isinstance(result, (list, tuple, set, frozenset, dict, str, bytes)):
        return len(result) == 0
    # Số, bool, object tùy ý...: không đủ căn cứ để kết luận là rỗng.
    return False


class Quote(BaseComponent):
    """Historical and real-time price data."""

    # AUTO = tầng 1 ẩn danh: hệ thống tự chọn provider ổn định và tự xoay vòng
    # khi gặp rate-limit / mất kết nối (xem _run_with_failover).
    SUPPORTED_SOURCES = ["VCI", "KBS", "TCBS", "DNSE", "SSI", "AUTO"]
    # One-way only: SSI needs a key/quota, so KBS/VCI never fall back into SSI (W2).
    FALLBACK_MAP = {"DNSE": ["KBS", "VCI"], "SSI": ["KBS", "VCI"]}

    def __init__(self, symbol: str, source: str = "KBS",
                 auth_token: Optional[str] = None,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 gateway_client: Optional[Any] = None,
                 gateway_request_func: Optional[Any] = None,
                 show_log: bool = True):
        self.auth_token = auth_token
        self.api_key = api_key
        self.api_secret = api_secret
        self.show_log = show_log
        self.symbol = symbol.upper() if symbol else None

        # Set up auto sources for failover when source is AUTO.
        # Must happen before super().__init__() because _load_data_source()
        # resolves AUTO to a specific provider.
        if source.upper() == "AUTO":
            from vnbroker.core import source_router
            candidates = source_router.get_auto_candidates("quote")
            self._auto_sources = {}
            for src in candidates:
                try:
                    self._auto_sources[src] = self._load_direct_provider_for_source(src)
                except Exception:
                    pass

        super().__init__(symbol, source)

    def _require_symbol(self) -> str:
        """Narrow ``self.symbol`` cho các provider bắt buộc có symbol.

        Provider ``explorer/*`` đều cần ``symbol: str``; trước đây ``None``
        chạy thẳng xuống constructor và chết sâu bên trong với lỗi khó hiểu.
        """
        if not self.symbol:
            raise ValueError(
                f"{type(self).__name__} cần symbol để dựng provider, "
                "nhưng symbol đang là None. Truyền symbol khi khởi tạo hoặc gọi update_symbol()."
            )
        return self.symbol

    def _load_data_source(self):
        """Load quote data source module."""
        return self._load_direct_provider()

    def _load_direct_provider(self) -> Any:
        """Load direct provider adapter based on source.

        Với ``source == "AUTO"`` (tầng 1 ẩn danh) chỉ khởi tạo provider đầu
        tiên trong pool; provider thực sự phục vụ được chọn động bởi
        ``_run_with_failover`` dựa trên health store.
        """
        from vnbroker.core import source_router

        symbol = self._require_symbol()
        source = self.source.lower()
        if source == "auto":
            candidates = source_router.get_auto_candidates("quote")
            if not candidates:
                raise ValueError(
                    "Không có provider ẩn danh khả dụng cho module 'quote'."
                )
            source = candidates[0]
            self.source = source.upper()
        if source == "vci":
            from vnbroker.explorer.vci.quote import Quote as VCIQuote
            return VCIQuote(symbol, show_log=self.show_log)
        elif source == "kbs":
            from vnbroker.explorer.kbs.quote import Quote as KBSQuote
            return KBSQuote(symbol, show_log=self.show_log)
        elif source == "tcbs":
            from vnbroker.explorer.tcbs.quote import Quote as TCBSQuote
            return TCBSQuote(symbol, auth_token=self.auth_token, show_log=self.show_log)
        elif source == "dnse":
            from vnbroker.explorer.dnse.quote import DNSEQuote
            return DNSEQuote(symbol, api_key=self.api_key, api_secret=self.api_secret, show_log=self.show_log)
        elif source == "ssi":
            from vnbroker.explorer.ssi.quote import SSIQuote
            return SSIQuote(symbol, api_key=self.api_key, api_secret=self.api_secret, show_log=self.show_log)
        else:
            raise ValueError(f"Direct provider not implemented for source: {self.source}")

    def _load_direct_provider_for_source(self, source: str) -> Any:
        """Create a provider instance for a given source name.

        Used by AUTO mode to pre-instantiate all candidate providers
        for failover. Mirrors _load_direct_provider but takes an explicit
        source string instead of using self.source.
        """
        symbol = self._require_symbol()
        source = source.lower()
        if source == "vci":
            from vnbroker.explorer.vci.quote import Quote as VCIQuote
            return VCIQuote(symbol, show_log=self.show_log)
        elif source == "kbs":
            from vnbroker.explorer.kbs.quote import Quote as KBSQuote
            return KBSQuote(symbol, show_log=self.show_log)
        elif source == "tcbs":
            from vnbroker.explorer.tcbs.quote import Quote as TCBSQuote
            return TCBSQuote(symbol, auth_token=self.auth_token, show_log=self.show_log)
        elif source == "dnse":
            from vnbroker.explorer.dnse.quote import DNSEQuote
            return DNSEQuote(symbol, api_key=self.api_key, api_secret=self.api_secret, show_log=self.show_log)
        elif source == "ssi":
            from vnbroker.explorer.ssi.quote import SSIQuote
            return SSIQuote(symbol, api_key=self.api_key, api_secret=self.api_secret, show_log=self.show_log)
        else:
            raise ValueError(f"Direct provider not implemented for source: {source}")

    def _update_data_source(self, symbol: Optional[str] = None):
        """Update symbol and reload data source if needed."""
        if symbol:
            self.symbol = symbol.upper()
            self.data_source = self._load_data_source()

    def _run_with_failover(
        self,
        method_name: str,
        module_name: str,
        kwargs: Dict[str, Any],
    ) -> Any:
        """Gọi ``method_name`` trên provider, tự xoay vòng khi provider lỗi.

        Tầng 1 — dữ liệu thị trường ẩn danh. Người dùng gọi một lần, không cần
        biết provider nào phục vụ; hệ thống ưu tiên provider ổn định và xoay vòng
        khi gặp rate-limit / mất kết nối.

        Dùng cơ chế thật của ``core.source_router``:
        ``build_source_order`` (loại provider đang cooldown + hash-shard theo
        symbol) và ``should_failover`` (quyết định lỗi nào đáng xoay vòng).

        Nguyên tắc: **hết provider thì ném lỗi gốc, không bao giờ trả DataFrame
        rỗng.** Frame rỗng khiến người dùng tưởng 'hôm nay không giao dịch' thay
        vì 'đã lỗi mạng' — đó là lỗi âm thầm nguy hiểm nhất.

        Args:
            method_name: Tên method trên provider (vd ``history``).
            module_name: Module dùng cho health store (vd ``quote``).
            kwargs: Tham số truyền xuống provider (đã lọc theo signature).

        Returns:
            Kết quả từ provider đầu tiên thành công.

        Raises:
            Exception: Lỗi gốc của provider cuối cùng khi mọi provider đều lỗi.
        """
        from vnbroker.core import source_router

        sources = getattr(self, "_auto_sources", None)
        if not sources:
            # Đường không-auto: một provider cố định, retry cả lời gọi provider
            # theo hành vi lịch sử (DEFAULT_RETRIES lần).
            self._update_data_source()
            method = getattr(self.data_source, method_name)
            filtered = _filter_kwargs(method, kwargs)
            return Retrying(
                stop=stop_after_attempt(Config.DEFAULT_RETRIES),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type((
                    requests.exceptions.RequestException,
                    ConnectionError,
                    TimeoutError,
                )),
                reraise=True,
            )(method, **filtered)

        # Retry áp cho TỪNG provider: một provider gặp lỗi mạng tạm thời thì thử
        # lại chính nó vài lần trước khi chuyển sang provider kế tiếp. Retry cả vòng
        # failover sẽ khiến mỗi provider bị thử N lần khi hết pool.
        def _call_once() -> Any:
            method = getattr(self.data_source, method_name)
            return method(**_filter_kwargs(method, kwargs))

        per_provider_retry = Retrying(
            stop=stop_after_attempt(Config.DEFAULT_RETRIES),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((
                requests.exceptions.RequestException,
                ConnectionError,
                TimeoutError,
            )),
            reraise=True,
        )

        # Cho phép ghim thứ tự (dùng cho test) — xem _make_quote trong
        # tests/contract/test_failover_tier1.py.
        pinned_order = getattr(self, "_fixed_source_order", None)
        if callable(pinned_order):
            ordered_sources = pinned_order(module_name, self.symbol)
        else:
            ordered_sources = source_router.build_source_order(module_name, self.symbol)

        last_exc: Exception | None = None
        for source in ordered_sources:
            if source not in sources:
                continue
            self.source = source.upper()
            self.data_source = sources[source]
            try:
                result = per_provider_retry(_call_once)
            except Exception as exc:  # noqa: BLE001 - quyết định nhờ should_failover
                if not source_router.should_failover(exc):
                    # Lỗi lập trình, không phải lỗi mạng: ném ra, đừng che.
                    raise
                source_router.record_failure(module_name, source)
                last_exc = exc
                continue
            if _is_unusable_provider_result(result):
                # Provider KHÔNG ném lỗi nhưng cũng không phục vụ được: coi như
                # thất bại, tuyệt đối không record_success (xem helper để biết vì
                # sao "rỗng" được hiểu là mất schema chứ không phải ngày nghỉ).
                exc = EmptyProviderResult(
                    f"Provider {source!r} trả kết quả không dùng được "
                    f"({method_name}, module={module_name!r}): {_describe_empty(result)}."
                )
                source_router.record_failure(module_name, source)
                last_exc = exc
                continue
            source_router.record_success(module_name, source)
            return source_router.annotate_result_source(result, source)

        raise last_exc if last_exc else RuntimeError(
            f"Không có provider khả dụng cho module={module_name!r}."
        )

    def history(self, symbol: Optional[str] = None, **kwargs):
        """Fetch historical price data.

        Retry policy:
        - **Đường không-auto** (một provider cố định): decorator ``@retry`` bọc
          cả lời gọi provider, giữ hành vi lịch sử (``DEFAULT_RETRIES`` lần).
        - **Đường auto** (``_auto_sources``): decorator bị bỏ qua, retry áp cho
          TỪNG provider trong ``_run_with_failover`` — nếu không, hết pool sẽ bị
          thử lại N lần.
        """
        if symbol:
            self.symbol = symbol.upper()
        result = self._run_with_failover("history", "quote", kwargs)
        # Hợp đồng tầng 1: chuẩn hoá tz + lọc biên ở MỘT chỗ duy nhất để mọi
        # provider ẩn danh trả về cùng schema. Xem _normalize_quote_result.
        if kwargs.get("to_df", True):
            from vnbroker.core.utils.normalizer import Normalizer
            return Normalizer.normalize_history(result, kwargs.get("start"), kwargs.get("end"))
        return result

    @retry(
        stop=stop_after_attempt(Config.DEFAULT_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, ConnectionError, TimeoutError)),
        reraise=True,
    )
    def intraday(self, symbol: Optional[str] = None, **kwargs):
        """Fetch intraday trading data.

        Cùng cơ chế failover như `history` (xem `_run_with_failover`), vì intraday
        cũng là dữ liệu thị trường ẩn danh: user không cần biết provider, và hệ
        thống phải xoay vòng khi provider lỗi — nếu không thì chỉ cần provider
        "chính" hết hạn là toàn bộ người dùng mất dữ liệu trong phiên.

        Khác `history`: intraday không lọc theo `start`/`end` (đó là khoảng ngày
        giao dịch, provider tự xử lý), nhưng `time` vẫn phải tz-aware và tăng dần
        để `concat` với `history` không hỏng.
        """
        if symbol:
            self.symbol = symbol.upper()
        result = self._run_with_failover("intraday", "quote", kwargs)
        if kwargs.get("to_df", True) and isinstance(result, pd.DataFrame):
            # Không truyền start/end: intraday trả dữ liệu trong phiên, lọc theo
            # ngày là việc của provider.
            return _normalize_quote_result(result)
        return result

    @retry(
        stop=stop_after_attempt(Config.DEFAULT_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, ConnectionError, TimeoutError)),
        reraise=True,
    )
    def price_depth(self, symbol: Optional[str] = None, **kwargs):
        """Fetch order book depth data.

        Có failover như `history`/`intraday` — cùng lý do: dữ liệu ẩn danh, user
        không biết provider, provider chính hết hạn thì phải tự chuyển.

        KHÔNG chuẩn hoá tz: `price_depth` là bảng giá hai chiều, không có cột
        `time` theo dòng nên `_normalize_quote_result` không áp dụng (hàm đó tự
        bỏ qua frame không có cột `time`).
        """
        if symbol:
            self.symbol = symbol.upper()
        return self._run_with_failover("price_depth", "quote", kwargs)


def _canonical_tz() -> Any:
    """Timezone chuẩn của thị trường Việt Nam (giờ giao dịch)."""
    return pytz.timezone("Asia/Ho_Chi_Minh")


def _to_canonical_tz(series: "pd.Series") -> "pd.Series":
    """Chuẩn hoá cột ``time`` thành tz-aware Asia/Ho_Chi_Minh.

    Vì sao cần (GĐ2 của kế hoạch hai tầng):

    - ``ohlc_to_df`` chỉ ``tz_convert`` cho nhánh ``source == 'VCI'``; nhánh
      ``else`` để nguyên ``pd.to_datetime(...)`` nên ra tz-naive
      (vnbroker/core/utils/transform.py:331-338).
    - Hệ quả: provider tz-naive + provider tz-aware khiến ``pd.concat`` sinh
      dtype ``object`` — phá mọi phép tính thời gian phía downstream, và
      **không** ném exception.

    Naive được hiểu là giờ Việt Nam chứ không phải UTC: provider trả
    ``'2024-01-02 09:00'`` nghĩa là 09:00 VN. Nếu localize UTC rồi convert sang
    VN thì nó thành 16:00 — sai 7 tiếng, và sai này rất khó phát hiện vì vẫn là
    timestamp hợp lệ.
    """
    if getattr(series.dt, "tz", None) is None:
        return series.dt.tz_localize(_canonical_tz())
    return series


def _parse_boundary(value: Any, *, inclusive_end: bool) -> "pd.Timestamp | None":
    """Parse ngày biên của lời gọi. Trả None nếu thiếu/không parse được."""
    if value is None or value == "":
        return None
    try:
        ts = pd.to_datetime(value)
    except (ValueError, TypeError):
        return None
    if pd.isna(ts):
        return None
    if getattr(ts, "tzinfo", None) is None:
        ts = ts.tz_localize(_canonical_tz())
    if inclusive_end and ts.hour == 0 and ts.minute == 0 and ts.second == 0:
        # Người dùng truyền '2024-01-31' nghĩa là hết ngày đó, không phải 00:00.
        ts = ts + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return ts


def _normalize_quote_result(
    result: Any,
    start: Any = None,
    end: Any = None,
) -> Any:
    """Chuẩn hoá DataFrame giá theo hợp đồng tầng 1 (dữ liệu ẩn danh).

    Hợp đồng mà mọi provider ẩn danh phải tuân thủ, khoá ở MỘT chỗ duy nhất:

    1. ``time`` luôn tz-aware ``Asia/Ho_Chi_Minh``.
    2. Không có dòng nào ngoài khoảng ``[start, end]`` (bỏ qua nếu không truyền).
    3. ``time`` tăng dần.
    4. Không thêm/bớt cột, không mutate DataFrame của provider.

    Vì sao ở đây mà không sửa từng provider: đây là điểm kiểm soát duy nhất
    người dùng đi qua (``Vnbroker``); provider mới thêm vào sau này tự động
    tuân thủ. Gọi provider trực tiếp (``VCIQuote(...).history()``) giữ hành vi cũ.

    Args:
        result: DataFrame trả về từ provider (có thể không phải DataFrame).
        start: Ngày bắt đầu caller yêu cầu.
        end: Ngày kết thúc caller yêu cầu.

    Returns:
        DataFrame đã chuẩn hoá, hoặc nguyên ``result`` nếu không phải DataFrame.
    """
    if not isinstance(result, pd.DataFrame) or "time" not in result.columns:
        return result

    df = result.copy()

    df["time"] = _to_canonical_tz(pd.to_datetime(df["time"], errors="coerce"))
    # Timestamp không parse được thì loại bỏ thay vì để NaT làm hỏng phép so sánh.
    df = df[df["time"].notna()]

    lo = _parse_boundary(start, inclusive_end=False)
    if lo is not None:
        df = df[df["time"] >= lo]

    hi = _parse_boundary(end, inclusive_end=True)
    if hi is not None:
        df = df[df["time"] <= hi]

    return df.sort_values("time").reset_index(drop=True)


def _filter_kwargs(method: Any, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Lọc kwargs theo signature của provider method (pattern vnbroker v3.5 — nội bộ).

    - Provider có VAR_KEYWORD (**kwargs) → passthrough toàn bộ.
    - Không → chỉ giữ param có trong signature; kwargs lạ bị bỏ + logger.debug.
    - Luôn giữ `show_log` khi caller truyền (không filter mất).
    - Không inject thêm gì (giữ nguyên behavior khi caller không truyền).
    """
    try:
        params = inspect.signature(method).parameters
    except (TypeError, ValueError):
        return dict(kwargs)
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return dict(kwargs)
    allowed = set(params)
    filtered: Dict[str, Any] = {}
    for key, value in kwargs.items():
        if key in allowed:
            filtered[key] = value
        else:
            logger.debug(
                "Quote: bỏ kwarg không hỗ trợ %r cho %s.",
                key,
                getattr(method, "__name__", method),
            )
    return filtered


class Listing(BaseComponent):
    """Symbol listing and grouping data."""

    SUPPORTED_SOURCES = ["VCI", "KBS", "TCBS", "DNSE", "SSI"]
    # One-way only: SSI needs a key/quota, so KBS/VCI never fall back into SSI (W2).
    FALLBACK_MAP = {"DNSE": ["KBS", "VCI"], "SSI": ["KBS", "VCI"]}

    def __init__(self, source: str = "KBS",
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 gateway_client: Optional[Any] = None,
                 gateway_request_func: Optional[Any] = None,
                 show_log: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.show_log = show_log
        super().__init__(symbol=None, source=source)

    def _load_data_source(self):
        """Load listing data source module."""
        return self._load_direct_provider()

    def _load_direct_provider(self):
        """Load direct provider adapter based on source."""
        source = self.source.lower()
        if source == "vci":
            from vnbroker.explorer.vci.listing import Listing as VCIListing
            return VCIListing(show_log=self.show_log)
        elif source == "kbs":
            from vnbroker.explorer.kbs.listing import Listing as KBSListing
            return KBSListing(show_log=self.show_log)
        elif source == "tcbs":
            from vnbroker.explorer.tcbs.listing import Listing as TCBSListing
            return TCBSListing(show_log=self.show_log)
        elif source == "dnse":
            from vnbroker.explorer.dnse.listing import DNSEListing
            return DNSEListing(api_key=self.api_key, api_secret=self.api_secret, show_log=self.show_log)
        elif source == "ssi":
            from vnbroker.explorer.ssi.listing import SSIListing
            return SSIListing(api_key=self.api_key, api_secret=self.api_secret, show_log=self.show_log)
        else:
            raise ValueError(f"Direct provider not implemented for source: {self.source}")

    @lru_cache(maxsize=Config.CACHE_SIZE)
    def all_symbols(self, **kwargs):
        """Get all available symbols."""
        return self.data_source.all_symbols(**kwargs)

    @lru_cache(maxsize=Config.CACHE_SIZE)
    def symbols_by_industries(self, **kwargs):
        """Get symbols grouped by industry."""
        return self.data_source.symbols_by_industries(**kwargs)

    @lru_cache(maxsize=Config.CACHE_SIZE)
    def symbols_by_exchange(self, **kwargs):
        """Get symbols for specific exchange."""
        return self.data_source.symbols_by_exchange(**kwargs)

    @lru_cache(maxsize=Config.CACHE_SIZE)
    def symbols_by_group(self, group='VN30', **kwargs):
        """Get symbols for market group (VN30, HNX, etc.)."""
        return self.data_source.symbols_by_group(group, **kwargs)

    @lru_cache(maxsize=Config.CACHE_SIZE)
    def industries_icb(self, **kwargs):
        """Get ICB industry classification."""
        return self.data_source.industries_icb(**kwargs)

    @lru_cache(maxsize=Config.CACHE_SIZE)
    def all_future_indices(self, **kwargs):
        """Get all available futures indices."""
        return self.data_source.all_future_indices(**kwargs)

    @lru_cache(maxsize=Config.CACHE_SIZE)
    def all_covered_warrant(self, **kwargs):
        """Get all covered warrants."""
        return self.data_source.all_covered_warrant(**kwargs)

    @lru_cache(maxsize=Config.CACHE_SIZE)
    def all_bonds(self, **kwargs):
        """Get all bonds."""
        return self.data_source.all_bonds(**kwargs)

    @lru_cache(maxsize=Config.CACHE_SIZE)
    def all_government_bonds(self, **kwargs):
        """Get all government bonds."""
        return self.data_source.all_government_bonds(**kwargs)


class Trading(BaseComponent):
    """Real-time trading data and market board information."""

    SUPPORTED_SOURCES = ["VCI", "KBS", "TCBS", "DNSE", "SSI"]
    # One-way only (W2): line 581 duplicated this map and dropped SSI — removed.
    FALLBACK_MAP = {"DNSE": ["KBS", "VCI"], "SSI": ["KBS", "VCI"]}

    def __init__(self, symbol: Optional[str] = 'VN30F1M',
                 source: str = "KBS",
                 auth_token: Optional[str] = None,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 gateway_client: Optional[Any] = None,
                 gateway_request_func: Optional[Any] = None,
                 show_log: bool = True):
        self.auth_token = auth_token
        self.api_key = api_key
        self.api_secret = api_secret
        self.show_log = show_log
        super().__init__(symbol, source)

    def _load_data_source(self):
        """Load trading data source module."""
        return self._load_direct_provider()

    def _load_direct_provider(self):
        """Load direct provider adapter based on source."""
        source = self.source.lower()
        if source == "vci":
            from vnbroker.explorer.vci.trading import Trading as VCITrading
            return VCITrading(self.symbol, show_log=self.show_log)
        elif source == "kbs":
            from vnbroker.explorer.kbs.trading import Trading as KBSTrading
            return KBSTrading(self.symbol, show_log=self.show_log)
        elif source == "tcbs":
            from vnbroker.explorer.tcbs.trading import Trading as TCBSTrading
            return TCBSTrading(self.symbol, auth_token=self.auth_token, show_log=self.show_log)
        elif source == "dnse":
            from vnbroker.explorer.dnse.trading import DNSETrading
            return DNSETrading(self.symbol, api_key=self.api_key, api_secret=self.api_secret, show_log=self.show_log)
        elif source == "ssi":
            from vnbroker.explorer.ssi.trading import SSITrading
            return SSITrading(self.symbol, api_key=self.api_key, api_secret=self.api_secret, show_log=self.show_log)
        else:
            raise ValueError(f"Direct provider not implemented for source: {self.source}")

    def _update_data_source(self, symbol: Optional[str] = None):
        """Update symbol and reload data source if needed."""
        if symbol:
            self.symbol = symbol.upper()
        self.data_source = self._load_data_source()

    @retry(
        stop=stop_after_attempt(Config.DEFAULT_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, ConnectionError, TimeoutError)),
        reraise=True,
    )
    def price_board(self, symbols_list: list, **kwargs):
        """Fetch price board for multiple symbols."""
        return self._call_with_fallback('price_board', symbols_list, **kwargs)


class Company(BaseComponent):
    """Company profile, management, ownership information."""

    SUPPORTED_SOURCES = ["VCI", "KBS", "TCBS", "DNSE", "SSI"]
    FALLBACK_MAP = {"DNSE": ["KBS", "VCI"], "SSI": ["KBS", "VCI"]}

    def __init__(self, symbol: Optional[str] = 'ACB',
                 source: str = "KBS",
                 auth_token: Optional[str] = None,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 gateway_client: Optional[Any] = None,
                 gateway_request_func: Optional[Any] = None,
                 show_log: bool = True):
        self.auth_token = auth_token
        self.api_key = api_key
        self.api_secret = api_secret
        self.show_log = show_log
        super().__init__(symbol, source)

    def _load_data_source(self):
        """Load company data source module."""
        return self._load_direct_provider()

    def _load_direct_provider(self):
        """Load direct provider adapter based on source."""
        source = self.source.lower()
        if source == "vci":
            from vnbroker.explorer.vci.company import Company as VCICompany
            return VCICompany(self.symbol, show_log=self.show_log)
        elif source == "kbs":
            from vnbroker.explorer.kbs.company import Company as KBSCompany
            return KBSCompany(self.symbol, show_log=self.show_log)
        elif source == "tcbs":
            from vnbroker.explorer.tcbs.company import Company as TCBSCompany
            return TCBSCompany(self.symbol, auth_token=self.auth_token, show_log=self.show_log)
        elif source == "dnse":
            from vnbroker.explorer.dnse.company import DNSECompany
            return DNSECompany(self.symbol, api_key=self.api_key, api_secret=self.api_secret, show_log=self.show_log)
        elif source == "ssi":
            from vnbroker.explorer.ssi.company import SSICompany
            return SSICompany(self.symbol, api_key=self.api_key, api_secret=self.api_secret, show_log=self.show_log)
        else:
            raise ValueError(f"Direct provider not implemented for source: {self.source}")

    def _update_data_source(self, symbol: Optional[str] = None):
        """Update symbol and reload data source if needed."""
        if symbol:
            self.symbol = symbol.upper()
            self.data_source = self._load_data_source()

    # NOTE: intentionally no @lru_cache here — methods depend on self.symbol;
    # caching `self` would leak instances and return stale data after
    # update_symbol(). Use TTLCache with explicit (symbol, source, params) key
    # if caching is needed (see core/utils/cache.py).
    def overview(self, **kwargs):
        return self._call_with_fallback('overview', **kwargs)

    def profile(self, **kwargs):
        return self._call_with_fallback('profile', **kwargs)

    def shareholders(self, **kwargs):
        return self._call_with_fallback('shareholders', **kwargs)

    def insider_deals(self, **kwargs):
        standardize = kwargs.pop("standardize", True)
        result = self._call_with_fallback('insider_deals', **kwargs)
        if not standardize:
            return result
        if isinstance(result, pd.DataFrame):
            return _normalize_company_insider_deals_df(result, symbol=self.symbol)
        return result

    def subsidiaries(self, **kwargs):
        return self._call_with_fallback('subsidiaries', **kwargs)

    def officers(self, **kwargs):
        return self._call_with_fallback('officers', **kwargs)

    def events(self, **kwargs):
        return self._call_with_fallback('events', **kwargs)

    def news(self, **kwargs):
        return self._call_with_fallback('news', **kwargs)

    def dividends(self, **kwargs):
        return self._call_with_fallback('dividends', **kwargs)

    def affiliate(self, **kwargs):
        return self._call_with_fallback('affiliate', **kwargs)

    def trading_stats(self, **kwargs):
        return self._call_with_fallback('trading_stats', **kwargs)

    def ratio_summary(self, **kwargs):
        return self._call_with_fallback('ratio_summary', **kwargs)





class News(BaseComponent):
    """Multi-source normalized stock news access."""

    SUPPORTED_SOURCES = ["VCI", "KBS", "TCBS", "DNSE", "SSI"]

    def __init__(self, symbol: Optional[str] = None,
                 source: str = "KBS",
                 auth_token: Optional[str] = None,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 gateway_client: Optional[Any] = None,
                 gateway_request_func: Optional[Any] = None,
                 show_log: bool = True):
        self.auth_token = auth_token
        self.api_key = api_key
        self.api_secret = api_secret
        self.show_log = show_log
        super().__init__(symbol, source)

    def _load_data_source(self):
        """Load news data source module."""
        return self._load_direct_provider()

    def _load_direct_provider(self):
        """Load direct provider adapter based on source."""
        source = self.source.lower()
        if source == "vci":
            from vnbroker.explorer.vci.news import News as VCINews
            return VCINews(self.symbol, show_log=self.show_log)
        elif source == "kbs":
            from vnbroker.explorer.kbs.news import News as KBSNews
            return KBSNews(self.symbol, show_log=self.show_log)
        elif source == "tcbs":
            from vnbroker.explorer.tcbs.news import News as TCBSNews
            return TCBSNews(self.symbol, auth_token=self.auth_token, show_log=self.show_log)
        elif source == "dnse":
            # DNSE doesn't have news — explicit fallback to VCI.
            # Annotated via source_used so callers know real origin.
            from vnbroker.explorer.vci.news import News as VCINews
            provider = VCINews(self.symbol, show_log=self.show_log)
            provider._vnbroker_fallback_note = ("DNSE", "VCI")
            return provider
        elif source == "ssi":
            # SSI doesn't have news — explicit fallback to VCI (same as DNSE).
            from vnbroker.explorer.vci.news import News as VCINews
            provider = VCINews(self.symbol, show_log=self.show_log)
            provider._vnbroker_fallback_note = ("SSI", "VCI")
            return provider
        else:
            raise ValueError(f"Direct provider not implemented for source: {self.source}")

    def health(self) -> Dict[str, Dict[str, Any]]:
        """Return current source health snapshot used by AUTO news routing."""
        from vnbroker.core.source_router import get_source_health_snapshot

        return get_source_health_snapshot("news")

    def health_dataframe(self):
        """Return health snapshot as a pandas DataFrame."""
        from vnbroker.news.health import health_snapshot_to_dataframe

        return health_snapshot_to_dataframe(self.health(), module_name="news")

    def log_health(self, file_path: str, fmt: str = "jsonl") -> str:
        """Append the current health snapshot to JSONL or CSV file."""
        from vnbroker.news.health import append_health_log

        return append_health_log(self.health(), file_path=file_path, fmt=fmt, module_name="news")

    def sanitize_health_log(self, file_path: str):
        """Sanitize an existing JSONL health log (NaN -> null)."""
        from vnbroker.news.health import sanitize_health_jsonl_file

        return sanitize_health_jsonl_file(file_path)

    def alerts(self, max_failures: int = 2, max_cooldown_sec: float = 30.0):
        """Evaluate health snapshot and return alert records by threshold."""
        from vnbroker.news.monitor import evaluate_health_alerts

        return evaluate_health_alerts(
            self.health(),
            max_failures=max_failures,
            max_cooldown_sec=max_cooldown_sec,
        )

    def monitor_health(
        self,
        file_path: Optional[str] = None,
        fmt: str = "jsonl",
        max_failures: int = 2,
        max_cooldown_sec: float = 30.0,
    ) -> Dict[str, Any]:
        """Collect snapshot, optionally persist it, and evaluate alerts."""
        snapshot = self.health()

        logged_path = None
        if file_path:
            from vnbroker.news.health import append_health_log

            logged_path = append_health_log(snapshot, file_path=file_path, fmt=fmt, module_name="news")

        from vnbroker.news.monitor import evaluate_health_alerts

        alerts = evaluate_health_alerts(
            snapshot,
            max_failures=max_failures,
            max_cooldown_sec=max_cooldown_sec,
        )
        return {
            "snapshot": snapshot,
            "alerts": alerts,
            "logged_path": logged_path,
        }

    def _update_data_source(self, symbol: Optional[str] = None):
        """Update symbol and reload data source if needed."""
        if symbol and symbol != self.symbol:
            self.symbol = symbol.upper()
            self.data_source = self._load_data_source()

    # NOTE: no @lru_cache — symbol-dependent, would leak `self` (see Company).
    def _annotate_news_fallback(self, result):
        """Ghi source_used=VCI khi source=DNSE/SSI fallback (minh bạch nguồn thật)."""
        if self.source in ("DNSE", "SSI"):
            try:
                if isinstance(getattr(result, "attrs", None), dict):
                    result.attrs["source"] = result.attrs.get("source", "VCI")
                    result.attrs["source_used"] = "VCI"
                    result.attrs["source_requested"] = self.source
            except Exception:
                pass
        return result

    def latest(self, symbol: Optional[str] = None, **kwargs):
        """Get latest normalized news."""
        self._update_data_source(symbol)
        return self._annotate_news_fallback(self.data_source.latest(**kwargs))

    def search(self, query: str, symbol: Optional[str] = None, **kwargs):
        """Search normalized news."""
        self._update_data_source(symbol)
        return self._annotate_news_fallback(
            self.data_source.search(query=query, **kwargs)
        )

    def by_symbol(self, symbol: str, **kwargs):
        """Get normalized news by symbol."""
        self._update_data_source(symbol)
        return self._annotate_news_fallback(
            self.data_source.by_symbol(symbol=symbol, **kwargs)
        )

    def filter(
        self,
        symbol: Optional[str] = None,
        query: Optional[str] = None,
        sources: Optional[list] = None,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        regex: bool = False,
        case: bool = False,
        fields: tuple = ("title", "summary"),
        limit: int = 100,
        base_limit: int = 300,
        **kwargs,
    ):
        """Get and filter news by symbol/text/source/time criteria."""
        from vnbroker.news.filtering import filter_news_dataframe

        target_symbol = symbol or self.symbol
        if target_symbol:
            base = self.by_symbol(symbol=target_symbol, limit=base_limit, **kwargs)
        else:
            base = self.latest(limit=base_limit, **kwargs)

        return filter_news_dataframe(
            base,
            symbol=target_symbol,
            query=query,
            sources=sources,
            from_time=from_time,
            to_time=to_time,
            regex=regex,
            case=case,
            fields=fields,
            limit=limit,
        )

    def query(self, query: str, symbol: Optional[str] = None, limit: int = 100, **kwargs):
        """Convenience method for text search over normalized title/summary fields."""
        return self.filter(symbol=symbol, query=query, limit=limit, **kwargs)


class Finance(BaseComponent):
    """Financial statements and ratios."""

    SUPPORTED_SOURCES = ["VCI", "KBS", "TCBS", "DNSE", "SSI"]
    FALLBACK_MAP = {"DNSE": ["KBS", "VCI"], "SSI": ["KBS", "VCI"]}
    SUPPORTED_PERIODS = ["quarter", "year", "annual"]

    def __init__(
        self,
        symbol: str,
        period: str = 'quarter',
        source: str = 'KBS',
        get_all: bool = True,
        auth_token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        gateway_client: Optional[Any] = None,
        gateway_request_func: Optional[Any] = None,
        show_log: bool = True
    ):
        self.auth_token = auth_token
        self.api_key = api_key
        self.api_secret = api_secret
        self.show_log = show_log

        normalized_period = (period or 'quarter').lower()
        if normalized_period == 'annual':
            normalized_period = 'year'

        self.period = normalized_period
        if self.period not in self.SUPPORTED_PERIODS:
            periods_str = ', '.join(self.SUPPORTED_PERIODS)
            raise ValueError(
                f"Period must be one of {periods_str}. Got: {period}"
            )

        self.get_all = get_all
        super().__init__(symbol, source)

    def _load_data_source(self):
        """Load finance data source module."""
        return self._load_direct_provider()

    def _load_direct_provider(self):
        """Load direct provider adapter based on source."""
        source = self.source.lower()
        if source == "vci":
            from vnbroker.explorer.vci.financial import Finance as VCIFinancial
            return VCIFinancial(self.symbol, period=self.period, get_all=self.get_all, show_log=self.show_log)
        elif source == "kbs":
            from vnbroker.explorer.kbs.financial import Finance as KBSFinancial
            return KBSFinancial(self.symbol, show_log=self.show_log)
        elif source == "tcbs":
            from vnbroker.explorer.tcbs.financial import Finance as TCBSFinancial
            return TCBSFinancial(self.symbol, period=self.period, get_all=self.get_all, auth_token=self.auth_token, show_log=self.show_log)
        elif source == "dnse":
            # DNSE doesn't support financial data, fallback to KBS
            from vnbroker.explorer.kbs.financial import Finance as KBSFinancial
            return KBSFinancial(self.symbol, show_log=self.show_log)
        elif source == "ssi":
            # SSI doesn't support financial data, fallback to KBS
            from vnbroker.explorer.kbs.financial import Finance as KBSFinancial
            return KBSFinancial(self.symbol, show_log=self.show_log)
        else:
            raise ValueError(f"Direct provider not implemented for source: {self.source}")

    def _update_data_source(self, symbol: Optional[str] = None):
        """Update symbol and reload data source if needed."""
        if symbol:
            self.symbol = symbol.upper()
            try:
                self.data_source = self._load_data_source()
            except (ImportError, AttributeError) as e:
                logger.error(f"Failed to update data source: {e}")
                raise

    def _process_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Filter and validate kwargs for the specific source."""
        allowed_kwargs = ['lang', 'dropna', 'period', 'show_log']
        processed = {k: v for k, v in kwargs.items()
                     if k in allowed_kwargs}

        if 'period' not in processed:
            processed['period'] = self.period

        return processed

    def _get_financial_data(self, data_type: str,
                            symbol: Optional[str] = None, **kwargs) -> Any:
        """Generic method to fetch financial data."""
        if symbol:
            self._update_data_source(symbol)
        processed_kwargs = self._process_kwargs(kwargs)

        return self._call_with_fallback(data_type, **processed_kwargs)

    # NOTE: no @lru_cache — symbol-dependent, would leak `self` (see Company).
    def balance_sheet(self, symbol: Optional[str] = None,
                      **kwargs) -> Any:
        """Get balance sheet."""
        return self._get_financial_data('balance_sheet', symbol, **kwargs)

    def income_statement(self, symbol: Optional[str] = None,
                         **kwargs) -> Any:
        """Get income statement."""
        return self._get_financial_data('income_statement', symbol, **kwargs)

    def cash_flow(self, symbol: Optional[str] = None,
                  **kwargs) -> Any:
        """Get cash flow statement."""
        return self._get_financial_data('cash_flow', symbol, **kwargs)

    def ratio(self, symbol: Optional[str] = None, **kwargs) -> Any:
        """Get financial ratios."""
        return self._get_financial_data('ratio', symbol, **kwargs)

    def fundamental_snapshot(
        self,
        symbol: Optional[str] = None,
        metrics: Optional[list[str]] = None,
        period: Optional[str] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Build a normalized latest fundamental snapshot from provider data.

        Returns standardized rows with columns:
        symbol, period, report_date, metric, value, unit, source, source_used
        """
        target_symbol = (symbol or self.symbol or "").upper()
        effective_period = (period or self.period or "quarter").lower()

        frame = self._get_financial_data('ratio', symbol, period=effective_period, **kwargs)
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "period",
                    "report_date",
                    "metric",
                    "value",
                    "unit",
                    "source",
                    "source_used",
                ]
            )

        df = frame.copy()
        report_date = None
        if "period" in df.columns:
            report_date = str(df.iloc[0]["period"])
        elif len(df.index) > 0:
            report_date = str(df.index[0])

        selected_metrics = metrics
        if not selected_metrics:
            selected_metrics = [
                col for col in df.columns
                if is_numeric_dtype(df[col])
            ][:20]

        source = None
        if isinstance(getattr(df, "attrs", None), dict):
            source = df.attrs.get("source") or df.attrs.get("source_used")
        if source is None:
            source = getattr(df, "source", None)
        source_text = str(source).upper() if source is not None else self.source.upper()

        source_used = None
        if isinstance(getattr(df, "attrs", None), dict):
            source_used = df.attrs.get("source_used")
        source_used_text = str(source_used).upper() if source_used is not None else source_text

        records: list[dict[str, Any]] = []
        first_row = df.iloc[0]
        for metric in selected_metrics:
            if metric not in df.columns:
                continue
            value = first_row.get(metric)
            if pd.isna(value):
                value = None
            records.append(
                {
                    "symbol": target_symbol,
                    "period": "year" if effective_period == "annual" else effective_period,
                    "report_date": report_date,
                    "metric": metric,
                    "value": value,
                    "unit": None,
                    "source": source_text,
                    "source_used": source_used_text,
                }
            )

        return pd.DataFrame(records)

    def industry_peers(
        self,
        symbol: Optional[str] = None,
        level: int = 4,
        include_exchanges: Optional[list[str]] = None,
        max_peers: int = 100,
    ) -> pd.DataFrame:
        """
        Get peer symbols in the same industry as target symbol.

        Args:
            symbol: Target stock symbol.
            level: Reserved for future ICB granularity support.
            include_exchanges: Optional exchange filter (if exchange column exists).
            max_peers: Maximum number of peers to return.
        """
        _ = level
        target_symbol = (symbol or self.symbol or "").upper()
        if not target_symbol:
            raise ValueError("symbol is required for industry_peers")

        listing = Listing(source='KBS')
        by_industry = listing.symbols_by_industries()
        if not isinstance(by_industry, pd.DataFrame) or by_industry.empty:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "industry_code",
                    "industry_name",
                    "peer_symbol",
                    "source",
                    "source_used",
                ]
            )

        df = by_industry.copy()
        if include_exchanges and "exchange" in df.columns:
            exchange_set = {e.upper() for e in include_exchanges}
            df = df[df["exchange"].astype(str).str.upper().isin(exchange_set)]

        target_rows = df[df["symbol"].astype(str).str.upper() == target_symbol]
        if target_rows.empty:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "industry_code",
                    "industry_name",
                    "peer_symbol",
                    "source",
                    "source_used",
                ]
            )

        industry_code = target_rows.iloc[0].get("industry_code")
        industry_name = target_rows.iloc[0].get("industry_name")

        peers = df
        if "industry_code" in df.columns and pd.notna(industry_code):
            peers = df[df["industry_code"] == industry_code]
        elif "industry_name" in df.columns:
            peers = df[df["industry_name"] == industry_name]

        peer_symbols = (
            peers["symbol"].astype(str).str.upper().drop_duplicates().head(max_peers).tolist()
        )

        out = pd.DataFrame(
            {
                "symbol": [target_symbol] * len(peer_symbols),
                "industry_code": [industry_code] * len(peer_symbols),
                "industry_name": [industry_name] * len(peer_symbols),
                "peer_symbol": peer_symbols,
                "source": ["KBS"] * len(peer_symbols),
                "source_used": ["KBS"] * len(peer_symbols),
            }
        )
        return out

    def _extract_latest_metric_values(
        self,
        ratio_df: pd.DataFrame,
        metrics: list[str],
    ) -> dict[str, Optional[float]]:
        if not isinstance(ratio_df, pd.DataFrame) or ratio_df.empty:
            return {m: None for m in metrics}
        row = ratio_df.iloc[0]
        values: dict[str, Optional[float]] = {}
        for m in metrics:
            if m in ratio_df.columns:
                v = pd.to_numeric(pd.Series([row.get(m)]), errors="coerce").iloc[0]
                values[m] = None if pd.isna(v) else float(v)
            else:
                values[m] = None
        return values

    def industry_benchmark(
        self,
        symbol: Optional[str] = None,
        metrics: Optional[list[str]] = None,
        period: str = "quarter",
        method: str = "median",
    ) -> pd.DataFrame:
        """
        Compute industry benchmark (median/mean) for requested metrics.
        """
        _ = method
        target_symbol = (symbol or self.symbol or "").upper()
        if not target_symbol:
            raise ValueError("symbol is required for industry_benchmark")
        if not metrics:
            raise ValueError("metrics is required for industry_benchmark")

        peers_df = self.industry_peers(symbol=target_symbol)
        if peers_df.empty:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "industry_code",
                    "industry_name",
                    "peer_symbol",
                    "metric",
                    "peer_value",
                    "industry_median",
                    "industry_mean",
                    "percentile",
                    "zscore",
                    "rank",
                    "total_peers",
                    "source",
                    "source_used",
                ]
            )

        records: list[dict[str, Any]] = []
        for peer_symbol in peers_df["peer_symbol"].tolist():
            ratio_df = self._get_financial_data('ratio', peer_symbol, period=period)
            metric_values = self._extract_latest_metric_values(ratio_df, metrics)
            for metric, value in metric_values.items():
                records.append(
                    {
                        "peer_symbol": peer_symbol,
                        "metric": metric,
                        "peer_value": value,
                    }
                )

        values_df = pd.DataFrame(records)
        if values_df.empty:
            return values_df

        agg = values_df.groupby("metric", dropna=False)["peer_value"].agg(
            industry_median="median",
            industry_mean="mean",
            total_peers=lambda s: int(s.notna().sum()),
        )
        out = values_df.merge(agg, on="metric", how="left")

        base = peers_df.iloc[0]
        out.insert(0, "symbol", target_symbol)
        out.insert(1, "industry_code", base.get("industry_code"))
        out.insert(2, "industry_name", base.get("industry_name"))

        out["percentile"] = None
        out["zscore"] = None
        out["rank"] = None
        out["source"] = self.source.upper()
        out["source_used"] = self.source.upper()

        out = out[
            [
                "symbol",
                "industry_code",
                "industry_name",
                "peer_symbol",
                "metric",
                "peer_value",
                "industry_median",
                "industry_mean",
                "percentile",
                "zscore",
                "rank",
                "total_peers",
                "source",
                "source_used",
            ]
        ]
        return out

    def industry_rank(
        self,
        symbol: Optional[str] = None,
        metric: str = "roe",
        period: str = "quarter",
        method: str = "percentile",
    ) -> pd.DataFrame:
        """
        Compute rank/percentile/z-score for one metric in symbol's industry.
        """
        _ = method
        target_symbol = (symbol or self.symbol or "").upper()
        bench = self.industry_benchmark(symbol=target_symbol, metrics=[metric], period=period)
        if bench.empty:
            return bench

        df = bench.copy()
        mask = df["metric"] == metric
        metric_df = df[mask].copy()
        if metric_df.empty:
            return bench

        metric_df["rank"] = metric_df["peer_value"].rank(method="min", ascending=False)
        n = metric_df["peer_value"].notna().sum()

        if n <= 1:
            metric_df["percentile"] = 100.0
        else:
            metric_df["percentile"] = metric_df["rank"].map(lambda r: ((n - r) / (n - 1)) * 100 if pd.notna(r) else None)

        std = metric_df["peer_value"].std(skipna=True)
        mean = metric_df["peer_value"].mean(skipna=True)
        if pd.isna(std) or std == 0:
            metric_df["zscore"] = 0.0
        else:
            metric_df["zscore"] = (metric_df["peer_value"] - mean) / std

        bench.loc[mask, ["rank", "percentile", "zscore"]] = metric_df[["rank", "percentile", "zscore"]].values
        return bench







class Screener(BaseComponent):
    """Stock screening and filtering."""

    SUPPORTED_SOURCES = ["TCBS", "VCI", "KBS"]

    def __init__(self, source: str = "TCBS",
                 auth_token: Optional[str] = None):
        self.auth_token = auth_token
        super().__init__(symbol=None, source=source)

    def _load_data_source(self):
        """Load screener data source module."""
        module = importlib.import_module(self.source_module)
        return _instantiate_supported(
            module.Screener,
            auth_token=self.auth_token,
        )

    @retry(
        stop=stop_after_attempt(Config.DEFAULT_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, ConnectionError, TimeoutError)),
        reraise=True,
    )
    def stock(self, **kwargs):
        """Screen stocks with criteria."""
        allowed_kwargs = ['params', 'limit', 'lang', 'id']
        processed = {k: v for k, v in kwargs.items() if k in allowed_kwargs}

        try:
            return self.data_source.stock(**processed)
        except Exception as e:
            if self.source == "TCBS":
                from vnbroker.core.utils.logger import get_logger
                logger = get_logger(__name__)
                logger.warning(f"Screener {self.source} failed: {e}. Trying fallback...")

                fallbacks = []
                if self.source != "VCI":
                    try:
                        from vnbroker.explorer.vci.screener import VCIScreener
                        fallbacks.append(("VCI", VCIScreener(auth_token=self.auth_token)))
                    except Exception:
                        pass
                if self.source != "KBS":
                    try:
                        from vnbroker.explorer.kbs.screener import KBSScreener
                        fallbacks.append(("KBS", KBSScreener(auth_token=self.auth_token)))
                    except Exception:
                        pass

                for name, fallback in fallbacks:
                    try:
                        result = fallback.stock(**processed)
                        if not result.empty:
                            logger.info(f"Screener fallback to {name} succeeded")
                            return result
                    except Exception as fallback_e:
                        logger.warning(f"Screener {name} fallback failed: {fallback_e}")

            raise


class Fund(BaseComponent):
    """Fund/Mutual fund data."""

    SUPPORTED_SOURCES = ["FMARKET"]

    def __init__(self, source: str = "FMARKET", random_agent: bool = False):
        """
        Initialize fund component.

        Args:
            source: Data source (FMARKET)
            random_agent: Use random user agent for requests
        """
        self.random_agent = random_agent
        super().__init__(symbol=None, source=source)
        self.details = self.data_source.details

    def _load_data_source(self):
        """Load fund data source module."""
        module = importlib.import_module(self.source_module)
        return module.Fund(random_agent=self.random_agent)

    def listing(self, **kwargs):
        """Get list of open funds."""
        return self.data_source.listing(**kwargs)
