import pandas as pd

from vnbroker.common.data import _normalize_company_insider_deals_df
from vnbroker.common.data import Company


def test_normalize_company_insider_deals_from_tcbs_like_columns():
    df = pd.DataFrame(
        {
            "deal_announce_date": ["10/04/26"],
            "deal_method": ["Cổ đông lớn"],
            "deal_action": ["Bán"],
            "deal_quantity": ["120000"],
            "deal_price": ["88500"],
            "deal_ratio": ["0.12"],
        }
    )
    df.source = "TCBS"

    out = _normalize_company_insider_deals_df(df, symbol="VCB")

    assert out.loc[0, "symbol"] == "VCB"
    assert out.loc[0, "announce_date"] == "2026-04-10"
    assert out.loc[0, "actor_type"] == "Cổ đông lớn"
    assert out.loc[0, "action"] == "SELL"
    assert out.loc[0, "quantity"] == 120000
    assert out.loc[0, "price"] == 88500
    assert abs(out.loc[0, "ratio"] - 0.12) < 1e-9
    assert out.loc[0, "source"] == "TCBS"
    assert out.loc[0, "source_used"] == "TCBS"


def test_normalize_company_insider_deals_preserves_legacy_columns():
    df = pd.DataFrame(
        {
            "symbol": ["VCB"],
            "action": ["MUA"],
            "quantity": [1000],
            "custom_col": ["keep_me"],
        }
    )
    df.attrs["source"] = "KBS"
    df.attrs["source_used"] = "KBS"

    out = _normalize_company_insider_deals_df(df)

    assert "custom_col" in out.columns
    assert out.loc[0, "custom_col"] == "keep_me"
    assert out.loc[0, "action"] == "BUY"
    assert out.attrs.get("insider_schema_version") == "1.0"


def test_normalize_company_insider_deals_empty_dataframe_has_standard_columns():
    out = _normalize_company_insider_deals_df(pd.DataFrame(), symbol="VCB")

    expected = {
        "symbol",
        "announce_date",
        "deal_date",
        "actor_name",
        "actor_type",
        "action",
        "quantity",
        "price",
        "ratio",
        "note",
        "source",
        "source_used",
    }
    assert expected.issubset(set(out.columns))
    assert out.empty


class _DummyCompanyDataSource:
    def insider_deals(self, **kwargs):
        _ = kwargs
        df = pd.DataFrame(
            {
                "symbol": ["VCB"],
                "deal_action": ["Bán"],
                "deal_quantity": [100],
            }
        )
        df.attrs["source"] = "KBS"
        return df


def test_company_insider_deals_standardize_true(monkeypatch):
    monkeypatch.setattr(Company, "_load_data_source", lambda self: _DummyCompanyDataSource())
    company = Company(symbol="VCB", source="GATEWAY")

    out = company.insider_deals()

    assert out.loc[0, "action"] == "SELL"
    assert out.loc[0, "source"] == "KBS"
    assert out.attrs.get("insider_schema_version") == "1.0"


def test_company_insider_deals_standardize_false(monkeypatch):
    monkeypatch.setattr(Company, "_load_data_source", lambda self: _DummyCompanyDataSource())
    company = Company(symbol="VCB", source="GATEWAY")

    out = company.insider_deals(standardize=False)

    assert "deal_action" in out.columns
    assert "announce_date" not in out.columns
