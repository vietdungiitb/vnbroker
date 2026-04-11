# Stock News FAQ

Last updated: 2026-04-11

This FAQ covers common implementation questions for vnstock News features.

## 1) Why does `news.query(...)` return empty even though I know matching headlines exist?

`News` can be symbol-bound when created from `stock("ACB")`.

That means `query(...)` will default to symbol `ACB` scope unless you pass another symbol explicitly.

```python
stock = Vnstock(show_log=False).stock("ACB", source="AUTO")

# Scoped to ACB by default
df1 = stock.news.query("co tuc")

# Explicitly query a different symbol
df2 = stock.news.query("co tuc", symbol="VCB")
```

## 2) Which fields are searched by default in text filtering?

`News.filter(...)` searches `title` and `summary` by default.

Use `fields` to override:

```python
df = stock.news.filter(query="thanh khoan", fields=("summary",))
```

## 3) Is query matching regex or plain text?

Default is plain substring (`regex=False`).

Enable regex explicitly:

```python
df = stock.news.filter(query="\\bACB\\b", regex=True)
```

## 4) Why are time-range filters returning no records?

Ensure `from_time` and `to_time` are valid ISO timestamps and in UTC-compatible format, for example:

- `2026-04-11T00:00:00Z`
- `2026-04-11T23:59:59Z`

If source data contains missing/invalid `published_at`, those rows may be excluded by time filters.

## 5) What source names are valid in filtering?

Use uppercase source values matching normalized output, for example:

- `VCI`
- `KBS`
- `TCBS`
- `RSS_CAFEF`
- `RSS_VNECONOMY`

Example:

```python
df = stock.news.filter(sources=["VCI", "RSS_CAFEF"], limit=100)
```

## 6) What is the difference between `search(...)` and `filter(...)`?

- `search(...)`: provider-facing text search helper (source-specific behavior).
- `filter(...)`: normalized, unified, post-fetch filtering by multiple criteria.

For consistent cross-source behavior, prefer `filter(...)`.

## 7) Why do I see no alerts from `news.alerts(...)`?

No alerts means current snapshot does not cross configured thresholds.

Tune thresholds for your environment:

```python
alerts = stock.news.alerts(max_failures=1, max_cooldown_sec=5.0)
```

## 8) How do I persist monitor logs for observability?

Use JSONL for append-friendly logs:

```python
stock.news.monitor_health(
    file_path="tmp/news_health/news_health.jsonl",
    fmt="jsonl",
)
```

Use CSV if your ETL expects tabular files:

```python
stock.news.log_health("tmp/news_health/news_health.csv", fmt="csv")
```

## 9) How should production services poll health?

- Poll every 1-5 minutes.
- Persist JSONL logs and forward to APM/ELK.
- Alert only on consecutive non-empty alert windows to reduce noise.
- Keep read path on `source="AUTO"` unless you need a hard source pin.

## 10) Where is the complete usage guide?

See:

- `docs/STOCK_NEWS_USAGE_GUIDE.md`
- `docs/EXTERNAL_PROJECT_INTEGRATION.md`

## 11) How do I clean old JSONL health logs that still contain `NaN`?

Use the built-in sanitizer:

```python
stats = stock.news.sanitize_health_log("tmp/news_health/news_health.jsonl")
print(stats)
```

Or via CLI:

```bash
python -m tests.examples.news_health_sanitize --file tmp/news_health/news_health.jsonl
```

The function rewrites the file and converts non-standard `NaN` to JSON-safe `null`.