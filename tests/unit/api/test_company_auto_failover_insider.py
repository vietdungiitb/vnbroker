import pandas as pd

from vnbroker.api.company import Company as CompanyAdapter
from vnbroker.core.registry import ProviderRegistry
from vnbroker.core.source_router import reset_router_state


class _FakeVCICompany:
    def __init__(self, symbol=None, **kwargs):
        _ = (symbol, kwargs)

    def insider_deals(self, **kwargs):
        _ = kwargs
        raise NotImplementedError("VCI chưa hỗ trợ endpoint insider_deals.")


class _FakeKBSCompany:
    def __init__(self, symbol=None, **kwargs):
        _ = (symbol, kwargs)

    def insider_deals(self, **kwargs):
        _ = kwargs
        df = pd.DataFrame({"symbol": ["VCB"], "deal_action": ["Mua"], "deal_quantity": [1000]})
        df.attrs["source"] = "KBS"
        return df


def test_company_auto_failover_for_insider_deals(monkeypatch):
    reset_router_state()
    monkeypatch.setitem(ProviderRegistry._registry, ("company", "vci"), _FakeVCICompany)
    monkeypatch.setitem(ProviderRegistry._registry, ("company", "kbs"), _FakeKBSCompany)

    company = CompanyAdapter(source="auto", symbol="VCB", show_log=False)
    out = company.insider_deals(page=1, page_size=10)

    assert not out.empty
    assert out.attrs.get("source") == "KBS"
    assert out.attrs.get("source_used") == "KBS"
