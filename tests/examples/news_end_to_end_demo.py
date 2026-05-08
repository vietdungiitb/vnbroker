"""
End-to-end Stock News demo.

Usage:
python -m tests.examples.news_end_to_end_demo --symbol ACB --source AUTO --query "ket qua" --out tmp/news_health/demo_news_health.jsonl
"""

from __future__ import annotations

import argparse

from vnbroker.common.client import Vnbroker
from vnbroker.news.monitor import summarize_alerts


def run(symbol: str, source: str, query: str, out: str):
    stock = Vnbroker(show_log=False).stock(symbol, source=source)

    print("=== 1) latest ===")
    latest = stock.news.latest(limit=10)
    print(f"rows={len(latest)} cols={list(latest.columns)[:6]}")

    print("=== 2) query ===")
    queried = stock.news.query(query, symbol=symbol, limit=10)
    print(f"query='{query}' rows={len(queried)}")

    print("=== 3) filter (symbol + source) ===")
    filtered = stock.news.filter(symbol=symbol, sources=["VCI", "KBS", "RSS_CAFEF"], limit=10)
    print(f"filtered rows={len(filtered)}")

    print("=== 4) monitor health ===")
    result = stock.news.monitor_health(
        file_path=out,
        fmt="jsonl",
        max_failures=2,
        max_cooldown_sec=30.0,
    )
    alerts = result["alerts"]
    print(f"alerts={len(alerts)} summary={summarize_alerts(alerts)}")
    print(f"logged_path={result['logged_path']}")


def parse_args():
    parser = argparse.ArgumentParser(description="Run end-to-end Stock News demo")
    parser.add_argument("--symbol", default="ACB")
    parser.add_argument("--source", default="AUTO")
    parser.add_argument("--query", default="ket qua")
    parser.add_argument("--out", default="tmp/news_health/demo_news_health.jsonl")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(symbol=args.symbol, source=args.source, query=args.query, out=args.out)
