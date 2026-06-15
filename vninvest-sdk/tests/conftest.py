"""
Test configuration and fixtures for vninvest-sdk tests.
"""

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

import bcrypt
import fakeredis.aioredis
import pytest

from vninvest.models import PATScope, PersonalAccessToken
from vninvest.pat import PATStorage


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
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
def sample_pat_scopes():
    """Sample PAT scopes for tests."""
    return [PATScope.QUOTE_READ, PATScope.COMPANY_READ]


@pytest.fixture
def sample_pat(sample_tenant_id, sample_user_id, sample_pat_scopes):
    """Sample PAT model for tests."""
    plaintext = "vninvest_pat_testtoken123456789012"
    token_hash = bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(12)).decode()
    return PersonalAccessToken(
        tenant_id=sample_tenant_id,
        user_id=sample_user_id,
        name="Test PAT",
        token_hash=token_hash,
        prefix="vninvest_pat_testtoken",
        scopes=sample_pat_scopes,
        expires_at=datetime.utcnow() + timedelta(days=30),
    )


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
    )


@pytest.fixture
def expired_pat(sample_tenant_id, sample_user_id, sample_pat_scopes):
    """Expired PAT for testing."""
    plaintext = "vninvest_pat_expiredtoken1234567"
    token_hash = bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(12)).decode()
    return PersonalAccessToken(
        tenant_id=sample_tenant_id,
        user_id=sample_user_id,
        name="Expired PAT",
        token_hash=token_hash,
        prefix="vninvest_pat_expiredto",
        scopes=sample_pat_scopes,
        expires_at=datetime.utcnow() - timedelta(days=1),
    )


@pytest.fixture
def revoked_pat(sample_tenant_id, sample_user_id, sample_pat_scopes):
    """Revoked PAT for testing."""
    plaintext = "vninvest_pat_revokedtoken1234567"
    token_hash = bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(12)).decode()
    return PersonalAccessToken(
        tenant_id=sample_tenant_id,
        user_id=sample_user_id,
        name="Revoked PAT",
        token_hash=token_hash,
        prefix="vninvest_pat_revokedto",
        scopes=sample_pat_scopes,
        expires_at=datetime.utcnow() + timedelta(days=30),
        revoked_at=datetime.utcnow(),
    )
