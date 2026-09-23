import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from vnbroker.explorer.tcbs.quote import Quote as TCBSQuote


@pytest.mark.unit
def test_tcbs_history_multiday_raises_not_implemented():
    quote = TCBSQuote("ACB", show_log=False)
    with pytest.raises(NotImplementedError, match="TCBS iFlash OpenAPI does not support"):
        quote.history(start="2024-01-01", end="2024-01-10", interval="1D")


@pytest.mark.unit
def test_tcbs_history_single_day_computes_from_intraday(monkeypatch):
    mock_response = {
        "data": [
            {"t": "09:15:00", "p": 100.0, "v": 200000, "a": "BU"},
            {"t": "14:30:00", "p": 103.0, "v": 400000, "a": "BU"},
        ]
    }
    monkeypatch.setattr("vnbroker.core.utils.client.send_request", lambda *args, **kwargs: mock_response)
    
    quote = TCBSQuote("ACB", show_log=False)
    df = quote.history(start="2024-01-01", end="2024-01-01", interval="1D")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "time" in df.columns
    assert df.iloc[0]["open"] == 100.0
    assert df.iloc[0]["close"] == 103.0
