# Stock News Multi-Source Implementation Blueprint

Last updated: 2026-04-11
Status: Design for phased implementation

## 1) Product target

Build a production-grade, multi-source stock news library in vnbroker with:

- Fast ingestion from prioritized sources
- Unified news schema
- Cross-source deduplication
- Stable public API for downstream systems
- Observability, retries, and quality controls

## 2) Source onboarding priority

## Tier A - Immediate integration (Sprint 1)

1. VCI company news (existing provider path)
2. KBS company news (existing provider path)
3. AUTO company news route
4. CafeF RSS
5. VnEconomy RSS

## Tier B - Stabilization integration (Sprint 2)

1. TCBS company news (fix endpoint/auth/runtime reliability)
2. Vietstock RSS (redirect/session handling)
3. Tinnhanhchungkhoan RSS (parser resilience)

## Tier C - Strategic growth (Sprint 3+)

1. Licensed/commercial APIs with contractual usage rights
2. Official market announcement channels (exchange/issuer where accessible)
3. Optional international news enrichment feeds

## 3) Proposed architecture in vnbroker

## 3.1 New module layers

1. `vnbroker/api/news.py`
   - Public adapter for market-wide and symbol-scoped news
2. `vnbroker/explorer/<source>/news.py`
   - Source-specific providers (vci, kbs, rss_cafef, rss_vneconomy, etc.)
3. `vnbroker/news/normalize.py`
   - Canonical schema mapping
4. `vnbroker/news/dedup.py`
   - Dedup keys and similarity grouping
5. `vnbroker/news/quality.py`
   - Quality score and source reliability logic

## 3.2 Keep existing behavior

- Do not remove or change legacy `Company.news()` output contract in first phase.
- Add a new `News` adapter that can internally call provider-level company or RSS pipelines.
- Allow controlled migration later:
  - legacy path remains
  - new path exposed for richer, normalized output

## 4) Canonical schema (v1)

Mandatory fields:

- `news_id` (global stable id)
- `source` (vci, kbs, tcbs, cafef_rss, vneconomy_rss, ...)
- `source_article_id` (if available)
- `symbol` (nullable for market-wide news)
- `title`
- `summary`
- `url`
- `published_at` (UTC)
- `fetched_at` (UTC)
- `language`
- `tags` (list)
- `raw_hash`
- `dedup_group_id`
- `quality_score`

Optional metadata:

- `author`
- `image_url`
- `content_type` (analysis, announcement, flow, macro)
- `compliance_flags`

## 5) API contract proposal

## 5.1 Python API

- `News(source="AUTO").latest(limit=100, symbols=None, from_time=None, to_time=None)`
- `News(source="AUTO").search(query, symbols=None, limit=100)`
- `News(source="AUTO").by_symbol(symbol, limit=50)`

## 5.2 Source policy behavior

- `source="AUTO"` for news should resolve with source priority list by tier + health signal.
- Return `source_used` metadata in attrs for transparency.

## 6) Dedup strategy

Stage 1:

- Exact dedup by normalized URL
- Exact dedup by `hash(title + published_date + source_article_id)`

Stage 2:

- Fuzzy title similarity for near-duplicates
- Time-window grouping (example: +/- 6 hours)

## 7) Reliability and observability

- Retry/backoff at provider fetch level
- Per-source health counters:
  - fetch success rate
  - parse success rate
  - error rate
  - median latency
- Add source cooldown when repeated failures occur
- Structured logs for ingestion and normalization errors

## 8) Compliance and legal guardrails

- Preserve source URL + attribution in every record
- Respect robots/terms for web sources
- Disable full-text storage for sources not permitting it
- Maintain a source registry with legal notes

Suggested file:

- `docs/STOCK_NEWS_SOURCE_POLICY.md`

## 9) Testing strategy

## 9.1 Unit tests

- Schema normalization per source
- Dedup deterministic behavior
- Date/time parsing and timezone normalization
- AUTO source ordering and fallback

## 9.2 Integration tests

- Smoke tests for Tier A sources
- Graceful degradation when one source is down
- Contract test ensuring mandatory fields are always present

## 9.3 Data quality tests

- Duplicate ratio threshold
- Missing required field threshold
- Broken URL ratio threshold

## 10) Milestone plan

## Milestone 1 (1-2 weeks)

- Create `News` adapter skeleton
- Integrate Tier A provider wrappers
- Implement canonical schema v1
- Add base tests and docs

Exit criteria:

- Tier A sources return normalized records
- Basic dedup enabled
- No regression for existing `Company.news()`

## Milestone 2 (1-2 weeks)

- Add RSS parsers and resilience improvements
- Add source health metrics and fallback refinement
- Stabilize TCBS integration where feasible

Exit criteria:

- Multi-source ingestion stable over repeated test runs
- Quality metrics report generated

## Milestone 3 (2+ weeks)

- Add ranking/quality score tuning
- Add compliance policy registry
- Prepare public documentation and migration notes

Exit criteria:

- Production-ready quality dashboard
- Clear source policy and operational runbook

## 11) Suggested task order for implementation

1. Add `api/news.py` adapter interface
2. Add `explorer/vci/news.py` and `explorer/kbs/news.py` wrappers
3. Add `explorer/rss_cafef/news.py` and `explorer/rss_vneconomy/news.py`
4. Implement `news/normalize.py`
5. Implement `news/dedup.py`
6. Wire `AUTO` source policy for news
7. Add unit + integration tests
8. Document operational and legal policy

## 12) Immediate next coding step

Start with Tier A only, then run a small benchmark over 3-5 symbols and 2 RSS feeds to validate:

- freshness
- normalization success rate
- duplicate ratio
