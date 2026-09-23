import pytest
from unittest.mock import MagicMock
import requests

from vnbroker.common.data import Quote


@pytest.mark.unit
def test_quote_history_does_not_retry_on_value_error():
    quote = Quote("ACB", source="VCI")
    mock_source = MagicMock()
    mock_source.history.side_effect = ValueError("Invalid parameter")
    quote.data_source = mock_source
    
    # Should raise ValueError immediately without retrying 3 times
    with pytest.raises(ValueError, match="Invalid parameter"):
        quote.history()
    
    assert mock_source.history.call_count == 1


@pytest.mark.unit
def test_quote_history_retries_on_network_error():
    quote = Quote("ACB", source="VCI")
    mock_source = MagicMock()
    mock_source.history.side_effect = requests.exceptions.ConnectionError("Network down")
    quote.data_source = mock_source
    
    with pytest.raises(requests.exceptions.ConnectionError, match="Network down"):
        quote.history()
    
    # Config.DEFAULT_RETRIES is 3
    assert mock_source.history.call_count == 3
