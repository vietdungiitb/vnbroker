"""Deduplication helpers for multi-source news frames."""

from __future__ import annotations

import pandas as pd


def deduplicate_news_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate by URL first, then by title + published timestamp."""
    if df is None or df.empty:
        return df

    out = df.copy()
    if "url" in out.columns:
        out["_url_key"] = out["url"].fillna("").astype(str).str.strip().str.lower()
    else:
        out["_url_key"] = ""

    out["_title_key"] = out.get("title", "").fillna("").astype(str).str.strip().str.lower()
    out["_time_key"] = out.get("published_at", "").fillna("").astype(str)
    out["_dup_key"] = out["_url_key"].where(
        out["_url_key"].str.len() > 0,
        out["_title_key"] + "|" + out["_time_key"],
    )

    out = out.drop_duplicates(subset=["_dup_key"], keep="first").copy()
    out["dedup_group_id"] = out["_dup_key"]

    return out.drop(columns=["_url_key", "_title_key", "_time_key", "_dup_key"])
