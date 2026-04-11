# Performance Profiles and Auto-Tuning

This document covers five performance layers in vnstock:

1. Preset profiles for benchmark, production, and market-hours.
2. Time-aware automatic profile selection.
3. Concurrency auto-tuning script with JSON/CSV output.
4. Adaptive concurrency environment variables for VCI and KBS.
5. Shared `AdaptiveController` and `GlobalPressure` cross-provider backpressure.

---

## 1) Preset Profiles

Three built-in profiles:

| Profile | Use case |
|---|---|
| `benchmark_max_speed` | Offline benchmarks, static datasets (stats disabled) |
| `production_stable` | Live APIs/services with conservative back-off |
| `market_hours` | Live fetch during VN market open sessions |

```python
from vnstock.core.performance_profiles import apply_profile, list_profiles

print(list_profiles())          # ['benchmark_max_speed', 'market_hours', 'production_stable']
apply_profile("production_stable", overwrite=False)
```

Apply and run benchmark from CLI:

```bash
python -m tests.examples.perf_profile_runner --profile benchmark_max_speed --show-env --run-benchmark
```

---

## 2) Time-Aware Auto Profile Selection

`apply_profile_for_current_time()` detects whether the current time falls inside a
VN market session (Mon–Fri 09:00–11:30 or 13:00–15:30 ICT) and applies the correct profile
automatically.

```python
from vnstock.core.performance_profiles import apply_profile_for_current_time, is_market_hours

# Check once
if is_market_hours():
    print("Đang trong phiên giao dịch — dùng profile thận trọng")

# OR: set-and-forget at process startup
result = apply_profile_for_current_time(
    peak_profile="market_hours",
    offpeak_profile="benchmark_max_speed",
)
print(f"Profile đã áp dụng: {result['_applied_profile']}")
```

Custom peak/off-peak profiles:

```python
apply_profile_for_current_time(
    peak_profile="production_stable",
    offpeak_profile="benchmark_max_speed",
)
```

### `is_market_hours()` parameters

| Parameter | Default | Description |
|---|---|---|
| `now` | `None` (current ICT time) | Override with a `datetime` for testing |

---

## 3) Auto-Tune Concurrency

Run auto-tuning for VCI:

```bash
python -m tests.examples.auto_tune_concurrency \
  --provider vci \
  --symbols ACB,VCB,TCB,HPG,VNM \
  --concurrency 8,12,16,24 \
  --runs 2
```

Run auto-tuning for KBS:

```bash
python -m tests.examples.auto_tune_concurrency \
  --provider kbs \
  --symbols ACB,VCB,TCB \
  --concurrency 4,8,12 \
  --runs 2
```

Default reports:

- `tmp/bench/auto_tune.csv`
- `tmp/bench/auto_tune.json`

Custom output paths:

```bash
python -m tests.examples.auto_tune_concurrency \
  --provider vci --concurrency 8,16,24 \
  --output-csv reports/vci.csv \
  --output-json reports/vci.json
```

### Nightly GitHub Actions auto-tune

The workflow `.github/workflows/nightly_autotune.yml` runs automatically Mon–Fri at 01:00 UTC
(08:00 ICT, before market open). It:

1. Runs the auto-tune script for both VCI and KBS in parallel.
2. Uploads CSV + JSON result artifacts (retained 30 days).
3. Posts a formatted summary table to the GitHub job summary page.

Trigger manually from the GitHub Actions UI:

```
Actions → Nightly Auto-Tune Concurrency → Run workflow
```

---

## 4) Adaptive Concurrency Environment Variables

All 8 knobs are identical for VCI and KBS — just swap the prefix:

| Variable | VCI prefix | KBS prefix | Default |
|---|---|---|---|
| Enable adaptive | `VNSTOCK_VCI_ADAPTIVE_CONCURRENCY` | `VNSTOCK_KBS_ADAPTIVE_CONCURRENCY` | `0` (off) |
| Start concurrency | `..._START_CONCURRENCY` | same pattern | `6` / `4` |
| Min concurrency | `..._MIN_CONCURRENCY` | same pattern | `4` / `2` |
| Step up | `..._STEP_UP` | same pattern | `2` / `1` |
| Step down | `..._STEP_DOWN` | same pattern | `3` / `2` |
| Fail threshold | `..._FAIL_THRESHOLD` | same pattern | `0.20` |
| P95 low (ramp up) | `..._P95_LOW_SECONDS` | same pattern | `0.35` / `0.50` |
| P95 high (back off) | `..._P95_HIGH_SECONDS` | same pattern | `1.20` / `1.50` |

Global variables:

| Variable | Default | Effect |
|---|---|---|
| `VNSTOCK_MAX_RETRIES` | `3` | HTTP retry count |
| `VNSTOCK_ASYNC_STATS_ENABLED` | `1` | `0` = disable lock-based counters (~53% throughput gain) |

Set `VNSTOCK_ASYNC_STATS_ENABLED=0` in benchmark runs for maximum throughput. The
`benchmark_max_speed` profile does this automatically.

---

## 5) Shared AdaptiveController and GlobalPressure

### AdaptiveController

`AdaptiveController` lives in `vnstock.core.adaptive_controller` and is shared by both
VCI (async) and KBS (sync) paths:

```python
from vnstock.core.adaptive_controller import AdaptiveController

# Stateless — one-off calculation
new_w = AdaptiveController.compute(
    current=12,
    batch_size=10,
    success_count=9,
    max_concurrency=24,
    min_concurrency=2,
    step_up=2,
    step_down=3,
    fail_threshold=0.20,
    batch_p95_seconds=0.40,
    p95_high_seconds=1.20,
    p95_low_seconds=0.35,
)

# Stateful — persists across batch windows
ctrl = AdaptiveController.from_env("VNSTOCK_VCI_ADAPTIVE_")
for batch in batches:
    results = await fetch_batch(batch)
    new_w = ctrl.adjust(
        batch_size=len(batch),
        success_count=len([r for r in results if r is not None]),
        batch_p95_seconds=measure_p95(results),
    )
```

### GlobalPressure (cross-provider backpressure)

A process-wide singleton that halves the concurrency cap for *all* providers when
combined error rate exceeds 30%, and self-heals after 3 consecutive clean windows:

```python
from vnstock.core.adaptive_controller import get_global_pressure

gp = get_global_pressure()
gp.record_batch(batch_size=10, error_count=4)   # 40% error → stressed
print(gp.stressed)       # True
print(gp.multiplier)     # 0.5  → all providers cap at 50% of normal max
```

This is wired automatically inside `VCIQuote.fetch_multiple()` and `KBSQuote.fetch_multiple()`.
No extra configuration is needed.
