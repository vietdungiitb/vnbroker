"""
vnbroker/core/unified_registry.py

Unified Registry for both Data Providers and Broker Clients.

Provides a single entry point to discover and access all available
data providers (explorer/connector) and broker clients (TCBS, SSI, VNDirect).
"""

from __future__ import annotations

from typing import Dict, List, Type, Any
from logging import getLogger

from vnbroker.core.registry import ProviderRegistry
from vnbroker.broker.registry import BrokerRegistry

logger = getLogger(__name__)


class UnifiedRegistry:
    """
    Unified registry combining ProviderRegistry and BrokerRegistry.
    
    Provides a single interface to discover and access:
    - Data providers (quote, company, financial, listing, trading, news, screener, etc.)
    - Broker clients (tcbs, ssi, vndirect, etc.)
    
    Usage:
        >>> from vnbroker.core.unified_registry import UnifiedRegistry
        >>> UnifiedRegistry.list_providers()
        >>> UnifiedRegistry.list_brokers()
        >>> UnifiedRegistry.get_provider('quote', 'vci')
        >>> UnifiedRegistry.get_broker('ssi')
    """
    
    @classmethod
    def list_providers(cls) -> Dict[str, List[str]]:
        """
        List all available data providers grouped by type.
        
        Returns:
            Dict[str, List[str]]: {provider_type: [source_names]}
        """
        return ProviderRegistry.list_all()
    
    @classmethod
    def list_brokers(cls) -> List[str]:
        """
        List all available broker clients.
        
        Returns:
            List[str]: List of broker names
        """
        return BrokerRegistry.list_providers()
    
    @classmethod
    def list_all(cls) -> Dict[str, Any]:
        """
        List everything: providers and brokers.
        
        Returns:
            Dict with 'providers' and 'brokers' keys
        """
        return {
            "providers": cls.list_providers(),
            "brokers": cls.list_brokers(),
        }
    
    @classmethod
    def get_provider(cls, provider_type: str, source_name: str) -> Type:
        """
        Get a data provider class.
        
        Args:
            provider_type: Type of provider (quote, company, financial, etc.)
            source_name: Source name (vci, tcbs, msn, kbs, etc.)
            
        Returns:
            Provider class
        """
        return ProviderRegistry.get(provider_type, source_name)
    
    @classmethod
    def get_broker(cls, broker_name: str) -> Type:
        """
        Get a broker client class.
        
        Args:
            broker_name: Broker name (tcbs, ssi, vndirect, etc.)
            
        Returns:
            Broker client class
        """
        return BrokerRegistry.get(broker_name)
    
    @classmethod
    def is_provider_registered(cls, provider_type: str, source_name: str) -> bool:
        """Check if a data provider is registered."""
        return ProviderRegistry.is_registered(provider_type, source_name)
    
    @classmethod
    def is_broker_registered(cls, broker_name: str) -> bool:
        """Check if a broker client is registered."""
        try:
            BrokerRegistry.get(broker_name)
            return True
        except KeyError:
            return False
    
    @classmethod
    def get_provider_sources(cls, provider_type: str) -> List[str]:
        """Get available sources for a provider type."""
        return ProviderRegistry.list_available(provider_type)
    
    @classmethod
    def debug_info(cls) -> str:
        """
        Get comprehensive debug info about all registered components.
        
        Returns:
            str: Formatted debug information
        """
        info = []
        info.append("=" * 70)
        info.append("UNIFIED REGISTRY DEBUG INFO")
        info.append("=" * 70)
        
        # Providers
        info.append("\n📊 DATA PROVIDERS")
        info.append("-" * 70)
        providers = cls.list_providers()
        if not providers:
            info.append("  (No providers registered)")
        else:
            for provider_type in sorted(providers.keys()):
                sources = providers[provider_type]
                info.append(f"\n  [{provider_type}]")
                for source in sources:
                    provider_class = ProviderRegistry.get(provider_type, source)
                    info.append(
                        f"    • {source:12} -> "
                        f"{provider_class.__module__}.{provider_class.__name__}"
                    )
        
        # Brokers
        info.append("\n\n🏦 BROKER CLIENTS")
        info.append("-" * 70)
        brokers = cls.list_brokers()
        if not brokers:
            info.append("  (No brokers registered)")
        else:
            for broker in sorted(brokers):
                broker_class = BrokerRegistry.get(broker)
                info.append(
                    f"  • {broker:12} -> "
                    f"{broker_class.__module__}.{broker_class.__name__}"
                )
        
        info.append("\n" + "=" * 70)
        return "\n".join(info)
    
    @classmethod
    def print_debug_info(cls) -> None:
        """Print debug info to stdout."""
        print(cls.debug_info())


# Convenience functions
def list_providers() -> Dict[str, List[str]]:
    """List all available data providers."""
    return UnifiedRegistry.list_providers()


def list_brokers() -> List[str]:
    """List all available broker clients."""
    return UnifiedRegistry.list_brokers()


def list_all() -> Dict[str, Any]:
    """List everything: providers and brokers."""
    return UnifiedRegistry.list_all()


def get_provider(provider_type: str, source_name: str) -> Type:
    """Get a data provider class."""
    return UnifiedRegistry.get_provider(provider_type, source_name)


def get_broker(broker_name: str) -> Type:
    """Get a broker client class."""
    return UnifiedRegistry.get_broker(broker_name)


def debug_info() -> str:
    """Get debug info."""
    return UnifiedRegistry.debug_info()


def print_debug_info() -> None:
    """Print debug info."""
    UnifiedRegistry.print_debug_info()