"""Local execution decorators.

These decorators intentionally act as no-ops to avoid any external tracking
or quota-related side effects in runtime data calls.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def _passthrough_decorator(_provider: str) -> Callable[[F], F]:
    """Return a no-op decorator preserving wrapped function metadata."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def optimize_execution(provider: str) -> Callable[[F], F]:
    """No-op replacement for vnai.optimize_execution."""

    return _passthrough_decorator(provider)


def agg_execution(provider: str) -> Callable[[F], F]:
    """No-op replacement for vnai.agg_execution."""

    return _passthrough_decorator(provider)
