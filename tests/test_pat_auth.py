"""
Unit tests for PAT authentication and Gateway client.

Run with: pytest tests/test_pat_auth.py -v
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from vnbroker.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    QuotaExceededError,
    InvalidPATFormatError,
    GatewayUnavailableError,
    EmergencyQuotaExceededError,
)
from vnbroker.core.utils.gateway_client import GatewayHttpClient, DEFAULT_PAT
from vnbroker.core.dispatch import local_dispatch_fallback, get_supported_fallback_endpoints
from vnbroker.common.client import Vnbroker


class TestPATFormatValidation:
    """Test PAT format validation."""
    
    def test_valid_pat_format(self):
        """Test that valid PAT format is accepted."""
        client = GatewayHttpClient(pat_key="vninvest_pat_valid_token_123")
        assert client.pat_key == "vninvest_pat_valid_token_123"
    
    def test_invalid_pat_format_raises_error(self):
        """Test that invalid PAT format raises InvalidPATFormatError."""
        with pytest.raises(InvalidPATFormatError):
            GatewayHttpClient(pat_key="invalid_token")
    
    def test_empty_pat_uses_default(self):
        """Test that empty PAT uses DEFAULT_PAT."""
        client = GatewayHttpClient(pat_key="")
        assert client.pat_key == DEFAULT_PAT
    
    def test_none_pat_uses_default(self):
        """Test that None PAT uses DEFAULT_PAT."""
        client = GatewayHttpClient(pat_key=None)
        assert client.pat_key == DEFAULT_PAT


class TestGatewayHttpClient:
    """Test GatewayHttpClient functionality."""
    
    @patch('vnbroker.core.utils.gateway_client.requests.Session')
    def test_initialization_sets_headers(self, mock_session_class):
        """Test that initialization sets correct headers."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        client = GatewayHttpClient(pat_key="vninvest_pat_test_token", show_log=False)
        
        # Check headers were set
        mock_session.headers.update.assert_called_once()
        call_args = mock_session.headers.update.call_args[0][0]
        assert call_args["Authorization"] == "Bearer vninvest_pat_test_token"
        assert call_args["Content-Type"] == "application/json"
        assert "vnbroker-client-python" in call_args["User-Agent"]
    
    @patch('vnbroker.core.utils.gateway_client.requests.Session')
    def test_request_success(self, mock_session_class):
        """Test successful request."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"symbol": "ACB", "price": 25000}]}
        mock_session.request.return_value = mock_response
        
        client = GatewayHttpClient(pat_key="vninvest_pat_test_token", show_log=False)
        result = client.request("/api/v1/quote/history", "POST", {"symbol": "ACB"})
        
        assert result == {"data": [{"symbol": "ACB", "price": 25000}]}
        mock_session.request.assert_called_once()
    
    @patch('vnbroker.core.utils.gateway_client.requests.Session')
    def test_request_401_raises_authentication_error(self, mock_session_class):
        """Test that 401 raises AuthenticationError."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 401
        mock_session.request.return_value = mock_response
        
        client = GatewayHttpClient(pat_key="vninvest_pat_test_token", show_log=False)
        
        with pytest.raises(AuthenticationError) as exc_info:
            client.request("/api/v1/quote/history", "POST", {"symbol": "ACB"})
        
        assert exc_info.value.error_code == "AUTH_001"
    
    @patch('vnbroker.core.utils.gateway_client.requests.Session')
    def test_request_403_raises_authorization_error(self, mock_session_class):
        """Test that 403 raises AuthorizationError."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 403
        mock_session.request.return_value = mock_response
        
        client = GatewayHttpClient(pat_key="vninvest_pat_test_token", show_log=False)
        
        with pytest.raises(AuthorizationError) as exc_info:
            client.request("/api/v1/finance/balance_sheet", "POST", {"symbol": "ACB"})
        
        assert exc_info.value.error_code == "AUTH_002"
    
    @patch('vnbroker.core.utils.gateway_client.requests.Session')
    def test_request_429_raises_quota_exceeded_error(self, mock_session_class):
        """Test that 429 raises QuotaExceededError."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers.get.return_value = "3600"
        mock_session.request.return_value = mock_response
        
        client = GatewayHttpClient(pat_key="vninvest_pat_test_token", show_log=False)
        
        with pytest.raises(QuotaExceededError) as exc_info:
            client.request("/api/v1/quote/history", "POST", {"symbol": "ACB"})
        
        assert exc_info.value.error_code == "AUTH_003"
        assert exc_info.value.details.get("retry_after") == "3600"
    
    @patch('vnbroker.core.utils.gateway_client.requests.Session')
    def test_connection_error_triggers_fallback(self, mock_session_class):
        """Test that connection error raises GatewayUnavailableError."""
        import requests
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.request.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        client = GatewayHttpClient(pat_key="vninvest_pat_test_token", show_log=False)
        
        with pytest.raises(GatewayUnavailableError):
            client.request("/api/v1/quote/history", "POST", {"symbol": "ACB"})
    
    @patch('vnbroker.core.utils.gateway_client.requests.Session')
    def test_timeout_triggers_fallback(self, mock_session_class):
        """Test that timeout raises GatewayUnavailableError."""
        import requests
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.request.side_effect = requests.exceptions.Timeout("Request timed out")
        
        client = GatewayHttpClient(pat_key="vninvest_pat_test_token", show_log=False)
        
        with pytest.raises(GatewayUnavailableError):
            client.request("/api/v1/quote/history", "POST", {"symbol": "ACB"})


class TestEmergencyFallback:
    """Test emergency fallback mechanism."""
    
    @patch('vnbroker.core.utils.gateway_client.requests.Session')
    @patch('vnbroker.core.dispatch.local_dispatch_fallback')
    def test_emergency_fallback_counter(self, mock_dispatch, mock_session_class):
        """Test emergency fallback call counter."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_dispatch.return_value = {"data": []}
        import requests
        mock_session.request.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        client = GatewayHttpClient(pat_key="vninvest_pat_test_token", show_log=False)
        
        # Call emergency fallback with required parameters
        client._emergency_fallback("/api/v1/quote/history", {"symbol": "ACB", "start": "2024-01-01", "end": "2024-01-31"})
        
        status = client.get_emergency_status()
        assert status["emergency_calls_used_today"] == 1
        assert status["emergency_calls_remaining"] == 9
    
    @patch('vnbroker.core.utils.gateway_client.requests.Session')
    @patch('vnbroker.core.dispatch.local_dispatch_fallback')
    def test_emergency_quota_exceeded(self, mock_dispatch, mock_session_class):
        """Test emergency quota exceeded after 10 calls."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_dispatch.return_value = {"data": []}
        import requests
        mock_session.request.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        client = GatewayHttpClient(pat_key="vninvest_pat_test_token", show_log=False)
        
        # Make 10 calls to exhaust emergency quota
        for i in range(10):
            client._emergency_fallback("/api/v1/quote/history", {"symbol": "ACB", "start": "2024-01-01", "end": "2024-01-31"})
        
        # 11th call should raise EmergencyQuotaExceededError
        with pytest.raises(EmergencyQuotaExceededError):
            client._emergency_fallback("/api/v1/quote/history", {"symbol": "ACB", "start": "2024-01-01", "end": "2024-01-31"})


class TestVnbrokerPATInitialization:
    """Test Vnbroker PAT initialization."""
    
    def test_vnbroker_with_explicit_pat(self):
        """Test Vnbroker initialization with explicit PAT."""
        vn = Vnbroker(pat_key="vninvest_pat_explicit_token", show_log=False)
        assert vn._use_gateway is True
        assert vn.gateway_client.pat_key == "vninvest_pat_explicit_token"
    
    def test_vnbroker_with_env_pat(self):
        """Test Vnbroker initialization with env PAT."""
        with patch.dict(os.environ, {"VNBROKER_PAT_KEY": "vninvest_pat_env_token"}):
            vn = Vnbroker(show_log=False)
            assert vn.gateway_client.pat_key == "vninvest_pat_env_token"
    
    def test_vnbroker_with_default_pat(self):
        """Test Vnbroker initialization with default PAT."""
        with patch.dict(os.environ, {}, clear=True):
            vn = Vnbroker(show_log=False)
            assert vn.gateway_client.pat_key == DEFAULT_PAT
    
    def test_vnbroker_invalid_pat_raises_error(self):
        """Test Vnbroker with invalid PAT raises error."""
        with pytest.raises(InvalidPATFormatError):
            Vnbroker(pat_key="invalid_token", show_log=False)
    
    def test_vnbroker_legacy_mode(self):
        """Test Vnbroker in legacy direct mode raises ValueError."""
        with pytest.raises(ValueError, match="Supported sources"):
            Vnbroker(source="VCI", show_log=False)
    
    def test_vnbroker_gateway_mode_default(self):
        """Test Vnbroker defaults to GATEWAY mode."""
        vn = Vnbroker(show_log=False)
        assert vn._use_gateway is True
        assert vn.source == "GATEWAY"


class TestDispatchFallback:
    """Test emergency fallback dispatch."""
    
    def test_supported_endpoints_list(self):
        """Test that supported endpoints list is returned."""
        endpoints = get_supported_fallback_endpoints()
        assert isinstance(endpoints, list)
        assert len(endpoints) > 0
        assert "/api/v1/quote/history" in endpoints
        assert "/api/v1/company/profile" in endpoints
    
    def test_is_endpoint_supported(self):
        """Test endpoint support check."""
        from vnbroker.core.dispatch import is_endpoint_supported_in_fallback
        assert is_endpoint_supported_in_fallback("/api/v1/quote/history") is True
        assert is_endpoint_supported_in_fallback("/api/v1/unknown/endpoint") is False
    
    @patch('vnbroker.core.dispatch._import_explorer_function')
    def test_local_dispatch_fallback_success(self, mock_import):
        """Test successful fallback dispatch."""
        mock_func = Mock(return_value=pd.DataFrame({"symbol": ["ACB"], "price": [25000]}))
        mock_import.return_value = mock_func
        
        result = local_dispatch_fallback("/api/v1/quote/history", {"symbol": "ACB", "start": "2024-01-01", "end": "2024-01-31"})
        
        assert "data" in result
        assert result["source"] == "emergency_fallback"
        assert "provider_used" in result
    
    @patch('vnbroker.core.dispatch._import_explorer_function')
    def test_local_dispatch_fallback_unsupported_endpoint(self, mock_import):
        """Test fallback with unsupported endpoint."""
        with pytest.raises(Exception) as exc_info:
            local_dispatch_fallback("/api/v1/unknown/endpoint", {})
        
        assert "not supported in emergency fallback mode" in str(exc_info.value)


class TestGatewayHealthCheck:
    """Test Gateway health check."""
    
    @patch('vnbroker.core.utils.gateway_client.requests.Session')
    def test_health_check_healthy(self, mock_session_class):
        """Test health check returns healthy status."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response
        
        client = GatewayHttpClient(pat_key="vninvest_pat_test_token", show_log=False)
        result = client.health_check()
        
        assert result["status"] == "healthy"
        assert result["status_code"] == 200
    
    @patch('vnbroker.core.utils.gateway_client.requests.Session')
    def test_health_check_unhealthy(self, mock_session_class):
        """Test health check returns unhealthy status."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.get.side_effect = Exception("Connection failed")
        
        client = GatewayHttpClient(pat_key="vninvest_pat_test_token", show_log=False)
        result = client.health_check()
        
        assert result["status"] == "unhealthy"
        assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])