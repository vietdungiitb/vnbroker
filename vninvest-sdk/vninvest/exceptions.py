"""
Custom exceptions for Vninvest SDK.
"""

from __future__ import annotations

from typing import Any


class VninvestError(Exception):
    """Base exception for all Vninvest SDK errors."""

    def __init__(
        self,
        message: str,
        code: str = "VNINVEST_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 500,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class ConfigurationError(VninvestError):
    """Raised when SDK configuration is invalid."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, code="CONFIGURATION_ERROR", details=details, status_code=500)


class AuthenticationError(VninvestError):
    """Raised when API key authentication fails."""

    def __init__(self, message: str = "Invalid or missing API key", details: dict[str, Any] | None = None):
        super().__init__(message, code="AUTHENTICATION_ERROR", details=details, status_code=401)


class AuthorizationError(VninvestError):
    """Raised when tenant is not authorized for an operation."""

    def __init__(self, message: str = "Insufficient permissions", details: dict[str, Any] | None = None):
        super().__init__(message, code="AUTHORIZATION_ERROR", details=details, status_code=403)


class QuotaExceededError(VninvestError):
    """Raised when tenant exceeds their quota limits."""

    def __init__(
        self,
        message: str = "Quota exceeded",
        limit_type: str = "daily_calls",
        limit_value: int = 0,
        current_value: int = 0,
        reset_at: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        details.update(
            {
                "limit_type": limit_type,
                "limit_value": limit_value,
                "current_value": current_value,
                "reset_at": reset_at,
            }
        )
        super().__init__(message, code="QUOTA_EXCEEDED", details=details, status_code=429)


class RateLimitError(VninvestError):
    """Raised when request rate exceeds allowed limit."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after_seconds: int = 60,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        details["retry_after_seconds"] = retry_after_seconds
        super().__init__(message, code="RATE_LIMIT_EXCEEDED", details=details, status_code=429)


class ProviderError(VninvestError):
    """Raised when upstream data provider returns an error."""

    def __init__(
        self,
        message: str = "Data provider error",
        provider: str = "unknown",
        original_error: Exception | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        details["provider"] = provider
        if original_error:
            details["original_error"] = str(original_error)
            details["original_error_type"] = type(original_error).__name__
        super().__init__(message, code="PROVIDER_ERROR", details=details, status_code=502)


class CacheError(VninvestError):
    """Raised when cache operations fail."""

    def __init__(
        self,
        message: str = "Cache operation failed",
        operation: str = "unknown",
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        details["operation"] = operation
        super().__init__(message, code="CACHE_ERROR", details=details, status_code=500)


class StreamingError(VninvestError):
    """Raised when WebSocket streaming encounters an error."""

    def __init__(
        self,
        message: str = "Streaming error",
        stream_id: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if stream_id:
            details["stream_id"] = stream_id
        super().__init__(message, code="STREAMING_ERROR", details=details, status_code=500)


class TenantNotFoundError(VninvestError):
    """Raised when tenant cannot be resolved."""

    def __init__(self, message: str = "Tenant not found", details: dict[str, Any] | None = None):
        super().__init__(message, code="TENANT_NOT_FOUND", details=details, status_code=404)


class TenantSuspendedError(VninvestError):
    """Raised when tenant account is suspended."""

    def __init__(self, message: str = "Tenant account suspended", details: dict[str, Any] | None = None):
        super().__init__(message, code="TENANT_SUSPENDED", details=details, status_code=403)


class SymbolNotAllowedError(VninvestError):
    """Raised when tenant tries to access unauthorized symbols."""

    def __init__(
        self,
        message: str = "Symbol not allowed for this tenant",
        symbol: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if symbol:
            details["symbol"] = symbol
        super().__init__(message, code="SYMBOL_NOT_ALLOWED", details=details, status_code=403)


class ValidationError(VninvestError):
    """Raised when request validation fails."""

    def __init__(
        self,
        message: str = "Validation error",
        field_errors: dict[str, str] | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if field_errors:
            details["field_errors"] = field_errors
        super().__init__(message, code="VALIDATION_ERROR", details=details, status_code=400)


class ScopeDeniedError(VninvestError):
    """Raised when token lacks required scope for an operation."""

    def __init__(self, required_scope: str, details: dict[str, Any] | None = None):
        details = details or {}
        details["required_scope"] = required_scope
        super().__init__(
            f"Token missing required scope: {required_scope}",
            code="SCOPE_DENIED",
            details=details,
            status_code=403,
        )
