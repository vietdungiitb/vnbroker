"""Tests for AUTO benchmark helpers and report export."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from tests.examples.auto_source_benchmark import (
    BenchmarkRow,
    benchmark_row_to_dict,
    build_report_payload,
    interleave_exchange_symbols,
    write_results_csv,
    write_results_json,
)


def make_row(provider: str, concurrency: int) -> BenchmarkRow:
    return BenchmarkRow(
        provider_requested=provider,
        concurrency=concurrency,
        runs=1,
        symbols=4,
        success_count=4,
        failure_count=0,
        total_rows_fetched=120,
        elapsed_seconds=2.0,
        requests_per_second=2.0,
        requests_per_minute=120.0,
        p50_latency_seconds=0.4,
        p95_latency_seconds=0.8,
        min_latency_seconds=0.2,
        max_latency_seconds=1.0,
        mean_latency_seconds=0.5,
        provider_breakdown={provider: 4},
        error_breakdown={},
    )


def make_args() -> argparse.Namespace:
    return argparse.Namespace(
        providers="AUTO,VCI,KBS",
        concurrency="8,16",
        runs=1,
        start="2026-03-03",
        end="2026-04-03",
        interval="1D",
        count_back=30,
        listing_source="AUTO",
        symbol_count=60,
        profile="benchmark_max_speed",
        output_csv="",
        output_json="",
    )


def test_interleave_exchange_symbols_round_robins_groups():
    groups = {
        "HOSE": ["AAA", "AAB", "AAC"],
        "HNX": ["BBB", "BBC"],
        "UPCOM": ["CCC"],
    }

    result = interleave_exchange_symbols(groups, limit=6)

    assert result == ["AAA", "BBB", "CCC", "AAB", "BBC", "AAC"]


def test_benchmark_row_to_dict_serializes_breakdowns():
    payload = benchmark_row_to_dict(make_row("AUTO", 8))

    assert payload["total_requests"] == 4
    assert payload["success_rate"] == 100.0
    assert json.loads(payload["provider_breakdown_json"]) == {"AUTO": 4}


def test_write_results_csv_creates_report(tmp_path: Path):
    out_path = tmp_path / "reports" / "auto_benchmark.csv"
    rows = [make_row("AUTO", 8), make_row("VCI", 16)]

    write_results_csv(out_path, rows)

    with out_path.open("r", encoding="utf-8", newline="") as f:
        records = list(csv.DictReader(f))

    assert len(records) == 2
    assert records[0]["provider_requested"] == "AUTO"
    assert records[1]["concurrency"] == "16"


def test_write_results_json_creates_report(tmp_path: Path):
    out_path = tmp_path / "reports" / "auto_benchmark.json"
    rows = [make_row("AUTO", 8), make_row("KBS", 16)]

    write_results_json(out_path, rows, ["ACB", "VCB", "TCB"], make_args())

    with out_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    assert payload["symbols"] == ["ACB", "VCB", "TCB"]
    assert payload["config"]["profile"] == "benchmark_max_speed"
    assert payload["best"]["provider_requested"] == "AUTO"


def test_build_report_payload_selects_highest_rps():
    rows = [make_row("AUTO", 8), make_row("VCI", 16)]
    rows[1].requests_per_second = 3.5

    payload = build_report_payload(rows, ["ACB"], make_args())

    assert payload["best"]["provider_requested"] == "VCI"