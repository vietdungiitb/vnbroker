"""Regression tests for cross-provider quote price unit consistency."""

import pytest

from vnbroker.api.quote import Quote


def _mock_vci_history_response(*args, **kwargs):
    return {
        "data": [
            {
                "t": 1711958400,
                "o": 30343.8,
                "h": 30500.0,
                "l": 30010.0,
                "c": 30400.0,
                "v": 123456,
            }
        ]
    }


def _mock_kbs_history_response(*args, **kwargs):
    return {
        "data_day": [
            {
                "t": "2024-04-01",
                "o": 30343.8,
                "h": 30500.0,
                "l": 30010.0,
                "c": 30400.0,
                "v": 123456,
            }
        ]
    }


def _mock_tcbs_history_response(*args, **kwargs):
    # Shape theo spec TCBS `GET /nyx/v2/stock/bars-long-term`.
    # Bản gốc mock `{t,p,v,a}` — đó là shape intraday tick, chính là cái mà
    # commit nối `bars` đã gỡ bỏ. Giữ shape cũ thì test đang kiểm một hợp
    # đồng không còn tồn tại.
    return {
        "ticker": "VNM",
        "data": [
            {
                "open": 30400.0,
                "high": 30400.0,
                "low": 30400.0,
                "close": 30400.0,
                "volume": 123456,
                "tradingDate": "2024-04-01T00:00:00Z",
            }
        ],
    }


@pytest.mark.unit
@pytest.mark.api
def test_quote_history_vci_and_kbs_are_consistent_in_vnd(monkeypatch):
    monkeypatch.delenv("vnbroker_PRICE_UNIT", raising=False)
    monkeypatch.setattr("vnbroker.explorer.vci.quote.send_request", _mock_vci_history_response)
    monkeypatch.setattr("vnbroker.explorer.kbs.quote.send_request", _mock_kbs_history_response)
    monkeypatch.setattr("vnbroker.explorer.tcbs.quote.client.send_request", _mock_tcbs_history_response)

    vci_df = Quote(source="VCI", symbol="ACB", show_log=False).history(
        start="2024-04-01", end="2024-04-01", interval="1D"
    )
    kbs_df = Quote(source="KBS", symbol="ACB", show_log=False).history(
        start="2024-04-01", end="2024-04-01", interval="1D"
    )
    tcbs_df = Quote(source="TCBS", symbol="ACB", show_log=False).history(
        start="2024-04-01", end="2024-04-01", interval="1D"
    )

    assert vci_df.attrs["price_unit"] == "VND"
    assert kbs_df.attrs["price_unit"] == "VND"
    assert tcbs_df.attrs["price_unit"] == "VND"
    assert vci_df.iloc[0]["close"] == pytest.approx(30400.0)
    assert kbs_df.iloc[0]["close"] == pytest.approx(30400.0)
    assert tcbs_df.iloc[0]["close"] == pytest.approx(30400.0)


@pytest.mark.unit
@pytest.mark.api
def test_quote_history_vci_and_kbs_are_consistent_in_thousand_vnd(monkeypatch):
    monkeypatch.setenv("vnbroker_PRICE_UNIT", "THOUSAND_VND")
    monkeypatch.setattr("vnbroker.explorer.vci.quote.send_request", _mock_vci_history_response)
    monkeypatch.setattr("vnbroker.explorer.kbs.quote.send_request", _mock_kbs_history_response)
    monkeypatch.setattr("vnbroker.explorer.tcbs.quote.client.send_request", _mock_tcbs_history_response)

    vci_df = Quote(source="VCI", symbol="ACB", show_log=False).history(
        start="2024-04-01", end="2024-04-01", interval="1D"
    )
    kbs_df = Quote(source="KBS", symbol="ACB", show_log=False).history(
        start="2024-04-01", end="2024-04-01", interval="1D"
    )
    tcbs_df = Quote(source="TCBS", symbol="ACB", show_log=False).history(
        start="2024-04-01", end="2024-04-01", interval="1D"
    )

    assert vci_df.attrs["price_unit"] == "THOUSAND_VND"
    assert kbs_df.attrs["price_unit"] == "THOUSAND_VND"
    assert tcbs_df.attrs["price_unit"] == "THOUSAND_VND"
    assert vci_df.iloc[0]["close"] == pytest.approx(30.4)
    assert kbs_df.iloc[0]["close"] == pytest.approx(30.4)
    assert tcbs_df.iloc[0]["close"] == pytest.approx(30.4)


def _mock_dnse_ohlc_stock(*args, **kwargs):
    return (200, {
        "data": [
            {"t": 1711958400, "o": 30400.0, "h": 30500.0,
             "l": 30010.0, "c": 30400.0, "v": 123456}
        ]
    })


def _mock_dnse_ohlc_index(*args, **kwargs):
    return (200, {
        "data": [
            {"t": 1711958400, "o": 1700.0, "h": 1710.0,
             "l": 1690.0, "c": 1705.0, "v": 1000}
        ]
    })


@pytest.mark.unit
@pytest.mark.api
def test_quote_history_4_providers_stock_consistent_in_vnd(monkeypatch):
    """Matrix: VCI/KBS/TCBS/DNSE x stock → same VND unit and value."""
    from vnbroker.connector.dnse.services.market_service import MarketService

    monkeypatch.delenv("vnbroker_PRICE_UNIT", raising=False)
    monkeypatch.setattr("vnbroker.explorer.vci.quote.send_request", _mock_vci_history_response)
    monkeypatch.setattr("vnbroker.explorer.kbs.quote.send_request", _mock_kbs_history_response)
    monkeypatch.setattr("vnbroker.explorer.tcbs.quote.client.send_request", _mock_tcbs_history_response)
    monkeypatch.setattr(MarketService, "get_ohlc", _mock_dnse_ohlc_stock)

    kwargs = {"start": "2024-04-01", "end": "2024-04-01", "interval": "1D"}
    vci_df = Quote(source="VCI", symbol="ACB", show_log=False).history(**kwargs)
    kbs_df = Quote(source="KBS", symbol="ACB", show_log=False).history(**kwargs)
    tcbs_df = Quote(source="TCBS", symbol="ACB", show_log=False).history(**kwargs)
    dnse_df = Quote(
        source="DNSE", symbol="ACB", show_log=False,
        api_key="dummy", api_secret="dummy",
    ).history(**kwargs)

    for df in (vci_df, kbs_df, tcbs_df, dnse_df):
        assert df.attrs["price_unit"] == "VND"
        assert df.iloc[0]["close"] == pytest.approx(30400.0)


@pytest.mark.unit
@pytest.mark.api
def test_quote_history_index_not_scaled(monkeypatch):
    """Matrix: index points must not be x1000-scaled in VND mode."""
    from vnbroker.core.utils.transform import normalize_ohlc_prices
    import pandas as pd

    monkeypatch.delenv("vnbroker_PRICE_UNIT", raising=False)
    raw = pd.DataFrame([{
        "time": "2024-04-01", "open": 1700.0, "high": 1710.0,
        "low": 1690.0, "close": 1705.0, "volume": 1000,
    }])
    out = normalize_ohlc_prices(raw, asset_type="index")
    assert out.attrs["price_unit"] == "VND"
    assert out.iloc[0]["close"] == pytest.approx(1705.0)

    # THOUSAND_VND target must still not scale index points
    monkeypatch.setenv("vnbroker_PRICE_UNIT", "THOUSAND_VND")
    raw2 = pd.DataFrame([{
        "time": "2024-04-01", "open": 1700.0, "high": 1710.0,
        "low": 1690.0, "close": 1705.0, "volume": 1000,
    }])
    out2 = normalize_ohlc_prices(raw2, asset_type="index")
    assert out2.attrs["price_unit"] == "THOUSAND_VND"
    assert out2.iloc[0]["close"] == pytest.approx(1705.0)


@pytest.mark.unit
@pytest.mark.api
def test_quote_history_dnse_stock_thousand_vnd(monkeypatch):
    """DNSE stock follows the same VND→THOUSAND_VND (÷1000) rule."""
    from vnbroker.connector.dnse.services.market_service import MarketService

    monkeypatch.setenv("vnbroker_PRICE_UNIT", "THOUSAND_VND")
    monkeypatch.setattr(MarketService, "get_ohlc", _mock_dnse_ohlc_stock)

    dnse_df = Quote(
        source="DNSE", symbol="ACB", show_log=False,
        api_key="dummy", api_secret="dummy",
    ).history(start="2024-04-01", end="2024-04-01", interval="1D")

    assert dnse_df.attrs["price_unit"] == "THOUSAND_VND"
    assert dnse_df.iloc[0]["close"] == pytest.approx(30.4)
