"""Benchmark TCBS broker + explorer endpoint throughput và latency.

Hai lane độc lập:
  1. Explorer lane  — public endpoints, không cần auth
  2. Broker lane    — authenticated endpoints, cần API key + OTP

Cách sử dụng:

  # Explorer lane (không cần auth):
  python -m tests.examples.tcbs_broker_benchmark --mode explorer --symbols ACB,VCB,TCB,HPG,VNM

  # Broker lane (cần TCBS_API_KEY env + nhập OTP tại prompt):
  python -m tests.examples.tcbs_broker_benchmark --mode broker

  # Cả hai lanes:
  python -m tests.examples.tcbs_broker_benchmark --mode all --runs 3 --output-json tmp/bench/tcbs_bench.json

  # Explorer với nhiều symbols từ CSV:
  python -m tests.examples.tcbs_broker_benchmark --mode explorer --symbol-file assets/data/vn30_symbols.csv --concurrency 4,8,12

ENV VARS:
  TCBS_API_KEY  hoặc  VNBROKER_BROKER_TCBS_API_KEY  — TCBS OpenAPI key
  TCBS_AUTH_TOKEN  — Pre-obtained JWT Bearer token (bỏ qua OTP prompt)
"""
from __future__ import annotations

import argparse
import csv
import getpass
import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ExplorerBatchResult:
    endpoint: str
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


@dataclass
class BrokerEndpointResult:
    endpoint: str
    runs: int
    success_count: int
    failure_count: int
    elapsed_seconds: float
    p50_latency_seconds: float
    p95_latency_seconds: float
    min_latency_seconds: float
    max_latency_seconds: float
    mean_latency_seconds: float
    sample_rows: int  # số dòng trả về từ lần chạy cuối (0 nếu scalar)


# ──────────────────────────────────────────────────────────────────────────────
# Explorer Lane — Quote history throughput
# ──────────────────────────────────────────────────────────────────────────────

def _fetch_one_quote(
    symbol: str,
    interval: str,
    length: str,
    auth_token: Optional[str],
) -> Optional[int]:
    """Lấy quote history 1 symbol. Trả về số dòng nếu thành công, None nếu lỗi.

    Lưu ý: TCBS explorer dùng domain riêng (apiextaws.tcbs.com.vn) yêu cầu
    session token khác với OpenAPI JWT. 401 là expected khi chỉ có OpenAPI key.
    """
    try:
        from vnbroker.explorer.tcbs.quote import Quote  # noqa: PLC0415

        q = Quote(symbol=symbol, show_log=False, auth_token=auth_token)
        # Lưu ý: history() dùng self.symbol, không nhận kwarg 'symbol'
        df = q.history(start=None, end=None, interval=interval, count_back=100, show_log=False)
        if df is not None and not df.empty:
            return len(df)
        return None
    except Exception:
        return None


def run_quote_batch(
    symbols: List[str],
    interval: str,
    length: str,
    concurrency: int,
    runs: int,
    auth_token: Optional[str],
) -> ExplorerBatchResult:
    latencies: List[float] = []
    success_count = 0
    failure_count = 0

    started = time.perf_counter()
    for _ in range(runs):
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(_fetch_one_quote, sym, interval, length, auth_token): sym
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

    return ExplorerBatchResult(
        endpoint="quote.history",
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


def _fetch_listing(auth_token: Optional[str]) -> Optional[int]:
    """Lấy toàn bộ danh sách symbols từ TCBS Listing."""
    try:
        from vnbroker.explorer.tcbs.listing import Listing  # noqa: PLC0415

        listing = Listing()
        df = listing.all_symbols(show_log=False)
        if df is not None and not df.empty:
            return len(df)
        # Listing trả về empty thì thử symbols_by_group
        df2 = listing.symbols_by_group(group="VN30", show_log=False)
        if df2 is not None and not df2.empty:
            return len(df2)
        return None
    except Exception:
        return None


def run_listing_benchmark(runs: int, auth_token: Optional[str]) -> ExplorerBatchResult:
    latencies: List[float] = []
    success_count = 0
    failure_count = 0

    started = time.perf_counter()
    for _ in range(runs):
        t0 = time.perf_counter()
        result = _fetch_listing(auth_token)
        t1 = time.perf_counter()
        latencies.append(t1 - t0)
        if result is not None:
            success_count += 1
        else:
            failure_count += 1

    finished = time.perf_counter()
    elapsed = max(finished - started, 1e-9)
    total = runs
    rps = total / elapsed

    sorted_lat = sorted(latencies)
    p50 = statistics.median(sorted_lat)
    p95 = (
        statistics.quantiles(sorted_lat, n=100)[94]
        if len(sorted_lat) >= 2
        else sorted_lat[0]
    )

    return ExplorerBatchResult(
        endpoint="listing.all_symbols",
        concurrency=1,
        runs=runs,
        symbols=1,
        success_count=success_count,
        failure_count=failure_count,
        elapsed_seconds=elapsed,
        requests_per_second=rps,
        requests_per_minute=rps * 60,
        p50_latency_seconds=p50,
        p95_latency_seconds=p95,
        min_latency_seconds=min(sorted_lat),
        max_latency_seconds=max(sorted_lat),
        mean_latency_seconds=statistics.mean(sorted_lat),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Broker Lane — authenticated endpoint latency
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_api_key() -> Optional[str]:
    """Đọc API key từ env (không log giá trị)."""
    return (
        os.getenv("VNBROKER_BROKER_TCBS_API_KEY")
        or os.getenv("vnbroker_TCBS_OPENAPI_API_KEY")
        or os.getenv("TCBS_API_KEY")
    )


def _resolve_auth_token() -> Optional[str]:
    """Đọc pre-obtained JWT từ env."""
    return (
        os.getenv("TCBS_AUTH_TOKEN")
        or os.getenv("vnbroker_TCBS_AUTH_TOKEN")
        or os.getenv("VNBROKER_TCBS_AUTH_TOKEN")
    )


def _authenticate_broker(api_key: str, otp: str):
    """Xác thực và trả về TCBSBrokerClient đã authenticated."""
    from vnbroker.broker.tcbs.client import TCBSBrokerClient  # noqa: PLC0415

    client = TCBSBrokerClient(api_key=api_key)
    client.authenticate(otp=otp)
    return client


def _benchmark_endpoint(
    label: str,
    fn,
    runs: int,
) -> BrokerEndpointResult:
    """Chạy fn() runs lần, đo latency từng lần."""
    latencies: List[float] = []
    success_count = 0
    failure_count = 0
    sample_rows = 0

    started = time.perf_counter()
    for _ in range(runs):
        t0 = time.perf_counter()
        try:
            result = fn()
            t1 = time.perf_counter()
            latencies.append(t1 - t0)
            success_count += 1
            # Đếm số dòng nếu là DataFrame
            try:
                import pandas as pd  # noqa: PLC0415
                if isinstance(result, pd.DataFrame):
                    sample_rows = len(result)
                elif isinstance(result, list):
                    sample_rows = len(result)
                elif isinstance(result, dict):
                    sample_rows = 1
            except Exception:
                sample_rows = 0
        except Exception as exc:
            t1 = time.perf_counter()
            latencies.append(t1 - t0)
            failure_count += 1
            # Log lỗi nhưng tiếp tục
            print(f"  [WARN] {label}: {type(exc).__name__}: {exc}", file=sys.stderr)

    finished = time.perf_counter()
    elapsed = max(finished - started, 1e-9)

    if not latencies:
        latencies = [0.0]

    sorted_lat = sorted(latencies)
    p50 = statistics.median(sorted_lat)
    p95 = (
        statistics.quantiles(sorted_lat, n=100)[94]
        if len(sorted_lat) >= 2
        else sorted_lat[0]
    )

    return BrokerEndpointResult(
        endpoint=label,
        runs=runs,
        success_count=success_count,
        failure_count=failure_count,
        elapsed_seconds=elapsed,
        p50_latency_seconds=p50,
        p95_latency_seconds=p95,
        min_latency_seconds=min(sorted_lat),
        max_latency_seconds=max(sorted_lat),
        mean_latency_seconds=statistics.mean(sorted_lat),
        sample_rows=sample_rows,
    )


def _resolve_account_no() -> Optional[str]:
    """Đọc account_no từ env (10 chữ số, dạng 0001170730)."""
    return (
        os.getenv("VNBROKER_BROKER_TCBS_ACCOUNT_NO")
        or os.getenv("TCBS_ACCOUNT_NO")
    )


def run_broker_benchmark(client, runs: int, account_no: Optional[str] = None) -> List[BrokerEndpointResult]:
    """Benchmark tất cả read-only broker endpoints.

    account_no: 10-digit string (e.g. '0001170730').
    Nếu không truyền, đọc từ env TCBS_ACCOUNT_NO / VNBROKER_BROKER_TCBS_ACCOUNT_NO.
    """
    results: List[BrokerEndpointResult] = []

    # Lấy account_no
    if not account_no:
        account_no = _resolve_account_no()
    if account_no:
        masked = f"{account_no[:4]}****{account_no[-4:] if len(account_no) > 8 else ''}"
        print(f"  → account_no: {masked}")

    # ── Market endpoints (không cần account_no) ───────────────────────────────
    print("  → benchmarking get_ticker_info()...")
    results.append(_benchmark_endpoint(
        "get_ticker_info",
        lambda: client.get_ticker_info(tickers=["ACB", "VCB", "TCB"]),
        runs=runs,
    ))

    print("  → benchmarking get_intraday_history()...")
    results.append(_benchmark_endpoint(
        "get_intraday_history",
        lambda: client.get_intraday_history(ticker="ACB"),
        runs=runs,
    ))

    print("  → benchmarking get_bsa()...")
    results.append(_benchmark_endpoint(
        "get_bsa",
        lambda: client.get_bsa(ticker="ACB"),
        runs=runs,
    ))

    # ── Account endpoints (cần account_no) ───────────────────────────────────
    if not account_no:
        print("  [INFO] Không có account_no — set env TCBS_ACCOUNT_NO=<số tiểu khoản>", file=sys.stderr)
        print("  [SKIP] Bỏ qua các endpoint per-account.", file=sys.stderr)
        return results

    print("  → benchmarking get_balance()...")
    results.append(_benchmark_endpoint(
        "get_balance",
        lambda: client.get_balance(account_no),
        runs=runs,
    ))

    print("  → benchmarking get_holdings()...")
    results.append(_benchmark_endpoint(
        "get_holdings",
        lambda: client.get_holdings(account_no, enrich_prices=False),
        runs=runs,
    ))

    print("  → benchmarking get_orders()...")
    results.append(_benchmark_endpoint(
        "get_orders",
        lambda: client.get_orders(account_no),
        runs=runs,
    ))

    print("  → benchmarking get_purchasing_power()...")
    results.append(_benchmark_endpoint(
        "get_purchasing_power",
        lambda: client.get_purchasing_power(account_no),
        runs=runs,
    ))

    print("  → benchmarking portfolio_snapshot()...")
    results.append(_benchmark_endpoint(
        "portfolio_snapshot",
        lambda: client.portfolio_snapshot(account_no),
        runs=runs,
    ))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ──────────────────────────────────────────────────────────────────────────────

def format_explorer_row(r: ExplorerBatchResult) -> str:
    total = r.runs * r.symbols
    success_rate = (r.success_count / total) * 100 if total else 0.0
    return (
        f"endpoint={r.endpoint:<22} concurrency={r.concurrency:>3}"
        f" | total={total:>4} | ok={r.success_count:>4} | fail={r.failure_count:>4}"
        f" ({success_rate:6.2f}%) | elapsed={r.elapsed_seconds:7.2f}s"
        f" | rps={r.requests_per_second:6.2f} | rpm={r.requests_per_minute:7.2f}"
        f" | p50={r.p50_latency_seconds:6.3f}s | p95={r.p95_latency_seconds:6.3f}s"
        f" | min={r.min_latency_seconds:6.3f}s | max={r.max_latency_seconds:6.3f}s"
    )


def format_broker_row(r: BrokerEndpointResult) -> str:
    success_rate = (r.success_count / r.runs) * 100 if r.runs else 0.0
    return (
        f"endpoint={r.endpoint:<22}"
        f" | runs={r.runs:>3} | ok={r.success_count:>3} | fail={r.failure_count:>3}"
        f" ({success_rate:6.2f}%) | elapsed={r.elapsed_seconds:7.2f}s"
        f" | p50={r.p50_latency_seconds:6.3f}s | p95={r.p95_latency_seconds:6.3f}s"
        f" | min={r.min_latency_seconds:6.3f}s | max={r.max_latency_seconds:6.3f}s"
        f" | rows={r.sample_rows:>5}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Symbol helpers
# ──────────────────────────────────────────────────────────────────────────────

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


def parse_concurrency(raw: str) -> List[int]:
    values = [int(x.strip()) for x in raw.split(",") if x.strip()]
    if not values:
        raise ValueError("Concurrency list rỗng.")
    if any(v <= 0 for v in values):
        raise ValueError("Concurrency phải là số dương.")
    return values


# ──────────────────────────────────────────────────────────────────────────────
# Output helpers
# ──────────────────────────────────────────────────────────────────────────────

def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_results_json(
    path: Path,
    explorer_rows: List[ExplorerBatchResult],
    broker_rows: List[BrokerEndpointResult],
    config: Dict[str, Any],
) -> None:
    ensure_parent_dir(path)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "config": config,
        "explorer": [asdict(r) for r in explorer_rows],
        "broker": [asdict(r) for r in broker_rows],
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_results_csv(
    path: Path,
    explorer_rows: List[ExplorerBatchResult],
    broker_rows: List[BrokerEndpointResult],
) -> None:
    ensure_parent_dir(path)
    rows: List[Dict[str, Any]] = []
    for r in explorer_rows:
        d = asdict(r)
        d["lane"] = "explorer"
        rows.append(d)
    for r in broker_rows:
        d = asdict(r)
        d["lane"] = "broker"
        rows.append(d)
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ──────────────────────────────────────────────────────────────────────────────
# argparse
# ──────────────────────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="TCBS broker + explorer benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["explorer", "broker", "all"],
        default="explorer",
        help="Lane cần benchmark (default: explorer)",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default="ACB,VCB,TCB,HPG,VNM,FPT,MWG,BID,CTG,STB",
        help="Danh sách symbols cách nhau bằng dấu phẩy",
    )
    parser.add_argument("--symbol-file", type=str, default="")
    parser.add_argument("--symbol-limit", type=int, default=20)
    parser.add_argument(
        "--concurrency",
        type=str,
        default="4,8,12",
        help="Các mức concurrency cho explorer lane (default: 4,8,12)",
    )
    parser.add_argument(
        "--interval",
        type=str,
        default="1D",
        help="Interval cho quote.history (default: 1D)",
    )
    parser.add_argument(
        "--length",
        type=str,
        default="3M",
        help="Lookback length cho quote.history (default: 3M)",
    )
    parser.add_argument("--runs", type=int, default=3, help="Số lần chạy mỗi batch (default: 3)")
    parser.add_argument("--skip-listing", action="store_true", help="Bỏ qua listing.all_symbols benchmark")
    parser.add_argument(
        "--account-no",
        type=str,
        default="",
        help="Số tiểu khoản TCBS (10 chữ số, vd: 0001170730). Fallback: env TCBS_ACCOUNT_NO",
    )
    parser.add_argument("--output-json", type=str, default="", help="Đường dẫn file JSON output")
    parser.add_argument("--output-csv", type=str, default="", help="Đường dẫn file CSV output")
    return parser


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    run_explorer = args.mode in ("explorer", "all")
    run_broker = args.mode in ("broker", "all")

    explorer_rows: List[ExplorerBatchResult] = []
    broker_rows: List[BrokerEndpointResult] = []

    # ── Symbols ──
    if args.symbol_file:
        symbols = load_symbols_from_csv(Path(args.symbol_file), limit=args.symbol_limit)
    else:
        symbols = parse_symbols(args.symbols)

    concurrency_levels = parse_concurrency(args.concurrency)

    print("=" * 80)
    print("  TCBS Benchmark — vnbroker")
    print(f"  Mode      : {args.mode}")
    print(f"  Date/Time : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # ──────────────────────────────────────────────────────────────────────────
    # PRE-AUTH: Authenticate once, get JWT for both lanes
    # ──────────────────────────────────────────────────────────────────────────
    broker_client = None
    jwt_token: Optional[str] = _resolve_auth_token()  # check env first

    api_key = _resolve_api_key()
    if api_key and not jwt_token:
        print(f"\n[Auth] API key tìm thấy (****{api_key[-8:]})")
        print("  TCBS yêu cầu OTP để lấy JWT token cho tất cả endpoints.")
        print("  (Mở TCBS app → Smart OTP → nhập 6 số bên dưới)")
        print("  Nhấn Enter để bỏ qua auth (chỉ chạy public endpoints):")
        try:
            otp_input = getpass.getpass("  OTP: ").strip()
        except (EOFError, KeyboardInterrupt):
            otp_input = ""

        if otp_input:
            try:
                print("  Đang xác thực ...")
                from vnbroker.broker.tcbs.client import TCBSBrokerClient  # noqa: PLC0415
                broker_client = TCBSBrokerClient(api_key=api_key)
                broker_client.authenticate(otp=otp_input)
                if broker_client.is_authenticated:
                    jwt_token = broker_client.session.token
                    # Expose cho explorer auth module
                    os.environ["TCBS_AUTH_TOKEN"] = jwt_token or ""
                    os.environ["vnbroker_TCBS_AUTH_TOKEN"] = jwt_token or ""
                    print("  ✓ Xác thực thành công — JWT sẽ dùng cho cả explorer và broker lane")
                else:
                    print("  [WARN] Xác thực thất bại — chạy public endpoints.")
            except Exception as exc:
                print(f"  [WARN] Auth error: {exc} — chạy public endpoints.")
        else:
            print("  [SKIP] Bỏ qua auth — chạy public endpoints (có thể gặp 401).")
    elif jwt_token:
        print(f"\n[Auth] Dùng JWT từ env (TCBS_AUTH_TOKEN)")
        # Pre-create broker client with injected token
        if api_key:
            try:
                from vnbroker.broker.tcbs.client import TCBSBrokerClient  # noqa: PLC0415
                broker_client = TCBSBrokerClient(api_key=api_key)
                broker_client.session._token = jwt_token  # type: ignore[attr-defined]
                broker_client.session._authenticated = True  # type: ignore[attr-defined]
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────────────────
    # EXPLORER LANE
    # ──────────────────────────────────────────────────────────────────────────
    if run_explorer:
        auth_token = _resolve_auth_token()
        auth_note = "có auth_token" if auth_token else "không có auth (public endpoints)"

        print(f"\n[Explorer Lane] ({auth_note})")
        print(f"  Symbols     : {len(symbols)} — {symbols[:5]}{'...' if len(symbols) > 5 else ''}")
        print(f"  Interval    : {args.interval}")
        print(f"  Runs/level  : {args.runs}")
        print(f"  Concurrency : {concurrency_levels}")
        print(f"  [NOTE] TCBS stock-insight domain (apiextaws.tcbs.com.vn) yêu cầu")
        print(f"         session token riêng biệt — OpenAPI JWT không dùng được ở đây.")
        print(f"         401 là expected nếu chỉ có OpenAPI key.")
        print()

        # Listing benchmark
        if not args.skip_listing:
            print("  [1/2] Listing.all_symbols ...")
            listing_result = run_listing_benchmark(runs=args.runs, auth_token=auth_token)
            explorer_rows.append(listing_result)
            print("  " + format_explorer_row(listing_result))

        # Quote history benchmark
        print(f"\n  [2/2] Quote.history (interval={args.interval}, count_back=100) ...")
        for c in concurrency_levels:
            result = run_quote_batch(
                symbols=symbols,
                interval=args.interval,
                length=args.length,
                concurrency=c,
                runs=args.runs,
                auth_token=auth_token,
            )
            explorer_rows.append(result)
            print("  " + format_explorer_row(result))

        if explorer_rows:
            best_rps = max(
                (r for r in explorer_rows if r.endpoint == "quote.history"),
                key=lambda r: r.requests_per_second,
                default=None,
            )
            if best_rps:
                print(f"\n  Best Quote throughput:")
                print("  " + format_explorer_row(best_rps))

    # ──────────────────────────────────────────────────────────────────────────
    # BROKER LANE
    # ──────────────────────────────────────────────────────────────────────────
    if run_broker:
        print(f"\n[Broker Lane]")

        api_key = _resolve_api_key()
        if not api_key:
            print(
                "  [ERROR] Không tìm thấy TCBS API key.\n"
                "  Set env: $env:TCBS_API_KEY = '<your_key>'  hoặc\n"
                "           $env:VNBROKER_BROKER_TCBS_API_KEY = '<your_key>'",
                file=sys.stderr,
            )
            if not run_explorer:
                return 1
        else:
            print(f"  API key  : ****{api_key[-8:]}")
            print(f"  Runs     : {args.runs}")
            print()

            # Dùng broker_client đã xác thực ở pre-auth (nếu có)
            client = broker_client

            if client is None:
                # Pre-auth không thành công — thử lại lần cuối
                broker_auth_token = (
                    os.getenv("TCBS_AUTH_TOKEN")
                    or os.getenv("vnbroker_TCBS_AUTH_TOKEN")
                )
                if broker_auth_token:
                    print("  Dùng pre-obtained JWT token từ TCBS_AUTH_TOKEN ...")
                    from vnbroker.broker.tcbs.client import TCBSBrokerClient  # noqa: PLC0415
                    client = TCBSBrokerClient(api_key=api_key)
                    client.session._token = broker_auth_token  # type: ignore[attr-defined]
                    client.session._authenticated = True  # type: ignore[attr-defined]
                    print("  ✓ Session khởi tạo từ pre-obtained token")
                else:
                    print("  [SKIP] Bỏ qua broker lane (chưa xác thực — hãy nhập OTP ở prompt đầu tiên).")

            try:
                if client is not None:
                    print()
                    acct = getattr(args, "account_no", None) or None
                    broker_rows = run_broker_benchmark(client=client, runs=args.runs, account_no=acct)

                    print("\n  === Broker Endpoint Results ===")
                    for r in broker_rows:
                        print("  " + format_broker_row(r))

                    if broker_rows:
                        fastest = min(broker_rows, key=lambda r: r.p50_latency_seconds)
                        print(f"\n  Fastest endpoint (p50): {fastest.endpoint} — {fastest.p50_latency_seconds:.3f}s")

            except KeyboardInterrupt:
                print("\n  [INTERRUPTED] Broker benchmark bị huỷ.", file=sys.stderr)
            except Exception as exc:
                print(f"  [ERROR] Broker benchmark thất bại: {exc}", file=sys.stderr)

    # ──────────────────────────────────────────────────────────────────────────
    # Output files
    # ──────────────────────────────────────────────────────────────────────────
    config: Dict[str, Any] = {
        "mode": args.mode,
        "symbols": symbols,
        "concurrency": concurrency_levels,
        "interval": args.interval,
        "length": args.length,
        "runs": args.runs,
    }

    if args.output_json:
        json_path = Path(args.output_json)
        write_results_json(json_path, explorer_rows, broker_rows, config)
        print(f"\nJSON report: {json_path}")

    if args.output_csv:
        csv_path = Path(args.output_csv)
        write_results_csv(csv_path, explorer_rows, broker_rows)
        print(f"CSV report: {csv_path}")

    print("\n" + "=" * 80)
    print("  Benchmark hoàn thành.")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    # Fix Unicode output on Windows (cp1252 → utf-8)
    import io
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.exit(main())
