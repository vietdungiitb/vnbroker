"""
Custom exceptions for vnbroker library.

This module provides a hierarchy of exceptions with error codes
for better error handling and debugging.
"""

from typing import Optional, Dict, Any


# ============================================================================
# BASE EXCEPTION
# ============================================================================

class vnbrokerError(Exception):
    """Base exception for all vnbroker errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code or "vnbroker_000"
        self.details = details or {}
        super().__init__(self.format_message())

    def format_message(self) -> str:
        msg = f"[{self.error_code}] {self.message}"
        if self.details:
            details_str = ", ".join(
                f"{k}={v}" for k, v in self.details.items()
            )
            msg += f" ({details_str})"
        return msg

    def __str__(self) -> str:
        return self.format_message()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "type": self.__class__.__name__,
        }


# ============================================================================
# PROVIDER ERRORS
# ============================================================================

class ProviderError(vnbrokerError):
    """Base exception for provider-related errors."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if provider:
            details["provider"] = provider

        super().__init__(
            message=message,
            error_code=error_code or "PROVIDER_000",
            details=details,
        )


class UnsupportedProviderError(ProviderError):
    """Raised when a provider is not supported or not found."""

    def __init__(
        self,
        provider: str,
        category: Optional[str] = None,
        available_providers: Optional[list] = None,
    ):
        msg = f"Provider '{provider}' is not supported"
        if category:
            msg += f" for category '{category}'"

        details = {}
        if available_providers:
            details["available_providers"] = available_providers

        super().__init__(
            message=msg,
            provider=provider,
            error_code="PROVIDER_001",
            details=details,
        )


class UnsupportedMethodError(ProviderError):
    """Raised when a method is not supported by the provider."""

    def __init__(
        self,
        provider: str,
        method: str,
        supported_methods: Optional[list] = None,
    ):
        msg = f"Method '{method}' is not supported by provider '{provider}'"

        details = {}
        if supported_methods:
            details["supported_methods"] = supported_methods

        super().__init__(
            message=msg,
            provider=provider,
            error_code="PROVIDER_002",
            details=details,
        )


class ProviderInitializationError(ProviderError):
    """Raised when provider initialization fails."""

    def __init__(
        self,
        provider: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        msg = f"Failed to initialize provider '{provider}': {reason}"

        super().__init__(
            message=msg,
            provider=provider,
            error_code="PROVIDER_003",
            details=details,
        )


# ============================================================================
# DATA ERRORS
# ============================================================================

class DataFetchError(vnbrokerError):
    """Raised when data fetching fails."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        symbol: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if provider:
            details["provider"] = provider
        if symbol:
            details["symbol"] = symbol
        if status_code:
            details["status_code"] = status_code

        super().__init__(
            message=message,
            error_code="DATA_001",
            details=details,
        )


class DataParsingError(vnbrokerError):
    """Raised when data parsing/transformation fails."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        raw_data: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if provider:
            details["provider"] = provider
        if raw_data and len(str(raw_data)) < 200:
            details["raw_data_preview"] = str(raw_data)[:200]

        super().__init__(
            message=message,
            error_code="DATA_002",
            details=details,
        )


class DataValidationError(vnbrokerError):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = value

        super().__init__(
            message=message,
            error_code="DATA_003",
            details=details,
        )


# ============================================================================
# CONFIGURATION ERRORS
# ============================================================================

class ConfigurationError(vnbrokerError):
    """Raised when configuration is invalid or missing."""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if config_key:
            details["config_key"] = config_key

        super().__init__(
            message=message,
            error_code="CONFIG_001",
            details=details,
        )


class MissingAPIKeyError(ConfigurationError):
    """Raised when required API key is missing."""

    def __init__(
        self,
        provider: str,
        env_var: Optional[str] = None,
    ):
        msg = f"API key required for provider '{provider}'"
        if env_var:
            msg += f". Set environment variable '{env_var}' or pass api_key"

        details = {"provider": provider}
        if env_var:
            details["env_var"] = env_var

        super().__init__(
            message=msg,
            config_key="api_key",
            details=details,
        )


# ============================================================================
# NETWORK ERRORS
# ============================================================================

class NetworkError(vnbrokerError):
    """Raised when network request fails."""

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if url:
            details["url"] = url
        if status_code:
            details["status_code"] = status_code

        super().__init__(
            message=message,
            error_code="NETWORK_001",
            details=details,
        )


class RateLimitError(NetworkError):
    """Raised when upstream provider throttles requests."""

    def __init__(
        self,
        provider: str,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        msg = f"Provider '{provider}' temporarily throttled requests"
        if retry_after:
            msg += f". Retry after {retry_after} seconds"

        details = details or {}
        details["provider"] = provider
        if retry_after:
            details["retry_after"] = retry_after

        super().__init__(
            message=msg,
            details=details,
        )


class TimeoutError(NetworkError):
    """Raised when request times out."""

    def __init__(
        self,
        provider: str,
        timeout: float,
        details: Optional[Dict[str, Any]] = None,
    ):
        msg = f"Request to '{provider}' timed out after {timeout}s"

        details = details or {}
        details["provider"] = provider
        details["timeout"] = timeout

        super().__init__(
            message=msg,
            details=details,
        )


# ============================================================================
# DEPRECATION WARNING
# ============================================================================

class vnbrokerDeprecationWarning(UserWarning):
    """Warning for deprecated features."""
    pass


# Backward compatibility alias
DeprecationWarning = vnbrokerDeprecationWarning


# ============================================================================
# ERROR CODE REFERENCE
# ============================================================================

ERROR_CODES = {
    "vnbroker_000": "General vnbroker error",
    "PROVIDER_000": "General provider error",
    "PROVIDER_001": "Unsupported provider",
    "PROVIDER_002": "Unsupported method",
    "PROVIDER_003": "Provider initialization failed",
    "DATA_001": "Data fetch failed",
    "DATA_002": "Data parsing failed",
    "DATA_003": "Data validation failed",
    "CONFIG_001": "Configuration error",
    "NETWORK_001": "Network request failed",
    "NETWORK_002": "Request temporarily throttled by provider",
    "NETWORK_003": "Request timeout",
}


def get_error_description(error_code: str) -> str:
    """Get description for an error code."""
    return ERROR_CODES.get(error_code, "Unknown error code")
