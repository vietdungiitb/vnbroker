from typing import Any, Dict, Optional
import inspect
from abc import ABC
from functools import wraps
import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from vnbroker.config import Config
from vnbroker.core.registry import ProviderRegistry
from vnbroker.core.source_router import (
    annotate_result_source,
    build_source_order,
    get_auto_candidates,
    is_auto_source,
    record_failure,
    record_success,
    should_failover,
)


def dynamic_method(func):
    """
    Decorator for adapter methods:
    - Ensures the loaded provider supports this method
    - Filters kwargs to only those the provider’s signature accepts
    """
    method_name = func.__name__

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if hasattr(self, '_call_dynamic_method'):
            return self._call_dynamic_method(method_name, *args, **kwargs)
        if not hasattr(self._provider, method_name):
            raise NotImplementedError(
                f"Source '{self.source}' does not support '{method_name}'"
            )
        provider_method = getattr(self._provider, method_name)
        sig = inspect.signature(provider_method)
        filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return provider_method(*args, **filtered)

    return wrapper


class BaseAdapter(ABC):
    """
    Base adapter that uses ProviderRegistry to discover and instantiate
    providers from both explorer and connector packages.
    """

    _module_name: str  # e.g. "quote", "company", etc.

    def __init__(
        self,
        source: str,
        symbol: Optional[str] = None,
        **kwargs
    ):
        # Preserve requested source and resolved source separately.
        self.source = source
        self._requested_source = source
        self._resolved_source = None
        self.symbol = symbol
        self._provider_kwargs = dict(kwargs)

        initial_source = self._pick_initial_source()
        self._provider = self._instantiate_provider(initial_source, symbol, **kwargs)
        self._resolved_source = initial_source

    @property
    def provider(self):
        return self._provider

    @property
    def resolved_source(self) -> Optional[str]:
        return self._resolved_source

    def _pick_initial_source(self) -> str:
        if is_auto_source(self._requested_source):
            candidates = build_source_order(self._module_name, symbol=self.symbol)
            if not candidates:
                raise ValueError(
                    f"AUTO source is not configured for '{self._module_name}'."
                )
            return candidates[0]
        return self._requested_source

    def _instantiate_provider(self, source: str, symbol: Optional[str] = None, **kwargs):
        actual_symbol = self.symbol if symbol is None else symbol

        # Get provider class from registry
        try:
            impl_cls = ProviderRegistry.get(self._module_name, source)
        except ValueError as e:
            raise ValueError(str(e)) from e

        # Inspect constructor signature and filter kwargs
        sig = inspect.signature(impl_cls.__init__)
        init_kwargs = {}
        # Only pass symbol if accepted
        if actual_symbol is not None and 'symbol' in sig.parameters:
            init_kwargs['symbol'] = actual_symbol
        # Pass only recognized provider kwargs
        for key, val in kwargs.items():
            if key in sig.parameters:
                init_kwargs[key] = val

        return impl_cls(**init_kwargs)

    def _update_provider(
        self,
        source: Optional[str] = None,
        symbol: Optional[str] = None,
    ):
        target_source = source or self._resolved_source or self._pick_initial_source()
        target_symbol = self.symbol if symbol is None else symbol
        self._provider = self._instantiate_provider(
            target_source,
            target_symbol,
            **self._provider_kwargs,
        )
        self._resolved_source = target_source
        return self._provider

    def _normalize_derivative_listing(self, result, method_name: str):
        if method_name != "all_future_indices":
            return result
        if isinstance(result, pd.Series):
            df = result.to_frame("symbol")
            df["exchange"] = "HNX"
            return df
        return result

    def _post_process_result(self, result: Any, method_name: str, kwargs: Dict[str, Any]) -> Any:
        """Hook chạy sau khi provider trả về, trước khi kết quả ra tới người dùng.

        Mặc định chỉ xử lý danh sách hợp đồng phái sinh. Lớp con override để
        áp thêm chuẩn hoá của module mình (ví dụ `api.quote.Quote` ép hợp đồng
        tầng 1 lên `history`/`intraday`).

        ⚠ **Đây là điểm móc duy nhất dùng được cho `history`/`intraday` của
        `api.quote`.** Hai method đó được trang bị `@dynamic_method`
        (`base.py:21`), và decorator đó rẽ sang `_call_dynamic_method` **trước
        khi thân hàm chạy** — nên bất kỳ dòng nào viết trong thân hàm đều là
        dead code. Đo 2026-10-10: đặt `self._normalize(...)` vào thân
        `api/quote.py::history` khiến `_delegate_to_provider` được gọi **0**
        lần. Dữ liệu trả về y nguyên frame thô của provider.
        """
        return self._normalize_derivative_listing(result, method_name)

    def _invoke_provider_method(self, method_name: str, *args, **kwargs):
        if not hasattr(self._provider, method_name):
            raise NotImplementedError(
                f"Source '{self._resolved_source or self.source}' does not support '{method_name}'"
            )
        provider_method = getattr(self._provider, method_name)
        sig = inspect.signature(provider_method)
        filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
        result = provider_method(*args, **filtered)
        return self._post_process_result(result, method_name, kwargs)

    def _call_provider_method(self, method_name: str, *args, **kwargs):
        if not is_auto_source(self._requested_source):
            return self._invoke_provider_method(method_name, *args, **kwargs)

        candidates = build_source_order(self._module_name, symbol=self.symbol)
        if not candidates:
            raise ValueError(
                f"AUTO source is not configured for '{self._module_name}'. Available open sources: {get_auto_candidates(self._module_name)}"
            )

        last_error = None
        for candidate in candidates:
            try:
                if candidate != self._resolved_source:
                    self._update_provider(source=candidate)
                result = self._invoke_provider_method(method_name, *args, **kwargs)
                record_success(self._module_name, candidate)
                return annotate_result_source(result, candidate)
            except Exception as exc:
                last_error = exc
                if should_failover(exc):
                    record_failure(self._module_name, candidate)
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise ConnectionError(
            f"No healthy source available for {self._module_name}."
        )

    def _call_dynamic_method(self, method_name: str, *args, **kwargs):
        return self._call_provider_method(method_name, *args, **kwargs)

    def __getattr__(self, name):
        # Delegate attribute access to the provider
        return getattr(self._provider, name)

    @retry(
        stop=stop_after_attempt(Config.RETRIES),
        wait=wait_exponential(
            multiplier=Config.BACKOFF_MULTIPLIER,
            min=Config.BACKOFF_MIN,
            max=Config.BACKOFF_MAX
        ),
        retry=retry_if_exception_type((requests.exceptions.RequestException, ConnectionError, TimeoutError)),
        reraise=True,
    )
    def history(self, *args, **kwargs):
        # Generic retry wrapper for any .history() calls
        return self._call_provider_method('history', *args, **kwargs)
