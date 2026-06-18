"""
vnbroker/explorer/dnse/__init__.py

Đăng ký DNSE explorer providers vào ProviderRegistry của vnbroker.
"""

from vnbroker.core.registry import ProviderRegistry
from .quote import DNSEQuote
from .listing import DNSEListing
from .company import DNSECompany
from .finance import DNSEFinance
from .trading import DNSETrading
from .news import DNSENews

# Đăng ký Quote provider
ProviderRegistry.register("quote", "dnse", DNSEQuote)

# Đăng ký Listing provider
ProviderRegistry.register("listing", "dnse", DNSEListing)

# Đăng ký Company provider (fallback - DNSE OpenAPI không hỗ trợ company endpoints)
ProviderRegistry.register("company", "dnse", DNSECompany)

# Đăng ký Finance provider (fallback - DNSE OpenAPI không hỗ trợ financial endpoints)
ProviderRegistry.register("financial", "dnse", DNSEFinance)

# Đăng ký Trading provider (fallback - DNSE OpenAPI không hỗ trợ trading endpoints)
ProviderRegistry.register("trading", "dnse", DNSETrading)

# Đăng ký News provider (fallback - DNSE OpenAPI không hỗ trợ news endpoints)
ProviderRegistry.register("news", "dnse", DNSENews)

__all__ = ["DNSEQuote", "DNSEListing", "DNSECompany", "DNSEFinance", "DNSETrading", "DNSENews"]
