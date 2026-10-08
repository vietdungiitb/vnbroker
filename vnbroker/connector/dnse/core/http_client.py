from __future__ import annotations

import json
import time
from urllib.parse import urlencode

import requests

from .config import DNSEConfig
from .errors import DNSETransportError, raise_for_status
from .signature import build_signature_header


class DNSEHttpClient:
    def __init__(self, config: DNSEConfig):
        self._config = config

    def request(
        self,
        method: str,
        path: str,
        query: dict | None = None,
        body: dict | None = None,
        headers: dict | None = None,
        dry_run: bool = False,
    ) -> tuple[int | None, dict | list | str | None]:
        query = query or None
        url = f"{self._config.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"

        date_value, signature_header = build_signature_header(
            api_key=self._config.api_key,
            api_secret=self._config.api_secret,
            method=method,
            path=path,
            algorithm=self._config.algorithm,
            hmac_nonce_enabled=self._config.hmac_nonce_enabled,
            date_header_name="X-Aux-Date",
        )

        req_headers = {
            "X-Aux-Date": date_value,
            "X-Signature": signature_header,
            "x-api-key": self._config.api_key,
            "version": self._config.api_version,
        }
        if body is not None:
            req_headers["Content-Type"] = "application/json"
        if headers:
            req_headers.update(headers)

        # The dry-run envelope is what a human reads to verify a call. It must
        # never be a credential dump.
        #
        # It used to mask exactly one header ("trading-token") via a hardcoded
        # check, so `X-Signature` and `x-api-key` - both transmitted on every
        # single request - were printed verbatim. The provider's own SDK is
        # worse: it prints the entire header dict.
        #
        # Deriving the mask from Redactor instead of a hand-written list means a
        # newly added header is covered the day it is added.
        from vnbroker.broker.security.redaction import Redactor

        masked_headers = Redactor.redact_headers(req_headers)

        if dry_run:
            return None, {
                "url": Redactor.redact_url(url),
                "method": method,
                "query": Redactor.redact_dict(query) if query else {},
                "headers": masked_headers,
                "body": Redactor.redact_dict(body) if isinstance(body, dict) else body,
            }

        started = time.perf_counter()
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=req_headers,
                data=json.dumps(body) if body is not None else None,
                timeout=self._config.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise DNSETransportError(str(exc)) from exc
        finally:
            _ = time.perf_counter() - started

        text = response.text or ""
        parsed = None
        if text:
            try:
                parsed = response.json()
            except ValueError:
                parsed = text

        if response.status_code >= 400:
            message = text or f"HTTP {response.status_code}"
            error_code = None
            request_id = response.headers.get("X-Request-ID")
            if isinstance(parsed, dict):
                error_code = str(parsed.get("code") or parsed.get("errorCode") or "") or None
                message = str(parsed.get("message") or parsed.get("error") or message)
            raise_for_status(
                status_code=response.status_code,
                message=message,
                error_code=error_code,
                request_id=request_id,
                payload=parsed,
            )

        return response.status_code, parsed
