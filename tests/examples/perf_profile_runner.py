"""Apply a vnbroker performance profile and optionally run throughput benchmark.

Examples:
- python -m tests.examples.perf_profile_runner --profile benchmark_max_speed --show-env
- python -m tests.examples.perf_profile_runner --profile production_stable --run-benchmark --symbols ACB,VCB,TCB --concurrency 8,16,24
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from vnbroker.core.performance_profiles import apply_profile, list_profiles


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply vnbroker performance profile presets")
    parser.add_argument("--profile", type=str, default="production_stable", choices=list_profiles())
    parser.add_argument("--show-env", action="store_true")
    parser.add_argument("--run-benchmark", action="store_true")
    parser.add_argument("--symbols", type=str, default="ACB,VCB,TCB,HPG,VNM")
    parser.add_argument("--concurrency", type=str, default="8,16,24")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--start", type=str, default="2026-03-31")
    parser.add_argument("--end", type=str, default="2026-04-03")
    parser.add_argument("--count-back", type=int, default=5)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    applied = apply_profile(args.profile, overwrite=True)
    print(f"Applied profile: {args.profile}")

    if args.show_env:
        for key in sorted(applied):
            print(f"{key}={os.environ.get(key, '')}")

    if not args.run_benchmark:
        return 0

    root = Path(__file__).resolve().parents[2]
    command = [
        sys.executable,
        "-m",
        "tests.examples.vci_perf_benchmark",
        "--symbols",
        args.symbols,
        "--concurrency",
        args.concurrency,
        "--runs",
        str(args.runs),
        "--count-back",
        str(args.count_back),
        "--start",
        args.start,
        "--end",
        args.end,
    ]
    completed = subprocess.run(command, cwd=str(root), check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
