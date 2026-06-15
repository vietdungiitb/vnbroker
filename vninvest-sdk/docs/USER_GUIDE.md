# Vninvest SDK User Guide

Enterprise-grade Python SDK for Vietnam stock market data with multi-tenancy, quota management, and real-time streaming.

## What is Vninvest SDK?

Vninvest SDK is a **SaaS (Software as a Service) wrapper** built on top of vnbroker that adds enterprise-grade features:

| Feature | Description |
|--------|-------------|
| **Multi-tenancy** | Serve multiple customers (tenants) from a single instance with isolated data |
| **Quota Management** | Limit API usage per customer based on pricing plan |
| **Usage Metering** | Track API calls for billing and analytics |
| **Caching** | Redis-backed caching to reduce provider costs |
| **Real-time Streaming** | WebSocket price streaming for live data |
| **PAT Authentication** | Personal Access Token-based auth with fine-grained scopes |
| **Observability** | OpenTelemetry tracing and Prometheus metrics |

### Why Use Vninvest SDK?

If you're building:
- A **SaaS product** that resells Vietnam stock data → Use vninvest-sdk
- An **internal tool** → Use vnbroker directly (simpler)

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Your Application                         │
├─────────────────────────────────────────────────────────────┤
│                      VninvestClient                        │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │  Auth   │  │  Quota  │  │  Cache  │  │ Stream │     │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘     │
└───────┼────────────┼────────────┼────────────┼───────────┘
        │            │            │            │
        ▼            ▼            ▼            ▼
   ┌─────────────────────────────────────────┐
   │              vnbroker                  │
   │    (VCI, KBS, MSN, TCBS, DNSE)        │
   └─────────────────────────────────────────┘
        │
        ▼
   ┌─────────────────────────────────────────┐
   │         Data Providers                  │
   │      Vietnam Stock Market              │
   └─────────────────────────────────────────┘
```

**Component Flow:**
1. Your app sends request with PAT token
2. Auth validates token → identifies tenant
3. Quota checks if tenant has remaining API calls
4. Cache checks if data is already cached
5. If not cached → fetch from vnbroker → cache result
6. Return data to your app

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Authentication](#authentication)
- [Architecture](#architecture)
- [API Usage](#api-usage)
  - [Quote API](#quote-api)
  - [Company API](#company-api)
  - [Finance API](#finance-api)
  - [News API](#news-api)
  - [Streaming API](#streaming-api)
- [Pricing Tiers](#pricing-tiers)
- [Error Handling](#error-handling)
- [Advanced Topics](#advanced-topics)
- [FastAPI Integration](#fastapi-integration)

---

## Installation

```bash
pip install vninvest-sdk
```

### Requirements

- Python 3.10+
- Redis (optional, for production)
- FastAPI (optional, for API server)

### Environment Variables

```bash
# Redis (required for production)
VNINVEST_REDIS_URL=redis://localhost:6379/0

# Authentication
VNINVEST_AUTH_MODE=local
VNINVEST_AUTH_SECRET=your-secret-key

# vnbroker
VNINVEST_VNBROKER_DEFAULT_SOURCE=AUTO
```

---

## Quick Start

```python
import asyncio
from vninvest import VninvestClient, QuoteRequest

async def main():
    # Initialize client with PAT token
    client = VninvestClient(api_key="vninvest_pat_...")
    
    async with client:
        # Get quote data
        request = QuoteRequest(symbols=["ACB", "VCB"])
        quotes = await client.quote(request)
        
        for quote in quotes:
            print(f"{quote.symbol}: {quote.data}")

asyncio.run(main())
```

---

## Configuration

### Settings

The SDK uses Pydantic Settings for configuration:

```python
from vninvest import Settings, get_settings

# Default settings (reads from environment)
settings = get_settings()

# Custom settings
settings = Settings(
    redis={"url": "redis://localhost:6379/0"},
    auth={"mode": "local", "secret_key": "my-secret"},
    vnbroker={"default_source": "VCI"},
)
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VNINVEST_REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `VNINVEST_AUTH_MODE` | Auth mode: local/remote | `local` |
| `VNINVEST_AUTH_SECRET` | HMAC secret for local auth | - |
| `VNINVEST_VNBROKER_DEFAULT_SOURCE` | Default data source | `AUTO` |
| `VNINVEST_ENVIRONMENT` | Environment: development/staging/production | `development` |

---

## Authentication

### PAT (Personal Access Token)

The SDK uses PAT tokens for authentication. Tokens must start with `vninvest_pat_`:

```python
client = VninvestClient(api_key="vninvest_pat_abc123...")
```

### PAT Scopes

PAT tokens can have the following scopes:

| Scope | Description |
|-------|-------------|
| `quote:read` | Read quote data |
| `company:read` | Read company data |
| `finance:read` | Read financial reports |
| `news:read` | Read news data |
| `stream:price` | Subscribe to price streams |
| `stream:depth` | Subscribe to order book depth |
| `stream:trade` | Subscribe to trade data |
| `admin:tenant` | Admin operations |

### Creating PAT Tokens

```python
from vninvest import PATStorage, PATScope, TenantTier
import uuid

async def create_pat():
    storage = PATStorage(redis_url="redis://localhost:6379/0")
    
    pat = await storage.create_pat(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="My API Token",
        scopes=[PATScope.QUOTE_READ, PATScope.COMPANY_READ],
        expires_days=90,
    )
    
    print(f"PAT Token: {pat.token}")
    # Output: vninvest_pat_...

asyncio.run(create_pat())
```

---

## API Usage

### Quote API

Get historical and intraday quote data:

```python
from vninvest import VninvestClient, QuoteRequest

client = VninvestClient(api_key="vninvest_pat_...")

request = QuoteRequest(
    symbols=["ACB", "VCB", "BIDV"],
    interval="1D",           # 1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M
    start_date="2024-01-01",
    end_date="2024-12-31",
    adjust_price=True,       # Adjust for splits/dividends
    to_df=True,              # Return as DataFrame
)

quotes = await client.quote(request)

for quote in quotes:
    print(f"Symbol: {quote.symbol}")
    print(f"Data: {quote.data}")
    print(f"Source: {quote.source_used}")
    print(f"Rows: {quote.row_count}")
```

### Company API

Get company information:

```python
from vninvest import VninvestClient, CompanyRequest

request = CompanyRequest(
    symbol="ACB",
    include_overview=True,
    include_profile=True,
    include_shareholders=True,
    include_insiders=True,
)

company = await client.company(request)

print(company["overview"])
print(company["profile"])
print(company["shareholders"])
```

### Finance API

Get financial reports:

```python
from vninvest import VninvestClient, FinanceRequest

request = FinanceRequest(
    symbol="ACB",
    report_type="all",       # income_statement, balance_sheet, cash_flow, ratio, all
    period="quarterly",     # quarterly or yearly
    language="vi",         # vi or en
    limit=10,
)

finance = await client.finance(request)

print(finance["income_statement"])
print(finance["balance_sheet"])
print(finance["cash_flow"])
print(finance["ratios"])
```

### News API

Get latest news:

```python
from vninvest import VninvestClient, NewsRequest

# By symbol
request = NewsRequest(
    symbol="ACB",
    limit=20,
)

news = await client.news(request)

# By query
request = NewsRequest(
    query="VNIndex",
    limit=10,
)

news = await client.news(request)
```

### Streaming API

Real-time price streaming:

```python
from vninvest import VninvestClient, StreamConfig

config = StreamConfig(
    symbols=["ACB", "VCB"],
    channels=["price"],       # price, depth, trade
)

stream = client.stream(config)

async for message in stream:
    print(message)
```

---

## Pricing Tiers

| Tier | Daily API Calls | Concurrent | Symbols/Request | Cache TTL | Streaming |
|------|-----------------|-------------|-----------------|----------|------------|
| Free | 1,000 | 5 | 10 | 5 min | ❌ |
| Pro | 100,000 | 50 | 100 | 1 min | ✅ |
| Enterprise | 1,000,000 | 200 | 500 | 30 sec | ✅ |

### Plan Limits

```python
from vninvest import TenantPlan, TenantTier

# Get default plan for tier
plan = TenantPlan.from_tier(TenantTier.PRO)

# Custom plan
plan = TenantPlan(
    tier=TenantTier.ENTERPRISE,
    daily_api_calls=500_000,
    concurrent_requests=100,
    symbols_per_request=200,
    cache_ttl_seconds=60,
    streaming_enabled=True,
)
```

---

## Error Handling

```python
from vninvest import (
    VninvestError,
    AuthenticationError,
    AuthorizationError,
    QuotaExceededError,
    RateLimitError,
    ScopeDeniedError,
    ProviderError,
)

try:
    quotes = await client.quote(request)
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except AuthorizationError as e:
    print(f"Authorization failed: {e}")
except QuotaExceededError as e:
    print(f"Quota exceeded: {e}")
except ScopeDeniedError as e:
    print(f"Required scope missing: {e}")
except ProviderError as e:
    print(f"Provider error: {e}")
except VninvestError as e:
    print(f"SDK error: {e}")
```

---

## Advanced Topics

### Caching

```python
from vninvest import CacheConfig, create_cache_backend, CacheLayer

# Custom cache configuration
cache_config = CacheConfig(
    enabled=True,
    max_key_length=200,
    default_ttl=300,
)

# Create cache backend
cache_backend = create_cache_backend(
    redis_url="redis://localhost:6379/0",
    key_prefix="myapp:cache",
    default_ttl=300,
    serializer="json",
)

# Use with client
client = VninvestClient(
    api_key="vninvest_pat_...",
    cache_redis_url="redis://localhost:6379/0",
    cache_config=cache_config,
)
```

### Quota Management

```python
from vninvest import QuotaManager, QuotaContextManager

quota = QuotaManager(redis_url="redis://localhost:6379/0")

# Check quota status
status = await quota.get_quota_status(context)
print(status)

# Context manager (automatic quota checking)
async with QuotaContextManager(quota, context, required_scope=PATScope.QUOTE_READ):
    # API call within quota
    quotes = await client.quote(request)
```

### Metering

```python
from vninvest import UsageTracker, create_metering_backend

metering = UsageTracker(
    backend=create_metering_backend(
        redis_url="redis://localhost:6379/0",
    )
)

# Record API call
await metering.record_call(
    context=tenant_context,
    endpoint="quote.history",
    provider="VCI",
    symbols=["ACB"],
    latency_ms=150,
    status_code=200,
    data_bytes=1024,
    cache_hit=False,
)

# Get usage metrics
metrics = await metering.get_usage(tenant_id, start_date, end_date)
print(metrics)
```

### Observability

```python
from vninvest import setup_observability, get_tracer, traced

# Setup OpenTelemetry
setup_observability(settings.observability)

# Using decorator
@traced
async def my_api_call():
    # ... API call
    pass

# Manual tracing
tracer = get_tracer()
with tracer.start_as_current_span("my-operation") as span:
    # ... operation
    span.set_attribute("key", "value")
```

---

## FastAPI Integration

### Basic Setup

```python
from vninvest_fastapi import create_app
from vninvest import Settings

settings = Settings(
    redis={"url": "redis://localhost:6379/0"},
    auth={"mode": "local", "secret_key": "my-secret"},
)

app = create_app(settings)

# Run with uvicorn
# uvicorn vninvest_fastapi.main:app --host 0.0.0.0 --port 8000
```

### Using Dependencies

```python
from fastapi import Depends
from vninvest import get_tenant_context, require_quote_read, TenantContext

@app.get("/api/v1/quote")
async def get_quote(
    context: TenantContext = Depends(require_quote_read),
):
    # context is the resolved tenant
    return {"tenant_id": str(context.tenant_id)}
```

### API Endpoints

Once the FastAPI app is running:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/quote` | POST | Get quote data |
| `/api/v1/company` | POST | Get company data |
| `/api/v1/finance` | POST | Get financial data |
| `/api/v1/news` | POST | Get news |
| `/api/v1/stream/ws` | WebSocket | Real-time stream |
| `/api/v1/admin/tenants` | GET | List tenants |
| `/api/v1/admin/health` | GET | System health |
| `/health` | GET | Health check |

### Example Request

```python
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        # With Bearer token
        response = await client.post(
            "http://localhost:8000/api/v1/quote",
            json={
                "symbols": ["ACB", "VCB"],
                "interval": "1D",
            },
            headers={
                "Authorization": "Bearer vninvest_pat_..."
            }
        )
        
        print(response.json())

asyncio.run(main())
```

---

## Support

- Documentation: https://github.com/vnstock/vnbrokder
- Issues: https://github.com/vnstock/vnbrokder/issues
- License: MIT
