"""
vnbroker.broker.tcbs._write_http — POST JSON + map status sang exception (dùng chung).

Lý do tồn tại (audit round 2, F-1 — major):
  `money.py._check_status` chỉ map 401/403/5xx, nên **400/404/422/429 rơi qua và
  `resp.json()` được trả về y như thành công**. Với write động tiền
  (nộp/rút/chuyển margin) đó là lỗi nghiêm trọng: server trả lỗi, caller thấy dict.

  Thêm nhánh map vào `money.py` sẽ đẩy file từ 791L lên ~809L, vượt ngân sách 800L
  (`CLAUDE.md:15`). Tách ra đây vừa sửa lỗi vừa giữ file dưới ngân sách.

  Đây là bước đầu của nợ N8 (5 bản `_post` trùng nhau trong `broker/tcbs/`).
  `condition_orders.py` có bản riêng đã đúng — **không** sửa file đó ở round này.

HỢP ĐỒNG:

  HTTP >= 400  -> raise BrokerError tương ứng (KHÔNG bao giờ trả về body lỗi).
  HTTP 200     -> trả `resp.json()` **nguyên văn**, KHÔNG kiểm `rc` nghiệp vụ.
                 Lý do: spec chỉ mô tả `rc` ("1: success, <0: error") nhưng không
                 liệt kê đủ mã để suy ra tập "thành công", và chưa có JWT để probe
                 server thật. Tự ý raise theo tập mã đoán là rủi ro chặn lệnh hợp lệ.
                 ⇒ **Caller PHẢI tự kiểm `rc`** — xem `describe_business_code()`.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

import requests

from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerNetworkError,
    BrokerOrderError,
    BrokerPermissionError,
    BrokerRateLimitError,
    BrokerSessionExpiredError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.session import BrokerSession


def raise_for_status(resp: requests.Response) -> None:
    """Map mọi HTTP >= 400 sang exception. Dùng chung cho write endpoint."""
    status = resp.status_code
    if status == 401:
        raise BrokerAuthError(
            message="Token hết hạn hoặc không hợp lệ.",
            code="TOKEN_EXPIRED",
            http_status=401,
        )
    if status == 403:
        raise BrokerPermissionError(
            message="Không đủ quyền thực thi lệnh.",
            code="FORBIDDEN",
            http_status=403,
        )
    if status == 400:
        raise BrokerValidationError(
            message=f"Request không hợp lệ: {resp.text[:200]}",
            code="BAD_REQUEST",
            http_status=400,
        )
    if status == 422:
        raise BrokerOrderError(
            message=f"Lỗi nghiệp vụ lệnh: {resp.text[:200]}",
            code="ORDER_REJECTED",
            http_status=422,
        )
    if status == 404:
        raise BrokerValidationError(
            message="Endpoint không tồn tại ở phía TCBS.",
            code="ENDPOINT_NOT_FOUND",
            http_status=404,
        )
    if status == 429:
        raise BrokerRateLimitError(
            message="Vượt rate limit TCBS.",
            code="RATE_LIMIT",
            http_status=429,
        )
    if status >= 500:
        raise BrokerNetworkError(
            message=f"TCBS server error {status}.",
            code="SERVER_ERROR",
            http_status=status,
        )


def post_json(
    session: BrokerSession,
    config: TCBSCredentialConfig,
    path: str,
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    POST JSON kèm Bearer token, map lỗi, trả body nguyên văn.

    KHÔNG log payload — có thể chứa số tiền và thông tin tài khoản.
    """
    try:
        token = session.token
    except BrokerSessionExpiredError:
        raise

    if not token:
        raise BrokerPermissionError(
            message="Session chưa được xác thực. Gọi authenticate() trước.",
            code="NOT_AUTHENTICATED",
            http_status=403,
        )

    url = config.base_url.rstrip("/") + path
    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = requests.post(
            url,
            json=dict(payload),
            headers=headers,
            timeout=config.timeout_seconds,
        )
    except requests.exceptions.Timeout as exc:
        raise BrokerNetworkError(
            message=f"Timeout khi gọi POST {path}.",
            code="NETWORK_TIMEOUT",
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise BrokerNetworkError(
            message=f"Lỗi mạng: {type(exc).__name__}",
            code="NETWORK_ERROR",
        ) from exc

    raise_for_status(resp)
    data: Dict[str, Any] = resp.json()
    return data


def describe_business_code(payload: Optional[Mapping[str, Any]]) -> Optional[str]:
    """
    Trả mã nghiệp vụ của response TCBS (`rc` hoặc `code`) để caller tự kiểm.

    Spec mô tả `rc` = "1: success, < 0: error" cho các write endpoint. Thư viện
    **không** tự raise theo mã này — xem giải thích ở đầu module.

    Returns:
        None nếu response không mang mã nghiệp vụ.
    """
    if not isinstance(payload, Mapping):
        return None
    for key in ("rc", "code"):
        value = payload.get(key)
        if value is not None:
            return str(value)
    return None