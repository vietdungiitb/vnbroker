"""Unit tests for SSICompany (fallback: empty frames, standard schema)."""

from __future__ import annotations

import pytest

from vnbroker.explorer.ssi.company import (
    SSICompany,
    _AFFILIATE_COLUMNS,
    _DIVIDENDS_COLUMNS,
    _EVENTS_COLUMNS,
    _NEWS_COLUMNS,
    _OFFICERS_COLUMNS,
    _OVERVIEW_COLUMNS,
    _RATIO_SUMMARY_COLUMNS,
    _SHAREHOLDERS_COLUMNS,
    _SUBSIDIARIES_COLUMNS,
    _TRADING_STATS_COLUMNS,
)


def _make_company(**kwargs: object) -> SSICompany:
    return SSICompany(
        "VNM", api_key="test-ssi-key", api_secret="test-ssi-secret", **kwargs
    )


class TestSSICompanyInit:
    """Credential tests."""

    def test_raises_without_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_KEY", raising=False)
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_SECRET", raising=False)
        with pytest.raises(ValueError, match="SSI cần api_key và api_secret"):
            SSICompany("VNM")

    def test_symbol_uppercase(self) -> None:
        assert _make_company().symbol == "VNM"


class TestSSICompanyMethods:
    """AC-C1.1: every method returns an empty frame with standard columns."""

    _CASES = [
        ("overview", _OVERVIEW_COLUMNS),
        ("profile", _OVERVIEW_COLUMNS),
        ("shareholders", _SHAREHOLDERS_COLUMNS),
        ("officers", _OFFICERS_COLUMNS),
        ("subsidiaries", _SUBSIDIARIES_COLUMNS),
        ("affiliate", _AFFILIATE_COLUMNS),
        ("news", _NEWS_COLUMNS),
        ("events", _EVENTS_COLUMNS),
        ("dividends", _DIVIDENDS_COLUMNS),
        ("trading_stats", _TRADING_STATS_COLUMNS),
        ("ratio_summary", _RATIO_SUMMARY_COLUMNS),
    ]

    @pytest.mark.parametrize("method,columns", _CASES)
    def test_empty_standard_schema(self, method: str, columns: list[str]) -> None:
        df = getattr(_make_company(), method)()
        assert df.empty
        assert list(df.columns) == columns
