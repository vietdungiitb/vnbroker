"""Tests for WP-2 fixes: PRIMARY_SOURCE_POOLS quote shard + News provider re-instantiation."""

from vnbroker.core.source_router import PRIMARY_SOURCE_POOLS, build_source_order, reset_router_state
from vnbroker.common.data import News


def test_quote_pool_has_two_providers():
    """PRIMARY_SOURCE_POOLS['quote'] should have 2 providers for hash-shard distribution."""
    assert len(PRIMARY_SOURCE_POOLS["quote"]) == 2
    assert "vci" in PRIMARY_SOURCE_POOLS["quote"]
    assert "kbs" in PRIMARY_SOURCE_POOLS["quote"]


def test_hash_shard_distributes():
    """Different symbols should map to different providers via hash-shard."""
    reset_router_state()
    # Collect the first (primary) provider for each symbol across many symbols
    symbol_to_primary = {}
    for i in range(20):
        symbol = f"SYM{i:03d}"
        order = build_source_order("quote", symbol)
        if order:
            symbol_to_primary[symbol] = order[0]

    # With 2 providers in the pool, we should see both providers used as primary
    unique_primaries = set(symbol_to_primary.values())
    assert len(unique_primaries) >= 2, (
        f"Hash-shard should distribute across both providers, "
        f"but only saw: {unique_primaries}"
    )


def test_news_provider_not_reinstantiated():
    """News provider should not be re-instantiated when symbol is unchanged."""
    news = News(symbol="ACB", source="VCI")
    original_provider = news.data_source

    # Call _update_data_source with the same symbol — should NOT re-instantiate
    news._update_data_source("ACB")
    assert news.data_source is original_provider, (
        "Provider was re-instantiated even though symbol did not change"
    )

    # Call with None — should NOT re-instantiate
    news._update_data_source(None)
    assert news.data_source is original_provider, (
        "Provider was re-instantiated when symbol was None"
    )

    # Call with a different symbol — SHOULD re-instantiate
    news._update_data_source("VNM")
    assert news.data_source is not original_provider, (
        "Provider should be re-instantiated when symbol changes"
    )
    assert news.symbol == "VNM"
