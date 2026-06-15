"""
Integration tests for Gateway mode with StockComponents.

Run with: pytest tests/test_gateway_integration.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from vnbroker.common.client import Vnbroker
from vnbroker.common.data import StockComponents, GatewayQuoteAdapter, GatewayListingAdapter


class TestStockComponentsGatewayMode:
    """Test StockComponents in Gateway mode."""
    
    def test_stock_components_gateway_initialization(self):
        """Test StockComponents initializes with Gateway adapters."""
        mock_gateway_request = Mock(return_value={"data": []})
        
        components = StockComponents(
            symbol="ACB",
            source="GATEWAY",
            gateway_request_func=mock_gateway_request,
            show_log=False
        )
        
        assert components._use_gateway is True
        assert components.quote is not None
        assert components.company is not None
        assert components.finance is not None
        assert components.trading is not None
        assert components.listing is not None
    
    def test_quote_history_gateway_call(self):
        """Test quote.history calls gateway."""
        mock_gateway_request = Mock(return_value={
            "data": [
                {"symbol": "ACB", "date": "2024-01-01", "open": 25000, "high": 25500, "low": 24800, "close": 25200, "volume": 1000000}
            ]
        })
        
        components = StockComponents(
            symbol="ACB",
            source="GATEWAY",
            gateway_request_func=mock_gateway_request,
            show_log=False
        )
        
        result = components.quote.history(start="2024-01-01", end="2024-01-31")
        
        mock_gateway_request.assert_called_once()
        call_args = mock_gateway_request.call_args
        assert call_args[0][0] == "/api/v1/quote/history"
        assert call_args[0][1] == "POST"
        assert call_args[1]["json_data"]["symbol"] == "ACB"
        assert isinstance(result, pd.DataFrame)
    
    def test_listing_all_symbols_gateway_call(self):
        """Test listing.all_symbols calls gateway."""
        mock_gateway_request = Mock(return_value={
            "data": [
                {"symbol": "ACB", "name": "Asia Commercial Bank"},
                {"symbol": "VCB", "name": "Vietcombank"}
            ]
        })
        
        components = StockComponents(
            symbol="ACB",
            source="GATEWAY",
            gateway_request_func=mock_gateway_request,
            show_log=False
        )
        
        result = components.listing.all_symbols()
        
        mock_gateway_request.assert_called_once()
        call_args = mock_gateway_request.call_args
        assert call_args[0][0] == "/api/v1/listing/all_symbols"
        assert call_args[0][1] == "GET"
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
    
    def test_company_profile_gateway_call(self):
        """Test company.profile calls gateway."""
        mock_gateway_request = Mock(return_value={
            "data": {"symbol": "ACB", "name": "Asia Commercial Bank", "industry": "Banking"}
        })
        
        components = StockComponents(
            symbol="ACB",
            source="GATEWAY",
            gateway_request_func=mock_gateway_request,
            show_log=False
        )
        
        result = components.company.profile()
        
        mock_gateway_request.assert_called_once()
        call_args = mock_gateway_request.call_args
        assert call_args[0][0] == "/api/v1/company/profile"
        assert call_args[0][1] == "POST"
        assert isinstance(result, pd.DataFrame)
    
    def test_finance_balance_sheet_gateway_call(self):
        """Test finance.balance_sheet calls gateway."""
        mock_gateway_request = Mock(return_value={
            "data": [
                {"symbol": "ACB", "period": "quarter", "total_assets": 500000000000}
            ]
        })
        
        components = StockComponents(
            symbol="ACB",
            source="GATEWAY",
            gateway_request_func=mock_gateway_request,
            show_log=False
        )
        
        result = components.finance.balance_sheet()
        
        mock_gateway_request.assert_called_once()
        call_args = mock_gateway_request.call_args
        assert call_args[0][0] == "/api/v1/finance/balance_sheet"
        assert call_args[0][1] == "POST"
        assert isinstance(result, pd.DataFrame)
    
    def test_trading_price_board_gateway_call(self):
        """Test trading.price_board calls gateway."""
        mock_gateway_request = Mock(return_value={
            "data": [
                {"symbol": "ACB", "price": 25000, "change": 1.5},
                {"symbol": "VCB", "price": 95000, "change": -0.5}
            ]
        })
        
        components = StockComponents(
            symbol="ACB",
            source="GATEWAY",
            gateway_request_func=mock_gateway_request,
            show_log=False
        )
        
        result = components.trading.price_board(["ACB", "VCB"])
        
        mock_gateway_request.assert_called_once()
        call_args = mock_gateway_request.call_args
        assert call_args[0][0] == "/api/v1/trading/price_board"
        assert call_args[0][1] == "POST"
        assert call_args[1]["json_data"]["symbols"] == ["ACB", "VCB"]
        assert isinstance(result, pd.DataFrame)


class TestVnbrokerGatewayIntegration:
    """Test Vnbroker integration with Gateway mode."""
    
    @patch('vnbroker.common.client.GatewayHttpClient')
    def test_vnbroker_stock_returns_gateway_components(self, mock_gateway_client_class):
        """Test Vnbroker.stock() returns StockComponents with Gateway."""
        mock_gateway_client = Mock()
        mock_gateway_client_class.return_value = mock_gateway_client
        
        vn = Vnbroker(pat_key="vninvest_pat_test", show_log=False)
        components = vn.stock("ACB")
        
        assert isinstance(components, StockComponents)
        assert components._use_gateway is True
        assert components.gateway_request_func is not None
    
    @patch('vnbroker.common.client.GatewayHttpClient')
    def test_vnbroker_gateway_request_flow(self, mock_gateway_client_class):
        """Test Vnbroker._gateway_request flow."""
        mock_gateway_client = Mock()
        mock_gateway_client.request.return_value = {"data": [{"symbol": "ACB", "price": 25000}]}
        mock_gateway_client_class.return_value = mock_gateway_client
        
        vn = Vnbroker(pat_key="vninvest_pat_test", show_log=False)
        result = vn._gateway_request("/api/v1/quote/history", "POST", {"symbol": "ACB"})
        
        assert result == {"data": [{"symbol": "ACB", "price": 25000}]}
        mock_gateway_client.request.assert_called_once_with(
            "/api/v1/quote/history", "POST", {"symbol": "ACB"}, None
        )
    
    @patch('vnbroker.common.client.GatewayHttpClient')
    def test_vnbroker_gateway_fallback_flow(self, mock_gateway_client_class):
        """Test Vnbroker fallback when Gateway fails."""
        from vnbroker.core.exceptions import GatewayUnavailableError
        
        mock_gateway_client = Mock()
        mock_gateway_client.request.side_effect = GatewayUnavailableError("Gateway down")
        mock_gateway_client._emergency_fallback.return_value = {"data": [{"symbol": "ACB", "price": 25000}]}
        mock_gateway_client_class.return_value = mock_gateway_client
        
        vn = Vnbroker(pat_key="vninvest_pat_test", show_log=False)
        result = vn._gateway_request("/api/v1/quote/history", "POST", {"symbol": "ACB"})
        
        assert result == {"data": [{"symbol": "ACB", "price": 25000}]}
        mock_gateway_client._emergency_fallback.assert_called_once()


class TestGatewayAdapters:
    """Test Gateway adapter classes directly."""
    
    def test_gateway_quote_adapter_history(self):
        """Test GatewayQuoteAdapter.history."""
        mock_request = Mock(return_value={
            "data": [{"symbol": "ACB", "date": "2024-01-01", "close": 25000}]
        })
        
        adapter = GatewayQuoteAdapter("ACB", mock_request)
        result = adapter.history(start="2024-01-01", end="2024-01-31")
        
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "/api/v1/quote/history"
        assert call_args[1]["json_data"]["symbol"] == "ACB"
        assert isinstance(result, pd.DataFrame)
    
    def test_gateway_listing_adapter_all_symbols(self):
        """Test GatewayListingAdapter.all_symbols."""
        mock_request = Mock(return_value={
            "data": [{"symbol": "ACB"}, {"symbol": "VCB"}]
        })
        
        adapter = GatewayListingAdapter(mock_request)
        result = adapter.all_symbols()
        
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "/api/v1/listing/all_symbols"
        assert call_args[0][1] == "GET"
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
    
    def test_gateway_company_adapter_profile(self):
        """Test GatewayCompanyAdapter.profile."""
        mock_request = Mock(return_value={
            "data": {"symbol": "ACB", "name": "Asia Commercial Bank"}
        })
        
        from vnbroker.common.data import GatewayCompanyAdapter
        adapter = GatewayCompanyAdapter("ACB", mock_request)
        result = adapter.profile()
        
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "/api/v1/company/profile"
        assert call_args[0][1] == "POST"
        assert isinstance(result, pd.DataFrame)
    
    def test_gateway_finance_adapter_balance_sheet(self):
        """Test GatewayFinanceAdapter.balance_sheet."""
        mock_request = Mock(return_value={
            "data": [{"symbol": "ACB", "total_assets": 500000000000}]
        })
        
        from vnbroker.common.data import GatewayFinanceAdapter
        adapter = GatewayFinanceAdapter("ACB", "quarter", True, mock_request)
        result = adapter.balance_sheet()
        
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "/api/v1/finance/balance_sheet"
        assert call_args[0][1] == "POST"
        assert isinstance(result, pd.DataFrame)
    
    def test_gateway_news_adapter_market_news(self):
        """Test GatewayNewsAdapter.market_news."""
        mock_request = Mock(return_value={
            "data": [{"title": "Market up", "source": "Cafef"}]
        })
        
        from vnbroker.common.data import GatewayNewsAdapter
        adapter = GatewayNewsAdapter("ACB", mock_request)
        result = adapter.market_news(limit=10)
        
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "/api/v1/news/market"
        assert call_args[0][1] == "POST"
        assert call_args[1]["json_data"]["limit"] == 10
        assert isinstance(result, pd.DataFrame)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])