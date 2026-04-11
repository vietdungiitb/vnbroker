"""
Sanitize a News health JSONL file (rewrite NaN to null).

Usage:
python -m tests.examples.news_health_sanitize --file tmp/news_health/news_health.jsonl
"""

from __future__ import annotations

import argparse

from vnstock.news.health import sanitize_health_jsonl_file


def parse_args():
    parser = argparse.ArgumentParser(description="Sanitize News health JSONL log")
    parser.add_argument("--file", required=True, help="Path to JSONL log file")
    return parser.parse_args()


def main():
    args = parse_args()
    stats = sanitize_health_jsonl_file(args.file)
    print(stats)


if __name__ == "__main__":
    main()
