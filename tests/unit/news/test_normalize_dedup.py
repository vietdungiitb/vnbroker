import pandas as pd
import pytest

from vnstock.news.dedup import deduplicate_news_dataframe
from vnstock.news.normalize import normalize_news_dataframe


@pytest.mark.unit
class TestNewsNormalizeDedup:
    def test_normalize_vci_shape(self):
        raw = pd.DataFrame([
            {
                "id": 123,
                "news_title": "ABC cong bo ket qua kinh doanh",
                "news_short_content": "Loi nhuan tang truong",
                "news_source_link": "https://example.com/a",
                "public_date": "2026-04-11T09:00:00+07:00",
            }
        ])

        out = normalize_news_dataframe(raw, source="vci", symbol="ABC")

        required_cols = {
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
        }
        assert required_cols.issubset(set(out.columns))
        assert out.iloc[0]["symbol"] == "ABC"

    def test_deduplicate_by_url(self):
        raw = pd.DataFrame([
            {
                "source": "VCI",
                "title": "Tin 1",
                "summary": "S",
                "url": "https://example.com/a",
                "published_at": "2026-04-11T00:00:00Z",
                "source_article_id": "1",
            },
            {
                "source": "KBS",
                "title": "Tin 1 duplicate",
                "summary": "S2",
                "url": "https://example.com/a",
                "published_at": "2026-04-11T00:10:00Z",
                "source_article_id": "2",
            },
        ])

        normalized = normalize_news_dataframe(raw, source="kbs", symbol="ABC")
        deduped = deduplicate_news_dataframe(normalized)

        assert len(deduped) == 1
