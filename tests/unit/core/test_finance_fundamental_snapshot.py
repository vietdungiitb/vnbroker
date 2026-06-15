import pandas as pd

from vnbroker.common.data import Finance


class _DummyFinanceDataSource:
    def ratio(self, **kwargs):
        _ = kwargs
        df = pd.DataFrame(
            {
                "period": ["2025-Q4"],
                "roe": [0.18],
                "pe": [11.2],
                "ticker": ["VCB"],
            }
        )
        df.attrs["source"] = "KBS"
        df.attrs["source_used"] = "KBS"
        return df


def test_fundamental_snapshot_returns_standardized_rows(monkeypatch):
    monkeypatch.setattr(Finance, "_load_data_source", lambda self: _DummyFinanceDataSource())
    finance = Finance(symbol="VCB", source="GATEWAY")

    out = finance.fundamental_snapshot(metrics=["roe", "pe"], period="quarter")

    assert list(out.columns) == [
        "symbol",
        "period",
        "report_date",
        "metric",
        "value",
        "unit",
        "source",
        "source_used",
    ]
    assert len(out) == 2
    assert set(out["metric"].tolist()) == {"roe", "pe"}
    assert (out["symbol"] == "VCB").all()
    assert (out["source"] == "KBS").all()
    assert (out["source_used"] == "KBS").all()


def test_fundamental_snapshot_auto_selects_numeric_metrics(monkeypatch):
    monkeypatch.setattr(Finance, "_load_data_source", lambda self: _DummyFinanceDataSource())
    finance = Finance(symbol="VCB", source="GATEWAY")

    out = finance.fundamental_snapshot(period="quarter")

    metrics = set(out["metric"].tolist())
    assert "roe" in metrics
    assert "pe" in metrics
    assert "ticker" not in metrics


def test_fundamental_snapshot_empty_dataframe(monkeypatch):
    class _EmptyFinanceDataSource:
        def ratio(self, **kwargs):
            _ = kwargs
            return pd.DataFrame()

    monkeypatch.setattr(Finance, "_load_data_source", lambda self: _EmptyFinanceDataSource())
    finance = Finance(symbol="VCB", source="GATEWAY")

    out = finance.fundamental_snapshot(metrics=["roe"])
    assert out.empty
    assert list(out.columns) == [
        "symbol",
        "period",
        "report_date",
        "metric",
        "value",
        "unit",
        "source",
        "source_used",
    ]
