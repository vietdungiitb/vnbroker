"""
vnbroker.broker.vndirect — VNDirect Securities Broker Integration.

VNDirect OpenAPI wrapper for trading, account management, and market data.

Usage:
    from vnbroker.broker.vndirect import VNDirectBrokerClient

    client = VNDirectBrokerClient(api_key="your_api_key")
    client.authenticate()
    
    # Account operations
    balance = client.get_balance("123456")
    holdings = client.get_holdings("123456")
    
    # Trading
    client.enable_write()
    order = client.place_order(
        account_no="123456",
        symbol="VCB",
        side="BUY",
        order_type="LO",
        quantity=100,
        price=85000
    )
    
    # Market data
    snapshot = client.get_market_snapshot()
    intraday = client.get_intraday("VCB")
"""

from vnbroker.broker.vndirect.client import VNDirectBrokerClient

__all__ = ["VNDirectBrokerClient"]