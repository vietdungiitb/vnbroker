from __future__ import annotations

import json
import time
from urllib.parse import urlencode

import requests

from .config import DNSEConfig
from .errors import DNSETransportError, raise_for_status
from .signature import build_signature_header

#: HTTP verbs that change server state. GET/HEAD/OPTIONS never do.
WRITE_VERBS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Paths that write verbs are allowed on without an explicit opt-in.
#:
#: `send_email_otp` is how a caller *authenticates*. Gating it would mean the
#: gate blocks the login flow itself, so the "safe" configuration would be the
#: one that cannot log in. Owner decision 2026-10-08, recorded in
#: `HANDOFF_DNSE_ROUND2_20261009.md` §1.1.
#:
#: Note what is NOT here: `/registration/trading-token`. Issuing a trading
#: token is the step that authorises `post_order`, so it is gated like any
#: other write.
UNGATED_POST_PATHS = frozenset({"/registration/send-email-otp"})


class DNSEHttpClient:
    def __init__(self, config: DNSEConfig, write_enabled: bool = False):
        self._config = config
        # The P0 write gate. It lives here, at the single choke point every
        # request passes through, rather than on each calling method:
        #
        #   - `Trade._require_write` covers `Trade`'s 10 money methods, but
        #     `Trade.as_openapi_client()` is public and returns a `DNSEClient`,
        #     which had no gate at all. Measured: 6 real write requests
        #     (POST /accounts/orders, PUT, DELETE, PATCH, POST /positions/close,
        #     POST /registration/trading-token) with the gate off.
        #   - adding a guard per method reproduces that bug: one endpoint added
        #     is one hole. Deciding from the verb cannot be forgotten, because
        #     there is nothing to remember.
        self._write_enabled = write_enabled

    def enable_write(self, enabled: bool = True) -> None:
        """Allow (or forbid) state-changing requests.

        Off by default. Placing, editing, cancelling an order or issuing a
        trading token must be a deliberate act, not a side effect of a typo.
        """
        self._write_enabled = enabled

    def _require_write(self, method: str, path: str) -> None:
        verb = str(method).upper()
        if verb not in WRITE_VERBS or path in UNGATED_POST_PATHS:
            return
        if self._write_enabled:
            return
        from vnbroker.broker.exceptions import BrokerPermissionError

        raise BrokerPermissionError(
            message=(
                f"{verb} {path} changes server state and is not enabled. "
                f"Call enable_write() first."
            ),
            code="WRITE_NOT_ENABLED",
        )

    def request(
        self,
        method: str,
        path: str,
        query: dict | None = None,
        body: dict | None = None,
        headers: dict | None = None,
        dry_run: bool = False,
    ) -> tuple[int | None, dict | list | str | None]:
        # A dry run sends nothing, so it needs no permission: the envelope is
        # how a human verifies a payload before committing to it. Gating that
        # would make inspection the risky act and execution the safe one.
        if not dry_run:
            self._require_write(method, path)

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
