"""
vnbroker.broker — Broker lane package.

Tách hoàn toàn khỏi provider/explorer lane.
Entrypoint: TCBSBrokerClient hoặc get_broker() từ vnbroker.api.broker.
"""
from vnbroker.broker.registry import BrokerRegistry

__all__ = ["BrokerRegistry"]
