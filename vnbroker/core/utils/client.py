"""
API client utilities for vnbroker data sources.

This module provides utilities to send requests to vnbroker data sources,
supporting multiple modes of sending (direct, via proxy) and multiple proxy
selection modes (try, rotate, random, single).

Functions:
- send_request: interface for all modes of sending requests
- send_request_direct: send request directly
- send_proxy_request: send request via standard proxy
"""

import requests
import random
import math
from typing import Dict, Any, Optional, Union, List
from enum import Enum
from urllib.parse import urlsplit, urlunsplit
from pydantic import BaseModel
from vnbroker.core.exceptions import (
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderNotFoundError,
    RateLimitError,
)
from vnbroker.core.utils.logger import get_logger
from vnbroker.core.utils.proxy_manager import proxy_manager
from vnbroker.core.utils.rate_limiter import TokenBucketRateLimiter

# Initialize logger for module
logger = get_logger(__name__)

# Module-level rate limiter (disabled by default, opt-in via configure_rate_limiter)
_rate_limiter: Optional[TokenBucketRateLimiter] = None


def configure_rate_limiter(rate: float, capacity: Optional[float] = None) -> None:
    """
    Enable and configure the client-side rate limiter.

    Args:
        rate: Tokens added per second
        capacity: Bucket capacity (default: rate)
    """
    global _rate_limiter
    _rate_limiter = TokenBucketRateLimiter(rate=rate, capacity=capacity)
    logger.info(f"Rate limiter enabled: {rate} tokens/sec, capacity={capacity or rate}")


def get_rate_limiter() -> Optional[TokenBucketRateLimiter]:
    """Get the current rate limiter instance (None if disabled)."""
    return _rate_limiter


def _url_without_query(url: str) -> str:
    """URL bỏ query string — dùng khi GHI LOG.

    Client HMAC (DNSE, KBS) ký request bằng query string kiểu
    ``?api_key=…&signature=…``, nên URL thô **là** credential. Regex ở tầng
    logger không phải lưới an toàn: nó bắt ``key=value`` nhưng bỏ sót
    ``signature=…`` khi thứ tự tham số đảo (đo 2026-10-10). Bỏ query ngay tại
    nguồn thì không còn gì để lọt.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if not parts.query:
        return url
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", parts.fragment))


def parse_retry_after(headers: Any) -> Optional[float]:
    """Đọc header ``Retry-After`` (RFC 9110 §10.2.4) thành số giây.

    ⚠ **Chỉ đọc `Retry-After`, cố ý KHÔNG đọc `X-RateLimit-*`.** Đo ở `4cd0f2d`:
    `git grep -n 'X-RateLimit' 4cd0f2d` → **0** kết quả, và khảo sát provider của
    chính repo (`REPORT_TIER1_EXPLORER_SURVEY.md`) ghi "Đọc header `X-RateLimit-*`
    | **0** | Không provider nào công bố giới hạn". Đọc một header không tồn tại
    là **bịa đặc tả** — code trông thông minh nhưng không bao giờ chạy.

    Chỉ hỗ trợ dạng ``<số giây>``. Dạng ``HTTP-date`` (RFC đủ cho cả hai) **không**
    cài parser: không provider nào trong repo gửi dạng đó, thêm parser là bịa
    nhu cầu (nợ N10). Giá trị không parse được ⇒ trả ``None`` ⇒ coi như server
    **không nói gì** ⇒ cooldown rơi về suy đoán lũy thừa. ``None`` nghĩa là
    "không có thông tin", KHÔNG phải "chờ 0 giây".

    Args:
        headers: Mapping header của response (thường là ``CaseInsensitiveDict``).

    Returns:
        Số giây server bảo chờ, hoặc ``None`` nếu thiếu / không phải số.
    """
    if not headers:
        return None
    try:
        raw = headers.get("Retry-After")
    except AttributeError:  # object không phải mapping
        return None
    if raw is None:
        return None
    try:
        seconds = float(str(raw).strip())
    except (TypeError, ValueError):
        return None  # HTTP-date hoặc rác -> coi như không có thông tin
    if not math.isfinite(seconds) or seconds < 0:
        return None
    return seconds


# Proxy configuration model for use across the project
class ProxyConfig(BaseModel):
    """
    Configuration for proxy usage in API requests.
    Use for classes/modules that need to pass proxy settings.
    """
    proxy_list: Optional[List[str]] = None
    proxy_mode: 'ProxyMode' = 'try'
    request_mode: 'RequestMode' = 'direct'


logger = get_logger(__name__)


class ProxyMode(Enum):
    """
    Proxy usage modes for sending requests:
    - TRY: Try each proxy sequentially until successful
    - ROTATE: Rotate proxy after each call
    - RANDOM: Select random proxy for each call
    - SINGLE: Always use first proxy
    - AUTO: Auto-fetch proxies if none provided
    """
    TRY = "try"
    ROTATE = "rotate"
    RANDOM = "random"
    SINGLE = "single"
    AUTO = "auto"


class RequestMode(Enum):
    """
    Request sending modes:
    - DIRECT: Send directly without proxy
    - PROXY: Send via standard proxy
    """
    DIRECT = "direct"
    PROXY = "proxy"


# Global variable to track current proxy index for ROTATE mode
_current_proxy_index = 0


def _get_thread_session() -> requests.Session:
    """Get shared session from connection pool.

    Despite the name, this is ONE session shared by every thread. It was
    measured, not assumed: `requests` 2.33.1 guards its cookie jar with
    `RequestsCookieJar._cookies_lock`, an `RLock` taken by `set_cookie` and
    by `extract_cookies`, and an A/B run over 8 threads x 200 unique cookies
    recorded 1600/1600 cookies with zero loss. Do NOT "fix" this into
    per-thread sessions — that would trade a measured-safe shared session for
    a real cost (a fresh connection pool per thread).
    """
    from vnbroker.core.utils.connection_pool import ConnectionPool
    return ConnectionPool.get_instance().get_session()


def build_proxy_dict(proxy_url: str) -> Dict[str, str]:
    """
    Convert proxy URL to dict format for requests library.
    
    Args:
        proxy_url (str): URL of the proxy
        
    Returns:
        Dict[str, str]: Proxy configuration dict for requests
    """
    return {"http": proxy_url, "https": proxy_url}

def get_proxy_by_mode(proxy_list: List[str], mode: ProxyMode) -> str:
    """
    Get proxy from the list by selected mode.
    
    Args:
        proxy_list (List[str]): List of proxy URLs
        mode (ProxyMode): Proxy selection mode
        
    Returns:
        str: Selected proxy URL
    """
    global _current_proxy_index
    # Check proxy list
    if not proxy_list:
        raise ValueError("Proxy list is empty")
    # Select proxy by mode
    if mode == ProxyMode.SINGLE:
        return proxy_list[0]
    elif mode == ProxyMode.RANDOM:
        return random.choice(proxy_list)
    elif mode == ProxyMode.ROTATE:
        proxy = proxy_list[_current_proxy_index % len(proxy_list)]
        _current_proxy_index += 1
        return proxy
    else:  # TRY mode
        return proxy_list[0]



def send_request(
    url: str,
    headers: Dict[str, str],
    method: str = "GET",
    params: Optional[Dict] = None,
    payload: Optional[Union[Dict, str]] = None,
    show_log: bool = False,
    timeout: int = 30,
    proxy_list: Optional[List[str]] = None,
    proxy_mode: Union[ProxyMode, str] = ProxyMode.TRY,
    request_mode: Union[RequestMode, str] = RequestMode.DIRECT,
) -> Dict[str, Any]:
    """
    Central interface for all request sending modes.
    
    Based on request_mode and proxy_mode, selects appropriate
    request sending method.
    
    Args:
        url (str): Endpoint address
        headers (Dict[str, str]): Headers for request
        method (str): "GET" or "POST". Default "GET"
        params (Optional[Dict]): Query parameters for GET
        payload (Optional[Union[Dict, str]]): Data to send (POST)
        show_log (bool): Enable detailed logging
        timeout (int): Timeout in seconds
        proxy_list (Optional[List[str]]): List of proxy URLs
          (for PROXY mode)
        proxy_mode (Union[ProxyMode, str]): Proxy usage mode
        request_mode (Union[RequestMode, str]): Request sending mode
        
    Returns:
        Dict[str, Any]: Returned JSON data
        
    Raises:
        ConnectionError: Nếu tất cả proxy đều thất bại hoặc request lỗi
    """
    # Apply rate limiting if enabled
    if _rate_limiter is not None:
        _rate_limiter.wait()

    # Chuyển đổi string thành enum nếu cần
    if isinstance(proxy_mode, str):
        try:
            proxy_mode = ProxyMode(proxy_mode)
        except ValueError:
            raise ValueError(f"Invalid proxy_mode: {proxy_mode}")
    if isinstance(request_mode, str):
        try:
            request_mode = RequestMode(request_mode)
        except ValueError:
            raise ValueError(f"Invalid request_mode: {request_mode}")
    # Log thông tin request nếu cần
    if show_log:
        # URL thô có thể mang credential TRONG query string: client HMAC (DNSE,
        # KBS) ký bằng `?api_key=…&signature=…`. `redact_sensitive_data` ở tầng
        # logger chỉ bắt được `key=value` đúng thứ tự — `?signature=abc&api_key=X`
        # để lọt `signature=abc` (đo 2026-10-10, audit vòng 5 finding 2). Vì vậy
        # bỏ query ngay tại nguồn thay vì trông chờ regex ở tầng log.
        logger.info(
            f"{method.upper()} request to {_url_without_query(url)} "
            f"(mode: {request_mode.value})"
        )
        if params:
            logger.info(f"Params: {params}")
        if payload:
            logger.info(f"Payload: {payload}")
    # Handle different request modes
    if request_mode == RequestMode.PROXY:
        # Send via standard proxy
        if proxy_mode == ProxyMode.AUTO and not proxy_list:
            # Auto-fetch proxies if none provided
            if show_log:
                logger.info("Auto-fetching proxies via ProxyManager...")
            proxy_list = proxy_manager.get_fresh_proxies(use_cache=True)
            if not proxy_list:
                # If auto-fetch failed, fallback to direct or error? 
                # For now let's error to be explicit, or fallback to direct if user prefers?
                # Sticking to error to match "PROXY mode" intent.
                raise ConnectionError("Failed to auto-fetch valid proxies.")

        if not proxy_list:
            raise ValueError(
                "proxy_list is required for PROXY mode"
            )
        if proxy_mode == ProxyMode.TRY:
            # Try each proxy sequentially until successful
            last_exception = None
            last_rate_limit = None
            for proxy_url in proxy_list:
                try:
                    if show_log:
                        logger.info(f"Trying proxy: {proxy_url}")
                    proxies = build_proxy_dict(proxy_url)
                    return send_request_direct(
                        url, headers, method, params, payload,
                        timeout, proxies
                    )
                except ConnectionError as e:
                    last_exception = e
                    # Giữ lại `retry_after` của server thay vì ghi đè bằng
                    # ConnectionError chung. `RateLimitError` là subclass của
                    # ConnectionError nên nó lọt vào `except` ở trên; nếu ta bọc
                    # lại thành ConnectionError thì circuit breaker rơi về
                    # cooldown suy đoán 5s, mất đúng con số server đã gửi.
                    if isinstance(e, RateLimitError):
                        last_rate_limit = e
                    if show_log:
                        logger.warning(
                            f"Proxy {proxy_url} failed: {e}"
                        )
                    continue
            if last_rate_limit is not None:
                # Mọi proxy đều bị throttle: ném nguyên exception cuối để
                # `record_failure` nhận được `retry_after`.
                raise last_rate_limit
            msg = (
                f"All proxies failed. "
                f"Last error: {last_exception}"
            )
            raise ConnectionError(msg)
        else:
            # Select proxy by mode
            selected_proxy = get_proxy_by_mode(
                proxy_list, proxy_mode
            )
            proxies = build_proxy_dict(selected_proxy)
            if show_log:
                msg = (
                    f"Using proxy ({proxy_mode.value} mode): "
                    f"{selected_proxy}"
                )
                logger.info(msg)
            return send_request_direct(
                url, headers, method, params, payload, timeout,
                proxies
            )
    else:  # RequestMode.DIRECT
        # Send direct request without proxy
        if show_log:
            logger.info("Sending direct request (no proxy)")
        return send_request_direct(
            url, headers, method, params, payload, timeout,
            proxies=None
        )


def send_request_direct(
    url: str,
    headers: Dict[str, str],
    method: str = "GET",
    params: Optional[Dict] = None,
    payload: Optional[Union[Dict, str]] = None,
    timeout: int = 30,
    proxies: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Send request directly to endpoint without special proxy.
    
    Args:
        url (str): Endpoint URL
        headers (Dict[str, str]): Headers for request
        method (str): "GET" or "POST"
        params (Optional[Dict]): Query parameters for GET
        payload (Optional[Union[Dict, str]]): Data to send (POST)
        timeout (int): Timeout in seconds
        proxies (Optional[Dict[str, str]]): Proxy dict if any
        
    Returns:
        Dict[str, Any]: Returned JSON data

    Raises:
        RateLimitError: If server answers HTTP 429 (throttling). Kế thừa
            ``ConnectionError`` nên code bắt ``except ConnectionError`` vẫn
            bắt được; khác ở chỗ mang theo ``retry_after`` đọc từ header
            ``Retry-After`` để circuit breaker đặt cooldown đúng số.
        ProviderAuthError: HTTP 401/403 — đáp án cuối, không retry/failover.
        ProviderNotFoundError: HTTP 404 — đáp án cuối, không retry/failover.
        ProviderBadRequestError: HTTP 400/422 — đáp án cuối.
        ConnectionError: các lỗi còn lại (500, mạng, ...).
    """
    try:
        session = _get_thread_session()
        method_upper = method.upper()

        request_kwargs: Dict[str, Any] = {
            "headers": headers,
            "timeout": timeout,
            "proxies": proxies,
        }
        if method_upper == "GET":
            request_kwargs["params"] = params
        else:
            if payload is not None:
                if isinstance(payload, dict):
                    request_kwargs["json"] = payload
                elif isinstance(payload, str):
                    request_kwargs["data"] = payload
                else:
                    msg = (
                        "Payload must be either a dict "
                        "or a raw string."
                    )
                    raise ValueError(msg)

        response = session.request(method_upper, url, **request_kwargs)
        # Check response status
        if response.status_code != 200:
            # `details["url"]` đi vào `__str__` của exception, tức đi thẳng ra
            # log/traceback của người dùng. Provider HMAC (DNSE, KBS) đặt
            # credential TRONG query string (`?api_key=…&signature=…`) — nhét
            # URL thô vào đây là tự rò credential qua chính exception của mình.
            # Vì vậy chỉ giữ scheme+netloc+path (bỏ query tại nguồn).
            safe_url = _url_without_query(url)
            if response.status_code == 429:
                # 429 là lời mời "chậm lại", KHÔNG phải "provider chết" — nên nó
                # phải mang theo Retry-After thay vì nằm chung với 403/500.
                # Trước đây 429 ra `ConnectionError` chung, nên cooldown chỉ
                # lớn theo suy đoán và retry thêm 3 lần vô ích.
                raise RateLimitError(
                    provider=urlsplit(url).netloc or url,
                    retry_after=parse_retry_after(getattr(response, "headers", None)),
                    details={"url": safe_url, "status_code": 429},
                )
            if response.status_code in (401, 403):
                # Đáp án cuối (P-4): token hỏng/cấm với provider này thì provider
                # khác cũng trả lời y hệt — không retry, không xoay vòng.
                # Message cố ý không chứa marker của `should_failover`.
                raise ProviderAuthError(
                    "Token hết hạn/không hợp lệ hoặc provider từ chối quyền "
                    "truy cập. Đây là đáp án cuối, không thử lại.",
                    http_status=response.status_code,
                    url=safe_url,
                )
            if response.status_code == 404:
                raise ProviderNotFoundError(
                    "Endpoint không tồn tại ở phía provider (HTTP 404). "
                    "Đây là đáp án cuối, không thử lại.",
                    http_status=response.status_code,
                    url=safe_url,
                )
            if response.status_code in (400, 422):
                raise ProviderBadRequestError(
                    "Provider từ chối request vì không hợp lệ/không đạt kiểm "
                    "tra. Đây là đáp án cuối, không thử lại.",
                    http_status=response.status_code,
                    url=safe_url,
                )
            msg = (
                f"Failed to fetch data: "
                f"{response.status_code} - {response.reason}"
            )
            raise ConnectionError(msg)
        return response.json()
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        logger.error(error_msg)
        raise ConnectionError(error_msg)


def reset_proxy_rotation():
    """
    Reset proxy rotation index to 0.
    
    Use when you want to restart the proxy rotation cycle in ROTATE mode.
    """
    global _current_proxy_index
    _current_proxy_index = 0


def send_direct_request(
    url: str, headers: Dict[str, str], **kwargs
):
    """
    Send request directly without proxy.
    
    Args:
        url (str): Endpoint URL
        headers (Dict[str, str]): Headers for request
        **kwargs: Additional parameters for send_request
        
    Returns:
        Dict[str, Any]: Returned JSON data
    """
    return send_request(
        url, headers, request_mode=RequestMode.DIRECT, **kwargs
    )

def send_proxy_request(
    url: str, headers: Dict[str, str], proxy_list: List[str],
    **kwargs
):
    """
    Send request via standard proxy.
    
    Args:
        url (str): Endpoint URL
        headers (Dict[str, str]): Headers for request
        proxy_list (List[str]): List of proxy URLs
        **kwargs: Additional parameters for send_request
        
    Returns:
        Dict[str, Any]: Returned JSON data
    """
    return send_request(
        url, headers, proxy_list=proxy_list,
        request_mode=RequestMode.PROXY, **kwargs
    )



