"""Unit tests for SSIFinancial (fallback: empty frames, standard schema)."""

from __future__ import annotations

import pytest

from vnbroker.explorer.ssi.financial import SSIFinancial


def _make_finance(**kwargs: object) -> SSIFinancial:
    return SSIFinancial(
        "VNM", api_key="test-ssi-key", api_secret="test-ssi-secret", **kwargs
    )


class TestSSIFinancialInit:
    """Credential tests."""

    def test_lazy_init_without_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # W4: fallback modules must init without keys so facade can fall back.
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_KEY", raising=False)
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_SECRET", raising=False)
        assert SSIFinancial("VNM").balance_sheet().empty


class TestSSIFinancialMethods:
    """AC-F1.1: every method returns an empty long-format frame."""

    _EXPECTED = ["item", "item_en", "item_id"]

    @pytest.mark.parametrize(
        "method", ["balance_sheet", "income_statement", "cash_flow", "ratio", "financial_ratios"]
    )
    def test_empty_standard_schema(self, method: str) -> None:
        df = getattr(_make_finance(), method)()
        assert df.empty
        assert list(df.columns) == self._EXPECTED
