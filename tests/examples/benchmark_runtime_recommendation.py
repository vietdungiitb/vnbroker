"""Build runtime recommendation from benchmark JSON reports.

Examples:
- python -m tests.examples.benchmark_runtime_recommendation --bench-json tmp/bench/price_board_rate_limit_60s_20260413.json
- python -m tests.examples.benchmark_runtime_recommendation --bench-json tmp/bench/price_board_rate_limit_60s_20260413.json --output-json tmp/bench/runtime_recommendation_20260413.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _safe_row(rows: list[dict[str, Any]], provider: str) -> dict[str, Any] | None:
    candidates = [
        row
        for row in rows
        if row.get("provider") == provider
        and float(row.get("throttle_rate_pct", 100.0)) == 0.0
        and float(row.get("success_rate_pct", 0.0)) >= 99.0
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: float(r.get("success_per_minute", 0.0)))


def _max_row(rows: list[dict[str, Any]], provider: str) -> dict[str, Any] | None:
    candidates = [
        row
        for row in rows
        if row.get("provider") == provider
        and float(row.get("throttle_rate_pct", 100.0)) <= 5.0
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: float(r.get("attempts_per_minute", 0.0)))


def build_recommendation(payload: dict[str, Any]) -> dict[str, Any]:
    rows = list(payload.get("rows", []))

    kbs_safe = _safe_row(rows, "kbs")
    vci_safe = _safe_row(rows, "vci")
    kbs_max = _max_row(rows, "kbs")
    vci_max = _max_row(rows, "vci")

    primary = "kbs"
    if vci_safe and not kbs_safe:
        primary = "vci"
    elif vci_safe and kbs_safe:
        if float(vci_safe.get("success_per_minute", 0.0)) > float(kbs_safe.get("success_per_minute", 0.0)):
            primary = "vci"

    fallback = "vci" if primary == "kbs" else "kbs"

    kbs_target = kbs_safe or kbs_max
    vci_target = vci_safe or vci_max

    env = {
        "VNSTOCK_TRADING_AUTO_PRIMARY": primary,
    }
    if kbs_target is not None:
        env["VNSTOCK_KBS_ADAPTIVE_START_CONCURRENCY"] = str(int(kbs_target["concurrency"]))
    if vci_target is not None:
        env["VNSTOCK_VCI_ADAPTIVE_START_CONCURRENCY"] = str(int(vci_target["concurrency"]))

    return {
        "source": payload.get("generated_at"),
        "providers": payload.get("providers", []),
        "trading": {
            "primary": primary,
            "fallback": fallback,
            "kbs_safe": kbs_safe,
            "kbs_max": kbs_max,
            "vci_safe": vci_safe,
            "vci_max": vci_max,
        },
        "recommended_env": env,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate runtime recommendation from benchmark JSON")
    parser.add_argument("--bench-json", required=True)
    parser.add_argument("--output-json", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    in_path = Path(args.bench_json)
    with in_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    recommendation = build_recommendation(payload)

    print("=== Runtime Recommendation ===")
    print(f"primary={recommendation['trading']['primary']} | fallback={recommendation['trading']['fallback']}")
    for key, value in recommendation["recommended_env"].items():
        print(f"{key}={value}")

    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(recommendation, f, ensure_ascii=True, indent=2)
            f.write("\n")
        print(f"json_report={out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
