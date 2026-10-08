"""Bulk router for distributing symbol fetching across multiple providers.

Uses HealthRouter to pick healthy providers, distributes symbols round-robin,
and fetches concurrently via ThreadPoolExecutor. Provider failures are
captured per-provider without crashing the entire batch.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import pandas as pd

from vnbroker.core.health_router import HealthRouter

logger = logging.getLogger(__name__)


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
    ) -> Dict[str, Any]:
        """Fetch history for multiple symbols using multiple providers.

        Returns a structured dict with per-provider results, errors, and
        metadata about the distribution.
        """
        if not symbols:
            return {
                "results": {},
                "errors": {},
                "providers_used": [],
                "symbols_requested": 0,
                "symbols_returned": 0,
            }

        # 1. Get healthy providers
        providers = self._health.get_healthy_providers(module)
        if not providers:
            raise ConnectionError("No healthy providers available")

        # 2. Distribute symbols across providers (round-robin)
        plan: Dict[str, List[str]] = {p: [] for p in providers}
        for i, sym in enumerate(symbols):
            plan[providers[i % len(providers)]].append(sym)

        # 3. Fetch concurrently using ThreadPoolExecutor
        results: Dict[str, Any] = {}
        errors: Dict[str, str] = {}

        with ThreadPoolExecutor(max_workers=len(providers)) as executor:
            futures = {
                executor.submit(self._fetch_batch, provider, syms, start, end, module): provider
                for provider, syms in plan.items()
                if syms
            }
            for future in as_completed(futures):
                provider = futures[future]
                try:
                    results[provider] = future.result()
                except Exception as e:
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

    def _fetch_batch(
        self,
        provider: str,
        symbols: List[str],
        start: Optional[str],
        end: Optional[str],
        module: str,
    ) -> List[pd.DataFrame]:
        """Fetch a batch of symbols from a specific provider.

        Uses provider's fetch_multiple if available; falls back to individual
        fetches. Returns a list of DataFrames (one per symbol).
        """
        from vnbroker.core import source_router

        # Try to get the provider class from the registry
        try:
            from vnbroker.core.registry import ProviderRegistry
            provider_class = ProviderRegistry.get(module, provider)
        except (ValueError, KeyError):
            provider_class = None

        frames: List[pd.DataFrame] = []

        if provider_class is not None:
            try:
                instance = provider_class()
                # Check for fetch_multiple / bulk method
                if hasattr(instance, "fetch_multiple"):
                    result = instance.fetch_multiple(symbols, start, end)
                    if isinstance(result, list):
                        frames.extend(result)
                    elif isinstance(result, dict):
                        for sym in symbols:
                            if sym in result:
                                frames.append(result[sym])
                    return frames
                elif hasattr(instance, "history"):
                    for sym in symbols:
                        try:
                            df = instance.history(sym, start, end)
                            if df is not None and not df.empty:
                                frames.append(df)
                        except Exception as e:
                            logger.debug(
                                "Individual fetch failed for %s on %s: %s",
                                sym, provider, e,
                            )
                    return frames
            except Exception as e:
                logger.warning(
                    "Provider %s batch fetch failed: %s", provider, e,
                )

        # Fallback: use source_router's build_source_order for individual fetches
        for sym in symbols:
            try:
                order = source_router.build_source_order(module, symbol=sym)
                if order:
                    # Use the first available source (should be our provider)
                    from vnbroker.core.unified_registry import get_provider
                    prov = get_provider(module, order[0])
                    if hasattr(prov, "history"):
                        df = prov.history(sym, start, end)
                        if df is not None and not df.empty:
                            frames.append(df)
            except Exception as e:
                logger.debug(
                    "Fallback fetch failed for %s via %s: %s", sym, provider, e,
                )

        return frames
