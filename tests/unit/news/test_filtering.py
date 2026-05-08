import pandas as pd
import pytest

from vnbroker.news.filtering import filter_news_dataframe


@pytest.mark.unit
class TestNewsFiltering:
    def _sample(self):
        return pd.DataFrame([
            {
                "symbol": "ACB",
                "source": "VCI",
                "title": "ACB cong bo ket qua quy 1",
                "summary": "Loi nhuan tang manh",
                "published_at": "2026-04-10T08:00:00Z",
            },
            {
                "symbol": "VCB",
                "source": "KBS",
                "title": "VCB cap nhat co tuc",
                "summary": "Thong tin dai hoi co dong",
                "published_at": "2026-04-11T08:00:00Z",
            },
            {
                "symbol": "ACB",
                "source": "RSS_CAFEF",
                "title": "Ngan hang ACB va xu huong tin dung",
                "summary": "Doan van phan tich ve thanh khoan",
                "published_at": "2026-04-11T10:00:00Z",
            },
        ])

    def test_filter_by_symbol(self):
        out = filter_news_dataframe(self._sample(), symbol="ACB")
        assert len(out) == 2
        assert set(out["symbol"].unique()) == {"ACB"}

    def test_filter_by_query_substring(self):
        out = filter_news_dataframe(self._sample(), query="doan van", fields=("summary",))
        assert len(out) == 1
        assert out.iloc[0]["source"] == "RSS_CAFEF"

    def test_filter_by_sources(self):
        out = filter_news_dataframe(self._sample(), sources=["kbs"])
        assert len(out) == 1
        assert out.iloc[0]["symbol"] == "VCB"

    def test_filter_by_time_range(self):
        out = filter_news_dataframe(
            self._sample(),
            from_time="2026-04-11T00:00:00Z",
            to_time="2026-04-11T09:00:00Z",
        )
        assert len(out) == 1
        assert out.iloc[0]["symbol"] == "VCB"
