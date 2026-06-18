"""
Unit tests for VCI Quote explorer.

Tests VCI-specific quote data fetching, parsing, and transformations.
"""

import pytest
from vnbroker.explorer.vci.quote import Quote


@pytest.mark.unit
@pytest.mark.explorer
@pytest.mark.vci
class TestVCIQuote:
    """Test suite for VCI Quote explorer."""

    def test_vci_quote_instantiation(self):
        """Test VCI Quote can be instantiated."""
        quote = Quote(symbol='ACB', random_agent=False, show_log=False)
        assert quote is not None
        assert quote.symbol == 'ACB'

    def test_vci_quote_has_history_method(self):
        """Test VCI Quote has history method."""
        quote = Quote(symbol='VCB', random_agent=False, show_log=False)
        assert hasattr(quote, 'history')
        assert callable(quote.history)

    def test_vci_quote_has_intraday_method(self):
        """Test VCI Quote has intraday method."""
        quote = Quote(symbol='TCB', random_agent=False, show_log=False)
        assert hasattr(quote, 'intraday')
        assert callable(quote.intraday)

    def test_vci_quote_symbol_validation(self):
        """Test VCI Quote validates symbol input."""
        # VCI should accept standard Vietnamese stock symbols
        valid_symbols = ['ACB', 'VCB', 'TCB', 'BID']
        for symbol in valid_symbols:
            quote = Quote(
                symbol=symbol,
                random_agent=False,
                show_log=False
            )
            assert quote.symbol == symbol

    def test_adjust_concurrency_increases_on_clean_batch(self):
        """Adaptive concurrency should ramp up when batch has no failures."""
        from vnbroker.core.adaptive_controller import AdaptiveController
        next_value = AdaptiveController.compute(
            current=8,
            batch_size=8,
            success_count=8,
            max_concurrency=24,
            min_concurrency=4,
            step_up=2,
            step_down=3,
            fail_threshold=0.2,
            batch_p95_seconds=0.2,
            p95_high_seconds=1.2,
            p95_low_seconds=0.35,
        )
        assert next_value == 10

    def test_adjust_concurrency_decreases_when_fail_ratio_high(self):
        """Adaptive concurrency should reduce pressure when fail ratio exceeds threshold."""
        from vnbroker.core.adaptive_controller import AdaptiveController
        next_value = AdaptiveController.compute(
            current=12,
            batch_size=10,
            success_count=7,
            max_concurrency=24,
            min_concurrency=4,
            step_up=2,
            step_down=3,
            fail_threshold=0.2,
            batch_p95_seconds=0.4,
            p95_high_seconds=1.2,
            p95_low_seconds=0.35,
        )
        assert next_value == 9

    def test_adjust_concurrency_keeps_value_when_fail_ratio_tolerable(self):
        """Adaptive concurrency should hold when failures are within tolerance."""
        from vnbroker.core.adaptive_controller import AdaptiveController
        next_value = AdaptiveController.compute(
            current=12,
            batch_size=10,
            success_count=8,
            max_concurrency=24,
            min_concurrency=4,
            step_up=2,
            step_down=3,
            fail_threshold=0.2,
            batch_p95_seconds=0.6,
            p95_high_seconds=1.2,
            p95_low_seconds=0.35,
        )
        assert next_value == 12

    def test_adjust_concurrency_decreases_when_p95_too_high(self):
        """Adaptive concurrency should reduce load when p95 latency exceeds threshold."""
        from vnbroker.core.adaptive_controller import AdaptiveController
        next_value = AdaptiveController.compute(
            current=12,
            batch_size=10,
            success_count=10,
            max_concurrency=24,
            min_concurrency=4,
            step_up=2,
            step_down=3,
            fail_threshold=0.2,
            batch_p95_seconds=1.5,
            p95_high_seconds=1.2,
            p95_low_seconds=0.35,
        )
        assert next_value == 9

    def test_adjust_concurrency_holds_when_clean_but_latency_mid_range(self):
        """Adaptive concurrency should hold when clean batch latency is between low/high thresholds."""
        from vnbroker.core.adaptive_controller import AdaptiveController
        next_value = AdaptiveController.compute(
            current=12,
            batch_size=10,
            success_count=10,
            max_concurrency=24,
            min_concurrency=4,
            step_up=2,
            step_down=3,
            fail_threshold=0.2,
            batch_p95_seconds=0.7,
            p95_high_seconds=1.2,
            p95_low_seconds=0.35,
        )
        assert next_value == 12
