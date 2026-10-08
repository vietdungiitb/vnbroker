"""
Unit tests for vnbroker API Stream adapter.

Tests the Stream class for initialization, method presence,
and source validation.
"""

import pytest
from unittest.mock import patch, MagicMock
from vnbroker.api.stream import Stream, TickData


@pytest.mark.unit
@pytest.mark.api
class TestStreamAdapter:
    """Test suite for Stream API adapter."""

    @patch("vnbroker.base.BaseAdapter.__init__", return_value=None)
    def test_stream_init(self, mock_base_init):
        """Test Stream can be instantiated with valid source."""
        stream = Stream(source="vci", symbols=["VCB", "VNM"])
        assert stream is not None
        assert stream.source == "vci"
        assert stream.symbols == ["VCB", "VNM"]
        assert stream.poll_interval == 1.0
        assert stream.max_retries == 3

    @patch("vnbroker.base.BaseAdapter.__init__", return_value=None)
    def test_stream_init_kbs(self, mock_base_init):
        """Test Stream can be instantiated with KBS source."""
        stream = Stream(source="kbs", symbols=["VCB"])
        assert stream.source == "kbs"
        assert stream.symbols == ["VCB"]

    @patch("vnbroker.base.BaseAdapter.__init__", return_value=None)
    def test_stream_init_auto(self, mock_base_init):
        """Test Stream can be instantiated with auto source."""
        stream = Stream(source="auto", symbols=["VCB", "FPT"])
        assert stream.source == "auto"
        assert stream._fallback_sources == ["vci", "kbs"]

    @patch("vnbroker.base.BaseAdapter.__init__", return_value=None)
    def test_stream_has_methods(self, mock_base_init):
        """Test Stream has expected methods."""
        stream = Stream(source="vci", symbols=["VCB"])
        assert hasattr(stream, "ticks")
        assert callable(stream.ticks)
        assert hasattr(stream, "close")
        assert callable(stream.close)
        assert hasattr(stream, "get_current_source")
        assert callable(stream.get_current_source)
        assert hasattr(stream, "is_running")
        assert callable(stream.is_running)

    def test_stream_invalid_source(self):
        """Test Stream raises ValueError for invalid source."""
        with pytest.raises(ValueError, match="Stream source must be one of"):
            Stream(source="invalid_source", symbols=["VCB"])

    def test_stream_no_symbols_raises(self):
        """Test Stream raises ValueError when no symbols provided."""
        with pytest.raises(ValueError, match="At least one symbol"):
            Stream(source="vci", symbols=[])

    @patch("vnbroker.base.BaseAdapter.__init__", return_value=None)
    def test_stream_symbols_uppercased(self, mock_base_init):
        """Test Stream uppercases all symbols."""
        stream = Stream(source="vci", symbols=["vcb", "vnm", "fpt"])
        assert stream.symbols == ["VCB", "VNM", "FPT"]

    @patch("vnbroker.base.BaseAdapter.__init__", return_value=None)
    def test_stream_default_poll_interval(self, mock_base_init):
        """Test Stream default poll interval is 1.0."""
        stream = Stream(source="vci", symbols=["VCB"])
        assert stream.poll_interval == 1.0

    @patch("vnbroker.base.BaseAdapter.__init__", return_value=None)
    def test_stream_custom_poll_interval(self, mock_base_init):
        """Test Stream accepts custom poll interval."""
        stream = Stream(source="vci", symbols=["VCB"], poll_interval=2.5)
        assert stream.poll_interval == 2.5

    @patch("vnbroker.base.BaseAdapter.__init__", return_value=None)
    def test_stream_get_current_source_initially_none(self, mock_base_init):
        """Test get_current_source returns None before streaming."""
        stream = Stream(source="vci", symbols=["VCB"])
        assert stream.get_current_source() is None

    @patch("vnbroker.base.BaseAdapter.__init__", return_value=None)
    def test_stream_is_running_initially_false(self, mock_base_init):
        """Test is_running returns False before streaming."""
        stream = Stream(source="vci", symbols=["VCB"])
        assert stream.is_running() is False


@pytest.mark.unit
@pytest.mark.api
class TestTickData:
    """Test suite for TickData container."""

    def test_tick_data_init(self):
        """Test TickData can be instantiated."""
        tick = TickData(
            symbol="VCB",
            price=88.5,
            volume=1000,
            timestamp="2024-01-01T10:00:00",
        )
        assert tick.symbol == "VCB"
        assert tick.price == 88.5
        assert tick.volume == 1000
        assert tick.timestamp == "2024-01-01T10:00:00"

    def test_tick_data_to_dict(self):
        """Test TickData to_dict returns all fields."""
        tick = TickData(
            symbol="VCB",
            price=88.5,
            volume=1000,
            timestamp="2024-01-01T10:00:00",
            bid_price=88.4,
            ask_price=88.6,
            source="vci",
        )
        d = tick.to_dict()
        assert d["symbol"] == "VCB"
        assert d["price"] == 88.5
        assert d["bid_price"] == 88.4
        assert d["ask_price"] == 88.6
        assert d["source"] == "vci"

    def test_tick_data_repr(self):
        """Test TickData repr contains symbol and price."""
        tick = TickData(symbol="VCB", price=88.5, volume=1000, timestamp="2024-01-01T10:00:00")
        r = repr(tick)
        assert "VCB" in r
        assert "88.5" in r
