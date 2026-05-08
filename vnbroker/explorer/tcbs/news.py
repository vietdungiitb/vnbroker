"""TCBS news provider wrapper."""

from __future__ import annotations

import pandas as pd

from vnbroker.explorer.tcbs.company import Company as TCBSCompany
from vnbroker.news.dedup import deduplicate_news_dataframe
from vnbroker.news.normalize import normalize_news_dataframe


class News:
    def __init__(self, symbol: str = "", random_agent: bool = False, show_log: bool = False, auth_token: str = None):
        self.symbol = symbol
        self.random_agent = random_agent
        self.show_log = show_log
        self.auth_token = auth_token

    def latest(self, symbol: str = "", limit: int = 100, page: int = 0, page_size: int = 50, **kwargs) -> pd.DataFrame:
        target_symbol = (symbol or self.symbol or "").upper()
        if not target_symbol:
            return pd.DataFrame()

        df = TCBSCompany(
            symbol=target_symbol,
            random_agent=self.random_agent,
            show_log=self.show_log,
            auth_token=self.auth_token,
        ).news(page=page, page_size=page_size)
        normalized = normalize_news_dataframe(df, source="tcbs", symbol=target_symbol)
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


from vnbroker.core.registry import ProviderRegistry  # noqa: E402

ProviderRegistry.register("news", "tcbs", News)
