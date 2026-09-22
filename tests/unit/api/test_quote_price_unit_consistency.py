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
    return {
        "data": [
            {
                "t": "09:30:00",
                "p": 30400.0,
                "v": 123456,
                "a": "BU",
            }
        ]
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
