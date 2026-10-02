"""
vnbroker.broker.ssi._transport — HTTP client native cho SSI FastConnect v3.

Dùng requests.Session trực tiếp (cấm core/utils/client — rule broker lane).
Rate-limit native 10 req/s default + retry tenacity cho lỗi mạng.
KHÔNG log body/headers/token/signature ở bất kỳ level nào.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

import requests
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerError,
    BrokerNetworkError,
    BrokerRateLimitError,
)
from vnbroker.broker.ssi import _paths
from vnbroker.broker.ssi._signing import rsa_sign_hex

_logger = logging.getLogger("vnbroker.broker.ssi.transport")

_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS"})

_HEADER_SIGNATURE = "X-Signature"


class SSIHttpClient:
    """
    HTTP client có auth Bearer + rate-limit + retry cho SSI REST.

    Args:
        base_url: vd https://api.ssi.com.vn (đã rstrip "/").
        timeout: giây cho mỗi request.
        rate_limit_rps: 0 = không giới hạn.
        max_retries: số attempt tối đa cho lỗi mạng (timeout/connection).
        user_agent: vd "vnbroker/3.1.0".
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = _paths.DEFAULT_TIMEOUT_SECONDS,
        rate_limit_rps: float = _paths.DEFAULT_RATE_LIMIT_RPS,
        max_retries: int = _paths.DEFAULT_MAX_RETRIES,
        user_agent: str = "vnbroker",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._min_interval = (1.0 / rate_limit_rps) if rate_limit_rps > 0 else 0.0
        self._max_retries = max(1, max_retries)
        self._lock = threading.Lock()
        self._last_ts = 0.0
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": user_agent,
            }
        )

    # ── Auth header ──────────────────────────────────────────────────────

    def set_token(self, token: str) -> None:
        """Gắn Bearer token cho mọi request tiếp theo. KHÔNG log token."""
        self._session.headers["Authorization"] = f"Bearer {token}"

    def clear_token(self) -> None:
        """Xóa Bearer token (revoke/logout)."""
        self._session.headers.pop("Authorization", None)

    # ── Public request API ───────────────────────────────────────────────

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        raw_content: Optional[bytes] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Gửi request đã Bearer-auth. Trả JSON đã parse (204 → {}).

        Raises:
            BrokerAuthError: 401/403.
            BrokerRateLimitError: 429 (retry_after giữ trong message).
            BrokerNetworkError: timeout/connection sau hết retry.
            BrokerError: 4xx/5xx khác hoặc body không phải JSON.
        """
        url = self._base_url + path
        # Retry chỉ an toàn cho method IDEMPOTENT.
        #
        # Lý do (P0-1): `requests.exceptions.ConnectionError` cũng xảy ra khi
        # server ĐÃ nhận xong lệnh nhưng response bị mất trên đường về. Retry
        # một POST không idempotent sẽ gửi lại lệnh trùng — ở đường tiền thật
        # nghĩa là double-submit. Đã tái hiện: 1 lời gọi → 5 POST thật.
        #
        # Với POST ta KHÔNG retry: ném lỗi để caller tra cứu bằng
        # `clientRequestId` rồi quyết định đặt lại hay không. Đây là hành vi
        # an toàn: "chắc chắn không đặt" tốt hơn "chắc chắn không đặt trùng".
        idempotent = method.upper() in _IDEMPOTENT_METHODS
        attempts = self._max_retries if idempotent else 1
        retryer = Retrying(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=0.5, max=8.0),
            retry=retry_if_exception_type(
                (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
            ),
            reraise=True,
        )
        try:
            resp: requests.Response = retryer(
                self._do_request,
                url,
                method,
                params,
                json_body,
                raw_content,
                extra_headers,
            )
        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
        ) as exc:
            if not idempotent:
                raise BrokerNetworkError(
                    message=(
                        f"Lỗi mạng SSI ({type(exc).__name__}) trên "
                        f"{method.upper()} — KHÔNG retry tự động vì method "
                        f"không idempotent: server có thể đã nhận lệnh. "
                        f"Tra cứu bằng clientRequestId trước khi đặt lại."
                    ),
                    code="NETWORK_ERROR_NON_IDEMPOTENT",
                    http_status=0,
                ) from exc
            raise BrokerNetworkError(
                message=f"Lỗi mạng SSI ({type(exc).__name__}) sau {self._max_retries} attempt.",
                code="NETWORK_ERROR",
                http_status=0,
            ) from exc
        return self._handle_response(resp, method, path)

    def request_signed(
        self,
        method: str,
        path: str,
        body_str: str,
        private_key: str,
    ) -> Any:
        """
        Gửi write đã ký RSA: body raw bytes + header X-Signature.

        Args:
            body_str: chuỗi JSON đúng bytes sẽ gửi (chữ ký bao phủ toàn bộ).
            private_key: base64-XML RSA key (rỗng → BrokerValidationError từ signing).
        """
        signature = rsa_sign_hex(body_str, private_key)
        return self.request(
            method,
            path,
            raw_content=body_str.encode("utf-8"),
            extra_headers={_HEADER_SIGNATURE: signature},
        )

    def close(self) -> None:
        """Đóng session."""
        self._session.close()

    # ── Internals ────────────────────────────────────────────────────────

    def _throttle(self) -> None:
        """Rate-limit: ngủ nếu request trước chưa đủ min_interval."""
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_ts)
            if wait > 0:
                time.sleep(wait)
                self._last_ts = time.monotonic()
            else:
                self._last_ts = now

    def _do_request(
        self,
        url: str,
        method: str,
        params: Optional[Dict[str, Any]],
        json_body: Optional[Dict[str, Any]],
        raw_content: Optional[bytes],
        extra_headers: Optional[Dict[str, str]],
    ) -> requests.Response:
        self._throttle()
        return self._session.request(
            method,
            url,
            params=params,
            json=json_body,
            data=raw_content,
            headers=extra_headers,
            timeout=self._timeout,
        )

    def _handle_response(self, resp: requests.Response, method: str, path: str) -> Any:
        status = resp.status_code
        _logger.debug("SSI %s %s → %d", method, path, status)

        if status == 204:
            return {}
        if status in (401, 403):
            body = _safe_json(resp)
            raise BrokerAuthError(
                message=_body_message(body, f"SSI auth thất bại (HTTP {status})."),
                code=str(_body_code(body, status)),
                http_status=status,
            )
        if status == 429:
            retry_after: Optional[float] = None
            raw = resp.headers.get("Retry-After")
            try:
                retry_after = float(raw) if raw is not None else None
            except (ValueError, TypeError):
                retry_after = None
            suffix = f" Thử lại sau {retry_after}s." if retry_after is not None else ""
            raise BrokerRateLimitError(
                message=f"SSI rate limit (HTTP 429).{suffix}",
                code="RATE_LIMITED",
                http_status=429,
            )
        if status >= 400:
            body = _safe_json(resp)
            raise BrokerError(
                message=_body_message(body, f"SSI API lỗi (HTTP {status})."),
                code=str(_body_code(body, status)),
                http_status=status,
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise BrokerError(
                message="SSI trả body không phải JSON.",
                code="BAD_RESPONSE",
                http_status=status,
            ) from exc


def _safe_json(resp: requests.Response) -> Optional[Dict[str, Any]]:
    try:
        data = resp.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _body_message(body: Optional[Dict[str, Any]], fallback: str) -> str:
    if not body:
        return fallback
    for key in ("msg", "message", "error"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _body_code(body: Optional[Dict[str, Any]], status: int) -> Any:
    if body:
        for key in ("code", "errorCode"):
            if body.get(key) is not None:
                return body[key]
    return status
