import pytest
import pandas as pd
import time
from unittest.mock import MagicMock
from vnbroker.explorer.tcbs.quote import Quote as TCBSQuote
from vnbroker.core.adaptive_controller import get_global_pressure


@pytest.mark.unit
def test_tcbs_fetch_multiple_basic(monkeypatch):
    # Mock response
    mock_response = {
        "data": [
            {
                "tradingDate": "2024-01-01T00:00:00.000Z",
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 103.0,
                "volume": 1000000
            }
        ]
    }

    called_urls = []

    def mock_send_request(url, *args, **kwargs):
        called_urls.append(url)
        return mock_response

    monkeypatch.setattr("vnbroker.core.utils.client.send_request", mock_send_request)

    results = TCBSQuote.fetch_multiple(
        symbols=["ACB", "TCB", "VNM"],
        start="2024-01-01",
        end="2024-01-02",
        interval="1D",
        max_concurrency=4
    )

    assert len(results) == 3
    assert len(called_urls) == 3
    for df in results:
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "time" in df.columns
        assert df.iloc[0]["open"] == 100.0


@pytest.mark.unit
def test_tcbs_history_delegates_to_parallel(monkeypatch):
    mock_results = [pd.DataFrame({"close": [100.0]})]
    
    fetch_multiple_mock = MagicMock(return_value=mock_results)
    monkeypatch.setattr(TCBSQuote, "fetch_multiple", fetch_multiple_mock)

    quote = TCBSQuote("ACB", show_log=False)
    res = quote.history(
        start="2024-01-01",
        end="2024-01-02",
        parallel=True,
        symbols=["ACB", "TCB"]
    )

    assert res == mock_results
    fetch_multiple_mock.assert_called_once_with(
        symbols=["ACB", "TCB"],
        start="2024-01-01",
        end="2024-01-02",
        interval="1D",
        show_log=False,
        count_back=365,
        length=None,
        proxy_mode=None,
        proxy_list=None,
        max_concurrency=16,
        adaptive_concurrency=None
    )


@pytest.mark.unit
def test_tcbs_fetch_multiple_empty():
    results = TCBSQuote.fetch_multiple(symbols=[])
    assert results == []


@pytest.mark.unit
def test_tcbs_fetch_multiple_adaptive(monkeypatch):
    # Enable adaptive concurrency and verify it behaves correctly under mock
    monkeypatch.setenv("vnbroker_TCBS_ADAPTIVE_CONCURRENCY", "True")
    monkeypatch.setenv("vnbroker_TCBS_ADAPTIVE_START_CONCURRENCY", "4")
    monkeypatch.setenv("vnbroker_TCBS_ADAPTIVE_MIN_CONCURRENCY", "1")
    monkeypatch.setenv("vnbroker_TCBS_ADAPTIVE_FAIL_THRESHOLD", "0.1")

    # Mock response
    mock_response = {
        "data": [
            {
                "tradingDate": "2024-01-01T00:00:00.000Z",
                "open": 200.0,
                "high": 205.0,
                "low": 198.0,
                "close": 203.0,
                "volume": 500000
            }
        ]
    }

    def mock_send_request(url, *args, **kwargs):
        # Introduce a sleep to measure latency
        time.sleep(0.01)
        return mock_response

    monkeypatch.setattr("vnbroker.core.utils.client.send_request", mock_send_request)

    results = TCBSQuote.fetch_multiple(
        symbols=["ACB", "TCB", "VNM", "HPG", "VJC"],
        start="2024-01-01",
        end="2024-01-02",
        interval="1D",
        max_concurrency=4,
        adaptive_concurrency=True
    )

    assert len(results) == 5
