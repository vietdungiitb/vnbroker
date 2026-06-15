"""
Main Vninvest SDK Client.

High-level interface that wires together authentication, quota, caching,
metering, streaming, and vnbroker data providers.
"""

from __future__ import annotations

import time
from typing import Any

from vnbroker import Vnbroker

from .auth import APIKeyAuth
from .cache import CacheConfig, CacheLayer, create_cache_backend
from .config import get_settings
from .exceptions import ProviderError, ScopeDeniedError
from .metering import UsageTracker, create_metering_backend
from .models import (
    CompanyRequest,
    FinanceRequest,
    NewsRequest,
    PATScope,
    QuoteRequest,
    QuoteResponse,
    TenantContext,
)
from .observability import record_api_call, record_cache_hit, record_cache_miss
from .quota import QuotaContextManager, QuotaManager
from .streaming import PriceStream, StreamConfig, StreamManager, create_stream_manager


class VninvestClient:
    """
    Main client for Vninvest SaaS SDK.

    Handles:
    - Authentication (PAT - Personal Access Token)
    - Quota enforcement per tenant plan
    - Caching with tenant isolation
    - Usage metering for billing
    - Real-time streaming
    - vnbroker data provider integration

    Usage:
        client = VninvestClient(api_key="vninvest_pat_...")
        quotes = await client.quote(QuoteRequest(symbols=["ACB", "VCB"]))
        company = await client.company(CompanyRequest(symbol="ACB"))
        async for msg in client.stream(StreamConfig(...)):
            print(msg)
    """

    def __init__(
        self,
        api_key: str,
        *,
        # Auth
        auth: APIKeyAuth | None = None,
        auth_mode: str | None = None,
        auth_secret: str | None = None,
        auth_service_url: str | None = None,
        # Quota
        quota: QuotaManager | None = None,
        quota_redis_url: str | None = None,
        # Cache
        cache: CacheLayer | None = None,
        cache_redis_url: str | None = None,
        cache_config: CacheConfig | None = None,
        # Metering
        metering: UsageTracker | None = None,
        metering_redis_url: str | None = None,
        # Streaming
        stream: StreamManager | None = None,
        stream_redis_url: str | None = None,
        # vnbroker
        vnbroker_source: str | None = None,
        # Internal
        _tenant_context: TenantContext | None = None,
    ):
        """
        Initialize VninvestClient.

        Args:
            api_key: PAT token (vninvest_pat_...)
            auth: Pre-configured APIKeyAuth instance
            auth_mode: "local" or "remote" for APIKeyAuth (defaults to config)
            auth_secret: HMAC secret for local auth mode (defaults to config)
            auth_service_url: Auth service URL for remote mode (defaults to config)
            quota: Pre-configured QuotaManager instance
            quota_redis_url: Redis URL for QuotaManager (defaults to config)
            cache: Pre-configured CacheLayer instance
            cache_redis_url: Redis URL for cache backend (defaults to config)
            cache_config: CacheConfig for cache behavior (defaults to config)
            metering: Pre-configured UsageTracker instance
            metering_redis_url: Redis URL for metering backend (defaults to config)
            stream: Pre-configured StreamManager instance
            stream_redis_url: Redis URL for StreamManager (defaults to config)
            vnbroker_source: Data source for vnbroker (AUTO, VCI, KBS, etc.) (defaults to config)
            _tenant_context: Pre-resolved tenant context (for testing)
        """
        settings = get_settings()

        self._api_key = api_key
        self._vnbroker_source = vnbroker_source or settings.vnbroker.default_source

        # Initialize auth
        if auth is not None:
            self._auth = auth
        else:
            self._auth = APIKeyAuth(
                mode=auth_mode or settings.auth.mode,
                secret_key=auth_secret or settings.auth.secret_key,
                auth_service_url=auth_service_url or settings.auth.service_url,
                redis_url=quota_redis_url or cache_redis_url or metering_redis_url or stream_redis_url or settings.redis.url,
                cache_ttl_seconds=settings.auth.cache_ttl_seconds,
            )

        # Resolve tenant context
        if _tenant_context is not None:
            self.context = _tenant_context
        else:
            # This will be awaited in _initialize()
            self._context_coro = self._auth.resolve_tenant(api_key)
            self.context = None

        # Initialize vnbroker client
        self._broker = Vnbroker(source=self._vnbroker_source)

        # Initialize quota manager
        if quota is not None:
            self._quota = quota
        else:
            self._quota = QuotaManager(
                redis_url=quota_redis_url or settings.quota.redis_url or settings.redis.url,
                key_prefix=settings.quota.key_prefix,
                fallback_to_memory=settings.quota.fallback_to_memory,
            )

        # Initialize cache layer
        if cache is not None:
            self._cache = cache
        else:
            cache_backend = create_cache_backend(
                redis_url=cache_redis_url or settings.cache.redis_url or settings.redis.url,
                use_memory=(cache_redis_url or settings.cache.redis_url or settings.redis.url) is None,
                key_prefix=settings.cache.key_prefix,
                default_ttl=settings.cache.default_ttl,
                serializer=settings.cache.serializer,
            )
            self._cache = CacheLayer(
                backend=cache_backend,
                config=cache_config or CacheConfig(
                    enabled=settings.cache.enabled,
                    max_key_length=settings.cache.max_key_length,
                ),
                tenant_context=self.context,  # Will be updated after auth
            )

        # Initialize metering
        if metering is not None:
            self._metering = metering
        else:
            metering_backend = create_metering_backend(
                redis_url=metering_redis_url or settings.metering.redis_url or settings.redis.url,
                use_memory=(metering_redis_url or settings.metering.redis_url or settings.redis.url) is None,
            )
            self._metering = UsageTracker(backend=metering_backend)

        # Initialize stream manager
        if stream is not None:
            self._stream = stream
        else:
            self._stream = create_stream_manager(
                redis_url=stream_redis_url or settings.streaming.redis_url or settings.redis.url,
                max_messages_per_second=settings.streaming.max_messages_per_second,
                deduplication_window_ms=settings.streaming.deduplication_window_ms,
            )

        self._initialized = False

    async def _initialize(self) -> None:
        """Lazy initialization - resolve tenant context and update components."""
        if self._initialized:
            return

        if self.context is None:
            self.context = await self._context_coro

        # Update cache layer with resolved tenant context
        self._cache.tenant_context = self.context

        self._initialized = True

    async def close(self) -> None:
        """Close all connections and cleanup."""
        await self._auth.close()
        await self._quota.close()
        await self._cache.backend.close()
        await self._metering.close()
        await self._stream.close()

    # Scope-checking helpers

    def _require_scope(self, scope: PATScope) -> None:
        """Raise ScopeDeniedError if context doesn't have scope."""
        if not self.context.has_scope(scope):
            raise ScopeDeniedError(scope.value)

    # Quote API

    async def quote(self, request: QuoteRequest) -> list[QuoteResponse]:
        """
        Get historical/intraday quote data for symbols.

        Requires scope: quote:read
        """
        await self._initialize()
        self._require_scope(PATScope.QUOTE_READ)

        # Filter symbols based on tenant authorization
        allowed_symbols = self.context.filter_allowed_symbols(request.symbols)
        if len(allowed_symbols) != len(request.symbols):
            blocked = set(request.symbols) - set(allowed_symbols)
            raise SymbolNotAllowedError(symbol=", ".join(blocked))

        results = []
        for symbol in allowed_symbols:
            async with QuotaContextManager(self._quota, self.context, required_scope=PATScope.QUOTE_READ):
                start_time = time.time()

                # Check cache
                cache_params = request.model_dump()
                cache_params["symbol"] = symbol
                cached, hit = await self._cache.get_or_fetch(
                    data_type="quote_history",
                    endpoint="history",
                    params=cache_params,
                    fetch_func=lambda: self._fetch_quote_single(symbol, request),
                    required_scope=PATScope.QUOTE_READ,
                )

                latency_ms = int((time.time() - start_time) * 1000)

                # Record observability metrics
                if hit:
                    record_cache_hit("quote_history", self.context.tier.value)
                else:
                    record_cache_miss("quote_history", self.context.tier.value)

                record_api_call(
                    endpoint="quote.history",
                    provider=self._vnbroker_source,
                    status=200,
                    tenant_tier=self.context.tier.value,
                    latency_seconds=latency_ms / 1000.0,
                )

                # Record metering
                await self._metering.record_call(
                    context=self.context,
                    endpoint="quote.history",
                    provider=self._vnbroker_source,
                    symbols=[symbol],
                    latency_ms=latency_ms,
                    status_code=200,
                    data_bytes=0,  # Would calculate actual size
                    cache_hit=hit,
                )

                results.append(cached)

        return results

    def _fetch_quote_single(self, symbol: str, request: QuoteRequest) -> QuoteResponse:
        """Fetch quote for a single symbol using vnbroker."""
        try:
            stock = self._broker.stock(symbol, source=self._vnbroker_source)
            df = stock.quote.history(
                start=request.start_date,
                end=request.end_date,
                interval=request.interval,
                count_back=request.count_back,
                length=request.length,
                adjust_price=request.adjust_price,
            )

            return QuoteResponse(
                symbol=symbol,
                data=df if request.to_df else df.to_dict(orient="records"),
                source_used=self._vnbroker_source,
                fetched_at=time.time(),
                cache_hit=False,
                latency_ms=0,  # Will be set by caller
                row_count=len(df) if df is not None else 0,
                price_unit="VND",
            )
        except Exception as e:
            raise ProviderError(f"Failed to fetch quote for {symbol}", provider=self._vnbroker_source, original_error=e)

    # Company API

    async def company(self, request: CompanyRequest) -> dict[str, Any]:
        """
        Get company data (overview, profile, shareholders, etc.).

        Requires scope: company:read
        """
        await self._initialize()
        self._require_scope(PATScope.COMPANY_READ)

        # Check symbol authorization
        self.context.require_symbol_allowed(request.symbol)

        async with QuotaContextManager(self._quota, self.context, required_scope=PATScope.COMPANY_READ):
            start_time = time.time()

            cache_params = request.model_dump()
            cached, hit = await self._cache.get_or_fetch(
                data_type="company_overview",
                endpoint="overview",
                params=cache_params,
                fetch_func=lambda: self._fetch_company(request),
                required_scope=PATScope.COMPANY_READ,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Record observability metrics
            if hit:
                record_cache_hit("company_overview", self.context.tier.value)
            else:
                record_cache_miss("company_overview", self.context.tier.value)

            record_api_call(
                endpoint="company.overview",
                provider=self._vnbroker_source,
                status=200,
                tenant_tier=self.context.tier.value,
                latency_seconds=latency_ms / 1000.0,
            )

            await self._metering.record_call(
                context=self.context,
                endpoint="company.overview",
                provider=self._vnbroker_source,
                symbols=[request.symbol],
                latency_ms=latency_ms,
                status_code=200,
                cache_hit=hit,
            )

            return cached

    def _fetch_company(self, request: CompanyRequest) -> dict[str, Any]:
        """Fetch company data using vnbroker."""
        try:
            company = self._broker.stock(request.symbol, source=self._vnbroker_source).company
            result = {}

            if request.include_overview:
                result["overview"] = company.overview()
            if request.include_profile:
                result["profile"] = company.profile()
            if request.include_shareholders:
                result["shareholders"] = company.shareholders()
            if request.include_insiders:
                result["insiders"] = company.insiders()
            if request.include_subsidiaries:
                result["subsidiaries"] = company.subsidiaries()
            if request.include_officers:
                result["officers"] = company.officers()
            if request.include_events:
                result["events"] = company.events()

            return result
        except Exception as e:
            raise ProviderError(f"Failed to fetch company for {request.symbol}", provider=self._vnbroker_source, original_error=e)

    # Finance API

    async def finance(self, request: FinanceRequest) -> dict[str, Any]:
        """
        Get financial data (income statement, balance sheet, cash flow, ratios).

        Requires scope: finance:read
        """
        await self._initialize()
        self._require_scope(PATScope.FINANCE_READ)

        # Check symbol authorization
        self.context.require_symbol_allowed(request.symbol)

        async with QuotaContextManager(self._quota, self.context, required_scope=PATScope.FINANCE_READ):
            start_time = time.time()

            cache_params = request.model_dump()
            cached, hit = await self._cache.get_or_fetch(
                data_type="finance_report",
                endpoint="report",
                params=cache_params,
                fetch_func=lambda: self._fetch_finance(request),
                required_scope=PATScope.FINANCE_READ,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Record observability metrics
            if hit:
                record_cache_hit("finance_report", self.context.tier.value)
            else:
                record_cache_miss("finance_report", self.context.tier.value)

            record_api_call(
                endpoint="finance.report",
                provider=self._vnbroker_source,
                status=200,
                tenant_tier=self.context.tier.value,
                latency_seconds=latency_ms / 1000.0,
            )

            await self._metering.record_call(
                context=self.context,
                endpoint="finance.report",
                provider=self._vnbroker_source,
                symbols=[request.symbol],
                latency_ms=latency_ms,
                status_code=200,
                cache_hit=hit,
            )

            return cached

    def _fetch_finance(self, request: FinanceRequest) -> dict[str, Any]:
        """Fetch financial data using vnbroker."""
        try:
            finance = self._broker.stock(request.symbol, source=self._vnbroker_source).finance
            result = {}

            if request.report_type in ("all", "income_statement"):
                result["income_statement"] = finance.income_statement(period=request.period, language=request.language, limit=request.limit)
            if request.report_type in ("all", "balance_sheet"):
                result["balance_sheet"] = finance.balance_sheet(period=request.period, language=request.language, limit=request.limit)
            if request.report_type in ("all", "cash_flow"):
                result["cash_flow"] = finance.cash_flow(period=request.period, language=request.language, limit=request.limit)
            if request.report_type in ("all", "ratio"):
                result["ratios"] = finance.ratio(period=request.period, language=request.language, limit=request.limit)

            return result
        except Exception as e:
            raise ProviderError(f"Failed to fetch finance for {request.symbol}", provider=self._vnbroker_source, original_error=e)

    # News API

    async def news(self, request: NewsRequest) -> list[dict[str, Any]]:
        """
        Get news data.

        Requires scope: news:read
        """
        await self._initialize()
        self._require_scope(PATScope.NEWS_READ)

        # Check symbol authorization if symbol is specified
        if request.symbol:
            self.context.require_symbol_allowed(request.symbol)

        async with QuotaContextManager(self._quota, self.context, required_scope=PATScope.NEWS_READ):
            start_time = time.time()

            cache_params = request.model_dump()
            cached, hit = await self._cache.get_or_fetch(
                data_type="news_latest",
                endpoint="latest",
                params=cache_params,
                fetch_func=lambda: self._fetch_news(request),
                required_scope=PATScope.NEWS_READ,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Record observability metrics
            if hit:
                record_cache_hit("news_latest", self.context.tier.value)
            else:
                record_cache_miss("news_latest", self.context.tier.value)

            record_api_call(
                endpoint="news.latest",
                provider=self._vnbroker_source,
                status=200,
                tenant_tier=self.context.tier.value,
                latency_seconds=latency_ms / 1000.0,
            )

            await self._metering.record_call(
                context=self.context,
                endpoint="news.latest",
                provider=self._vnbroker_source,
                symbols=[request.symbol] if request.symbol else [],
                latency_ms=latency_ms,
                status_code=200,
                cache_hit=hit,
            )

            return cached

    def _fetch_news(self, request: NewsRequest) -> list[dict[str, Any]]:
        """Fetch news using vnbroker."""
        try:
            news_client = self._broker.news(source=self._vnbroker_source)
            if request.symbol:
                news_client = news_client.symbol(request.symbol)
            return news_client.latest(limit=request.limit)
        except Exception as e:
            raise ProviderError("Failed to fetch news", provider=self._vnbroker_source, original_error=e)

    # Streaming API

    def stream(self, config: StreamConfig) -> PriceStream:
        """
        Create a real-time price stream.

        Requires scope: stream:price (or stream:depth, stream:trade based on channels)
        """
        # Scope check done in PriceStream.subscribe()
        return PriceStream(self._stream, self.context, config)

    # Utility methods

    async def get_quota_status(self) -> dict[str, Any]:
        """Get current quota status for the tenant."""
        await self._initialize()
        return await self._quota.get_quota_status(self.context)

    async def get_cache_metrics(self) -> dict[str, Any]:
        """Get cache hit/miss metrics."""
        return self._cache.get_metrics()

    async def get_usage_metrics(self, start_date, end_date) -> Any:
        """Get usage metrics for the tenant."""
        await self._initialize()
        return await self._metering.get_usage(self.context.tenant_id, start_date, end_date)

    # Context manager support

    async def __aenter__(self) -> VninvestClient:
        await self._initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
