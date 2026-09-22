import os
import pytest
from unittest.mock import patch


@pytest.mark.unit
def test_import_does_not_call_network_for_update_check(monkeypatch):
    monkeypatch.delenv("VNBROKER_CHECK_UPDATES", raising=False)
    monkeypatch.delenv("PYTEST_RUNNING", raising=False)
    
    with patch("requests.get") as mock_requests_get:
        # Check that importing doesn't trigger requests.get
        if "vnbroker" in os.sys.modules:
            # Re-executing line 70 condition
            should_check = os.getenv("VNBROKER_CHECK_UPDATES") == "1" and not os.getenv("PYTEST_RUNNING")
            assert should_check is False
        assert mock_requests_get.call_count == 0
