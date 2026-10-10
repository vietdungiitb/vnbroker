# vnbroker - Project Instructions

> ⚠ **ĐỌC TRƯỚC MỌI VIỆC — repo này nối tài khoản chứng khoán thật.**
> Nạp skill [`project-lessons`](.opencode/skills/project-lessons/SKILL.md) **trước khi**
> lập kế hoạch / khai claim / sửa dòng code đầu tiên. Skill chỉ đọc 1–2 nhóm lesson theo
> tag (không đọc hết) và trả về `MANDATORY CHECKLIST` phải được tick.
> - Chạm `vnbroker/broker/**`, `money`, `write`, `token`, `order`, `tcbs`
>   → **luôn** nạp [`docs/LESSONS/broker-risk.md`](docs/LESSONS/broker-risk.md).
> - Đo lường, bằng chứng, spec, gate → [`docs/LESSONS/evidence.md`](docs/LESSONS/evidence.md).
> - Chia việc, worktree, claim, ngân sách dòng → [`docs/LESSONS/process.md`](docs/LESSONS/process.md).
>
> Mọi plan phải có dòng `Lessons áp dụng: [L-...]` hoặc `Lessons áp dụng: NONE - <lý do>`.
> Cổng gate: `.venv\Scripts\python.exe scripts\check_lessons.py` (chạy trong `check_all.ps1`).

## Tech Stack
- Language: Python 3.10+
- Core: requests, pandas, beautifulsoup4, pydantic, tenacity
- Testing: pytest, pytest-cov, pytest-timeout
- Type checking: mypy (strict)
- Linting: ruff, flake8

## Code Style
- snake_case cho functions/variables
- PascalCase cho classes
- Type hints bắt buộc (mypy strict)
- Immutability: prefer dataclasses/frozen, spread over mutation
- File size: 200-400 lines typical, 800 max
- Docstrings: Google style cho public APIs

## Architecture: Direct Provider Architecture (v3.0+)

### Core Principles
- **Two-tier data model (v3.5.0)**:
  - **Tier 1 — anonymous market data.** User does NOT pick a provider; the system
    prefers the most stable one and rotates on rate-limit / connection loss.
    Enable with `Market(auto=True)` or `Vnbroker(source="AUTO")`. Failover covers
    `history`, `intraday`, `price_depth`. Default stays `"KBS"` for compatibility.
    Providers: VCI, KBS (no auth required), **plus TCBS and DNSE when their
    credentials are present in `.env`** — Owner decision 2026-10-10: both now
    serve public market data on equal footing and must not be excluded.
    ⚠ Auto-detection was **broken until 2026-10-10**, three separate ways, all
    measured and all fixed: (a) `get_auto_candidates()` used a hardcoded list, so
    `screener` returned `[]` while the registry had `kbs`/`vci`; (b)
    `ProviderPool` demanded `TCBS_API_SECRET`, a variable that exists nowhere in
    production; (c) `explorer/tcbs/auth.py` read only `TCBS_AUTH_TOKEN` (a 48-char
    non-JWT that the server rejects with HTTP 401) and never read
    `TCBS_JWT_TOKEN` (a real 1290-char JWT that returns HTTP 200).
    Gate: `scripts/check_provider_consistency.py` (+ `--self-test`).
    See `docs/REPORT_TIER1_WAVE12.md` and `docs/PLAN_TIER1_WAVE12_EXECUTION.md`.
    ⚠ **DNSE is not verified working.** Measured 2026-10-10: the TLS handshake to
    `openapi.dnse.com.vn` **times out** from this host, so every DNSE market-data
    call raises `ConnectionResetError(10054)`. It may serve traffic as a candidate
    in `AUTO` only because the router health-checks first; never describe DNSE as
    "stable" without a fresh measurement.
  - **Tier 2 — personalized broker data.** Provider is chosen EXPLICITLY, each
    broker keeps its own OpenAPI shape (SSI RSA/ConsumerID + fixed IP, TCBS API
    Key + OTP, DNSE HMAC). Do NOT force these behind one interface.
  - Contract enforced by `tests/contract/`: all anonymous providers must return
    the same schema (`time` tz-aware `Asia/Ho_Chi_Minh`, required columns, no rows
    outside `[start, end]`).
    **Single enforcement point: `vnbroker/core/utils/normalizer.py::Normalizer`.**
    Three defects made this false until 2026-10-10, all fixed and all now locked
    by `tests/contract/test_normalizer_contract.py`:
    1. *Two copies* of the normalizer (`core/utils/normalizer.py` and
       `common/data.py::_normalize_quote_result`) that could drift apart.
       `common/data.py` now delegates — it is a call site, not an implementation.
    2. *`api/quote.py` bypassed both* (and `api/bulk.py` `pd.concat`-ed raw
       frames). Both now route through `Normalizer`.
    3. *tz-aware was not enough.* pandas ≥2 keeps the source **unit**, so KBS
       returned `datetime64[us, Asia/Ho_Chi_Minh]` and VCI
       `datetime64[s, Asia/Ho_Chi_Minh]`. Both are tz-aware; `pd.concat` of the
       two live frames still produced `dtype=object`, silently breaking every
       downstream time operation. The Normalizer now casts to one unit,
       `datetime64[ns, Asia/Ho_Chi_Minh]`.
    4. *`match_type` was not normalized.* `process_match_types`
       (`core/utils/transform.py`) already maps every provider spelling to
       `Buy`/`Sell`/`unknown`, but `explorer/kbs/quote.py` called `.str.lower()`
       on the next line and undid it — so `df[df.match_type == "Buy"]` returned
       **0 rows from KBS** and 67 from VCI for the same session.
    Tracking: `docs/REPORT_TIER1_WAVE12.md`, `docs/PLAN_TIER1_WAVE12_EXECUTION.md`.
- **No PAT/Gateway**: Direct access to provider APIs (VCI, KBS, TCBS, DNSE)
- **Adapter Pattern**: `BaseAdapter` with dynamic method delegation to provider-specific explorers
- **Provider Registry**: Centralized provider discovery via `ProviderRegistry`
- **Source Router**: Health-based failover with cooldown, exponential backoff, per-module primary pools
- **Lazy Loading**: Circular import avoidance via `_ensure_explorer_modules_loaded()`

### Project Structure
```
vnbroker/
├── __init__.py           # Main entry: Vnbroker class, lazy imports
├── base.py               # BaseAdapter, dynamic_method, ProviderRegistry
├── config.py             # Config, VERSION_REQUIREMENTS, upgrade notices
├── constants.py          # Market constants (indices, sectors, exchanges)
├── common/
│   ├── client.py         # Vnbroker main class, StockComponents, Fund
│   └── data.py           # BaseComponent, Quote, Company, Finance, Listing, Trading, News, Screener, Fund
├── core/
│   ├── registry.py       # ProviderRegistry
│   ├── source_router.py  # AUTO source, health-based failover
│   ├── dispatch.py       # Legacy Gateway fallback (deprecated, removable)
│   ├── exceptions.py     # Custom exceptions
│   └── utils/            # Logger, parser, upgrade checker
├── explorer/             # Market data providers (Direct Provider)
│   ├── vci/              # Viet Capital Securities
│   ├── kbs/              # KIS Vietnam Securities
│   ├── tcbs/             # Techcombank Securities
│   ├── dnse/             # Định Nghĩa Securities (HMAC auth)
│   ├── rss_cafef/        # RSS news source
│   ├── rss_vneconomy/    # RSS news source
│   └── fmarket/          # Fund data
├── ui/                   # Unified UI (Market/Reference/Fundamental/Retail/show_api)
├── common/
│   └── retail.py         # Retail facade (SJC/BTMC gold, VCB exchange rate)
├── broker/               # Brokerage Lane - Official OpenAPI
│   ├── tcbs/             # TCBS iFlash OpenAPI v1.0.0
│   ├── ssi/              # SSI FastConnect v3 native (auth/account/money/equity/
│   │                      #   market/portfolio/fco/stream/client, ký RSA, WS)
│   ├── base.py           # BaseBrokerClient
│   ├── registry.py       # BrokerRegistry (tcbs + ssi)
│   └── session.py        # BrokerSession, SessionState
├── brokerage/            # Brokerage Lane - Private APIs
│   ├── tcbs/             # TCBS Private API (HMAC-SHA256 + WebSocket)
│   └── base.py           # BrokerageBase (abstract)
├── connector/            # Low-level broker connectors
│   └── dnse/             # DNSE HMAC OpenAPI + JWT Trade client
├── analytics/            # Technical indicators (TODO: implement)
│   └── indicators.py     # Currently empty
├── bot/
│   └── notify.py         # Messenger (Slack, Telegram, Discord, Lark)
└── news/                 # News normalization, dedup, filtering
    ├── normalize.py
    ├── dedup.py
    └── filtering.py
```

### Key Components

> Ghi chú tên: thư mục `broker/` và `connector/` là **tầng 2** (broker lane, tường minh).
> `explorer/` + `common/` là **tầng 1** (dữ liệu ẩn danh, auto-failover).
> `trading` module trong explorer (bảng giá) là tầng 1, KHÁC với đặt lệnh.

#### Vnbroker (Main Entry)
```python
from vnbroker import Vnbroker

vn = Vnbroker(source="KBS")  # Default: KBS
acb = vn.stock("ACB")        # StockComponents with quote, company, finance, etc.
history = acb.quote.history(start="2024-01-01", end="2024-12-31")
overview = acb.company.overview()
finance = acb.finance.ratio()
news = acb.news.latest()
```

#### Supported Sources (Market Data)
| Source | Quote | Company | Finance | Listing | Trading | News | Auth |
|--------|-------|---------|---------|---------|---------|------|------|
| VCI    | ✅    | ✅      | ✅      | ✅      | ✅      | ✅   | None |
| KBS    | ✅    | ✅      | ✅      | ✅      | ✅      | ✅   | None |
| TCBS   | ✅    | ✅      | ✅      | ✅      | ✅      | ✅   | None |
| DNSE   | ✅    | ❌ NotImpl | ❌ NotImpl | ✅      | ✅      | ❌   | HMAC |

#### Brokerage (Private API) — Two TCBS Implementations

**Option 1: TCBS iFlash OpenAPI v1.0.0 (Official - `vnbroker.broker.tcbs`)**
- Production-ready, comprehensive test coverage (1001 tests)
- Auth: OTP + API Key
- Endpoints: `/tartarus/v1/...`, `/erebos/v1/...`
- Features: Full account, money, equity, derivatives, portfolio, market data

```python
from vnbroker import Vnbroker

vn = Vnbroker()
client = vn.broker(provider="tcbs", api_key="your_tcbs_openapi_key")
client.authenticate(otp="123456")
balance = client.get_balance("0123456789")
holdings = client.get_holdings("0123456789")
```

**Option 2: TCBS Private API (Advanced - `vnbroker.brokerage.tcbs`)**
- HMAC-SHA256 + WebSocket streaming
- Auth: API Key + Secret + OTP
- Endpoints: `/api/v1/...`
- Features: Balance, positions, orders, margin, real-time tick/order streaming

```python
from vnbroker.brokerage.tcbs import TCBSClient

client = TCBSClient(
    api_key="your_api_key",
    secret="your_base64_secret",
    account_no="0123456789",
    otp_handler=lambda otp_type: input(f"Enter {otp_type} OTP: ")
)

balance = client.get_balance()
positions = client.get_positions()

# Real-time streaming
async for tick in client.intratick_stream(["ACB", "VNM"]):
    print(f"{tick.symbol}: {tick.price}")

async for order_update in client.order_updates_stream():
    print(f"Order {order_update.order_id}: {order_update.status}")
```

**DNSE VNDirect (HMAC + JWT)**
```python
from vnbroker.connector.dnse import DNSEClient, Trade

# Market data + orders (HMAC)
dnse = DNSEClient(api_key="...", api_secret="...")

# Account + trading (JWT)
trade = Trade(username="...", password="...")
trade.login_and_get_trading_session(username, password, otp)
```

### Data Flow: Market Data
```
Vnbroker.stock(symbol, source="KBS")
    → StockComponents(symbol, source)
        → Quote/Company/Finance/Listing/Trading/News adapters (BaseAdapter)
            → ProviderRegistry.get(module, source)
                → Explorer implementation (vci/kbs/tcbs/dnse)
```

### Data Flow: Brokerage
```
Vnbroker.broker(provider="tcbs", api_key="...")
    → BrokerRegistry.create("TCBS", ...)
        → TCBSBrokerClient (iFlash OpenAPI)
            → AuthService → AccountService → MoneyService → EquityService → DerivativesService → MarketService
            → PortfolioEngine (pure compute)
```

### Source Router (AUTO mode)
- **Health-based failover** with exponential backoff cooldown (5s, 10s, 20s, 40s, max 90s)
- **Per-module primary pools**: VCI for quote/company/finance, KBS for trading
- **Hash-based sharding** for symbol-level affinity
- **Thread-safe** in-memory health state

## Testing
```bash
# Unit + contract tests (1001 passing)
pytest tests/unit -v

# Integration tests (require live credentials)
vnbroker_RUN_LIVE_INTEGRATION=1 pytest tests/integration -v

# Specific test suites
pytest tests/unit/api/test_quote_price_unit_consistency.py -v
pytest tests/unit/broker/tcbs/test_order_write_flow.py -v
```

### Test Organization
- `tests/unit/` — Mock-based unit tests (fast, no credentials needed)
- `tests/integration/` — Live API tests (gated by `vnbroker_RUN_LIVE_INTEGRATION=1`)
- `conftest.py` — Shared fixtures, loads `.env` for integration tests

## Security
- **Zero-knowledge**: Credentials never leave client process
- **No logging** of API keys, OTPs, tokens, secrets
- **dry_run=True** default for all write operations
- **Redaction** in logs for sensitive fields
- **Direct connections** — no intermediary Gateway

## Environment Variables

### Market Data
| Variable | Purpose | Required For |
|----------|---------|--------------|
| `DNSE_API_KEY` | DNSE HMAC OpenAPI Key | DNSE market data |
| `DNSE_API_SECRET` | DNSE HMAC OpenAPI Secret | DNSE market data |

### Brokerage - TCBS (iFlash OpenAPI)
| Variable | Purpose |
|----------|---------|
| `VNBROKER_BROKER_TCBS_API_KEY` | TCBS OpenAPI Key |
| `VNBROKER_BROKER_TCBS_BASE_URL` | Override base URL (optional) |
| `VNBROKER_BROKER_TCBS_CUSTODY_CODE` | Custody code 105C format (optional) |

### Brokerage - DNSE (VNDirect)
| Variable | Purpose |
|----------|---------|
| `DNSE_API_KEY` | DNSE HMAC OpenAPI Key |
| `DNSE_API_SECRET` | DNSE HMAC OpenAPI Secret |
| `DNSE_USERNAME` | DNSE trading username |
| `DNSE_PASSWORD` | DNSE trading password |

### Optional
| Variable | Purpose |
|----------|---------|
| `vnbroker_RATE_LIMIT_RPM` | Rate limit (default 500) |
| `vnbroker_LISTING_CACHE_TTL` | Listing cache TTL (default 86400) |
| `vnbroker_INDUSTRY_CACHE_TTL` | Industry cache TTL (default 86400) |
| `vnbroker_TRADING_AUTO_PRIMARY` | Override trading primary source (kbs/vci) |

## Development Workflow
1. **TDD mandatory**: Write test first (RED), implement (GREEN), refactor
2. **Run tests before commit**: `pytest tests/unit -v`
3. **Type check**: `mypy vnbroker --strict`
4. **Lint**: `ruff check vnbroker`
5. **Format**: `ruff format vnbroker`
6. **Dev tools**: `pip install -e .[test,lint]` (mypy/ruff come from the `lint` extra).
   Offline fallback (no PyPI): `python -m py_compile` touched files + grep checklist
   (no `print(`, no `core.utils.client` import in explorers, no secrets in logs) —
   **record the substitution in the PR so CI runs the real gates**.

## Gates — 1 lệnh, và đừng đọc CI

```bash
pwsh -File scripts/check_all.ps1            # tất cả gate, exit code thật
pwsh -File scripts/check_all.ps1 -Quick     # bỏ pytest toàn bộ (~3 phút)
pwsh -File scripts/check_all.ps1 -SelfTest  # chứng minh script FAIL khi gate đỏ
```

> ⚠ **GitHub Actions của repo này KHÔNG chạy** — job bị từ chối khởi động do billing
> (`"spending limit needs to be increased"`; mọi job có `steps: []`, `duration_ms` 2–3s).
> Lần chạy thành công cuối: **2026-10-02**. Từ đó tới `22d3d0a` có **74 commit** merge
> mà không gate nào chạy. **Badge CI không phải bằng chứng — job chưa bao giờ chạy.**
> Chạy `check_all.ps1`. Script in rõ *"CI GITHUB ACTIONS: CHUA CHAY"* ở cuối mỗi lần chạy.

> ⚠ **`mypy vnbroker --strict` ở dòng 255 là NO-OP.** Cả `mypy vnbroker` và
> `mypy vnbroker --strict` đều cho **1207 lỗi y hệt** — `strict = true` trong
> `[[tool.mypy.overrides]]` bị mypy nâng thành global dù comment trong `pyproject.toml`
> ghi ngược lại. Gate thật của type-check là `scripts/check_mypy_baseline.py`
> (so với baseline, chỉ fail lỗi MỚI). **Đừng ghi "strict PASS" trong báo cáo nào.**

> Mốc thực trạng đã đo (2026-10-09): `pytest tests/` **1414 passed, 30 skipped** (exit 0) ·
> `pytest tests/contract` **72 passed** (exit 0) · `ruff check vnbroker tests/unit tests/contract`
> exit 0 · `ruff check tests` **13 lỗi có sẵn** (exit 1, gate KNOWN-RED) · `mypy vnbroker`
> **1207 lỗi** (exit 1).

## Common Patterns

### Adding New Provider
1. Create `vnbroker/explorer/<provider>/` with modules: `quote.py`, `company.py`, `financial.py`, `listing.py`, `trading.py`, `news.py`
2. Implement classes with standard methods: `history()`, `intraday()`, `price_depth()`, `profile()`, `shareholders()`, `income_statement()`, `all_symbols()`, `industries()`, `price_board()`, `market_news()`, `symbol_news()`
3. Register with `@ProviderRegistry.register("module", "PROVIDER")` decorator
4. Add to `SUPPORTED_SOURCES` in `Vnbroker` and `OPEN_SOURCE_CANDIDATES` in `source_router.py`

### Adding New Brokerage
1. Extend `BrokerageBase` in `vnbroker/brokerage/<broker>/client.py`
2. Implement abstract methods: `get_balance()`, `get_positions()`, `get_orders()`, `place_order()`, `cancel_order()`, `modify_order()`
3. Register in `BrokerRegistry` (or create new registry entry)
4. Add authentication flow (HMAC, JWT, OAuth, etc.)

## Version Management
- Version defined in `pyproject.toml` (single source of truth)
- `config.py` `VERSION_REQUIREMENTS` tracks dependency requirements per version
- Upgrade notice checks GitHub release tags (not PyPI)
- Current version: **3.5.0** (`scripts/check_version_sync.py` enforces doc sync in CI)
- Release rule: every merge into `main` must carry an annotated tag `vX.Y.Z` (+ GitHub Release with Breaking section); `dev` may float

## Deprecated/Removed (v3.1.0)
- ❌ MSN explorer (no real data)
- ❌ FMP connector (no API key)
- ❌ PAT/Gateway architecture (vninvest-sdk)
- ❌ GATEWAY, AUTO, MSN, FMP from SUPPORTED_SOURCES
- ❌ GatewayHttpClient, launcher.py
- ❌ fx()/crypto()/world_index() tests (only worked with MSN/FMP)
- ❌ Legacy dispatch.py (Gateway fallback)

## Completed in v3.1.1
- ✅ fx()/crypto()/world_index() now raise NotImplementedError with clear guidance
- ✅ analytics/indicators.py implemented (SMA, EMA, RSI, MACD, Bollinger Bands, ATR, Stochastic, Williams %R, CCI)
- ✅ Broker lane differentiation documented

## Future Roadmap (v3.2+)
- [ ] FX/Crypto/World Index via new providers (Binance, TwelveData, etc.)
- [ ] DNSE Company/Finance: align to NotImplementedError consistently
- [ ] DNSE brokerage implementation (extend BrokerageBase)
- [ ] Async support for brokerage write operations
- [x] Circuit breaker pattern for provider failover (done in 3.4.0; HealthStore sqlite+memory, half-open probe, restart-safe)
- [ ] Type stubs (.pyi) for IDE support
- [ ] API reference documentation
- [ ] DNSE News/Stream support
- [ ] Unified DNSE client with dual auth modes