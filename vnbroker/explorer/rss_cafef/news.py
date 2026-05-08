"""RSS provider for CafeF stock news feed."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import List, Optional

import pandas as pd
import requests

from vnbroker.core.utils.user_agent import get_headers
from vnbroker.news.dedup import deduplicate_news_dataframe
from vnbroker.news.normalize import normalize_news_dataframe


_FEED_URL = "https://cafef.vn/thi-truong-chung-khoan.rss"


class News:
    def __init__(self, symbol: str = "", random_agent: bool = False, show_log: bool = False):
        self.symbol = symbol
        self.show_log = show_log
        self.headers = get_headers(data_source="VCI", random_agent=random_agent)

    def _fetch_items(self) -> List[dict]:
        response = requests.get(_FEED_URL, headers=self.headers, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        channel = root.find("channel")
        if channel is None:
            return []

        items: List[dict] = []
        for item in channel.findall("item"):
            pub = (item.findtext("pubDate") or "").strip()
            pub_iso = None
            try:
                pub_iso = parsedate_to_datetime(pub).isoformat()
            except Exception:
                pub_iso = pub

            items.append(
                {
                    "guid": (item.findtext("guid") or "").strip(),
                    "title": (item.findtext("title") or "").strip(),
                    "summary": (item.findtext("description") or "").strip(),
                    "link": (item.findtext("link") or "").strip(),
                    "pub_date": pub_iso,
                }
            )
        return items

    def latest(self, symbol: str = "", limit: int = 100, **kwargs) -> pd.DataFrame:
        items = self._fetch_items()
        df = pd.DataFrame(items)
        normalized = normalize_news_dataframe(df, source="rss_cafef", symbol=symbol or self.symbol)
        normalized = deduplicate_news_dataframe(normalized)
        return normalized.head(limit)

    def search(self, query: str, symbol: str = "", limit: int = 100, **kwargs) -> pd.DataFrame:
        df = self.latest(symbol=symbol, limit=max(limit, 200), **kwargs)
        if df.empty or not query:
            return df.head(limit)
        q = query.strip().lower()
        mask = (
            df["title"].fillna("").str.lower().str.contains(q, regex=False)
            | df["summary"].fillna("").str.lower().str.contains(q, regex=False)
        )
        return df[mask].head(limit)

    def by_symbol(self, symbol: str, limit: int = 100, **kwargs) -> pd.DataFrame:
        df = self.latest(symbol="", limit=max(limit, 200), **kwargs)
        if df.empty:
            return df
        token = symbol.upper()
        pattern = rf"(^|[^A-Z0-9]){re.escape(token)}([^A-Z0-9]|$)"
        mask = (
            df["title"].fillna("").str.upper().str.contains(pattern, regex=True)
            | df["summary"].fillna("").str.upper().str.contains(pattern, regex=True)
        )
        return df[mask].head(limit)


from vnbroker.core.registry import ProviderRegistry  # noqa: E402

ProviderRegistry.register("news", "rss_cafef", News)
