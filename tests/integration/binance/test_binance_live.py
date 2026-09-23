"""ISSUE-04: Binance live smoke (gated — needs network, no API key)."""

import os

import pytest

from vnbroker import Vnbroker

_LIVE = os.getenv("vnbroker_RUN_LIVE_INTEGRATION") == "1"

pytestmark = pytest.mark.integration


@pytest.mark.skipif(not _LIVE, reason="Set vnbroker_RUN_LIVE_INTEGRATION=1 for live smoke")
def test_binance_history_live_smoke():
    client = Vnbroker(show_log=False).crypto("BTC")
    df = client.history(interval="1D", limit=5)
    assert len(df) > 0
    assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]
    assert df.attrs["price_unit"] == "USDT"
    assert float(df.iloc[-1]["close"]) > 0
