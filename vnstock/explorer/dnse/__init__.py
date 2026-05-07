"""
vnstock/explorer/dnse/__init__.py

Đăng ký DNSE explorer providers vào ProviderRegistry của vnstock.
"""

from vnstock.core.registry import ProviderRegistry
from .quote import DNSEQuote
from .listing import DNSEListing

# Đăng ký Quote provider
ProviderRegistry.register("quote", "dnse", DNSEQuote)

# Đăng ký Listing provider
ProviderRegistry.register("listing", "dnse", DNSEListing)

__all__ = ["DNSEQuote", "DNSEListing"]
