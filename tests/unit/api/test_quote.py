"""
Unit tests for vnbroker API Quote adapter.

Tests the Quote class adapter pattern, parameter filtering,
and delegation to underlying explorer quote implementations.
"""

import pytest
from vnbroker.api.quote import Quote


@pytest.mark.unit
@pytest.mark.api
class TestQuoteAdapter:
    """Test suite for Quote API adapter."""

    def test_quote_instantiation_vci(self):
        """Test Quote can be instantiated with VCI source."""
        quote = Quote(source='VCI', symbol='ACB', show_log=False)
        assert quote is not None
        assert quote.source.lower() == 'vci'

    def test_quote_instantiation_kbs(self):
        """Test Quote can be instantiated with KBS source."""
        quote = Quote(source='KBS', symbol='VCB', show_log=False)
        assert quote is not None
        assert quote.source.lower() == 'kbs'

    def test_quote_instantiation_tcbs(self):
        """Test Quote can be instantiated with TCBS source."""
        quote = Quote(source='TCBS', symbol='VCB', show_log=False)
        assert quote is not None
        assert quote.source.lower() == 'tcbs'

    def test_quote_invalid_source_raises_error(self):
        """Test Quote raises ValueError for invalid source."""
        with pytest.raises(ValueError, match="chỉ nhận giá trị"):
            Quote(source='INVALID', symbol='ACB')

    def test_quote_has_history_method(self):
        """Test Quote has history method."""
        quote = Quote(source='VCI', symbol='ACB', show_log=False)
        assert hasattr(quote, 'history')
        assert callable(quote.history)

    def test_quote_accepts_symbol_parameter(self):
        """Test Quote accepts and stores symbol parameter."""
        quote = Quote(source='VCI', symbol='TCB', show_log=False)
        # Symbol should be accessible (implementation dependent)
        assert hasattr(quote, 'symbol') or hasattr(quote.client, 'symbol')

    def test_quote_default_source_is_kbs(self):
        """Test Quote defaults to KBS source."""
        quote = Quote(symbol='ACB', show_log=False)
        assert quote.source.lower() == 'kbs'

    @pytest.mark.parametrize("source", ['VCI', 'KBS', 'TCBS'])
    def test_quote_supports_multiple_sources(self, source):
        """Test Quote supports VCI, KBS, and TCBS sources."""
        quote = Quote(source=source, symbol='VNM', show_log=False)
        assert quote.source.lower() == source.lower()
