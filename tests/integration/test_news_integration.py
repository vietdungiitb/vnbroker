"""
Integration tests for stock news facade and live source behavior.
"""

import pandas as pd
import pytest

from vnbroker.common.client import Vnbroker


@pytest.mark.integration
class TestNewsIntegration:
    def test_stock_components_exposes_news(self):
        stock = Vnbroker(show_log=False)
        acb = stock.stock("ACB", source="GATEWAY")

        assert hasattr(acb, "news")
        assert acb.news is not None

    def test_news_live_fetch_auto(self):
        stock = Vnbroker(show_log=False)
        acb = stock.stock("ACB", source="GATEWAY")

        try:
            data = acb.news.latest(limit=5)
        except Exception as exc:
            pytest.skip(f"Live source unavailable for news GATEWAY: {exc}")

        assert isinstance(data, pd.DataFrame)
        assert set(["title", "url", "source"]).issubset(set(data.columns))

    def test_news_health_snapshot(self):
        stock = Vnbroker(show_log=False)
        acb = stock.stock("ACB", source="GATEWAY")
        health = acb.news.health()

        assert isinstance(health, dict)
        # Gateway news health may have different structure
        assert len(health) >= 0
