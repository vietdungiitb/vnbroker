from __future__ import annotations

from typing import Any


class DNSEBaseError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_code: str | None = None,
        request_id: str | None = None,
        payload: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.request_id = request_id
        self.payload = payload


class DNSEAuthError(DNSEBaseError):
    pass


class DNSEValidationError(DNSEBaseError):
    pass


class DNSERateLimitError(DNSEBaseError):
    pass


class DNSEServerError(DNSEBaseError):
    pass


class DNSETransportError(DNSEBaseError):
    pass


def raise_for_status(
    status_code: int,
    message: str,
    error_code: str | None = None,
    request_id: str | None = None,
    payload: Any | None = None,
) -> None:
    kwargs = {
        "message": message,
        "status_code": status_code,
        "error_code": error_code,
        "request_id": request_id,
        "payload": payload,
    }
    if status_code in (401, 403):
        raise DNSEAuthError(**kwargs)
    if status_code == 429:
        raise DNSERateLimitError(**kwargs)
    if status_code == 400:
        raise DNSEValidationError(**kwargs)
    if status_code >= 500:
        raise DNSEServerError(**kwargs)
    if status_code >= 400:
        raise DNSEBaseError(**kwargs)
