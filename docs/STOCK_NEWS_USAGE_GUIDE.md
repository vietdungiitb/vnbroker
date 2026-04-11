# Stock News Usage Guide

Last updated: 2026-04-11

This guide documents the implemented stock news features in vnstock so developers can integrate safely and consistently.

## 1) Scope

The News feature provides:

- Multi-source normalized news retrieval
- Symbol-based and text-based filtering
- Source health monitoring and cooldown visibility
- Health logging to JSONL or CSV
- Threshold-based alerts for degraded sources

## 2) Supported sources

- `AUTO` (recommended)
- `VCI`
- `KBS`
- `TCBS`
- `RSS_CAFEF`
- `RSS_VNECONOMY`

For `AUTO`, vnstock will route requests by source health and failover rules.

## 3) Quick start

```python
from vnstock.common.client import Vnstock

stock = Vnstock(show_log=False).stock("ACB", source="AUTO")

# Latest normalized news
df_latest = stock.news.latest(limit=20)

# Provider search
df_search = stock.news.search(query="co tuc", limit=20)

# Symbol-scoped retrieval
df_symbol = stock.news.by_symbol("VCB", limit=20)
```

## 4) Filtering by criteria

Use `filter(...)` when you need combined criteria.

```python
# Example: symbol + keyword in title/summary
df = stock.news.filter(
    symbol="ACB",
    query="ket qua kinh doanh",
    fields=("title", "summary"),
    limit=50,
)

# Example: filter by sources and time range
df = stock.news.filter(
    sources=["VCI", "RSS_CAFEF"],
    from_time="2026-04-11T00:00:00Z",
    to_time="2026-04-11T23:59:59Z",
    limit=100,
)

# Example: query alias
df = stock.news.query("co tuc", symbol="VCB", limit=20)
```

### Filter parameters

- `symbol`: stock symbol (`ACB`, `VCB`, ...)
- `query`: text query (substring by default)
- `sources`: list of source names
- `from_time`, `to_time`: ISO timestamps
- `regex`: treat query as regex
- `case`: case-sensitive search
- `fields`: text columns to search (default: `title`, `summary`)
- `limit`: number of rows returned
- `base_limit`: number of rows fetched before filtering

## 5) Important behavior notes

1. `News` instance may be symbol-bound.
2. If you initialize from `stock("ACB")`, then `news.query(...)` uses `ACB` as default scope.
3. To query another symbol, pass `symbol="..."` explicitly.

## 6) Monitoring source health

```python
# Raw snapshot as dict
snapshot = stock.news.health()

# Tabular snapshot
health_df = stock.news.health_dataframe()

# Append snapshot to disk
stock.news.log_health("tmp/news_health/news_health.jsonl", fmt="jsonl")
stock.news.log_health("tmp/news_health/news_health.csv", fmt="csv")

# Optional: sanitize old JSONL logs (NaN -> null)
stats = stock.news.sanitize_health_log("tmp/news_health/news_health.jsonl")
```

### Snapshot fields

- `failures`
- `in_cooldown`
- `cooldown_remaining_sec`
- `last_success_age_sec`
- `last_failure_age_sec`

## 7) Alerting and operational monitoring

```python
# Evaluate alerts from current snapshot
alerts = stock.news.alerts(max_failures=2, max_cooldown_sec=30.0)

# Collect snapshot + optional file log + alerts
result = stock.news.monitor_health(
    file_path="tmp/news_health/news_health.jsonl",
    fmt="jsonl",
    max_failures=2,
    max_cooldown_sec=30.0,
)
```

`monitor_health(...)` returns:

- `snapshot`: current source health snapshot
- `alerts`: alert list based on thresholds
- `logged_path`: file path if logging was requested

## 8) Data contract (normalized news)

Common output columns include:

- `news_id`
- `source`
- `source_article_id`
- `symbol`
- `title`
- `summary`
- `url`
- `published_at`
- `fetched_at`
- `language`
- `tags`
- `raw_hash`
- `dedup_group_id`
- `quality_score`

## 9) References

- Documentation index: `docs/STOCK_NEWS_INDEX.md`
- Architecture and rollout notes: `docs/STOCK_NEWS_IMPLEMENTATION_BLUEPRINT.md`
- Source governance: `docs/STOCK_NEWS_SOURCE_POLICY.md`
- Discussion log: `docs/STOCK_NEWS_DISCUSSION_LOG.md`
- Common troubleshooting: `docs/STOCK_NEWS_FAQ.md`
- Monitor example script: `tests/examples/news_health_monitor.py`