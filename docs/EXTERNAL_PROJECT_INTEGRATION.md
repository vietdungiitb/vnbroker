# External Project Integration Guide

This guide helps other projects integrate vnstock with the new performance features quickly.

Target users:

- Teams using vnstock in backend services (FastAPI, Django, Celery workers).
- Data pipelines that fetch high-volume quote data.
- Repos that need stable production profile and repeatable benchmark profile.

## 1) Installation Strategy

For reproducible deployments, pin a version or commit.

Stable from PyPI:

```bash
pip install "vnstock==1.0.0"
```

From GitHub branch/commit:

```bash
pip install "git+https://github.com/vietdungiitb/vnstock.git@<commit_or_tag>"
```

## 2) Apply Performance Presets in App Startup

Use built-in presets from vnstock core:

```python
from vnstock.core.performance_profiles import apply_profile

# production profile recommended for APIs/services
apply_profile("production_stable", overwrite=False)
```

For stress test/benchmark environment:

```python
from vnstock.core.performance_profiles import apply_profile

apply_profile("benchmark_max_speed", overwrite=True)
```

Available profiles:

| Profile | Description |
|---|---|
| `benchmark_max_speed` | Max throughput, stats disabled, aggressive ramp-up |
| `production_stable` | Conservative back-off, stats enabled |
| `market_hours` | Reduced concurrency for VN market open sessions |

## 2a) Time-Aware Auto Profile Selection

Let vnstock pick the right profile automatically based on the current VN market
session (ICT timezone, Mon–Fri):

```python
from vnstock.core.performance_profiles import apply_profile_for_current_time

# Call once at process start — picks market_hours or benchmark_max_speed automatically
result = apply_profile_for_current_time()
print(f"Active profile: {result['_applied_profile']}")
```

Customise which profiles to use:

```python
apply_profile_for_current_time(
    peak_profile="market_hours",
    offpeak_profile="benchmark_max_speed",
    overwrite=True,
)
```

For FastAPI:

```python
from fastapi import FastAPI
from vnstock.core.performance_profiles import apply_profile_for_current_time

app = FastAPI()

@app.on_event("startup")
def setup_vnstock_profile() -> None:
    apply_profile_for_current_time(overwrite=False)
```

## 3) Environment Variables for Fine-Tuning

VCI adaptive variables:

- `VNSTOCK_VCI_ADAPTIVE_CONCURRENCY`
- `VNSTOCK_VCI_ADAPTIVE_START_CONCURRENCY`
- `VNSTOCK_VCI_ADAPTIVE_MIN_CONCURRENCY`
- `VNSTOCK_VCI_ADAPTIVE_STEP_UP`
- `VNSTOCK_VCI_ADAPTIVE_STEP_DOWN`
- `VNSTOCK_VCI_ADAPTIVE_FAIL_THRESHOLD`
- `VNSTOCK_VCI_ADAPTIVE_P95_LOW_SECONDS`
- `VNSTOCK_VCI_ADAPTIVE_P95_HIGH_SECONDS`

KBS adaptive variables:

- `VNSTOCK_KBS_ADAPTIVE_CONCURRENCY`
- `VNSTOCK_KBS_ADAPTIVE_START_CONCURRENCY`
- `VNSTOCK_KBS_ADAPTIVE_MIN_CONCURRENCY`
- `VNSTOCK_KBS_ADAPTIVE_STEP_UP`
- `VNSTOCK_KBS_ADAPTIVE_STEP_DOWN`
- `VNSTOCK_KBS_ADAPTIVE_FAIL_THRESHOLD`
- `VNSTOCK_KBS_ADAPTIVE_P95_LOW_SECONDS`
- `VNSTOCK_KBS_ADAPTIVE_P95_HIGH_SECONDS`

Global retry variable:

- `VNSTOCK_MAX_RETRIES`

Global async diagnostics toggle:

- `VNSTOCK_ASYNC_STATS_ENABLED` — set to `0` to disable lock-based counters (~53%
  throughput gain in benchmarks). The `benchmark_max_speed` preset sets this automatically.

## 4) Example: FastAPI Startup (manual profile)

```python
from fastapi import FastAPI
from vnstock.core.performance_profiles import apply_profile

app = FastAPI()

@app.on_event("startup")
def setup_vnstock_profile() -> None:
    apply_profile("production_stable", overwrite=False)
```

## 5) Example: Django AppConfig

```python
from django.apps import AppConfig
from vnstock.core.performance_profiles import apply_profile_for_current_time

class MarketConfig(AppConfig):
    name = "market"

    def ready(self):
        # Auto-select profile based on market session clock
        apply_profile_for_current_time(overwrite=False)
```

## 6) Example: Celery Worker Bootstrap

```python
from celery import Celery
from vnstock.core.performance_profiles import apply_profile

apply_profile("production_stable", overwrite=False)
app = Celery("market")
```

## 7) Parallel Fetch Usage

VCI parallel multi-symbol:

```python
from vnstock.explorer.vci.quote import Quote as VCIQuote

quote = VCIQuote(symbol="ACB", show_log=False)
frames = quote.history(
    parallel=True,
    symbols=["ACB", "VCB", "TCB"],
    interval="1D",
    max_concurrency=24,
)
```

KBS parallel multi-symbol:

```python
from vnstock.explorer.kbs.quote import Quote as KBSQuote

quote = KBSQuote(symbol="ACB", show_log=False)
frames = quote.history(
    parallel=True,
    symbols=["ACB", "VCB", "TCB"],
    interval="1D",
    max_concurrency=12,
    adaptive_concurrency=True,
)
```

## 8) AdaptiveController — Advanced Usage

For custom providers or non-vnstock fetch loops that want the same adaptive windowing:

```python
from vnstock.core.adaptive_controller import AdaptiveController

ctrl = AdaptiveController.from_env(
    "VNSTOCK_VCI_ADAPTIVE_",
    default_start=8,
    default_min=2,
    default_max=24,
)

for batch in batches:
    results = fetch_batch(batch, workers=ctrl.current)
    successes = sum(1 for r in results if r is not None)
    p95 = measure_p95_latency(results)
    ctrl.adjust(batch_size=len(batch), success_count=successes, batch_p95_seconds=p95)
```

### GlobalPressure — cross-provider stress signal

```python
from vnstock.core.adaptive_controller import get_global_pressure

gp = get_global_pressure()
# Both VCI and KBS already call gp.record_batch() internally.
# You can read the state to inform application-level decisions:
if gp.stressed:
    logger.warning("All providers under stress — concurrency halved automatically")
```

## 9) Stock News Integration (Filtering + Monitoring)

Use the new News facade from stock components:

```python
from vnstock.common.client import Vnstock

stock = Vnstock(show_log=False).stock("ACB", source="AUTO")

# Latest normalized news
latest = stock.news.latest(limit=20)

# Criteria filtering (symbol, text, source, time range)
filtered = stock.news.filter(
    symbol="ACB",
    query="ket qua kinh doanh",
    sources=["VCI", "RSS_CAFEF"],
    from_time="2026-04-11T00:00:00Z",
    to_time="2026-04-11T23:59:59Z",
    limit=100,
)
```

Monitor source health and persist operational logs:

```python
# Snapshot as dict and DataFrame
snapshot = stock.news.health()
snapshot_df = stock.news.health_dataframe()

# Persist snapshot on each polling cycle
stock.news.log_health("tmp/news_health/news_health.jsonl", fmt="jsonl")

# Evaluate alert thresholds and collect monitor bundle
monitor_result = stock.news.monitor_health(
    file_path="tmp/news_health/news_health.jsonl",
    fmt="jsonl",
    max_failures=2,
    max_cooldown_sec=30.0,
)
```

Recommended production pattern:

- Poll `monitor_health(...)` on a schedule (e.g., every 1-5 minutes).
- Ship JSONL logs to your observability stack (ELK/Datadog/Splunk).
- Trigger incident alerts when `alerts` is non-empty for consecutive windows.
- Keep `source="AUTO"` in read paths unless a hard source pin is required.

Reference:

- `docs/STOCK_NEWS_USAGE_GUIDE.md`
- `docs/STOCK_NEWS_FAQ.md`

## 10) CI/CD Recommendation

Run auto-tune nightly via GitHub Actions (`.github/workflows/nightly_autotune.yml`)
or manually:

```bash
python -m tests.examples.auto_tune_concurrency \
  --provider vci \
  --symbols ACB,VCB,TCB,HPG,VNM \
  --concurrency 8,12,16,24 \
  --runs 2 \
  --output-csv tmp/bench/auto_tune_vci.csv \
  --output-json tmp/bench/auto_tune_vci.json
```

```bash
python -m tests.examples.auto_tune_concurrency \
  --provider kbs \
  --symbols ACB,VCB,TCB \
  --concurrency 4,8,12 \
  --runs 2 \
  --output-csv tmp/bench/auto_tune_kbs.csv \
  --output-json tmp/bench/auto_tune_kbs.json
```

## 11) Operational Best Practices

- Call `apply_profile_for_current_time()` at startup to auto-select concurrency.
- Use `production_stable` / `market_hours` for live services; never `benchmark_max_speed`.
- Keep `VNSTOCK_MAX_RETRIES` ≤ 2 for high-throughput workloads.
- Prefer direct mode unless proxy is required.
- Re-run auto-tune periodically (ideally via nightly CI) to keep configs fresh.
- Watch `GlobalPressure.stressed` via your APM if you need custom circuit-breaker logic.

## 12) Related Docs

- [docs/PERFORMANCE_PROFILES.md](PERFORMANCE_PROFILES.md)
- [tests/examples/perf_profile_runner.py](../tests/examples/perf_profile_runner.py)
- [tests/examples/auto_tune_concurrency.py](../tests/examples/auto_tune_concurrency.py)
- [.github/workflows/nightly_autotune.yml](../.github/workflows/nightly_autotune.yml)
