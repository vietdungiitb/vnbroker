"""Unit tests for cross-provider price unit normalization."""

import pandas as pd

from vnstock.core.utils.transform import intraday_to_df, ohlc_to_df


def test_ohlc_defaults_to_vnd_unit(monkeypatch):
    monkeypatch.delenv("VNSTOCK_PRICE_UNIT", raising=False)

    data = [
        {
            "t": 1711958400,
            "o": 30343.8,
            "h": 30500.0,
            "l": 30010.0,
            "c": 30400.0,
            "v": 123456,
        }
    ]

    out = ohlc_to_df(
        data=data,
        column_map={"t": "time", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"},
        dtype_map={
            "time": "datetime64[ns]",
            "open": "float64",
            "high": "float64",
            "low": "float64",
            "close": "float64",
            "volume": "int64",
        },
        asset_type="stock",
        symbol="ACB",
        source="VCI",
        interval="1D",
        floating=2,
    )

    assert out.attrs["price_unit"] == "VND"
    assert out.iloc[0]["open"] == 30343.8


def test_ohlc_supports_legacy_thousand_unit(monkeypatch):
    monkeypatch.setenv("VNSTOCK_PRICE_UNIT", "THOUSAND_VND")

    data = [
        {
            "t": 1711958400,
            "o": 30343.8,
            "h": 30500.0,
            "l": 30010.0,
            "c": 30400.0,
            "v": 123456,
        }
    ]

    out = ohlc_to_df(
        data=data,
        column_map={"t": "time", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"},
        dtype_map={
            "time": "datetime64[ns]",
            "open": "float64",
            "high": "float64",
            "low": "float64",
            "close": "float64",
            "volume": "int64",
        },
        asset_type="stock",
        symbol="ACB",
        source="VCI",
        interval="1D",
        floating=2,
    )

    assert out.attrs["price_unit"] == "THOUSAND_VND"
    assert out.iloc[0]["open"] == 30.34


def test_intraday_defaults_to_vnd_unit(monkeypatch):
    monkeypatch.delenv("VNSTOCK_PRICE_UNIT", raising=False)

    data = [
        {
            "truncTime": 1711958400,
            "matchPrice": 30343.8,
            "matchVol": 100,
            "matchType": "b",
            "id": "x1",
        }
    ]

    out = intraday_to_df(
        data=data,
        column_map={
            "truncTime": "time",
            "matchPrice": "price",
            "matchVol": "volume",
            "matchType": "match_type",
            "id": "id",
        },
        dtype_map={
            "time": "datetime64[ns]",
            "price": "float64",
            "volume": "int64",
            "match_type": "str",
            "id": "str",
        },
        symbol="ACB",
        asset_type="stock",
        source="VCI",
    )

    assert out.attrs["price_unit"] == "VND"
    assert out.iloc[0]["price"] == 30343.8
    assert isinstance(out, pd.DataFrame)
