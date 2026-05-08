"""Benchmark AUTO open-source routing versus fixed public providers.

Examples:
- python -m tests.examples.auto_source_benchmark --profile benchmark_max_speed --symbol-count 60 --providers AUTO,VCI,KBS --concurrency 8,16
- python -m tests.examples.auto_source_benchmark --symbols ACB,VCB,TCB,HPG,VNM --providers AUTO --runs 2 --count-back 30
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from vnbroker.api.listing import Listing
from vnbroker.api.quote import Quote
from vnbroker.core.performance_profiles import apply_profile, list_profiles


DEFAULT_BENCH_SYMBOLS = [
    "VCB", "VHM", "VIC", "VNM", "ACB", "MSN", "HPG", "TCB", "VPB", "GAS",
    "BID", "CTG", "MWG", "VRE", "FPT", "POW", "PLX", "SAB", "SSI", "HDB",
    "MBB", "STB", "GVR", "BCM", "VJC", "PDR", "PNJ", "DPM", "DGC", "HT1",
    "PVS", "SHS", "NVB", "CEO", "VCS", "PVI", "PVC", "VCG", "SHB", "MBS",
    "TNG", "PLC", "IDC", "NTP", "LAS", "BVS", "DTD", "HUT", "VFS", "IPA",
    "MCH", "LTG", "QNS", "VGI", "BSR", "DDV", "OIL", "VOC", "VEA", "ACV",
]

_STOCK_SYMBOL_RE = re.compile(r"^[A-Z]{3}$")


@dataclass
class RequestSample:
    success: bool
    latency_seconds: float
    source_used: str | None
    rows_fetched: int
    error_name: str | None


@dataclass
class BenchmarkRow:
    provider_requested: str
    concurrency: int
    runs: int
    symbols: int
    success_count: int
    failure_count: int
    total_rows_fetched: int
    elapsed_seconds: float
    requests_per_second: float
    requests_per_minute: float
    p50_latency_seconds: float
    p95_latency_seconds: float
    min_latency_seconds: float
    max_latency_seconds: float
    mean_latency_seconds: float
    provider_breakdown: Dict[str, int]
    error_breakdown: Dict[str, int]


def parse_symbols(raw_symbols: str) -> List[str]:
    values = [value.strip().upper() for value in raw_symbols.split(",") if value.strip()]
    if not values:
        raise ValueError("No symbols provided")
    return values


def parse_levels(raw: str) -> List[int]:
    values = [int(value.strip()) for value in raw.split(",") if value.strip()]
    if not values:
        raise ValueError("Concurrency list is empty")
    if any(value <= 0 for value in values):
        raise ValueError("Concurrency must be positive")
    return values


def parse_providers(raw: str) -> List[str]:
    providers = [value.strip().upper() for value in raw.split(",") if value.strip()]
    if not providers:
        raise ValueError("Provider list is empty")
    return providers


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def interleave_exchange_symbols(groups: Dict[str, List[str]], limit: int) -> List[str]:
    ordered_keys = [key for key in ("HOSE", "HNX", "UPCOM") if groups.get(key)]
    fallback_keys = [key for key in groups.keys() if key not in ordered_keys and groups.get(key)]
    keys = ordered_keys + fallback_keys
    if not keys:
        return []

    result: List[str] = []
    positions = {key: 0 for key in keys}
    while len(result) < limit:
        progressed = False
        for key in keys:
            items = groups.get(key, [])
            pos = positions[key]
            if pos < len(items):
                result.append(items[pos])
                positions[key] = pos + 1
                progressed = True
                if len(result) >= limit:
                    break
        if not progressed:
            break
    return result


def filter_stock_symbols(rows: Iterable[Dict[str, Any]]) -> List[str]:
    symbols: List[str] = []
    for row in rows:
        symbol = str(row.get("symbol", "")).strip().upper()
        if not _STOCK_SYMBOL_RE.match(symbol):
            continue
        symbol_type = str(row.get("type", "")).strip().upper()
        if symbol_type and symbol_type not in {"STOCK", "SHARE", "EQUITY"}:
            continue
        symbols.append(symbol)
    return symbols


def load_large_symbol_set(limit: int, listing_source: str = "AUTO") -> List[str]:
    try:
        listing = Listing(source=listing_source, show_log=False)
        data = listing.all_symbols(show_log=False, to_df=True)
        rows = data.to_dict("records") if hasattr(data, "to_dict") else []
        symbols = filter_stock_symbols(rows)
        if not symbols:
            raise ValueError("No stock symbols extracted from listing source")

        exchange_groups: Dict[str, List[str]] = {}
        for row in rows:
            symbol = str(row.get("symbol", "")).strip().upper()
            if symbol not in symbols:
                continue
            exchange = str(row.get("exchange", "OTHER")).strip().upper() or "OTHER"
            exchange_groups.setdefault(exchange, []).append(symbol)

        unique_groups = {
            key: list(dict.fromkeys(values))
            for key, values in exchange_groups.items()
        }
        diversified = interleave_exchange_symbols(unique_groups, limit)
        if diversified:
            return diversified[:limit]

        return list(dict.fromkeys(symbols))[:limit]
    except Exception:
        return DEFAULT_BENCH_SYMBOLS[:limit]


def benchmark_row_to_dict(row: BenchmarkRow) -> Dict[str, Any]:
    data = asdict(row)
    total_requests = row.runs * row.symbols
    data["total_requests"] = total_requests
    data["success_rate"] = (row.success_count / total_requests) * 100 if total_requests else 0.0
    data["provider_breakdown_json"] = json.dumps(row.provider_breakdown, ensure_ascii=True, sort_keys=True)
    data["error_breakdown_json"] = json.dumps(row.error_breakdown, ensure_ascii=True, sort_keys=True)
    del data["provider_breakdown"]
    del data["error_breakdown"]
    return data


def write_results_csv(path: Path, rows: List[BenchmarkRow]) -> None:
    ensure_parent_dir(path)
    fieldnames = list(benchmark_row_to_dict(rows[0]).keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            for row in rows:
                writer.writerow(benchmark_row_to_dict(row))


def build_report_payload(rows: List[BenchmarkRow], symbols: List[str], args: argparse.Namespace) -> Dict[str, Any]:
    best = max(rows, key=lambda row: row.requests_per_second) if rows else None
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "symbols": symbols,
        "config": {
            "providers": parse_providers(args.providers),
            "concurrency": parse_levels(args.concurrency),
            "runs": args.runs,
            "start": args.start or None,
            "end": args.end or None,
            "interval": args.interval,
            "count_back": args.count_back if args.count_back > 0 else None,
            "listing_source": args.listing_source,
            "symbol_count": args.symbol_count,
            "profile": args.profile or None,
        },
        "rows": [benchmark_row_to_dict(row) for row in rows],
        "best": benchmark_row_to_dict(best) if best else None,
    }


def write_results_json(path: Path, rows: List[BenchmarkRow], symbols: List[str], args: argparse.Namespace) -> None:
    ensure_parent_dir(path)
    payload = build_report_payload(rows, symbols, args)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=True, indent=2)
        f.write("\n")


def _run_one_request(provider: str, symbol: str, args: argparse.Namespace) -> RequestSample:
    started = time.perf_counter()
    try:
        frame = Quote(source=provider, symbol=symbol, show_log=False).history(
            start=args.start or None,
            end=args.end or None,
            interval=args.interval,
            count_back=args.count_back if args.count_back > 0 else None,
        )
        elapsed = time.perf_counter() - started
        attrs = getattr(frame, "attrs", {}) if frame is not None else {}
        source_used = str(attrs.get("source_used", provider)).upper()
        rows_fetched = int(len(frame)) if frame is not None else 0
        return RequestSample(
            success=True,
            latency_seconds=elapsed,
            source_used=source_used,
            rows_fetched=rows_fetched,
            error_name=None,
        )
    except Exception as exc:
        return RequestSample(
            success=False,
            latency_seconds=time.perf_counter() - started,
            source_used=None,
            rows_fetched=0,
            error_name=exc.__class__.__name__,
        )


def run_one_benchmark(provider: str, symbols: List[str], concurrency: int, args: argparse.Namespace) -> BenchmarkRow:
    samples: List[RequestSample] = []
    started = time.perf_counter()

    for _ in range(args.runs):
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            run_samples = list(executor.map(lambda symbol: _run_one_request(provider, symbol, args), symbols))
        samples.extend(run_samples)

    elapsed = max(time.perf_counter() - started, 1e-9)
    latencies = sorted(sample.latency_seconds for sample in samples)
    success_count = sum(1 for sample in samples if sample.success)
    failure_count = len(samples) - success_count
    provider_breakdown: Dict[str, int] = {}
    error_breakdown: Dict[str, int] = {}
    total_rows_fetched = 0

    for sample in samples:
        total_rows_fetched += sample.rows_fetched
        if sample.success and sample.source_used:
            provider_breakdown[sample.source_used] = provider_breakdown.get(sample.source_used, 0) + 1
        elif sample.error_name:
            error_breakdown[sample.error_name] = error_breakdown.get(sample.error_name, 0) + 1

    p50 = statistics.median(latencies)
    p95 = statistics.quantiles(latencies, n=100)[94] if len(latencies) >= 2 else latencies[0]
    total_requests = len(samples)
    rps = total_requests / elapsed

    return BenchmarkRow(
        provider_requested=provider,
        concurrency=concurrency,
        runs=args.runs,
        symbols=len(symbols),
        success_count=success_count,
        failure_count=failure_count,
        total_rows_fetched=total_rows_fetched,
        elapsed_seconds=elapsed,
        requests_per_second=rps,
        requests_per_minute=rps * 60,
        p50_latency_seconds=p50,
        p95_latency_seconds=p95,
        min_latency_seconds=min(latencies),
        max_latency_seconds=max(latencies),
        mean_latency_seconds=statistics.mean(latencies),
        provider_breakdown=provider_breakdown,
        error_breakdown=error_breakdown,
    )


def format_row(row: BenchmarkRow) -> str:
    total_requests = row.runs * row.symbols
    success_rate = (row.success_count / total_requests) * 100 if total_requests else 0.0
    provider_summary = ",".join(f"{key}:{value}" for key, value in sorted(row.provider_breakdown.items())) or "-"
    error_summary = ",".join(f"{key}:{value}" for key, value in sorted(row.error_breakdown.items())) or "-"
    return (
        f"provider={row.provider_requested:>4} | concurrency={row.concurrency:>3} | total={total_requests:>4} | "
        f"success={row.success_count:>4} | fail={row.failure_count:>4} ({success_rate:6.2f}%) | "
        f"rows={row.total_rows_fetched:>6} | elapsed={row.elapsed_seconds:7.2f}s | "
        f"rps={row.requests_per_second:7.2f} | p50={row.p50_latency_seconds:6.2f}s | "
        f"p95={row.p95_latency_seconds:6.2f}s | providers={provider_summary} | errors={error_summary}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark AUTO open-source routing with large symbol sets")
    parser.add_argument("--providers", type=str, default="AUTO,VCI,KBS")
    parser.add_argument("--symbols", type=str, default="")
    parser.add_argument("--symbol-count", type=int, default=60)
    parser.add_argument("--listing-source", type=str, default="AUTO")
    parser.add_argument("--concurrency", type=str, default="8,16")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--interval", type=str, default="1D")
    parser.add_argument("--start", type=str, default="2026-03-03")
    parser.add_argument("--end", type=str, default="2026-04-03")
    parser.add_argument("--count-back", type=int, default=30)
    parser.add_argument("--profile", type=str, default="", choices=[""] + list_profiles())
    parser.add_argument("--output-csv", type=str, default="")
    parser.add_argument("--output-json", type=str, default="")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    if args.profile:
        apply_profile(args.profile, overwrite=True)
        print(f"Applied profile: {args.profile}")

    symbols = parse_symbols(args.symbols) if args.symbols else load_large_symbol_set(args.symbol_count, args.listing_source)
    providers = parse_providers(args.providers)
    levels = parse_levels(args.concurrency)

    print("=== AUTO Open-Source Benchmark ===")
    print(f"Symbols: {len(symbols)}")
    print(f"Providers: {providers}")
    print(f"Concurrency levels: {levels}")
    print(f"Runs per level: {args.runs}")

    rows: List[BenchmarkRow] = []
    for provider in providers:
        for concurrency in levels:
            row = run_one_benchmark(provider, symbols, concurrency, args)
            rows.append(row)
            print(format_row(row))

    best = max(rows, key=lambda row: row.requests_per_second)
    print("\n=== Summary ===")
    print("Best throughput:")
    print(format_row(best))

    if args.output_csv:
        csv_path = Path(args.output_csv)
        write_results_csv(csv_path, rows)
        print(f"CSV report: {csv_path}")

    if args.output_json:
        json_path = Path(args.output_json)
        write_results_json(json_path, rows, symbols, args)
        print(f"JSON report: {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())