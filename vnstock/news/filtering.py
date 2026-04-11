"""Filtering helpers for normalized news frames."""

from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd


def filter_news_dataframe(
    df: pd.DataFrame,
    symbol: Optional[str] = None,
    query: Optional[str] = None,
    sources: Optional[Iterable[str]] = None,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    regex: bool = False,
    case: bool = False,
    fields: Iterable[str] = ("title", "summary"),
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """Filter normalized news DataFrame by symbol/text/source/time criteria."""
    if df is None or df.empty:
        return df

    out = df.copy()

    if symbol:
        sym = str(symbol).upper()
        if "symbol" in out.columns:
            out = out[out["symbol"].fillna("").astype(str).str.upper() == sym]

    if sources:
        srcs = {str(s).upper() for s in sources}
        if "source" in out.columns:
            out = out[out["source"].fillna("").astype(str).str.upper().isin(srcs)]

    if from_time or to_time:
        if "published_at" in out.columns:
            published = pd.to_datetime(out["published_at"], errors="coerce", utc=True)
            if from_time:
                start = pd.to_datetime(from_time, errors="coerce", utc=True)
                if pd.notna(start):
                    out = out[published >= start]
                    published = pd.to_datetime(out["published_at"], errors="coerce", utc=True)
            if to_time:
                end = pd.to_datetime(to_time, errors="coerce", utc=True)
                if pd.notna(end):
                    out = out[published <= end]

    if query:
        q = str(query)
        parts = []
        for col in fields:
            if col in out.columns:
                parts.append(
                    out[col].fillna("").astype(str).str.contains(q, case=case, regex=regex)
                )
        if parts:
            mask = parts[0]
            for m in parts[1:]:
                mask = mask | m
            out = out[mask]

    if limit is not None:
        out = out.head(int(limit))

    return out
