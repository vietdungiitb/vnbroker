"""Auto-tune concurrency for vnstock quote providers.

Examples:
- python -m tests.examples.auto_tune_concurrency --provider vci --symbols ACB,VCB,TCB,HPG,VNM --concurrency 8,12,16,24
- python -m tests.examples.auto_tune_concurrency --provider kbs --symbols ACB,VCB,TCB --concurrency 4,8,12
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, List

from vnstock.explorer.kbs.quote import Quote as KBSQuote
from vnstock.explorer.vci.quote import Quote as VCIQuote


@dataclass
class TuneRow:
    provider: str
    concurrency: int
    runs: int
    symbols: int
    success_count: int
    failure_count: int
    elapsed_seconds: float
    requests_per_second: float
    requests_per_minute: float
    p50_seconds: float
    p95_seconds: float



def parse_symbols(raw_symbols: str) -> List[str]:
    values = [s.strip().upper() for s in raw_symbols.split(",") if s.strip()]
    if not values:
        raise ValueError("No symbols provided")
    return values



def parse_concurrency(raw: str) -> List[int]:
    values = [int(x.strip()) for x in raw.split(",") if x.strip()]
    if not values:
        raise ValueError("Concurrency list is empty")
    if any(v <= 0 for v in values):
        raise ValueError("Concurrency must be positive")
    return values



def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)



def write_csv(path: Path, rows: List[TuneRow]) -> None:
    ensure_parent(path)
    fieldnames = list(asdict(rows[0]).keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            for row in rows:
                writer.writerow(asdict(row))



def write_json(path: Path, provider: str, symbols: List[str], rows: List[TuneRow]) -> None:
    ensure_parent(path)
    best = max(rows, key=lambda r: r.requests_per_second) if rows else None
    payload: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "provider": provider,
        "symbols": symbols,
        "rows": [asdict(row) for row in rows],
        "best": asdict(best) if best else None,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=True, indent=2)
        f.write("\n")


async def run_vci_once(symbols: List[str], concurrency: int, args: argparse.Namespace) -> int:
    results = await VCIQuote.fetch_multiple(
        symbols=symbols,
        start=args.start,
        end=args.end,
        interval=args.interval,
        count_back=args.count_back,
        length=args.length,
        max_concurrency=concurrency,
        show_log=False,
    )
    return len(results)


def run_kbs_once(symbols: List[str], concurrency: int, args: argparse.Namespace) -> int:
    results = KBSQuote.fetch_multiple(
        symbols=symbols,
        start=args.start,
        end=args.end,
        interval=args.interval,
        count_back=args.count_back,
        length=args.length,
        max_concurrency=concurrency,
        show_log=False,
        adaptive_concurrency=True,
    )
    return len(results)


async def benchmark_one_level(provider: str, symbols: List[str], concurrency: int, args: argparse.Namespace) -> TuneRow:
    latencies: List[float] = []
    success_count = 0
    failure_count = 0

    started = time.perf_counter()
    for _ in range(args.runs):
        t0 = time.perf_counter()
        if provider == "vci":
            success = await run_vci_once(symbols, concurrency, args)
        else:
            success = run_kbs_once(symbols, concurrency, args)
        t1 = time.perf_counter()

        latencies.append(t1 - t0)
        success_count += success
        failure_count += max(len(symbols) - success, 0)

    elapsed = max(time.perf_counter() - started, 1e-9)
    total = args.runs * len(symbols)
    rps = total / elapsed

    sorted_lat = sorted(latencies)
    p50 = statistics.median(sorted_lat)
    p95 = statistics.quantiles(sorted_lat, n=100)[94] if len(sorted_lat) >= 2 else sorted_lat[0]

    return TuneRow(
        provider=provider,
        concurrency=concurrency,
        runs=args.runs,
        symbols=len(symbols),
        success_count=success_count,
        failure_count=failure_count,
        elapsed_seconds=elapsed,
        requests_per_second=rps,
        requests_per_minute=rps * 60,
        p50_seconds=p50,
        p95_seconds=p95,
    )



def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Auto-tune vnstock concurrency")
    parser.add_argument("--provider", type=str, choices=["vci", "kbs"], default="vci")
    parser.add_argument("--symbols", type=str, default="ACB,VCB,TCB,HPG,VNM")
    parser.add_argument("--concurrency", type=str, default="6,8,12,16,24")
    parser.add_argument("--interval", type=str, default="1D")
    parser.add_argument("--start", type=str, default="2026-03-31")
    parser.add_argument("--end", type=str, default="2026-04-03")
    parser.add_argument("--length", type=str, default="")
    parser.add_argument("--count-back", type=int, default=5)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--output-csv", type=str, default="tmp/bench/auto_tune.csv")
    parser.add_argument("--output-json", type=str, default="tmp/bench/auto_tune.json")
    return parser


async def main_async() -> int:
    args = build_arg_parser().parse_args()
    symbols = parse_symbols(args.symbols)
    levels = parse_concurrency(args.concurrency)

    rows: List[TuneRow] = []
    print(f"=== Auto Tune: provider={args.provider} ===")
    print(f"Symbols: {len(symbols)} | runs={args.runs} | levels={levels}")

    for level in levels:
        row = await benchmark_one_level(args.provider, symbols, level, args)
        rows.append(row)
        print(
            f"concurrency={row.concurrency:>3} | rps={row.requests_per_second:7.2f} | "
            f"rpm={row.requests_per_minute:8.2f} | p50={row.p50_seconds:6.2f}s | "
            f"p95={row.p95_seconds:6.2f}s | success={row.success_count:>4} | fail={row.failure_count:>4}"
        )

    best = max(rows, key=lambda r: r.requests_per_second)
    print("\nBest level:")
    print(
        f"concurrency={best.concurrency} | rps={best.requests_per_second:.2f} | "
        f"rpm={best.requests_per_minute:.2f} | p95={best.p95_seconds:.2f}s"
    )

    csv_path = Path(args.output_csv)
    json_path = Path(args.output_json)
    write_csv(csv_path, rows)
    write_json(json_path, args.provider, symbols, rows)
    print(f"CSV report: {csv_path}")
    print(f"JSON report: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
