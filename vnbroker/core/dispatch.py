"""
Emergency Fallback Dispatch Module for vnbroker.

This module maps Gateway API endpoints to local explorer implementations
when the SaaS Gateway is unavailable. It provides a limited but functional
fallback using direct connections to data providers (VCI, KBS, TCBS, MSN).

Usage:
    from vnbroker.core.dispatch import local_dispatch_fallback
    result = local_dispatch_fallback("/api/v1/quote/history", {"symbol": "ACB", "start": "2024-01-01"})
"""

import logging
from typing import Dict, Any, Optional, List
import pandas as pd

from vnbroker.core.exceptions import ProviderError, DataFetchError

logger = logging.getLogger(__name__)

# Endpoint to local explorer mapping
# Format: endpoint_path -> (module_path, function_name, required_params)
ENDPOINT_MAPPING = {
    # Quote endpoints
    "/api/v1/quote/history": ("vnbroker.explorer.vci.quote", "history", ["symbol", "start", "end"]),
    "/api/v1/quote/intraday": ("vnbroker.explorer.vci.quote", "intraday", ["symbol"]),
    "/api/v1/quote/price_board": ("vnbroker.explorer.vci.quote", "price_board", ["symbols"]),
    "/api/v1/quote/price_depth": ("vnbroker.explorer.vci.quote", "price_depth", ["symbol"]),
    
    # Company endpoints
    "/api/v1/company/profile": ("vnbroker.explorer.vci.company", "profile", ["symbol"]),
    "/api/v1/company/officers": ("vnbroker.explorer.vci.company", "officers", ["symbol"]),
    "/api/v1/company/shareholders": ("vnbroker.explorer.vci.company", "shareholders", ["symbol"]),
    "/api/v1/company/insider_deals": ("vnbroker.explorer.vci.company", "insider_deals", ["symbol"]),
    "/api/v1/company/dividends": ("vnbroker.explorer.vci.company", "dividends", ["symbol"]),
    "/api/v1/company/events": ("vnbroker.explorer.vci.company", "events", ["symbol"]),
    "/api/v1/company/financial_ratios": ("vnbroker.explorer.vci.company", "financial_ratios", ["symbol"]),
    
    # Finance endpoints
    "/api/v1/finance/income_statement": ("vnbroker.explorer.vci.financial", "income_statement", ["symbol", "period"]),
    "/api/v1/finance/balance_sheet": ("vnbroker.explorer.vci.financial", "balance_sheet", ["symbol", "period"]),
    "/api/v1/finance/cash_flow": ("vnbroker.explorer.vci.financial", "cash_flow", ["symbol", "period"]),
    "/api/v1/finance/ratios": ("vnbroker.explorer.vci.financial", "ratios", ["symbol", "period"]),
    
    # Listing endpoints
    "/api/v1/listing/all_symbols": ("vnbroker.explorer.vci.listing", "all_symbols", []),
    "/api/v1/listing/industries": ("vnbroker.explorer.vci.listing", "industries", []),
    
    # Trading endpoints
    "/api/v1/trading/price_board": ("vnbroker.explorer.vci.trading", "price_board", ["symbols"]),
    
    # News endpoints
    "/api/v1/news/market": ("vnbroker.explorer.vci.news", "market_news", ["limit"]),
    "/api/v1/news/symbol": ("vnbroker.explorer.vci.news", "symbol_news", ["symbol", "limit"]),
}

# Alternative provider mappings (fallback chain)
PROVIDER_FALLBACK_CHAIN = {
    "vci": ["kbs", "tcbs", "msn"],
    "kbs": ["vci", "tcbs", "msn"],
    "tcbs": ["vci", "kbs", "msn"],
    "msn": ["vci", "kbs", "tcbs"],
}

# Default provider for fallback
DEFAULT_FALLBACK_PROVIDER = "vci"


def _import_explorer_function(module_path: str, function_name: str):
    """Dynamically import explorer function."""
    try:
        module = __import__(module_path, fromlist=[function_name])
        return getattr(module, function_name)
    except (ImportError, AttributeError) as e:
        logger.debug(f"Failed to import {function_name} from {module_path}: {e}")
        return None


def _call_with_fallback(
    primary_provider: str,
    module_path: str,
    function_name: str,
    params: Dict[str, Any],
) -> Any:
    """
    Call explorer function with provider fallback chain.
    
    Tries primary provider first, then falls back through chain.
    """
    providers_to_try = [primary_provider] + PROVIDER_FALLBACK_CHAIN.get(primary_provider, [])
    
    last_error = None
    for provider in providers_to_try:
        # Adjust module path for provider
        if provider != "vci":
            adjusted_module = module_path.replace(".vci.", f".{provider}.")
        else:
            adjusted_module = module_path
        
        func = _import_explorer_function(adjusted_module, function_name)
        if func is None:
            continue
            
        try:
            logger.debug(f"Trying fallback provider: {provider} for {function_name}")
            result = func(**params)
            if result is not None and (not isinstance(result, pd.DataFrame) or not result.empty):
                logger.info(f"Fallback successful with provider: {provider}")
                return result
        except Exception as e:
            last_error = e
            logger.debug(f"Fallback provider {provider} failed: {e}")
            continue
    
    # All providers failed
    raise DataFetchError(
        f"All fallback providers failed for {function_name}. Last error: {last_error}",
        provider=primary_provider,
        details={"attempted_providers": providers_to_try, "last_error": str(last_error)}
    )


def local_dispatch_fallback(
    endpoint: str,
    json_data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main entry point for emergency fallback dispatch.
    
    Maps Gateway endpoint to local explorer function and executes with fallback chain.
    
    Args:
        endpoint: Gateway API endpoint (e.g., "/api/v1/quote/history")
        json_data: POST request payload
        params: GET query parameters
        provider: Preferred provider (defaults to VCI)
        
    Returns:
        Standardized response dict with 'data' key containing DataFrame or dict
        
    Raises:
        ProviderError: If endpoint not supported in fallback mode
        DataFetchError: If all fallback providers fail
    """
    # Normalize endpoint
    endpoint = endpoint.rstrip("/")
    if not endpoint.startswith("/api/v1/"):
        endpoint = "/api/v1" + endpoint
    
    # Merge json_data and params
    request_params = {}
    if json_data:
        request_params.update(json_data)
    if params:
        request_params.update(params)
    
    # Get endpoint mapping
    if endpoint not in ENDPOINT_MAPPING:
        supported = list(ENDPOINT_MAPPING.keys())
        raise ProviderError(
            f"Endpoint '{endpoint}' not supported in emergency fallback mode. "
            f"Supported endpoints: {supported}",
            provider="fallback",
            error_code="FALLBACK_001",
            details={"endpoint": endpoint, "supported_endpoints": supported}
        )
    
    module_path, function_name, required_params = ENDPOINT_MAPPING[endpoint]
    provider = provider or DEFAULT_FALLBACK_PROVIDER
    
    # Validate required parameters
    missing_params = [p for p in required_params if p not in request_params]
    if missing_params:
        raise DataFetchError(
            f"Missing required parameters for {endpoint}: {missing_params}",
            provider=provider,
            details={"required": required_params, "provided": list(request_params.keys())}
        )
    
    # Filter only required params for the function
    filtered_params = {k: v for k, v in request_params.items() if k in required_params}
    
    logger.info(f"Emergency fallback: {endpoint} -> {module_path}.{function_name} (provider: {provider})")
    
    try:
        # Execute with fallback chain
        result = _call_with_fallback(provider, module_path, function_name, filtered_params)
        
        # Standardize response format
        if isinstance(result, pd.DataFrame):
            return {
                "data": result.to_dict(orient="records"),
                "columns": list(result.columns),
                "shape": result.shape,
                "source": "emergency_fallback",
                "provider_used": provider,
            }
        elif isinstance(result, dict):
            return {
                "data": result,
                "source": "emergency_fallback",
                "provider_used": provider,
            }
        elif isinstance(result, list):
            return {
                "data": result,
                "source": "emergency_fallback",
                "provider_used": provider,
            }
        else:
            return {
                "data": str(result),
                "source": "emergency_fallback",
                "provider_used": provider,
            }
            
    except Exception as e:
        logger.error(f"Emergency fallback failed for {endpoint}: {e}")
        raise


def get_supported_fallback_endpoints() -> List[str]:
    """Get list of endpoints supported in emergency fallback mode."""
    return list(ENDPOINT_MAPPING.keys())


def is_endpoint_supported_in_fallback(endpoint: str) -> bool:
    """Check if an endpoint is supported in fallback mode."""
    endpoint = endpoint.rstrip("/")
    if not endpoint.startswith("/api/v1/"):
        endpoint = "/api/v1" + endpoint
    return endpoint in ENDPOINT_MAPPING


# For testing and debugging
def test_fallback_endpoint(endpoint: str, **params) -> Dict[str, Any]:
    """Test a fallback endpoint directly (for development)."""
    return local_dispatch_fallback(endpoint, json_data=params)