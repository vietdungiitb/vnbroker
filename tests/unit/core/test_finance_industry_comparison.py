import pandas as pd

from vnbroker.common.data import Finance
from vnbroker.common.data import Listing


def _mock_symbols_by_industries(*args, **kwargs):
    _ = (args, kwargs)
    return pd.DataFrame(
        {
            "symbol": ["VCB", "TCB", "BID", "HPG"],
            "industry_code": [11, 11, 11, 21],
            "industry_name": ["Ngân hàng", "Ngân hàng", "Ngân hàng", "Vật liệu xây dựng"],
        }
    )


def _mock_get_financial_data(self, data_type, symbol=None, **kwargs):
    _ = kwargs
    assert data_type == "ratio"
    values = {
        "VCB": 0.18,
        "TCB": 0.15,
        "BID": 0.12,
        "HPG": 0.10,
    }
    sym = (symbol or self.symbol or "").upper()
    roe = values.get(sym)
    if roe is None:
        return pd.DataFrame()
    return pd.DataFrame({"period": ["2025-Q4"], "roe": [roe]})


def test_industry_peers_returns_same_industry_symbols(monkeypatch):
    monkeypatch.setattr(Finance, "_load_data_source", lambda self: object())
    monkeypatch.setattr(Listing, "symbols_by_industries", _mock_symbols_by_industries)

    finance = Finance(symbol="VCB", source="KBS")
    out = finance.industry_peers(symbol="VCB")

    assert not out.empty
    assert (out["industry_name"] == "Ngân hàng").all()
    assert set(out["peer_symbol"].tolist()) == {"VCB", "TCB", "BID"}


def test_industry_benchmark_computes_median_and_mean(monkeypatch):
    monkeypatch.setattr(Finance, "_load_data_source", lambda self: object())
    monkeypatch.setattr(Finance, "_get_financial_data", _mock_get_financial_data)
    monkeypatch.setattr(Listing, "symbols_by_industries", _mock_symbols_by_industries)

    finance = Finance(symbol="VCB", source="KBS")
    out = finance.industry_benchmark(symbol="VCB", metrics=["roe"], period="quarter")

    assert not out.empty
    assert set(out["metric"].tolist()) == {"roe"}
    assert abs(out.iloc[0]["industry_median"] - 0.15) < 1e-9
    assert abs(out.iloc[0]["industry_mean"] - 0.15) < 1e-9
    assert int(out.iloc[0]["total_peers"]) == 3


def test_industry_rank_computes_rank_percentile_zscore(monkeypatch):
    monkeypatch.setattr(Finance, "_load_data_source", lambda self: object())
    monkeypatch.setattr(Finance, "_get_financial_data", _mock_get_financial_data)
    monkeypatch.setattr(Listing, "symbols_by_industries", _mock_symbols_by_industries)

    finance = Finance(symbol="VCB", source="KBS")
    out = finance.industry_rank(symbol="VCB", metric="roe", period="quarter")

    assert not out.empty
    target = out[out["peer_symbol"] == "VCB"].iloc[0]
    assert int(target["rank"]) == 1
    assert float(target["percentile"]) == 100.0
    assert float(target["zscore"]) > 0
