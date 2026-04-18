import pandas as pd

from vnstock.base import BaseAdapter
from vnstock.core.registry import ProviderRegistry


class _MockFinancialProvider:
    def __init__(self, symbol=None, **kwargs):
        self.symbol = symbol
        self.kwargs = kwargs

    def ratio(self, period="quarter", **kwargs):
        _ = kwargs
        return pd.DataFrame(
            {
                "symbol": [self.symbol],
                "period": [period],
                "roe": [0.15],
            }
        )


class _MockFinancialAdapter(BaseAdapter):
    _module_name = "financial"

    def ratio(self, **kwargs):
        return self._call_provider_method("ratio", **kwargs)


def test_provider_onboarding_dry_run_without_core_rewrite(monkeypatch):
    # Isolate registry mutations for this test only.
    original_registry = dict(ProviderRegistry._registry)
    try:
        ProviderRegistry.register("financial", "mockdryrun", _MockFinancialProvider)

        adapter = _MockFinancialAdapter(source="mockdryrun", symbol="AAA")
        out = adapter.ratio(period="year")

        assert isinstance(out, pd.DataFrame)
        assert out.iloc[0]["symbol"] == "AAA"
        assert out.iloc[0]["period"] == "year"
        assert float(out.iloc[0]["roe"]) == 0.15
    finally:
        monkeypatch.setattr(ProviderRegistry, "_registry", original_registry)
