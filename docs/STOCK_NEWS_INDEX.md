# Stock News Documentation Index

Last updated: 2026-04-11

This page is the single entry point for all implemented Stock News features in vnbroker.

## 1) Start here

1. API usage and examples:
   - `docs/STOCK_NEWS_USAGE_GUIDE.md`
2. Troubleshooting and common pitfalls:
   - `docs/STOCK_NEWS_FAQ.md`
3. Integration for backend services:
   - `docs/EXTERNAL_PROJECT_INTEGRATION.md`

## 2) Architecture and planning references

1. Implementation blueprint:
   - `docs/STOCK_NEWS_IMPLEMENTATION_BLUEPRINT.md`
2. Source policy and governance:
   - `docs/STOCK_NEWS_SOURCE_POLICY.md`
3. Discussion and decision log:
   - `docs/STOCK_NEWS_DISCUSSION_LOG.md`

## 3) Quick API map

From `stock = vnbroker().stock("ACB", source="AUTO")`, News capabilities include:

1. Retrieval:
   - `stock.news.latest(...)`
   - `stock.news.search(...)`
   - `stock.news.by_symbol(...)`
2. Criteria filtering:
   - `stock.news.filter(...)`
   - `stock.news.query(...)`
3. Health and monitoring:
   - `stock.news.health()`
   - `stock.news.health_dataframe()`
   - `stock.news.log_health(...)`
   - `stock.news.alerts(...)`
   - `stock.news.monitor_health(...)`

## 4) End-to-end runnable example

- `tests/examples/news_end_to_end_demo.py`
- `tests/examples/news_health_monitor.py`
- `tests/examples/news_health_sanitize.py`

Run:

```bash
python -m tests.examples.news_end_to_end_demo --symbol ACB --source AUTO
python -m tests.examples.news_health_monitor --symbol ACB --source AUTO --iterations 3 --interval 5
python -m tests.examples.news_health_sanitize --file tmp/news_health/news_health.jsonl
```

## 5) Related tests

- `tests/integration/test_news_integration.py`
- `tests/unit/news/test_filtering.py`
- `tests/unit/news/test_news_facade_filter.py`
- `tests/unit/news/test_health_logging.py`
- `tests/unit/news/test_monitor_alerts.py`
- `tests/unit/news/test_normalize_dedup.py`
