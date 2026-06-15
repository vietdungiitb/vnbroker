# vninvest-sdk - Project Instructions

## Tech Stack
- Language: Python 3.11+
- Framework: FastAPI (vninvest_fastapi), asyncio
- Auth: PAT-only (bcrypt), 8 scopes
- Cache: Redis + in-memory fallback, CacheWarmer
- Streaming: WebSocket, vnbroker integration
- Testing: pytest, 36 core tests passing

## Code Style
- snake_case cho functions/variables
- PascalCase cho classes
- Type hints bắt buộc (mypy strict)
- Immutability: prefer dataclasses/frozen, spread over mutation
- File size: 200-400 lines typical, 800 max

## Testing (tuân thủ ~/.blackbox/rules/common/testing.md)
- Run tests: `pytest -v` (core), `pytest tests/test_integration_pat.py` (integration)
- TDD mandatory: write test first (RED), implement (GREEN), refactor
- Coverage target: 80%+
- Edge cases: null PAT, invalid format, expired token, rate limit, Redis down

## Security (tuân thủ ~/.blackbox/rules/common/security.md)
- PAT format: `vninvest_pat_<base64url>`
- Scopes: quote:read, company:read, finance:read, news:read, stream:price, stream:depth, stream:trade, admin:tenant
- Quota headers: X-Quota-Limit, X-Quota-Remaining, X-Quota-Reset
- Error responses: {error: string, code: string, details?: object}
- No hardcoded secrets, all in env vars

## Project Structure
vninvest/
├── auth.py          # PAT resolution, bcrypt verify, scope enforcement
├── client.py        # Sync/async client, quota headers
├── cache.py         # CacheWarmer, TTL, invalidation
├── metering.py      # Usage tracking
├── streaming.py     # WebSocket client
├── quota.py         # Sliding window quota
├── models.py        # Pydantic models
└── exceptions.py    # Custom exceptions

vninvest_fastapi/
├── middleware/auth.py    # FastAPI auth middleware
└── routes/               # API routes

## Global Agents/Skills Available
- @vn-sdk-reviewer (global agent)
- skill(skill_name="gen-test-data") (global skill)
- @code-reviewer, @security-reviewer, @planner, @architect, @tdd-guide (ECC agents)
- /code-review, /security-scan, /plan, /skill-stocktake (ECC commands)