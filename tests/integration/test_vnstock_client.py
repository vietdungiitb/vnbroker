"""
Integration tests for vnbroker main client interface.

Tests end-to-end workflows using the vnbroker class.
"""

import pytest
from vnbroker.common.client import Vnbroker


@pytest.mark.integration
class TestvnbrokerClient:
    """Test suite for vnbroker main client."""

    def test_vnbroker_instantiation(self):
        """Test vnbroker can be instantiated."""
        stock = Vnbroker(show_log=False)
        assert stock is not None

    def test_vnbroker_stock_method(self):
        """Test vnbroker.stock() method."""
        stock = Vnbroker(show_log=False)
        acb = stock.stock('ACB', source='KBS')
        assert acb is not None
        assert hasattr(acb, 'quote')
        assert hasattr(acb, 'company')
        assert hasattr(acb, 'finance')

    def test_vnbroker_stock_components_quote(self):
        """Test StockComponents has working quote component."""
        stock = Vnbroker(show_log=False)
        acb = stock.stock('ACB', source='KBS')
        assert hasattr(acb.quote, 'history')

    def test_vnbroker_stock_components_company(self):
        """Test StockComponents has working company component."""
        stock = Vnbroker(show_log=False)
        acb = stock.stock('ACB', source='KBS')
        assert hasattr(acb.company, 'overview')
        assert hasattr(acb.company, 'profile')

    def test_vnbroker_stock_components_finance(self):
        """Test StockComponents has working finance component."""
        stock = Vnbroker(show_log=False)
        acb = stock.stock('ACB', source='KBS')
        assert hasattr(acb.finance, 'balance_sheet')
        assert hasattr(acb.finance, 'income_statement')
        assert hasattr(acb.finance, 'cash_flow')

    def test_vnbroker_supported_sources(self):
        """Test vnbroker supports expected sources."""
        expected_sources = ['KBS', 'VCI', 'TCBS', 'DNSE', 'MSN', 'FMP']
        assert Vnbroker.SUPPORTED_SOURCES == expected_sources

    @pytest.mark.parametrize("source", ['VCI', 'KBS', 'TCBS'])
    def test_vnbroker_stock_with_different_sources(self, source):
        """Test vnbroker.stock() works with different sources."""
        stock = Vnbroker(show_log=False)
        acb = stock.stock('ACB', source=source)
        assert acb is not None
        assert acb.source.upper() == source

    def test_vnbroker_stock_with_dnse_source(self):
        """Test vnbroker.stock() works with DNSE source (requires credentials)."""
        import os
        if not (os.getenv('DNSE_API_KEY') and os.getenv('DNSE_API_SECRET')):
            pytest.skip("DNSE credentials not available")
        stock = Vnbroker(show_log=False)
        acb = stock.stock('ACB', source='DNSE')
        assert acb is not None
        assert acb.source.upper() == 'DNSE'

    def test_vnbroker_fx_method(self):
        """Test vnbroker.fx() method for forex data."""
        stock = Vnbroker(show_log=False)
        fx = stock.fx('USDVND', source='MSN')
        assert fx is not None
        assert hasattr(fx, 'quote')

    def test_vnbroker_crypto_method(self):
        """Test vnbroker.crypto() method."""
        stock = Vnbroker(show_log=False)
        btc = stock.crypto('BTC', source='MSN')
        assert btc is not None
        assert hasattr(btc, 'quote')

    def test_vnbroker_world_index_method(self):
        """Test vnbroker.world_index() method."""
        stock = Vnbroker(show_log=False)
        dji = stock.world_index('DJI', source='MSN')
        assert dji is not None
        assert hasattr(dji, 'quote')
