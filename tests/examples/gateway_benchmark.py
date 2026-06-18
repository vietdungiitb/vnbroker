"""Benchmark Gateway (PAT) vs Legacy Direct Access.

Usage:
    python -m tests.examples.gateway_benchmark --symbols ACB,VCB,TCB,HPG,VNM --runs 3
    python -m tests.examples.gateway_benchmark --symbol-count 20 --concurrency 4,8 --runs 2
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

from vnbroker import Vnbroker
from vnbroker.api.listing import Listing
from vnbroker.api.quote import Quote


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
    mode: str  # "GATEWAY" or "DIRECT_VCI" or "DIRECT_KBS"
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
        # Simple interleaving
        diversified = []
        max_len = max(len(v) for v in unique_groups.values()) if unique_groups else 0
        for i in range(max_len):
            for key in unique_groups:
                if i < len(unique_groups[key]):
                    diversified.append(unique_groups[key][i])
                    if len(diversified) >= limit:
                        return diversified
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
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(benchmark_row_to_dict(rows[0]).keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(benchmark_row_to_dict(row))


def write_results_json(path: Path, rows: List[BenchmarkRow], symbols: List[str], args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(),
        "symbols": symbols,
        "config": {
            "modes": args.modes,
            "concurrency": args.concurrency,
            "runs": args.runs,
            "start": args.start,
            "end": args.end,
            "interval": args.interval,
            "count_back": args.count_back,
            "listing_source": args.listing_source,
            "symbol_count": args.symbol_count,
        },
        "rows": [benchmark_row_to_dict(row) for row in rows],
        "best": benchmark_row_to_dict(max(rows, key=lambda r: r.requests_per_second)) if rows else None,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _run_one_request_gateway(vn: Vnbroker, symbol: str, args: argparse.Namespace) -> RequestSample:
    """Run quote.history via Gateway (PAT)."""
    started = time.perf_counter()
    try:
        acb = vn.stock(symbol)
        frame = acb.quote.history(
            start=args.start or None,
            end=args.end or None,
            interval=args.interval,
            count_back=args.count_back if args.count_back > 0 else None,
        )
        elapsed = time.perf_counter() - started
        attrs = getattr(frame, "attrs", {}) if frame is not None else {}
        source_used = str(attrs.get("source_used", "GATEWAY")).upper()
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


def _run_one_request_direct(provider: str, symbol: str, args: argparse.Namespace) -> RequestSample:
    """Run quote.history via Direct Mode (legacy)."""
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


def run_one_benchmark(mode: str, symbols: List[str], concurrency: int, args: argparse.Namespace, vn: Vnbroker | None = None) -> BenchmarkRow:
    samples: List[RequestSample] = []
    started = time.perf_counter()

    for _ in range(args.runs):
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            if mode == "GATEWAY":
                run_samples = list(executor.map(lambda s: _run_one_request_gateway(vn, s, args), symbols))
            else:  # DIRECT_VCI, DIRECT_KBS
                run_samples = list(executor.map(lambda s: _run_one_request_direct(mode.replace("DIRECT_", ""), s, args), symbols))
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
        mode=mode,
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
        f"mode={row.mode:>12} | concurrency={row.concurrency:>3} | total={total_requests:>4} | "
        f"success={row.success_count:>4} | fail={row.failure_count:>4} ({success_rate:6.2f}%) | "
        f"rows={row.total_rows_fetched:>6} | elapsed={row.elapsed_seconds:7.2f}s | "
        f"rps={row.requests_per_second:7.2f} | p50={row.p50_latency_seconds:6.2f}s | "
        f"p95={row.p95_latency_seconds:6.2f}s | providers={provider_summary} | errors={error_summary}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark Gateway (PAT) vs Legacy Direct Access")
    parser.add_argument("--modes", type=str, default="GATEWAY,DIRECT_VCI,DIRECT_KBS",
                        help="Comma-separated modes: GATEWAY, DIRECT_VCI, DIRECT_KBS")
    parser.add_argument("--symbols", type=str, default="")
    parser.add_argument("--symbol-count", type=int, default=20)
    parser.add_argument("--listing-source", type=str, default="AUTO")
    parser.add_argument("--concurrency", type=str, default="4,8")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--interval", type=str, default="1D")
    parser.add_argument("--start", type=str, default="2026-03-03")
    parser.add_argument("--end", type=str, default="2026-04-03")
    parser.add_argument("--count-back", type=int, default=30)
    parser.add_argument("--output-csv", type=str, default="")
    parser.add_argument("--output-json", type=str, default="")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    modes = [m.strip().upper() for m in args.modes.split(",") if m.strip()]
    valid_modes = {"GATEWAY", "DIRECT_VCI", "DIRECT_KBS"}
    for m in modes:
        if m not in valid_modes:
            raise ValueError(f"Invalid mode: {m}. Valid: {valid_modes}")

    symbols = parse_symbols(args.symbols) if args.symbols else load_large_symbol_set(args.symbol_count, args.listing_source)
    levels = parse_levels(args.concurrency)

    print("=== Gateway vs Direct Benchmark ===")
    print(f"Symbols: {len(symbols)} ({', '.join(symbols[:10])}{'...' if len(symbols) > 10 else ''})")
    print(f"Modes: {modes}")
    print(f"Concurrency levels: {levels}")
    print(f"Runs per level: {args.runs}")
    print(f"Date range: {args.start} to {args.end} (interval={args.interval}, count_back={args.count_back})")
    print()

    # Initialize Gateway client once
    vn = None
    if "GATEWAY" in modes:
        vn = Vnbroker(show_log=False)  # Uses DEFAULT_PAT + DEFAULT_GATEWAY_URL

    rows: List[BenchmarkRow] = []
    for mode in modes:
        for concurrency in levels:
            row = run_one_benchmark(mode, symbols, concurrency, args, vn)
            rows.append(row)
            print(format_row(row))

    print("\n=== Summary ===")
    best = max(rows, key=lambda row: row.requests_per_second)
    print("Best throughput:")
    print(format_row(best))

    # Comparison table
    print("\n=== Comparison (concurrency=4, runs=2) ===")
    for mode in modes:
        mode_rows = [r for r in rows if r.mode == mode and r.concurrency == 4]
        if mode_rows:
            r = mode_rows[0]
            print(f"{mode:>12}: success={r.success_count:>3}/{r.runs*r.symbols:<3} ({r.success_count/(r.runs*r.symbols)*100:5.1f}%) | "
                  f"rps={r.requests_per_second:6.2f} | p50={r.p50_latency_seconds:5.2f}s | p95={r.p95_latency_seconds:5.2f}s")

    if args.output_csv:
        csv_path = Path(args.output_csv)
        write_results_csv(csv_path, rows)
        print(f"\nCSV report: {csv_path}")

    if args.output_json:
        json_path = Path(args.output_json)
        write_results_json(json_path, rows, symbols, args)
        print(f"JSON report: {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())