"""Normalization helpers for multi-source news records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

import pandas as pd


_SOURCE_COLUMN_MAPS: Dict[str, Dict[str, str]] = {
    "vci": {
        "id": "source_article_id",
        "news_title": "title",
        "news_short_content": "summary",
        "news_source_link": "url",
        "public_date": "published_at",
    },
    "kbs": {
        "article_id": "source_article_id",
        "title": "title",
        "head": "summary",
        "url": "url",
        "publish_time": "published_at",
    },
    "tcbs": {
        "id": "source_article_id",
        "title": "title",
        "description": "summary",
        "link": "url",
        "publish_date": "published_at",
    },
    "rss_cafef": {
        "guid": "source_article_id",
        "title": "title",
        "summary": "summary",
        "link": "url",
        "pub_date": "published_at",
    },
    "rss_vneconomy": {
        "guid": "source_article_id",
        "title": "title",
        "summary": "summary",
        "link": "url",
        "pub_date": "published_at",
    },
}


def _to_utc_timestamp(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", utc=True)
    return parsed.dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_news_id(source: str, source_article_id: pd.Series, url: pd.Series) -> pd.Series:
    fallback = url.fillna("").astype(str)
    suffix = source_article_id.fillna("").astype(str)
    normalized_suffix = suffix.where(suffix.str.len() > 0, fallback)
    return source.lower() + ":" + normalized_suffix


def normalize_news_dataframe(
    df: pd.DataFrame,
    source: str,
    symbol: Optional[str] = None,
) -> pd.DataFrame:
    """Normalize source-specific news frames into canonical schema v1."""
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "news_id",
            "source",
            "source_article_id",
            "symbol",
            "title",
            "summary",
            "url",
            "published_at",
            "fetched_at",
            "language",
            "tags",
            "raw_hash",
            "dedup_group_id",
            "quality_score",
        ])

    source_key = source.lower()
    out = df.copy()

    # Normalize column names from known source mappings.
    for old_col, new_col in _SOURCE_COLUMN_MAPS.get(source_key, {}).items():
        if old_col in out.columns and new_col not in out.columns:
            out = out.rename(columns={old_col: new_col})

    if "source" not in out.columns:
        out["source"] = source.upper()
    if "symbol" not in out.columns:
        out["symbol"] = symbol.upper() if symbol else None

    for col in ["source_article_id", "title", "summary", "url", "published_at"]:
        if col not in out.columns:
            out[col] = None

    out["published_at"] = _to_utc_timestamp(out["published_at"])
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out["fetched_at"] = now_utc
    out["language"] = out.get("language", "vi")
    out["tags"] = out.get("tags", None)

    out["news_id"] = _build_news_id(source_key, out["source_article_id"], out["url"])
    out["raw_hash"] = (
        out["title"].fillna("").astype(str)
        + "|"
        + out["url"].fillna("").astype(str)
        + "|"
        + out["published_at"].fillna("").astype(str)
    ).map(lambda x: str(abs(hash(x))))

    if "dedup_group_id" not in out.columns:
        out["dedup_group_id"] = None
    if "quality_score" not in out.columns:
        out["quality_score"] = 0.8

    canonical_cols = [
        "news_id",
        "source",
        "source_article_id",
        "symbol",
        "title",
        "summary",
        "url",
        "published_at",
        "fetched_at",
        "language",
        "tags",
        "raw_hash",
        "dedup_group_id",
        "quality_score",
    ]
    return out[canonical_cols]
