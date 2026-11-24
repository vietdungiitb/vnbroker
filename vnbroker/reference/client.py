"""Fetch OHLC records from CafeF: XLSX primary, JSON pagination as fallback."""

from __future__ import annotations

import io
import logging
import time
from datetime import datetime
from typing import Any

import pandas as pd
import requests

from .const import (
    CANONICAL_FIELDS,
    EXCHANGES,
    EXPORT_PATH,
    HOST,
    JSON_FIELDS,
    JSON_PAGE_SIZE,
    JSON_PATH,
    MAX_PAGES,
    REFERER,
    USER_AGENT,
    XLSX_FIELDS,
)

logger = logging.getLogger(__name__)


def to_request_date(value: str) -> str:
    """Convert an ISO date (vnbroker convention) to CafeF's ``MM/DD/YYYY``.

    CafeF silently swaps day/month: ``31/12/2022`` would be accepted as a
    valid-looking string but returns 2021 bars. Parsing strictly here turns
    that silent corruption into a loud ``ValueError``.
    """
    parsed = datetime.strptime(value, "%Y-%m-%d")
    return parsed.strftime("%m/%d/%Y")


def _headers(symbol: str) -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Referer": REFERER.format(symbol=symbol),
    }


def _pick(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_rows(rows: list[Any], mapping: dict[str, str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        raw_date = _pick(row, next(k for k, v in mapping.items() if v == "date"))
        if raw_date in (None, ""):
            continue
        day, month, year = str(raw_date).strip().split("/")[:3]
        record: dict[str, Any] = {"date": f"{year}-{month}-{day}"}
        for source_key, target in mapping.items():
            if target in ("date", "symbol"):
                continue
            value = _pick(row, source_key)
            if target in ("volume", "put_through_volume"):
                record[target] = int(_to_float(value))
            else:
                record[target] = _to_float(value)
        record["symbol"] = str(_pick(row, next(k for k, v in mapping.items() if v == "symbol"), "")).upper()
        result.append(record)
    return result


def _fetch_xlsx(symbol: str, start: str, end: str, exchange: str) -> list[dict[str, Any]]:
    params: dict[str, str | int] = {
        "ExchangeType": exchange,
        "Symbol": symbol,
        "StartDate": start,
        "EndDate": end,
    }
    response = requests.get(
        HOST + EXPORT_PATH,
        params=params,
        headers=_headers(symbol),
        timeout=60,
    )
    response.raise_for_status()
    frame = pd.read_excel(io.BytesIO(response.content))
    rows = frame.to_dict(orient="records")
    return _normalize_rows(rows, XLSX_FIELDS)


def _fetch_json(symbol: str, start: str, end: str, exchange: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        params: dict[str, str | int] = {
            "ExchangeType": exchange,
            "Symbol": symbol,
            "StartDate": start,
            "EndDate": end,
            "PageIndex": page,
            "PageSize": JSON_PAGE_SIZE,
        }
        response = requests.get(
            HOST + JSON_PATH,
            params=params,
            headers=_headers(symbol),
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        rows = (body.get("Data") or {}).get("Data") or []
        if not rows:
            break
        records.extend(_normalize_rows(rows, JSON_FIELDS))
        # A short page is the last one; the live API caps PageSize at 30.
        if len(rows) < JSON_PAGE_SIZE:
            break
    return records


def fetch_ohlc(
    symbol: str,
    start: str,
    end: str,
    exchange: str = "HOSE",
    show_log: bool = False,
) -> list[dict[str, Any]]:
    """Return canonical CafeF OHLC records for ``[start, end]`` (ISO dates)."""
    symbol = symbol.upper()
    if exchange not in EXCHANGES:
        raise ValueError(f"Unsupported exchange {exchange!r}; expected one of {EXCHANGES}")
    request_start = to_request_date(start)
    request_end = to_request_date(end)

    try:
        records = _fetch_xlsx(symbol, request_start, request_end, exchange)
        if records:
            return records
        raise ValueError("empty XLSX response")
    except Exception as exc:
        if show_log:
            logger.warning("CafeF XLSX failed for %s: %s; falling back to JSON", symbol, exc)
        records = _fetch_json(symbol, request_start, request_end, exchange)

    records.sort(key=lambda item: item["date"])
    return [{key: item.get(key) for key in CANONICAL_FIELDS} | {"symbol": item.get("symbol", symbol)} for item in records]


# Bulk export cache: keyed (exchange, year). Avoids re-downloading ~4.5 MB/year.
_BULK_CACHE: dict[tuple[str, int], list[dict[str, Any]]] = {}
_MIN_REQUEST_INTERVAL_SEC = 1.0
_LAST_REQUEST_TS: float | None = None


def _throttle() -> None:
    """Global pacing between bulk requests (≥1 s), including across years/sides."""
    global _LAST_REQUEST_TS
    if _LAST_REQUEST_TS is not None:
        wait = _MIN_REQUEST_INTERVAL_SEC - (time.monotonic() - _LAST_REQUEST_TS)
        if wait > 0:
            time.sleep(wait)
    _LAST_REQUEST_TS = time.monotonic()


def bulk_year(exchange: str, year: int, show_log: bool = False) -> list[dict[str, Any]]:
    """Fetch one full year of ``Symbol=ALL`` XLSX (1 request per exchange/year).

    Pacing >=1 s between requests, 2 retries with linear backoff, cache by
    ``(exchange, year)``. Parsing uses ``io.BytesIO`` — no temp files to clean.

    Measured perf budget (Hose 2022, 101.756 rows / 4,47 MB): download ~2,4 s,
    parse ~34–40 s. Low-volume years (e.g. 2011, 66k rows) parse ~20 s — do not
    quote "~20 s" as the peak budget.
    """
    if exchange not in EXCHANGES:
        raise ValueError(f"Unsupported exchange {exchange!r}; expected one of {EXCHANGES}")
    key = (exchange, year)
    if key in _BULK_CACHE:
        return _BULK_CACHE[key]

    last_error: Exception | None = None
    for attempt in range(3):
        _throttle()
        if attempt:
            time.sleep(_MIN_REQUEST_INTERVAL_SEC * attempt)
        try:
            response = requests.get(
                HOST + EXPORT_PATH,
                params={
                    "ExchangeType": exchange,
                    "Symbol": "ALL",
                    "StartDate": f"01/01/{year}",
                    "EndDate": f"12/31/{year}",
                },
                headers={
                    "User-Agent": USER_AGENT,
                    "Referer": REFERER.format(symbol="ALL"),
                },
                timeout=180,
            )
            response.raise_for_status()
            frame = pd.read_excel(io.BytesIO(response.content))
            records = _normalize_rows(frame.to_dict(orient="records"), XLSX_FIELDS)
            records.sort(key=lambda item: item["date"])
            normalized = [
                {field: item.get(field) for field in CANONICAL_FIELDS} for item in records
            ]
            _BULK_CACHE[key] = normalized
            return normalized
        except Exception as exc:  # retry network/parse failures
            last_error = exc
            if show_log:
                logger.warning("CafeF bulk %s %s attempt %s failed: %s", exchange, year, attempt + 1, exc)
    raise RuntimeError(f"CafeF bulk {exchange} {year} failed after 3 attempts") from last_error
