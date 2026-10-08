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
                try:
                    results[provider] = future.result()
                except PROVIDER_ERRORS as e:
                    logger.warning("Bulk fetch failed for provider %s: %s", provider, e)
                    errors[provider] = str(e)

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

        Names are upper-cased so every downstream key (``results``,
        ``providers_used``, ``attrs['sources_used']``) reads the same way as
        ``df.attrs['source']``, regardless of the caller's casing.

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
                if not snapshot.get(p.upper(), {}).get("in_cooldown", False)
            ]

        if not selected:
            raise ConnectionError("No healthy providers available")
        return [p.upper() for p in selected]

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

        Prefers the provider's ``fetch_multiple`` (a classmethod on both VCI and
        KBS, sync for KBS and async for VCI); falls back to one ``history``
        call per symbol on a properly constructed instance.

        Every returned frame is tagged with ``attrs['symbol']`` when the
        provider did not do it itself, so the caller can attribute each frame
        to the provider that actually served it.

        Raises:
            Exception: One of ``PROGRAMMING_ERRORS`` always propagates — a
                programming error is never downgraded to a log line. Provider
                errors only propagate when the batch produced no frame at all.
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
        fetch_multiple = getattr(provider_class, "fetch_multiple", None)
        if fetch_multiple is not None:
            frames = self._frames_from_fetch_multiple(
                provider, fetch_multiple, symbols, start, end, interval, module
            )
        else:
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

    def _frames_from_fetch_multiple(
        self,
        provider: str,
        fetch_multiple: Any,
        symbols: List[str],
        start: Optional[str],
        end: Optional[str],
        interval: str,
        module: str,
    ) -> List[pd.DataFrame]:
        """Call a provider's ``fetch_multiple`` through the sync/async bridge.

        ``fetch_multiple`` is an ``async classmethod`` on VCI and a sync one on
        KBS. Calling it blindly returns a coroutine, whose ``isinstance(...,
        list)`` and ``isinstance(..., dict)`` are both False — the caller then
        sees an empty batch and reports success.

        An empty result for a non-empty request is treated as a provider
        failure, not a quiet success: KBS's own ``fetch_multiple`` catches
        every per-symbol exception and returns ``[]``, so without this the
        failure would never reach ``errors``.
        """
        from vnbroker.api.quote import call_provider_sync

        try:
            result = call_provider_sync(
                fetch_multiple,
                symbols=symbols,
                start=start,
                end=end,
                interval=interval,
            )
        except PROGRAMMING_ERRORS:
            raise
        except PROVIDER_ERRORS as exc:
            raise self._note_failure(provider, exc, module) from exc

        frames = self._normalize_multi_result(result, symbols)
        if symbols and not frames:
            empty_result = RuntimeError(
                f"Provider {provider} returned no data for "
                f"{len(symbols)} requested symbol(s): {symbols}"
            )
            raise self._note_failure(provider, empty_result, module) from empty_result
        return frames

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
        """Per-symbol fallback: construct one instance per symbol, then call
        ``history`` **on that instance**.

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
                df = instance.history(start=start, end=end, interval=interval)
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
            if df is not None and not df.empty:
                self._tag_symbol(df, sym)
                frames.append(df)

        if not frames and first_error is not None:
            raise first_error
        if symbols and not frames:
            empty_result = RuntimeError(
                f"Provider {provider} returned no data for "
                f"{len(symbols)} requested symbol(s): {symbols}"
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

    def _normalize_multi_result(
        self, result: Any, symbols: List[str]
    ) -> List[pd.DataFrame]:
        """Flatten a ``fetch_multiple`` return value into a list of frames."""
        if result is None:
            return []
        if isinstance(result, pd.DataFrame):
            if result.empty:
                return []
            if not result.attrs.get("symbol") and len(symbols) == 1:
                self._tag_symbol(result, symbols[0])
            return [result]
        if isinstance(result, dict):
            frames = []
            for sym in symbols:
                df = result.get(sym)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    self._tag_symbol(df, sym)
                    frames.append(df)
            return frames
        if isinstance(result, (list, tuple)):
            frames = [
                df for df in result if isinstance(df, pd.DataFrame) and not df.empty
            ]
            # Providers return one frame per requested symbol, in order. Only
            # align positionally when the counts match, otherwise guessing
            # would mislabel frames.
            if len(frames) == len(symbols):
                for df, sym in zip(frames, symbols):
                    self._tag_symbol(df, sym)
            return frames
        raise TypeError(
            "fetch_multiple returned an unsupported type "
            f"{type(result).__name__!r}; expected list, tuple, dict or DataFrame"
        )
