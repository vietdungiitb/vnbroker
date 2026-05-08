# Stock News - Discussion Log

Last updated: 2026-04-11
Scope: Define strategy to build a high-quality multi-source stock news library integrated deeply into vnbroker.

## 1) Objectives agreed

- Build a stock news library that follows international-style engineering standards:
  - Clear source attribution
  - Stable ingestion SLA
  - Standardized schema across sources
  - High observability and testability
- Integrate deeply with existing vnbroker adapter/provider architecture, not a parallel code path.
- Prioritize usable sources first, then expand.

## 2) Current codebase findings

- Existing dynamic adapter/provider pattern is strong and reusable for news expansion.
- Company-level news already exists in current providers:
  - VCI company news
  - KBS company news
  - TCBS company news (defined but runtime instability observed)
- AUTO routing exists and supports failover logic for modules.

## 3) Runtime validation done during discussion

- Smoke tests were run for `Company.news()` using symbol `ACB`:
  - `kbs`: success
  - `vci`: success
  - `auto`: success (resolved to VCI)
  - `tcbs`: failed in current runtime (retry/connection issue)

## 4) External internet sources reviewed

- RSS feeds confirmed as immediately ingestable:
  - CafeF stock market RSS
  - VnEconomy stock market RSS
- Sources needing extra stabilization before production use:
  - Vietstock RSS (redirect/anti-bot behavior observed)
  - Tinnhanhchungkhoan RSS (content extraction issue in quick probe)

## 5) Source priority decision

### Tier A (Use immediately)

1. VCI company news
2. KBS company news
3. AUTO company news (VCI/KBS path)
4. CafeF RSS
5. VnEconomy RSS

### Tier B (Stabilize before rollout)

1. TCBS company news (endpoint/auth/runtime hardening)
2. Vietstock RSS (session/redirect handling)
3. Tinnhanhchungkhoan RSS (parser and extraction hardening)

### Tier C (Future optional expansion)

- Additional licensed/commercial feeds
- Official exchange/issuer announcement APIs where legally and technically feasible

## 6) Engineering principles agreed

- Backward compatibility first: keep existing `Company.news()` behavior unchanged.
- Additive architecture: introduce new news module instead of breaking legacy paths.
- Provider-specific parsing, adapter-level normalization.
- Quality and compliance metadata are mandatory for production library maturity.

## 7) Risks identified

- Multi-source schema mismatch and duplicate content.
- Source instability and rate-limits.
- Legal/licensing constraints for some media feeds.
- Missing contract tests for cross-source news consistency.

## 8) Outputs requested by user

- Persist this discussion log in repository.
- Produce a practical implementation blueprint with clear source prioritization beyond VCI/KBS.

## 9) Next implementation artifact

- See: `docs/STOCK_NEWS_IMPLEMENTATION_BLUEPRINT.md`
