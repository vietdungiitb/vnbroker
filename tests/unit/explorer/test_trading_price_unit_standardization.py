"""Regression tests for trading price board unit normalization across providers."""

import pandas as pd
import pytest

from vnbroker.explorer.kbs.trading import Trading as KBSTrading
from vnbroker.explorer.tcbs.trading import Trading as TCBSTrading
from vnbroker.explorer.vci.trading import Trading as VCITrading


@pytest.mark.unit
@pytest.mark.explorer
def test_kbs_price_board_defaults_to_vnd(monkeypatch):
    monkeypatch.delenv("vnbroker_PRICE_UNIT", raising=False)

    sample = pd.DataFrame(
        [
            {
                "symbol": "ACB",
                "exchange": "HSX",
                "close_price": 30400.0,
                "reference_price": 30000.0,
            }
        ]
    )

    monkeypatch.setattr(
        KBSTrading,
        "_fetch_stock_board",
        lambda self, symbols_list, show_log=False: sample.copy(),
    )

    trading = KBSTrading(symbol="ACB", show_log=False)
    out = trading.price_board(["ACB"], get_all=True)

    assert out.attrs["price_unit"] == "VND"
    assert out.iloc[0]["close_price"] == pytest.approx(30400.0)


@pytest.mark.unit
@pytest.mark.explorer
def test_kbs_price_board_honors_explicit_thousand_unit(monkeypatch):
    monkeypatch.delenv("vnbroker_PRICE_UNIT", raising=False)

    sample = pd.DataFrame(
        [
            {
                "symbol": "ACB",
                "exchange": "HSX",
                "close_price": 30400.0,
            }
        ]
    )

    monkeypatch.setattr(
        KBSTrading,
        "_fetch_stock_board",
        lambda self, symbols_list, show_log=False: sample.copy(),
    )

    trading = KBSTrading(symbol="ACB", show_log=False)
    out = trading.price_board(["ACB"], get_all=True, price_unit="THOUSAND_VND")

    assert out.attrs["price_unit"] == "THOUSAND_VND"
    assert out.iloc[0]["close_price"] == pytest.approx(30.4)


@pytest.mark.unit
@pytest.mark.explorer
def test_tcbs_price_board_honors_explicit_thousand_unit(monkeypatch):
    monkeypatch.delenv("vnbroker_PRICE_UNIT", raising=False)

    monkeypatch.setattr(
        "vnbroker.explorer.tcbs.trading._PRICE_BOARD_STD_COLS",
        ["t", "cp"],
    )

    def _fake_send_request(*args, **kwargs):
        return {"data": [{"t": "ACB", "cp": 30400.0}]}

    monkeypatch.setattr("vnbroker.explorer.tcbs.trading.client.send_request", _fake_send_request)

    trading = TCBSTrading(symbol="ACB", show_log=False)
    out = trading.price_board(["ACB"], std_columns=True, price_unit="THOUSAND_VND")

    assert out.attrs["price_unit"] == "THOUSAND_VND"
    assert out.iloc[0]["Giá"] == pytest.approx(30.4)


@pytest.mark.unit
@pytest.mark.explorer
def test_vci_price_board_honors_explicit_thousand_unit(monkeypatch):
    monkeypatch.delenv("vnbroker_PRICE_UNIT", raising=False)

    def _fake_send_request(*args, **kwargs):
        return [
            {
                "listingInfo": {
                    "symbol": "ACB",
                    "board": "HSX",
                    "referencePrice": 30000.0,
                },
                "bidAsk": {
                    "bidPrices": [{"price": 29900.0, "volume": 100}],
                    "askPrices": [{"price": 30100.0, "volume": 120}],
                },
                "matchPrice": {
                    "price": 30000.0,
                },
            }
        ]

    monkeypatch.setattr("vnbroker.explorer.vci.trading.client.send_request", _fake_send_request)

    trading = VCITrading(symbol="ACB", show_log=False)
    out = trading.price_board(["ACB"], flatten_columns=False, price_unit="THOUSAND_VND")

    assert out.attrs["price_unit"] == "THOUSAND_VND"
    assert out[("bid_ask", "bid_1_price")].iloc[0] == pytest.approx(29.9)
