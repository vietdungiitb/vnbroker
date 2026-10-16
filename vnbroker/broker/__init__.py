"""
Broker package for vnbroker.

This module provides the broker lane for authenticated trading operations,
separate from the public provider/explorer lane.

Exports:
- TCBSBrokerClient: Main broker client for TCBS (iFlash OpenAPI v1.0.0)
- SSIBrokerClient: Main broker client for SSI (native FastConnect v3)
- BrokerRegistry: Registry for broker providers
- BrokerSession: Session state machine for auth lifecycle
- capabilities: Describe a lane's usable surface without credentials
"""

from vnbroker.broker.base import BaseBrokerClient
from vnbroker.broker.capabilities import capabilities
from vnbroker.broker.registry import BrokerRegistry
from vnbroker.broker.session import BrokerSession, SessionState

__all__ = [
    "BaseBrokerClient",
    "BrokerRegistry",
    "BrokerSession",
    "SessionState",
    "capabilities",
]

# Lazy import for TCBS broker client to avoid circular imports
def get_tcbs_broker_client():
    from vnbroker.broker.tcbs.client import TCBSBrokerClient
    if not BrokerRegistry.is_registered("tcbs"):
        BrokerRegistry.register("tcbs", TCBSBrokerClient)
    return TCBSBrokerClient


__all__.append("get_tcbs_broker_client")

# Lazy import for SSI broker client to avoid circular imports
def get_ssi_broker_client():
    from vnbroker.broker.ssi.client import SSIBrokerClient
    if not BrokerRegistry.is_registered("ssi"):
        BrokerRegistry.register("ssi", SSIBrokerClient)
    return SSIBrokerClient


__all__.append("get_ssi_broker_client")

# Auto-register standard broker providers
try:
    from vnbroker.broker.tcbs.client import TCBSBrokerClient
    if not BrokerRegistry.is_registered("tcbs"):
        BrokerRegistry.register("tcbs", TCBSBrokerClient)
except Exception:
    pass

try:
    from vnbroker.broker.ssi.client import SSIBrokerClient
    if not BrokerRegistry.is_registered("ssi"):
        BrokerRegistry.register("ssi", SSIBrokerClient)
except Exception:
    pass