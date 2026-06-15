"""
Integration tests for VninvestClient full flow.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from vninvest.auth import APIKeyAuth
from vninvest.cache import CacheLayer, InMemoryCacheBackend
from vninvest.client import VninvestClient
from vninvest.exceptions import ProviderError, ScopeDeniedError
from vninvest.metering import InMemoryMeteringBackend, UsageTracker
from vninvest.models import (
    CompanyRequest,
    FinanceRequest,
    NewsRequest,
    PATScope,
    QuoteRequest,
)
from vninvest.quota import QuotaManager
from vninvest.streaming import StreamConfig, StreamManager


class TestVninvestClient:
    """Integration tests for VninvestClient."""

    @pytest.fixture
    def mock_vnbroker(self):
        """Mock vnbroker.Vnbroker and its sub-components."""
        with patch("vninvest.client.Vnbroker") as mock_broker_class:
            mock_broker = MagicMock()
            mock_broker_class.return_value = mock_broker

            # Mock stock().quote.history()
            mock_stock = MagicMock()
            mock_broker.stock.return_value = mock_stock
            mock_quote = MagicMock()
            mock_stock.quote = mock_quote

            # Create a mock DataFrame
            import pandas as pd
            mock_df = MagicMock(spec=pd.DataFrame)
            mock_df.to_dict = MagicMock(return_value=[{"time": "2024-01-01", "close": 100}])
            mock_df.__len__ = MagicMock(return_value=2)

            mock_quote.history = MagicMock(return_value=mock_df)

            # Mock stock().company
            mock_company = MagicMock()
            mock_stock.company = mock_company
            mock_company.overview = MagicMock(return_value={"name": "Test Company"})
            mock_company.profile = MagicMock(return_value={"description": "Test"})
            mock_company.shareholders = MagicMock(return_value=[])
            mock_company.insiders = MagicMock(return_value=[])
            mock_company.subsidiaries = MagicMock(return_value=[])
            mock_company.officers = MagicMock(return_value=[])
            mock_company.events = MagicMock(return_value=[])

            # Mock stock().finance
            mock_finance = MagicMock()
            mock_stock.finance = mock_finance
            mock_finance.income_statement = MagicMock(return_value=[])
            mock_finance.balance_sheet = MagicMock(return_value=[])
            mock_finance.cash_flow = MagicMock(return_value=[])
            mock_finance.ratio = MagicMock(return_value=[])

            # Mock news
            mock_news = MagicMock()
            mock_broker.news.return_value = mock_news
            mock_news.symbol.return_value = mock_news
            mock_news.latest = MagicMock(return_value=[{"title": "Test News"}])

            yield mock_broker

    @pytest.fixture
    async def client_with_pat(self, pat_storage, sample_tenant_id, sample_user_id, mock_vnbroker):
        """Create a VninvestClient with a valid PAT."""
        # Create PAT
        pat, plaintext = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="Test Client PAT",
            scopes=list(PATScope),  # All scopes
            expires_in_days=30,
        )

        # Create auth with the same pat_storage
        auth = APIKeyAuth(
            mode="local",
            secret_key="test-secret",
            pat_storage=pat_storage,
        )

        # Create client with in-memory components for testing
        client = VninvestClient(
            api_key=plaintext,
            auth=auth,  # Use pre-configured auth
            quota_redis_url=None,  # Use in-memory
            cache_redis_url=None,  # Use in-memory
            metering_redis_url=None,  # Use in-memory
            stream_redis_url=None,  # Use in-memory
            vnbroker_source="AUTO",
        )

        # Replace with test doubles
        client._quota = QuotaManager(redis_client=pat_storage._redis_client)
        client._cache = CacheLayer(backend=InMemoryCacheBackend(), tenant_context=client.context)
        client._metering = UsageTracker(backend=InMemoryMeteringBackend())
        client._stream = StreamManager()

        await client._initialize()
        return client, pat, plaintext

    @pytest.mark.asyncio
    async def test_client_initialization(self, client_with_pat):
        """Test client initializes correctly with PAT."""
        client, pat, plaintext = client_with_pat

        assert client.context is not None
        assert client.context.tenant_id == pat.tenant_id
        assert client.context.pat_id == pat.pat_id
        assert client.context.user_id == pat.user_id
        assert len(client.context.effective_scopes) == len(PATScope)

    @pytest.mark.asyncio
    async def test_quote_method(self, client_with_pat, mock_vnbroker):
        """Test quote() method."""
        client, _, _ = client_with_pat

        # Mock the DataFrame returned by vnbroker
        import pandas as pd
        mock_df = pd.DataFrame({
            "time": [datetime(2024, 1, 1), datetime(2024, 1, 2)],
            "open": [100, 101],
            "high": [102, 103],
            "low": [99, 100],
            "close": [101, 102],
            "volume": [1000, 1100],
        })
        mock_vnbroker.stock.return_value.quote.history.return_value = mock_df

        request = QuoteRequest(symbols=["ACB"], interval="1D", start_date="2024-01-01", end_date="2024-01-31")
        results = await client.quote(request)

        assert len(results) == 1
        assert results[0].symbol == "ACB"
        assert results[0].row_count == 2
        assert results[0].source_used == "AUTO"

    @pytest.mark.asyncio
    async def test_quote_method_multiple_symbols(self, client_with_pat, mock_vnbroker):
        """Test quote() with multiple symbols."""
        client, _, _ = client_with_pat

        import pandas as pd
        mock_df = pd.DataFrame({"time": [datetime(2024, 1, 1)], "close": [100]})
        mock_vnbroker.stock.return_value.quote.history.return_value = mock_df

        request = QuoteRequest(symbols=["ACB", "VCB", "BID"], interval="1D")
        results = await client.quote(request)

        assert len(results) == 3
        symbols = {r.symbol for r in results}
        assert symbols == {"ACB", "VCB", "BID"}

    @pytest.mark.asyncio
    async def test_quote_scope_denied(self, pat_storage, sample_tenant_id, sample_user_id, mock_vnbroker):
        """Test quote() fails without quote:read scope."""
        # Create PAT without QUOTE_READ
        pat, plaintext = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="No Quote Scope",
            scopes=[PATScope.COMPANY_READ, PATScope.FINANCE_READ],
        )

        # Create auth with the same pat_storage
        auth = APIKeyAuth(
            mode="local",
            secret_key="test-secret",
            pat_storage=pat_storage,
        )

        client = VninvestClient(
            api_key=plaintext,
            auth=auth,
            quota_redis_url=None,
            cache_redis_url=None,
            metering_redis_url=None,
            stream_redis_url=None,
        )
        client._quota = QuotaManager(redis_client=pat_storage._redis_client)
        client._cache = CacheLayer(backend=InMemoryCacheBackend(), tenant_context=client.context)
        client._metering = UsageTracker(backend=InMemoryMeteringBackend())
        await client._initialize()

        request = QuoteRequest(symbols=["ACB"])
        with pytest.raises(ScopeDeniedError, match="quote:read"):
            await client.quote(request)

    @pytest.mark.asyncio
    async def test_company_method(self, client_with_pat, mock_vnbroker):
        """Test company() method."""
        client, _, _ = client_with_pat

        request = CompanyRequest(symbol="ACB", include_overview=True, include_profile=True)
        result = await client.company(request)

        assert "overview" in result
        assert "profile" in result
        assert result["overview"]["name"] == "Test Company"

    @pytest.mark.asyncio
    async def test_company_scope_denied(self, pat_storage, sample_tenant_id, sample_user_id, mock_vnbroker):
        """Test company() fails without company:read scope."""
        pat, plaintext = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="No Company Scope",
            scopes=[PATScope.QUOTE_READ, PATScope.FINANCE_READ],
        )

        # Create auth with the same pat_storage
        auth = APIKeyAuth(
            mode="local",
            secret_key="test-secret",
            pat_storage=pat_storage,
        )

        client = VninvestClient(
            api_key=plaintext,
            auth=auth,
            quota_redis_url=None,
            cache_redis_url=None,
            metering_redis_url=None,
            stream_redis_url=None,
        )
        client._quota = QuotaManager(redis_client=pat_storage._redis_client)
        client._cache = CacheLayer(backend=InMemoryCacheBackend(), tenant_context=client.context)
        client._metering = UsageTracker(backend=InMemoryMeteringBackend())
        await client._initialize()

        request = CompanyRequest(symbol="ACB")
        with pytest.raises(ScopeDeniedError, match="company:read"):
            await client.company(request)

    @pytest.mark.asyncio
    async def test_finance_method(self, client_with_pat, mock_vnbroker):
        """Test finance() method."""
        client, _, _ = client_with_pat

        request = FinanceRequest(symbol="ACB", report_type="all", period="quarterly")
        result = await client.finance(request)

        assert "income_statement" in result
        assert "balance_sheet" in result
        assert "cash_flow" in result
        assert "ratios" in result

    @pytest.mark.asyncio
    async def test_finance_scope_denied(self, pat_storage, sample_tenant_id, sample_user_id, mock_vnbroker):
        """Test finance() fails without finance:read scope."""
        pat, plaintext = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="No Finance Scope",
            scopes=[PATScope.QUOTE_READ, PATScope.COMPANY_READ],
        )

        # Create auth with the same pat_storage
        auth = APIKeyAuth(
            mode="local",
            secret_key="test-secret",
            pat_storage=pat_storage,
        )

        client = VninvestClient(
            api_key=plaintext,
            auth=auth,
            quota_redis_url=None,
            cache_redis_url=None,
            metering_redis_url=None,
            stream_redis_url=None,
        )
        client._quota = QuotaManager(redis_client=pat_storage._redis_client)
        client._cache = CacheLayer(backend=InMemoryCacheBackend(), tenant_context=client.context)
        client._metering = UsageTracker(backend=InMemoryMeteringBackend())
        await client._initialize()

        request = FinanceRequest(symbol="ACB")
        with pytest.raises(ScopeDeniedError, match="finance:read"):
            await client.finance(request)

    @pytest.mark.asyncio
    async def test_news_method(self, client_with_pat, mock_vnbroker):
        """Test news() method."""
        client, _, _ = client_with_pat

        request = NewsRequest(symbol="ACB", limit=10)
        result = await client.news(request)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["title"] == "Test News"

    @pytest.mark.asyncio
    async def test_news_scope_denied(self, pat_storage, sample_tenant_id, sample_user_id, mock_vnbroker):
        """Test news() fails without news:read scope."""
        pat, plaintext = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="No News Scope",
            scopes=[PATScope.QUOTE_READ, PATScope.COMPANY_READ],
        )

        # Create auth with the same pat_storage
        auth = APIKeyAuth(
            mode="local",
            secret_key="test-secret",
            pat_storage=pat_storage,
        )

        client = VninvestClient(
            api_key=plaintext,
            auth=auth,
            quota_redis_url=None,
            cache_redis_url=None,
            metering_redis_url=None,
            stream_redis_url=None,
        )
        client._quota = QuotaManager(redis_client=pat_storage._redis_client)
        client._cache = CacheLayer(backend=InMemoryCacheBackend(), tenant_context=client.context)
        client._metering = UsageTracker(backend=InMemoryMeteringBackend())
        await client._initialize()

        request = NewsRequest(symbol="ACB")
        with pytest.raises(ScopeDeniedError, match="news:read"):
            await client.news(request)

    @pytest.mark.asyncio
    async def test_stream_method(self, client_with_pat):
        """Test stream() method returns PriceStream."""
        client, _, _ = client_with_pat

        config = StreamConfig(
            tenant_id=client.context.tenant_id,
            symbols=["ACB", "VCB"],
            channels=["price", "trade"],
        )

        stream = client.stream(config)
        assert stream is not None
        assert stream.tenant_context == client.context

    @pytest.mark.asyncio
    async def test_context_manager(self, client_with_pat):
        """Test async context manager."""
        client, _, _ = client_with_pat

        async with client as c:
            assert c is client
            assert c.context is not None

        # After exit, client should be closed (but we don't verify close here)

    @pytest.mark.asyncio
    async def test_get_quota_status(self, client_with_pat):
        """Test get_quota_status()."""
        client, _, _ = client_with_pat

        status = await client.get_quota_status()
        assert "tenant_id" in status
        assert "limits" in status
        assert "usage" in status

    @pytest.mark.asyncio
    async def test_get_cache_metrics(self, client_with_pat):
        """Test get_cache_metrics()."""
        client, _, _ = client_with_pat

        metrics = await client.get_cache_metrics()
        assert "hits" in metrics
        assert "misses" in metrics
        assert "hit_rate_pct" in metrics

    @pytest.mark.asyncio
    async def test_provider_error_propagation(self, client_with_pat, mock_vnbroker):
        """Test that vnbroker errors are wrapped in ProviderError."""
        client, _, _ = client_with_pat

        mock_vnbroker.stock.return_value.quote.history.side_effect = Exception("Upstream error")

        request = QuoteRequest(symbols=["ACB"])
        with pytest.raises(ProviderError, match="Failed to fetch quote"):
            await client.quote(request)
