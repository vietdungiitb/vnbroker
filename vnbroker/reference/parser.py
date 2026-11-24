"""Parse canonical CafeF records into a reference frame and native explorer records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .const import PRICE_SCALE, VALUE_SCALE

REFERENCE_COLUMNS = [
    "time",
    "open",
    "high",
    "low",
    "close",
    "close_raw",
    "close_adjusted",
    "volume",
    "value",
    "put_through_volume",
    "put_through_value",
    "source",
    "fetched_at",
]

TZ = "Asia/Ho_Chi_Minh"


def parse_records(records: list[dict[str, Any]], symbol: str) -> pd.DataFrame:
    """Build the rich reference frame (distinct from the tier-1 6-column frame)."""
    rows: list[dict[str, Any]] = []
    for record in records:
        ts = pd.to_datetime(record["date"]).tz_localize(TZ)
        close_raw = float(record["close_raw"]) * PRICE_SCALE
        rows.append(
            {
                "time": ts,
                "open": float(record["open"]) * PRICE_SCALE,
                "high": float(record["high"]) * PRICE_SCALE,
                "low": float(record["low"]) * PRICE_SCALE,
                "close": close_raw,
                "close_raw": close_raw,
                "close_adjusted": float(record["close_adjusted"]) * PRICE_SCALE,
                "volume": int(record["volume"]),
                "value": float(record["value"]) * VALUE_SCALE,
                "put_through_volume": int(record["put_through_volume"] or 0),
                "put_through_value": float(record["put_through_value"] or 0) * VALUE_SCALE,
                "source": "cafef",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    frame = pd.DataFrame(rows, columns=REFERENCE_COLUMNS)
    if not frame.empty:
        frame = frame.sort_values("time").reset_index(drop=True)
    frame.attrs["symbol"] = symbol.upper()
    frame.attrs["source"] = "cafef"
    frame.attrs["data_origin"] = "cafef"
    return frame


def to_native_records(frame: pd.DataFrame, source: str) -> list[dict[str, Any]]:
    """Return ``t,o,h,l,c,v`` records matching each explorer's native pipeline.

    KBS renames ``t`` via ``_OHLC_MAP`` and parses it with ``pd.to_datetime``;
    VCI's ``ohlc_to_df`` calls ``.astype(int)`` on ``time`` (epoch seconds), so
    an ISO string would break it (lesson from audit O-1).
    """
    records: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        day = pd.Timestamp(row["time"]).date()
        timestamp: int | str
        if source.upper() == "VCI":
            timestamp = int(
                datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp()
            )
        else:
            timestamp = day.strftime("%Y-%m-%d") + " 07:00"
        records.append(
            {
                "t": timestamp,
                "o": row["open"],
                "h": row["high"],
                "l": row["low"],
                "c": row["close_raw"],
                "v": row["volume"],
            }
        )
    return records
