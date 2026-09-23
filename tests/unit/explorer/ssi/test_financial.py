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

    def test_raises_without_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_KEY", raising=False)
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_SECRET", raising=False)
        with pytest.raises(ValueError, match="SSI cần api_key và api_secret"):
            SSIFinancial("VNM")


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
