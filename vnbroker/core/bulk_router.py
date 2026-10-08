"""Bulk router for distributing symbol fetching across multiple providers.

Uses HealthRouter to pick healthy providers, distributes symbols round-robin,
and fetches concurrently via ThreadPoolExecutor. Provider failures are
captured per-provider without crashing the entire batch.

Lỗi lập trình (TypeError / AttributeError / ...) KHÔNG bị nuốt: chúng nổi lên
để lộ bug thật. Chỉ lỗi vận hành (mạng, provider từ chối, payload hỏng) mới
được ghi vào ``errors`` và đánh dấu provider suy giảm sức khỏe.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from vnbroker.core.health_router import HealthRouter

logger = logging.getLogger(__name__)


def _is_unusable(result: Any) -> bool:
    """Provider trả về thứ **không dùng được** không?

    MAJOR-2: tiêu chí nằm ở *schema*, KHÔNG phải số dòng. Frame đủ cột mà 0 dòng
    là ngày nghỉch giao dịch (Tết, cuối tuần, mã chưa có dữ liệu) và phải được coi
    là thành công; chỉ 0 cột mới là provider hỏng.

    Dùng lại đúng helper của ``common.data`` để hai đường đi không lệch nhau —
    ``common/data.py:465-467`` đã cảnh báo chính xác cái bẫy "coi 0 dòng thất bại"
    mà bulk đang mắc. Import trễ (trong hàm) vì ``common.data`` là module nặng
    và ``core`` nằm DƯỚI nó; đã kiểm tra KHÔNG có vòng import theo cả hai chiều.
    """
    from vnbroker.common.data import _is_unusable_provider_result

    return _is_unusable_provider_result(result)


def _filter_kwargs(method: Any, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Chỉ giữ kwarg mà ``method`` thật sự nhận.

    MAJOR-4: provider có tham số khác nhau (`history` của DNSE nhận ``symbol``,
    SSI không nhận ``to_df`` ở vị trí kia...), nên gửi thừa sẽ ném
    ``TypeError``. Dùng lại helper sẵn có của ``common.data`` thay vì viết
    lần hai.
    """
    from vnbroker.common.data import _filter_kwargs as _data_filter_kwargs

    return _data_filter_kwargs(method, kwargs)

# Lỗi lập trình: dấu hiệu gọi sai API (self bị bind nhầm vào chuỗi symbol,
# tham số không tồn tại, thiếu import). Nuốt chúng thành `logger.warning` là
# cách che bug nên chúng phải nổi lên tới caller.
PROGRAMMING_ERRORS: tuple[type[Exception], ...] = (
    TypeError,
    AttributeError,
    NameError,
    ImportError,
    IndentationError,
    SyntaxError,
    AssertionError,
)

# Lỗi vận hành: provider/network thất bại -> ghi vào `errors` + health store.
PROVIDER_ERRORS: tuple[type[Exception], ...] = (
    OSError,  # bao gồm ConnectionError, TimeoutError
    RuntimeError,
    ValueError,
    KeyError,  # subclass của LookupError
    LookupError,
    NotImplementedError,
)


def _display_key(provider: str) -> str:
    """Khoá provider trả về cho ``api/bulk.py``.

    Tên nội bộ của router là lower-case (khớp khoá health store), còn
    ``attrs['sources_used']`` / ``attrs['failed']`` phải đọc như
    ``df.attrs['source']`` nên upper-case. Chuyển đổi ở đúng MỘT chỗ.
    """
    return provider.upper()


class BulkRouter:
    """Distributes bulk requests across providers based on health."""

    def __init__(self, health_router: Optional[HealthRouter] = None):
        self._health = health_router or HealthRouter()

    def fetch_history(
        self,
        symbols: List[str],
        start: Optional[str] = None,
        end: Optional[str] = None,
        module: str = "quote",
        *,
        interval: str = "1D",
        providers: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Fetch history for multiple symbols using multiple providers.

        Args:
            symbols: Stock symbols to fetch.
            start: Start date (YYYY-MM-DD).
            end: End date (YYYY-MM-DD).
            module: Provider module name (quote, company, ...).
            interval: Data interval, forwarded to the provider. Keyword-only so
                the positional order stays compatible with older callers.
            providers: Explicit provider candidates (e.g. from ProviderPool).
                Narrowed to the entries that are healthy right now. ``None``
                means "whatever the health store knows about this module".

        Returns:
            A structured dict with per-provider results, errors, and
            metadata about the distribution.

        Raises:
            ConnectionError: When no healthy provider can serve the module.
        """
        if not symbols:
            return {
                "results": {},
                "errors": {},
                "providers_used": [],
                "symbols_requested": 0,
                "symbols_returned": 0,
            }

        # 1. Pick providers: health snapshot, optionally narrowed to a
        #    caller-supplied candidate list.
        selected = self._select_providers(module, providers)

        # 2. Distribute symbols across providers (round-robin)
        plan: Dict[str, List[str]] = {p: [] for p in selected}
        for i, sym in enumerate(symbols):
            plan[selected[i % len(selected)]].append(sym)

        # 3. Fetch concurrently using ThreadPoolExecutor
        results: Dict[str, Any] = {}
        errors: Dict[str, str] = {}

        # `selected` (và `provider`) là TÊN lower-case — đúng dạng khoá mà
        # `source_router._health_state` đọc. Chỉ khoá trả về cho `api/bulk.py`
        # mới upper-case (xem `_display_key`).
        with ThreadPoolExecutor(max_workers=len(selected)) as executor:
            futures = {
                executor.submit(
                    self._fetch_batch, provider, syms, start, end, module, interval
                ): provider
                for provider, syms in plan.items()
                if syms
            }
            for future in as_completed(futures):
                provider = futures[future]
                key = _display_key(provider)
                try:
                    results[key] = future.result()
                except PROVIDER_ERRORS as e:
                    logger.warning("Bulk fetch failed for provider %s: %s", provider, e)
                    errors[key] = str(e)

        # 4. Merge results
        return {
            "results": results,
            "errors": errors,
            "providers_used": list(results.keys()),
            "symbols_requested": len(symbols),
            "symbols_returned": sum(
                len(v) for v in results.values() if isinstance(v, list)
            ),
        }

    def _select_providers(
        self, module: str, providers: Optional[Sequence[str]]
    ) -> List[str]:
        """Resolve the provider list to distribute symbols across.

        Names are returned **lower-case**, because that is the form the health
        store keys on: ``source_router.get_source_health_snapshot`` reads
        ``_health_state[(module, s)]`` for ``s`` in ``get_auto_candidates(module)``
        (``['vci', 'kbs']``). Returning upper-case names made every
        ``record_success`` / ``record_failure`` write ``('quote', 'VCI')`` — a key
        the snapshot never reads — so the circuit breaker could never engage and
        the dead keys were still persisted to the SQLite store.

        Upper-casing now happens only where results are handed to the caller
        (``_display_key``), so ``attrs['sources_used']`` still reads like
        ``df.attrs['source']``.

        With no ``providers`` argument the health router decides — it only
        knows the module's AUTO candidates. When the caller *does* pass a list
        (ProviderPool does), that list is authoritative and the health store is
        consulted only to drop entries that are demonstrably in cooldown;
        a provider the store has never seen is unproven, not unhealthy.
        """
        if providers is None:
            selected = list(self._health.get_healthy_providers(module))
        else:
            snapshot = self._health_snapshot(module)
            selected = [
                p
                for p in providers
                if not snapshot.get(_display_key(p), {}).get("in_cooldown", False)
            ]

        if not selected:
            raise ConnectionError("No healthy providers available")
        return [p.lower() for p in selected]

    @staticmethod
    def _health_snapshot(module: str) -> Dict[str, Dict[str, Any]]:
        from vnbroker.core import source_router

        return source_router.get_source_health_snapshot(module)

    def _fetch_batch(
        self,
        provider: str,
        symbols: List[str],
        start: Optional[str],
        end: Optional[str],
        module: str,
        interval: str = "1D",
    ) -> List[pd.DataFrame]:
        """Fetch a batch of symbols from a specific provider.

        Two paths, both through the provider's own ``history``:

        - ``history(symbols=[...], parallel=True)`` when the provider's signature
          advertises both (VCI, KBS, TCBS). That method already owns the
          sync/async bridge to ``fetch_multiple`` (``explorer/vci/quote.py:496``).
        - one ``history`` call per symbol otherwise (SSI, DNSE).

        MAJOR-4: bulk used to import ``call_provider_sync`` from
        ``vnbroker.api.quote`` — a lower layer reaching into a higher one — and
        drive ``fetch_multiple`` itself, i.e. a second copy of a bridge that
        already existed in ``explorer``. The capability is called directly now.

        Every returned frame is tagged with ``attrs['symbol']`` when the
        provider did not do it itself, so the caller can attribute each frame
        to the provider that actually served it.

        Raises:
            Exception: One of ``PROGRAMMING_ERRORS`` always propagates — a
                programming error is never downgraded to a log line. Provider
                errors only propagate when the batch produced no usable frame.
        """
        provider_class = self._resolve_provider_class(module, provider)
        if provider_class is None:
            logger.warning(
                "Provider %s/%s is healthy but not registered; skipping",
                module,
                provider,
            )
            return []

        started = time.perf_counter()
        frames = self._frames_from_history(
            provider_class, provider, symbols, start, end, interval, module
        )

        if frames:
            self._health.record_success(
                provider, (time.perf_counter() - started) * 1000.0, module=module
            )
        return frames

    def _resolve_provider_class(self, module: str, provider: str) -> Optional[type]:
        """Look up a provider class without hiding genuine lookup bugs.

        A provider that is healthy but not registered is a configuration gap:
        report ``None`` and skip the batch instead of silently returning zero
        frames for every symbol while looking like a clean success.
        """
        from vnbroker.core.registry import ProviderRegistry

        try:
            return ProviderRegistry.get(module, provider)
        except ValueError:
            logger.debug("No registered %s provider named %s", module, provider)
            return None

    @staticmethod
    def _supports_parallel_history(provider_class: type) -> bool:
        """``history`` của provider có nhận ``parallel`` + ``symbols`` không?

        Quyết định dựa trên **tên tham số tường minh**, không dựa trên
        ``**kwargs``: SSI/DNSE có ``**kwargs`` nên `symbols`/`parallel` gửi vào
        sẽ bị nuốt im lặng thay vì chạy song song — im lặng là thứ tệ nhất.
        """
        import inspect

        history = getattr(provider_class, "history", None)
        if history is None:
            return False
        try:
            params = inspect.signature(history).parameters
        except (TypeError, ValueError):
            return False
        return "parallel" in params and "symbols" in params

    def _frames_from_history(
        self,
        provider_class: type,
        provider: str,
        symbols: List[str],
        start: Optional[str],
        end: Optional[str],
        interval: str,
        module: str,
    ) -> List[pd.DataFrame]:
        """Dispatch a batch to the provider's ``history``.

        MAJOR-4: the provider owns the bridge, not ``core``.
        """
        if self._supports_parallel_history(provider_class):
            return self._parallel_history_frames(
                provider_class, provider, symbols, start, end, interval, module
            )
        return self._sequential_history_frames(
            provider_class, provider, symbols, start, end, interval, module
        )

    def _parallel_history_frames(
        self,
        provider_class: type,
        provider: str,
        symbols: List[str],
        start: Optional[str],
        end: Optional[str],
        interval: str,
        module: str,
    ) -> List[pd.DataFrame]:
        """One ``history(symbols=..., parallel=True)`` call for the batch.

        VCI/KBS/TCBS already route this to their own ``fetch_multiple`` and own
        the sync/async bridging (``explorer/vci/quote.py:496``), so bulk needs
        no bridge of its own.

        A result carrying no usable schema is a provider failure, not a quiet
        success: KBS's ``fetch_multiple`` swallows per-symbol exceptions and
        returns ``[]``, so without this the failure never reaches ``errors``.
        The reverse matters equally — a batch of well-shaped 0-row frames is a
        market holiday, not a failure (MAJOR-2).
        """
        instance = self._build_instance(provider_class, symbols, provider)

        try:
            result = instance.history(
                **_filter_kwargs(
                    instance.history,
                    {
                        "symbols": symbols,
                        "start": start,
                        "end": end,
                        "interval": interval,
                        "parallel": True,
                    },
                )
            )
        except PROGRAMMING_ERRORS:
            raise
        except PROVIDER_ERRORS as exc:
            raise self._note_failure(provider, exc, module) from exc

        frames = self._normalize_multi_result(result, symbols)
        if symbols and not frames:
            empty_result = RuntimeError(
                f"Provider {provider} returned unusable data for "
                f"{len(symbols)} requested symbol(s): {symbols} "
                "(no frame carried a usable schema)"
            )
            raise self._note_failure(provider, empty_result, module) from empty_result
        return frames

    @staticmethod
    def _build_instance(
        provider_class: type, symbols: List[str], provider: str
    ) -> Any:
        """Dựng instance đúng cách cho provider.

        Mọi provider thật yêu cầu ``symbol`` ở ``__init__``; gọi
        ``provider_class()`` không tham số sẽ ném ``TypeError``. Ở nhánh song
        song ``self.symbol`` không được dùng (symbols truyền vào rồi) nhưng
        constructor vẫn bắt buộc có nó.
        """
        return provider_class(symbol=symbols[0] if symbols else None)

    def _sequential_history_frames(
        self,
        provider_class: type,
        provider: str,
        symbols: List[str],
        start: Optional[str],
        end: Optional[str],
        interval: str,
        module: str,
    ) -> List[pd.DataFrame]:
        """Per-symbol fallback: construct one instance per symbol, then call
        ``history`` **on that instance**.

        Used by providers whose ``history`` has no ``parallel``/``symbols``
        (SSI, DNSE).

        Two traps live here. ``__init__`` requires ``symbol``, so
        ``provider_class()`` raises ``TypeError``; and ``history`` takes no
        ``symbol`` parameter (the symbol lives on the instance), so
        ``history(sym, start, end)`` silently shifts every argument along.
        """
        frames: List[pd.DataFrame] = []
        first_error: Optional[Exception] = None

        for sym in symbols:
            instance = provider_class(symbol=sym)
            try:
                df = instance.history(
                    **_filter_kwargs(
                        instance.history,
                        {"start": start, "end": end, "interval": interval},
                    )
                )
            except PROGRAMMING_ERRORS:
                raise
            except PROVIDER_ERRORS as exc:
                self._note_failure(provider, exc, module)
                if first_error is None:
                    first_error = exc
                logger.debug(
                    "Individual fetch failed for %s on %s: %s", sym, provider, exc
                )
                continue
            if self._is_usable_frame(df):
                self._tag_symbol(df, sym)
                frames.append(df)

        if not frames and first_error is not None:
            raise first_error
        if symbols and not frames:
            empty_result = RuntimeError(
                f"Provider {provider} returned unusable data for "
                f"{len(symbols)} requested symbol(s): {symbols} "
                "(no frame carried a usable schema)"
            )
            raise self._note_failure(provider, empty_result, module) from empty_result
        return frames

    def _note_failure(
        self, provider: str, exc: Exception, module: str
    ) -> Exception:
        """Record a provider failure in the health store and return ``exc``.

        Returns instead of raises so callers can keep their
        ``except PROGRAMMING_ERRORS: raise`` clauses intact.
        """
        self._health.record_failure(provider, exc, module=module)
        return exc

    @staticmethod
    def _tag_symbol(df: pd.DataFrame, symbol: str) -> None:
        """Record which symbol a frame belongs to.

        KBS already sets ``attrs['symbol']``; VCI does not. Without this the
        caller cannot tell whose frame it is holding.
        """
        if not df.attrs.get("symbol"):
            df.attrs["symbol"] = symbol

    @staticmethod
    def _is_usable_frame(df: Any) -> bool:
        """Frame này có mang dữ liệu *dùng được* không?

        MAJOR-2: đủ cột + 0 dòng là ngày nghỉch giao dịch — giữ lại. 0 cột là
        provider trả về rỗng — loại. Trước đây chỗ này lọc ``not df.empty`` nên
        frame hợp lệ của ngày nghỉch bị loại TRƯỚC khi kịp kiểm tra schema, rồi
        batch rỗng bị quy thành provider hỏng.
        """
        return isinstance(df, pd.DataFrame) and not _is_unusable(df)

    def _normalize_multi_result(
        self, result: Any, symbols: List[str]
    ) -> List[pd.DataFrame]:
        """Flatten a provider ``history`` return value into a list of frames.

        Parallel-capable providers hand back what their ``fetch_multiple``
        produced: a list (or dict) of frames, or a bare DataFrame for one
        symbol.

        Chỉ frame **không dùng được** (thiếu schema) bị loại; frame đủ schema mà
        0 dòng vẫn được giữ để ngày nghỉch giao dịch không bị tính là lỗi.
        """
        if result is None:
            return []
        if isinstance(result, pd.DataFrame):
            if _is_unusable(result):
                return []
            if not result.attrs.get("symbol") and len(symbols) == 1:
                self._tag_symbol(result, symbols[0])
            return [result]
        if isinstance(result, dict):
            frames = []
            for sym in symbols:
                df = result.get(sym)
                if self._is_usable_frame(df):
                    self._tag_symbol(df, sym)
                    frames.append(df)
            return frames
        if isinstance(result, (list, tuple)):
            frames = [df for df in result if self._is_usable_frame(df)]
            # Providers return one frame per requested symbol, in order. Only
            # align positionally when the counts match, otherwise guessing
            # would mislabel frames.
            if len(frames) == len(symbols):
                for df, sym in zip(frames, symbols):
                    self._tag_symbol(df, sym)
            return frames
        raise TypeError(
            "provider history returned an unsupported type "
            f"{type(result).__name__!r}; expected list, tuple, dict or DataFrame"
        )
