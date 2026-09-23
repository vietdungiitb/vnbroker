"""
vnbroker.broker.security.redaction — Redactor cho mọi dữ liệu nhạy cảm trong broker lane.

RULE: Bất kỳ dict nào đi vào log, error message hay audit record
      PHẢI được chạy qua redact_dict() hoặc redact_headers() trước.
"""

from __future__ import annotations

from typing import Any

# Tập hợp key nhạy cảm — so sánh lowercase, phủ cả camelCase và snake_case
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "apikey",
        "api_key",
        "otp",
        "pincode",
        "pin_code",
        "authorization",
        "token",
        "auth_token",
        "password",
        "secret",
        "accountno",
        "account_no",
        "custodycode",
        "custody_code",
        "idno",
        "id_no",
        "phone",
        "email",
        "access_token",
        "accesstoken",
        "refresh_token",
        "refreshtoken",
        "bearer",
        "apisecret",
        "api_secret",
        "privatekey",
        "private_key",
        "transactionid",
        "transaction_id",
        "clientsecret",
        "client_secret",
    }
)


class Redactor:
    """
    Utility class — tất cả methods đều static, không cần instantiate.

    Dùng:
        safe = Redactor.redact_dict(payload)
        safe_headers = Redactor.redact_headers(headers)
    """

    REDACTED = "***REDACTED***"

    @staticmethod
    def redact_dict(
        data: dict[str, Any],
        keys: frozenset[str] = SENSITIVE_KEYS,
        _depth: int = 0,
        _max_depth: int = 10,
    ) -> dict[str, Any]:
        """
        Trả về bản sao dict với các key nhạy cảm đã thay bằng REDACTED.

        - So sánh key case-insensitive.
        - Xử lý nested dict đệ quy (tối đa 10 cấp).
        - Không mutate dict gốc.
        - Giữ nguyên value không phải dict/list.
        """
        if _depth > _max_depth:
            return data

        result: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(k, str) and k.lower() in keys:
                result[k] = Redactor.REDACTED
            elif isinstance(v, dict) and _depth < _max_depth:
                result[k] = Redactor.redact_dict(v, keys, _depth + 1, _max_depth)
            elif isinstance(v, list):
                result[k] = [
                    Redactor.redact_dict(item, keys, _depth + 1, _max_depth)
                    if isinstance(item, dict)
                    else item
                    for item in v
                ]
            else:
                result[k] = v
        return result

    @staticmethod
    def redact_headers(headers: dict[str, Any]) -> dict[str, Any]:
        """
        Redact Authorization header value.
        Giữ nguyên tất cả header khác.
        """
        result: dict[str, Any] = {}
        for k, v in headers.items():
            if isinstance(k, str) and k.lower() == "authorization":
                result[k] = Redactor.REDACTED
            else:
                result[k] = v
        return result

    @staticmethod
    def mask_account_no(account_no: str) -> str:
        """
        Mask số tài khoản — chỉ hiện 4 ký tự cuối.
        Ví dụ: '0123456789' → '******6789'
        """
        if len(account_no) <= 4:
            return "****"
        return "*" * (len(account_no) - 4) + account_no[-4:]
