"""Unit tests for SSINews (fallback: empty frames, standard schema)."""

from __future__ import annotations

import pytest

from vnbroker.explorer.ssi.news import SSINews

_EXPECTED = [
    "symbol", "title", "summary", "content", "publish_date",
    "source", "url", "image_url", "category",
]


class TestSSINewsInit:
    """Credential tests."""

    def test_raises_without_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_KEY", raising=False)
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_SECRET", raising=False)
        with pytest.raises(ValueError, match="SSI cần api_key và api_secret"):
            SSINews()


class TestSSINewsMethods:
    """AC-N1.1: every method returns an empty frame with standard columns."""

    def test_latest(self) -> None:
        df = SSINews(api_key="k", api_secret="s").latest(symbol="VNM")
        assert df.empty
        assert list(df.columns) == _EXPECTED

    @pytest.mark.parametrize("method", ["market_news", "search", "by_symbol"])
    def test_aliases(self, method: str) -> None:
        df = getattr(SSINews(api_key="k", api_secret="s"), method)()
        assert df.empty
        assert list(df.columns) == _EXPECTED
