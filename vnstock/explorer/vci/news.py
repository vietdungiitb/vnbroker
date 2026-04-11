"""VCI news provider wrapper."""

from __future__ import annotations

import pandas as pd

from vnstock.explorer.vci.company import Company as VCICompany
from vnstock.news.dedup import deduplicate_news_dataframe
from vnstock.news.normalize import normalize_news_dataframe


class News:
    def __init__(self, symbol: str = "", random_agent: bool = False, show_log: bool = False):
        self.symbol = symbol
        self.random_agent = random_agent
        self.show_log = show_log

    def latest(self, symbol: str = "", limit: int = 100, **kwargs) -> pd.DataFrame:
        target_symbol = (symbol or self.symbol or "").upper()
        if not target_symbol:
            return pd.DataFrame()

        df = VCICompany(
            symbol=target_symbol,
            random_agent=self.random_agent,
            show_log=self.show_log,
        ).news()
        normalized = normalize_news_dataframe(df, source="vci", symbol=target_symbol)
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
        return self.latest(symbol=symbol, limit=limit, **kwargs)


from vnstock.core.registry import ProviderRegistry  # noqa: E402

ProviderRegistry.register("news", "vci", News)
