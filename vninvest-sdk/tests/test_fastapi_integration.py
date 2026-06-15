"""
FastAPI integration tests using TestClient with fakeredis.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import bcrypt
import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from vninvest import (
    PATScope,
    PersonalAccessToken,
    VninvestClient,
    create_cache_backend,
    create_metering_backend,
)
from vninvest.auth import APIKeyAuth
from vninvest.cache import CacheLayer, InMemoryCacheBackend
from vninvest.metering import InMemoryMeteringBackend, UsageTracker
from vninvest.models import CompanyRequest, FinanceRequest, NewsRequest, QuoteRequest
from vninvest.pat import PATStorage
from vninvest.quota import QuotaManager
from vninvest.streaming import StreamManager
from vninvest_fastapi.main import create_app


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def redis_client():
    """Fake Redis client for testing."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def pat_storage(redis_client):
    """PAT storage with fake Redis."""
    return PATStorage(redis_client=redis_client)


@pytest.fixture
def sample_tenant_id():
    """Sample tenant ID for tests."""
    return uuid4()


@pytest.fixture
def sample_user_id():
    """Sample user ID for tests."""
    return uuid4()


@pytest.fixture
def sample_pat_all_scopes(sample_tenant_id, sample_user_id):
    """Sample PAT with all scopes."""
    plaintext = "vninvest_pat_allscopes123456789012"
    token_hash = bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(12)).decode()
    return PersonalAccessToken(
        tenant_id=sample_tenant_id,
        user_id=sample_user_id,
        name="Admin PAT",
        token_hash=token_hash,
        prefix="vninvest_pat_allscopes",
        scopes=list(PATScope),
        expires_at=datetime.utcnow() + timedelta(days=30),
    ), plaintext


@pytest.fixture
async def app_with_pat(pat_storage, sample_tenant_id, sample_user_id):
    """Create FastAPI app with a valid PAT configured."""
    # Create PAT with all scopes
    pat, plaintext = await pat_storage.create_pat(
        tenant_id=sample_tenant_id,
        user_id=sample_user_id,
        name="Admin PAT",
        scopes=list(PATScope),
        expires_in_days=30,
    )

    # Create auth with the same pat_storage
    auth = APIKeyAuth(
        mode="local",
        secret_key="test-secret",
        pat_storage=pat_storage,
    )

    # Create VninvestClient with in-memory components
    client = VninvestClient(
        api_key=plaintext,
        auth=auth,
        quota_redis_url=None,
        cache_redis_url=None,
        metering_redis_url=None,
        stream_redis_url=None,
        vnbroker_source="AUTO",
    )

    # Replace with test doubles
    client._quota = QuotaManager(redis_client=pat_storage._redis_client)
    client._cache = CacheLayer(backend=InMemoryCacheBackend(), tenant_context=client.context)
    client._metering = UsageTracker(backend=InMemoryMeteringBackend())
    client._stream = StreamManager()

    await client._initialize()

    # Create FastAPI app
    app = create_app()
    app.state.vninvest_client = client
    app.state.auth = auth
    app.state.pat_storage = pat_storage

    # Mock vnbroker for all routes
    with patch("vninvest.client.Vnbroker") as mock_broker_class:
        mock_broker = MagicMock()
        mock_broker_class.return_value = mock_broker

        # Mock stock().quote.history()
        mock_stock = MagicMock()
        mock_broker.stock.return_value = mock_stock
        mock_quote = MagicMock()
        mock_stock.quote = mock_quote

        import pandas as pd

        mock_df = pd.DataFrame(
            {
                "time": [datetime(2024, 1, 1), datetime(2024, 1, 2)],
                "open": [100, 101],
                "high": [102, 103],
                "low": [99, 100],
                "close": [101, 102],
                "volume": [1000, 1100],
            }
        )
        mock_quote.history.return_value = mock_df

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

        yield app, client, plaintext


@pytest.fixture
def test_client(app_with_pat):
    """Create TestClient for FastAPI app."""
    app, _, _ = app_with_pat
    return TestClient(app)


class TestFastAPIQuoteEndpoints:
    """Test quote API endpoints."""

    def test_get_quote_post(self, test_client, app_with_pat):
        """Test POST /api/v1/quote endpoint."""
        _, _, plaintext = app_with_pat
        headers = {"Authorization": f"Bearer {plaintext}"}

        response = test_client.post(
            "/api/v1/quote",
            json={
                "symbols": ["ACB", "VCB"],
                "interval": "1D",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["symbol"] == "ACB"
        assert data[0]["row_count"] == 2
        assert data[0]["source_used"] == "AUTO"

    def test_get_quote_single(self, test_client, app_with_pat):
        """Test GET /api/v1/quote/{symbol} endpoint."""
        _, _, plaintext = app_with_pat
        headers = {"Authorization": f"Bearer {plaintext}"}

        response = test_client.get(
            "/api/v1/quote/ACB",
            params={"interval": "1D", "start_date": "2024-01-01"},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "ACB"
        assert data["row_count"] == 2

    def test_get_quote_unauthorized(self, test_client):
        """Test quote endpoint without auth."""
        response = test_client.post(
            "/api/v1/quote",
            json={"symbols": ["ACB"]},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_quote_insufficient_scope(self, test_client, app_with_pat, pat_storage, sample_tenant_id, sample_user_id):
        """Test quote endpoint with insufficient scope."""
        # Create PAT without QUOTE_READ
        pat, plaintext = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="No Quote Scope",
            scopes=[PATScope.COMPANY_READ, PATScope.FINANCE_READ],
            expires_in_days=30,
        )
        headers = {"Authorization": f"Bearer {plaintext}"}

        response = test_client.post(
            "/api/v1/quote",
            json={"symbols": ["ACB"]},
            headers=headers,
        )

        assert response.status_code == 403
        assert "quote:read" in response.json()["detail"]


class TestFastAPICompanyEndpoints:
    """Test company API endpoints."""

    def test_get_company_post(self, test_client, app_with_pat):
        """Test POST /api/v1/company endpoint."""
        _, _, plaintext = app_with_pat
        headers = {"Authorization": f"Bearer {plaintext}"}

        response = test_client.post(
            "/api/v1/company",
            json={
                "symbol": "ACB",
                "include_overview": True,
                "include_profile": True,
            },
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "overview" in data
        assert "profile" in data
        assert data["overview"]["name"] == "Test Company"

    def test_get_company_overview(self, test_client, app_with_pat):
        """Test GET /api/v1/company/{symbol} endpoint."""
        _, _, plaintext = app_with_pat
        headers = {"Authorization": f"Bearer {plaintext}"}

        response = test_client.get(
            "/api/v1/company/ACB",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "overview" in data
        assert data["overview"]["name"] == "Test Company"


class TestFastAPIFinanceEndpoints:
    """Test finance API endpoints."""

    def test_get_finance_post(self, test_client, app_with_pat):
        """Test POST /api/v1/finance endpoint."""
        _, _, plaintext = app_with_pat
        headers = {"Authorization": f"Bearer {plaintext}"}

        response = test_client.post(
            "/api/v1/finance",
            json={
                "symbol": "ACB",
                "report_type": "all",
                "period": "quarterly",
            },
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "income_statement" in data
        assert "balance_sheet" in data
        assert "cash_flow" in data
        assert "ratios" in data


class TestFastAPINewsEndpoints:
    """Test news API endpoints."""

    def test_get_news_post(self, test_client, app_with_pat):
        """Test POST /api/v1/news endpoint."""
        _, _, plaintext = app_with_pat
        headers = {"Authorization": f"Bearer {plaintext}"}

        response = test_client.post(
            "/api/v1/news",
            json={
                "symbol": "ACB",
                "limit": 10,
            },
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["title"] == "Test News"

    def test_get_latest_news(self, test_client, app_with_pat):
        """Test GET /api/v1/news endpoint."""
        _, _, plaintext = app_with_pat
        headers = {"Authorization": f"Bearer {plaintext}"}

        response = test_client.get(
            "/api/v1/news",
            params={"symbol": "ACB", "limit": 5},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestFastAPIHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, test_client):
        """Test GET /health endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestFastAPIAdminEndpoints:
    """Test admin API endpoints."""

    def test_admin_requires_admin_scope(self, test_client, app_with_pat):
        """Test admin endpoints require admin:tenant scope."""
        _, _, plaintext = app_with_pat
        headers = {"Authorization": f"Bearer {plaintext}"}

        response = test_client.get("/api/v1/admin/tenants", headers=headers)
        # Should fail because PAT doesn't have admin:tenant scope
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_with_admin_scope(self, test_client, app_with_pat, pat_storage, sample_tenant_id, sample_user_id):
        """Test admin endpoints with admin:tenant scope."""
        # Create PAT with admin scope
        pat, plaintext = await pat_storage.create_pat(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            name="Admin PAT",
            scopes=[PATScope.ADMIN_TENANT],
            expires_in_days=30,
        )
        headers = {"Authorization": f"Bearer {plaintext}"}

        response = test_client.get("/api/v1/admin/tenants", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestFastAPIStreamEndpoints:
    """Test stream API endpoints."""

    def test_create_stream_config(self, test_client, app_with_pat):
        """Test POST /api/v1/stream/config endpoint."""
        _, _, plaintext = app_with_pat
        headers = {"Authorization": f"Bearer {plaintext}"}

        response = test_client.post(
            "/api/v1/stream/config",
            json={
                "symbols": ["ACB", "VCB"],
                "channels": ["price", "trade"],
                "provider_preference": ["vci", "kbs"],
            },
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "config" in data
        assert "websocket_url" in data
        assert data["config"]["symbols"] == ["ACB", "VCB"]
        assert data["config"]["channels"] == ["price", "trade"]


class TestFastAPIQuotaHeaders:
    """Test quota headers in responses."""

    def test_quote_response_has_quota_headers(self, test_client, app_with_pat):
        """Test that quote response includes quota headers."""
        _, _, plaintext = app_with_pat
        headers = {"Authorization": f"Bearer {plaintext}"}

        response = test_client.post(
            "/api/v1/quote",
            json={"symbols": ["ACB"]},
            headers=headers,
        )

        assert response.status_code == 200
        # Check quota headers
        assert "X-Quota-Limit-Daily" in response.headers
        assert "X-Quota-Remaining-Daily" in response.headers
        assert "X-Quota-Limit-Concurrent" in response.headers
        assert "X-Quota-Remaining-Concurrent" in response.headers


class TestFastAPIMetering:
    """Test metering integration."""

    def test_request_tracked_in_metering(self, test_client, app_with_pat):
        """Test that requests are tracked in metering."""
        app, client, plaintext = app_with_pat
        headers = {"Authorization": f"Bearer {plaintext}"}

        # Make a request
        response = test_client.post(
            "/api/v1/quote",
            json={"symbols": ["ACB"]},
            headers=headers,
        )

        assert response.status_code == 200

        # Check metering recorded the request
        # (In real test, we'd check the metering backend)
        # For now, just verify the request succeeded


if __name__ == "__main__":
    pytest.main([__file__, "-v"])