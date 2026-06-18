"""
vnbroker.broker.ssi — SSI Securities Broker Integration.

SSI FastConnect API wrapper for trading, account management, and market data.

Usage:
    from vnbroker.broker.ssi import SSIBrokerClient

    client = SSIBrokerClient(
        consumer_id="your_consumer_id",
        consumer_secret="your_consumer_secret"
    )
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

from vnbroker.broker.ssi.client import SSIBrokerClient

__all__ = ["SSIBrokerClient"]