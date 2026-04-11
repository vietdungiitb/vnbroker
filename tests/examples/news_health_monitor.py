"""
News health monitor example.

Usage:
python -m tests.examples.news_health_monitor --symbol ACB --source AUTO --iterations 3 --interval 5 --out tmp/news_health/news_health.jsonl
"""

from __future__ import annotations

import argparse
import time

from vnstock.common.client import Vnstock
from vnstock.news.monitor import summarize_alerts


def run_monitor(
    symbol: str,
    source: str,
    iterations: int,
    interval: int,
    out: str,
    fmt: str,
    max_failures: int,
    max_cooldown_sec: float,
):
    stock = Vnstock(show_log=False)
    target = stock.stock(symbol, source=source)

    for idx in range(iterations):
        result = target.news.monitor_health(
            file_path=out,
            fmt=fmt,
            max_failures=max_failures,
            max_cooldown_sec=max_cooldown_sec,
        )
        alerts = result["alerts"]
        summary = summarize_alerts(alerts)
        print(f"iteration={idx + 1} alerts={len(alerts)} summary={summary}")

        if idx + 1 < iterations:
            time.sleep(interval)


def parse_args():
    parser = argparse.ArgumentParser(description="Monitor vnstock news source health")
    parser.add_argument("--symbol", default="ACB")
    parser.add_argument("--source", default="AUTO")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--out", default="tmp/news_health/news_health.jsonl")
    parser.add_argument("--fmt", choices=["jsonl", "csv"], default="jsonl")
    parser.add_argument("--max-failures", type=int, default=2)
    parser.add_argument("--max-cooldown-sec", type=float, default=30.0)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_monitor(
        symbol=args.symbol,
        source=args.source,
        iterations=args.iterations,
        interval=args.interval,
        out=args.out,
        fmt=args.fmt,
        max_failures=args.max_failures,
        max_cooldown_sec=args.max_cooldown_sec,
    )
