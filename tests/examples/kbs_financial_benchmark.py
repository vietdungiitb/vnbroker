"""Benchmark KBS Finance throughput và latency theo report type.

Cách sử dụng:
- python -m tests.examples.kbs_financial_benchmark --symbols ACB,VCB,TCB,HPG,VNM --runs 3
- python -m tests.examples.kbs_financial_benchmark --symbols ACB,VCB,TCB --report-types income_statement,balance_sheet --period year --concurrency 4,8
- python -m tests.examples.kbs_financial_benchmark --symbol-file assets/data/vn30_symbols.csv --symbol-limit 20 --runs 2 --output-json tmp/bench/kbs_financial.json
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from vnbroker.explorer.kbs.financial import Finance, FieldDisplayMode


VALID_REPORT_TYPES = ["income_statement", "balance_sheet", "cash_flow", "financial_ratios"]
REPORT_METHOD_MAP = {
    "income_statement": "income_statement",
    "balance_sheet": "balance_sheet",
    "cash_flow": "cash_flow",
    "financial_ratios": "ratio",
}


@dataclass
class BatchResult:
    report_type: str
    period: str
    concurrency: int
    runs: int
    symbols: int
    success_count: int
    failure_count: int
    elapsed_seconds: float
    requests_per_second: float
    requests_per_minute: float
    p50_latency_seconds: float
    p95_latency_seconds: float
    min_latency_seconds: float
    max_latency_seconds: float
    mean_latency_seconds: float


def batch_result_to_dict(result: BatchResult) -> Dict[str, Any]:
    data = asdict(result)
    total = result.runs * result.symbols
    data["total_requests"] = total
    data["success_rate"] = (result.success_count / total) * 100 if total else 0.0
    return data


def fetch_one(symbol: str, report_type: str, period: str) -> Optional[int]:
    """Lấy một báo cáo tài chính. Trả về số dòng nếu thành công, None nếu thất bại."""
    try:
        finance = Finance(symbol=symbol, show_log=False)
        method_name = REPORT_METHOD_MAP[report_type]
        method = getattr(finance, method_name)
        df = method(period=period, display_mode=FieldDisplayMode.STD)
        if df is not None and not df.empty:
            return len(df)
        return None
    except Exception:
        return None


def run_one_batch(
    symbols: List[str],
    report_type: str,
    period: str,
    concurrency: int,
    runs: int,
) -> BatchResult:
    latencies: List[float] = []
    success_count = 0
    failure_count = 0

    started = time.perf_counter()

    for _ in range(runs):
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(fetch_one, sym, report_type, period): sym
                for sym in symbols
            }
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    success_count += 1
                else:
                    failure_count += 1
        t1 = time.perf_counter()
        latencies.append(t1 - t0)

    finished = time.perf_counter()
    elapsed = max(finished - started, 1e-9)

    total_requests = runs * len(symbols)
    rps = total_requests / elapsed
    rpm = rps * 60

    sorted_lat = sorted(latencies)
    p50 = statistics.median(sorted_lat)
    p95 = (
        statistics.quantiles(sorted_lat, n=100)[94]
        if len(sorted_lat) >= 2
        else sorted_lat[0]
    )

    return BatchResult(
        report_type=report_type,
        period=period,
        concurrency=concurrency,
        runs=runs,
        symbols=len(symbols),
        success_count=success_count,
        failure_count=failure_count,
        elapsed_seconds=elapsed,
        requests_per_second=rps,
        requests_per_minute=rpm,
        p50_latency_seconds=p50,
        p95_latency_seconds=p95,
        min_latency_seconds=min(sorted_lat),
        max_latency_seconds=max(sorted_lat),
        mean_latency_seconds=statistics.mean(sorted_lat),
    )


def format_row(r: BatchResult) -> str:
    total = r.runs * r.symbols
    success_rate = (r.success_count / total) * 100 if total else 0.0
    return (
        f"report={r.report_type:<20} period={r.period:<8} concurrency={r.concurrency:>3} "
        f"| total={total:>4} | ok={r.success_count:>4} | fail={r.failure_count:>4} "
        f"({success_rate:6.2f}%) | elapsed={r.elapsed_seconds:7.2f}s "
        f"| rps={r.requests_per_second:6.2f} | rpm={r.requests_per_minute:7.2f} "
        f"| p50={r.p50_latency_seconds:6.2f}s | p95={r.p95_latency_seconds:6.2f}s "
        f"| min={r.min_latency_seconds:6.2f}s | max={r.max_latency_seconds:6.2f}s"
    )


def parse_symbols(raw: str) -> List[str]:
    values = [s.strip().upper() for s in raw.split(",") if s.strip()]
    if not values:
        raise ValueError("Không có symbol nào được cung cấp.")
    return values


def load_symbols_from_csv(path: Path, limit: int) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {path}")
    symbols: List[str] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = {name.lower(): name for name in (reader.fieldnames or [])}
        symbol_col = cols.get("symbol")
        if symbol_col is None:
            raise ValueError("CSV phải có cột 'symbol'.")
        for row in reader:
            sym = str(row.get(symbol_col, "")).strip().upper()
            if sym:
                symbols.append(sym)
            if limit > 0 and len(symbols) >= limit:
                break
    if not symbols:
        raise ValueError("Không tải được symbol nào từ CSV.")
    return symbols


def parse_list(raw: str) -> List[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def parse_concurrency(raw: str) -> List[int]:
    values = [int(x.strip()) for x in raw.split(",") if x.strip()]
    if not values:
        raise ValueError("Danh sách concurrency rỗng.")
    if any(v <= 0 for v in values):
        raise ValueError("Concurrency phải là số dương.")
    return values


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_results_csv(path: Path, rows: List[BatchResult]) -> None:
    ensure_parent_dir(path)
    fieldnames = list(batch_result_to_dict(rows[0]).keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            for row in rows:
                writer.writerow(batch_result_to_dict(row))


def write_results_json(
    path: Path,
    rows: List[BatchResult],
    symbols: List[str],
    args: argparse.Namespace,
) -> None:
    ensure_parent_dir(path)
    successful_rows = [r for r in rows if r.success_count > 0]
    best = max(successful_rows, key=lambda r: r.requests_per_second) if successful_rows else None
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "KBS",
        "symbols": symbols,
        "config": {
            "runs": args.runs,
            "concurrency": parse_concurrency(args.concurrency),
            "report_types": parse_list(args.report_types),
            "period": args.period,
            "symbol_file": args.symbol_file or None,
            "symbol_limit": args.symbol_limit,
        },
        "rows": [batch_result_to_dict(r) for r in rows],
        "best": batch_result_to_dict(best) if best else None,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KBS Financial benchmark — đo throughput & latency báo cáo tài chính"
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default="ACB,VCB,TCB,HPG,VNM",
        help="Danh sách mã CK, phân cách bằng dấu phẩy (mặc định: ACB,VCB,TCB,HPG,VNM)",
    )
    parser.add_argument("--symbol-file", type=str, default="", help="Đường dẫn file CSV chứa cột 'symbol'")
    parser.add_argument("--symbol-limit", type=int, default=20, help="Số symbol tối đa khi tải từ CSV")
    parser.add_argument(
        "--report-types",
        type=str,
        default="income_statement,balance_sheet,cash_flow,financial_ratios",
        help="Loại báo cáo, phân cách bằng dấu phẩy",
    )
    parser.add_argument(
        "--period",
        type=str,
        default="year",
        choices=["year", "quarter"],
        help="Kỳ báo cáo: 'year' hoặc 'quarter' (mặc định: year)",
    )
    parser.add_argument(
        "--concurrency",
        type=str,
        default="4,8",
        help="Mức độ song song (thread pool), phân cách bằng dấu phẩy (mặc định: 4,8)",
    )
    parser.add_argument("--runs", type=int, default=2, help="Số lần lặp mỗi batch (mặc định: 2)")
    parser.add_argument("--output-csv", type=str, default="", help="Lưu kết quả ra file CSV")
    parser.add_argument("--output-json", type=str, default="", help="Lưu kết quả ra file JSON")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    # Load symbols
    if args.symbol_file:
        symbols = load_symbols_from_csv(Path(args.symbol_file), limit=args.symbol_limit)
    else:
        symbols = parse_symbols(args.symbols)

    report_types = parse_list(args.report_types)
    concurrency_levels = parse_concurrency(args.concurrency)

    # Validate report types
    invalid = [rt for rt in report_types if rt not in VALID_REPORT_TYPES]
    if invalid:
        print(f"[LỖI] Loại báo cáo không hợp lệ: {invalid}")
        print(f"Các giá trị hợp lệ: {VALID_REPORT_TYPES}")
        return 1

    print("=== KBS Financial Benchmark ===")
    print(f"Symbols ({len(symbols)}): {', '.join(symbols)}")
    print(f"Loại báo cáo: {report_types}")
    print(f"Kỳ: {args.period}")
    print(f"Runs/batch: {args.runs}")
    print(f"Concurrency levels: {concurrency_levels}")
    print()

    rows: List[BatchResult] = []

    for report_type in report_types:
        for concurrency in concurrency_levels:
            print(f"[Đang chạy] report={report_type} period={args.period} concurrency={concurrency}...")
            result = run_one_batch(
                symbols=symbols,
                report_type=report_type,
                period=args.period,
                concurrency=concurrency,
                runs=args.runs,
            )
            rows.append(result)
            print(f"  {format_row(result)}")

    print("\n=== Tổng kết ===")
    successful_rows = [r for r in rows if r.success_count > 0]
    if successful_rows:
        best = max(successful_rows, key=lambda r: r.requests_per_second)
        print("Throughput cao nhất:")
        print(f"  {format_row(best)}")
    else:
        print("Không có batch nào thành công hoàn toàn hoặc một phần.")

    if args.output_csv:
        csv_path = Path(args.output_csv)
        write_results_csv(csv_path, rows)
        print(f"\nBáo cáo CSV: {csv_path}")

    if args.output_json:
        json_path = Path(args.output_json)
        write_results_json(json_path, rows, symbols, args)
        print(f"Báo cáo JSON: {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
