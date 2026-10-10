"""
vnbroker.broker.tcbs.condition_orders — TCBSConditionOrderService: lệnh điều kiện.

WRITE endpoint (TCBS iFlash Open API v1.0.0 — /khronos service):
  POST /khronos/v1/order/condition/cancel   → cancel_condition_order()

Body theo spec: {accountId, subAccountId, orderNo} — required: ['accountId', 'orderNo'].
Response 200: {rc, rs, data[]} (rc = "1" là thành công).

LƯU Ý — `requestId` KHÔNG tồn tại trong spec (đếm chuỗi "requestId" trong toàn bộ
openapi-v1.0.0.json = 0 lần). `derivatives.py:702-705` và `equity.py:523-525` vẫn
gửi field đó — đó là bug có sẵn (N7), KHÔNG phải chuẩn. Lát này không copy.

RULE: Mọi write method bắt buộc @write_gate với `dry_run=True` mặc định.
      `write_gate` đọc `dry_run` từ **kwargs** (guards.py:46) ⇒ `dry_run` phải là
      keyword-only, nếu không caller truyền vị trí sẽ không bao giờ qua gate.

NỢ NHÂN BẢN (N8): `_post` dưới đây là bản riêng của module, chép từ
`derivatives.py:_write_request` (:714-782) rút gọn cho đúng 1 method POST.
Coordinator chốt phương án (c) — xem PLAN_TCBS_ROUND2.md §5b: không import từ
`derivatives.py` (file cấm chạm) và không refactor file đó. Bản chép giữ nguyên
ngữ nghĩa, không cải tiến âm thầm.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

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
from vnbroker.broker.security.guards import write_gate
from vnbroker.broker.session import BrokerSession

_logger = logging.getLogger("vnbroker.broker.tcbs.condition_orders")

_PATHS = {
    "cancel": "/khronos/v1/order/condition/cancel",
}


class TCBSConditionOrderService:
    """Write-only condition order service: huỷ lệnh điều kiện phái sinh."""

    def __init__(
        self,
        config: TCBSCredentialConfig,
        session: BrokerSession,
    ) -> None:
        self._config = config
        self._session = session

    def cancel_condition_order(
        self,
        account_id: str,
        order_no: str,
        sub_account_id: str = "",
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        POST /khronos/v1/order/condition/cancel

        Args:
            account_id: Mã custody (bắt buộc theo spec), ví dụ '105C334455'.
            order_no: pk_orderNo lấy từ sổ lệnh điều kiện (bắt buộc theo spec).
            sub_account_id: Tiểu khoản phái sinh. Không nằm trong `required`
                của spec ⇒ để trống thì KHÔNG gửi field này.
            dry_run: True (mặc định) → không gửi HTTP.

        Returns:
            dict — raw response của TCBS: {rc, rs, data[]}.
        """
        account_id = account_id.strip() if account_id else ""
        order_no = order_no.strip() if order_no else ""
        sub_account_id = sub_account_id.strip() if sub_account_id else ""

        if not account_id:
            raise BrokerValidationError(
                message="account_id không được để trống.",
                code="INVALID_ACCOUNT_ID",
            )
        if not order_no:
            raise BrokerValidationError(
                message="order_no không được để trống.",
                code="INVALID_ORDER_NO",
            )
        return self._gated_cancel_condition_order(
            account_id, order_no, sub_account_id, dry_run=dry_run
        )

    @write_gate
    def _gated_cancel_condition_order(
        self,
        account_id: str,
        order_no: str,
        sub_account_id: str,
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"accountId": account_id, "orderNo": order_no}
        if sub_account_id:
            payload["subAccountId"] = sub_account_id
        url = self._config.base_url.rstrip("/") + _PATHS["cancel"]
        return self._post(url, payload)

    # ── Write HTTP methods ───────────────────────────────────────────────────

    def _post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gửi POST. Authorization KHÔNG được log.
        """
        try:
            token = self._session.token
        except BrokerSessionExpiredError:
            raise

        headers = {"Authorization": f"Bearer {token}"}

        try:
            resp = requests.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                timeout=self._config.timeout_seconds,
            )
        except requests.exceptions.Timeout as exc:
            raise BrokerNetworkError(
                message=f"Timeout khi gọi POST {url}.",
                code="NETWORK_TIMEOUT",
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise BrokerNetworkError(
                message=f"Lỗi mạng: {type(exc).__name__}",
                code="NETWORK_ERROR",
            ) from exc

        if resp.status_code == 401:
            self._session.revoke()
            raise BrokerAuthError(
                message="Token hết hạn hoặc không hợp lệ.",
                code="TOKEN_EXPIRED",
                http_status=401,
            )
        if resp.status_code == 403:
            raise BrokerPermissionError(
                message="Không đủ quyền thực thi lệnh.",
                code="FORBIDDEN",
                http_status=403,
            )
        if resp.status_code == 422:
            raise BrokerOrderError(
                message=f"Lỗi nghiệp vụ lệnh: {resp.text[:200]}",
                code="ORDER_REJECTED",
                http_status=422,
            )
        if resp.status_code == 429:
            raise BrokerRateLimitError(
                message="Vượt rate limit TCBS.",
                code="RATE_LIMIT",
                http_status=429,
            )
        if resp.status_code == 400:
            raise BrokerValidationError(
                message=f"Request không hợp lệ: {resp.text[:200]}",
                code="BAD_REQUEST",
                http_status=400,
            )
        if resp.status_code >= 500:
            raise BrokerNetworkError(
                message=f"TCBS server error {resp.status_code}.",
                code="SERVER_ERROR",
                http_status=resp.status_code,
            )

        data: Dict[str, Any] = resp.json()
        return data