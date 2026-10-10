"""
vnbroker.broker.security.redaction — Redactor cho mọi dữ liệu nhạy cảm trong broker lane.

RULE: Bất kỳ dict nào đi vào log, error message hay audit record
      PHẢI được chạy qua redact_dict() hoặc redact_headers() trước.
      URL có query string chứa credential (api_key, signature) dùng redact_url().
"""

from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _norm_key(key: str) -> str:
    """Chuẩn hoá key về một dạng duy nhất: lowercase + gạch dưới.

    Mọi so khớp trong module này đi qua hàm này. Trước đây set lưu key theo
    nhiều kiểu viết (``x-api-key``, ``x-apikey``) trong khi chỗ tra lại lại
    chuẩn hoá ``-`` thành ``_`` — nên hai entry đó **không bao giờ khớp được**,
    và ``X-Signature``/``Trading-Token`` lọt ra ngoài.
    """
    return key.replace("-", "_").replace(" ", "_").lower()


# Tập hợp key nhạy cảm. Mọi entry ở đây được chuẩn hoá ngay tại chỗ định nghĩa
# (xem `NORMALISED_SENSITIVE_KEYS`) nên không thể viết ra một entry mà chỗ tra
# không bao giờ khớp.
_SENSITIVE_KEYS_RAW: frozenset[str] = frozenset(
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
        # HMAC signature + token đặt trong query string (S3: WS DNSE rò credential)
        "signature",
        "sig",
        "tradingtoken",
        "trading_token",
        "smartotp",
        "smart_otp",
        # Header của DNSE: `x-api-key` và `X-Signature` đều là credential thật.
        # Trước đây viết bằng dấu gạch nên không bao giờ khớp — lộ nguyên văn.
        "x-api-key",
        "x-apikey",
        "x-signature",
        "x-sign",
        "x-auth-token",
        "x-access-token",
        "wsseckettoken",
        "cookie",
        "set-cookie",
    }
)

#: Bản đã chuẩn hoá — đây mới là set dùng để so khớp.
SENSITIVE_KEYS: frozenset[str] = frozenset(_norm_key(k) for k in _SENSITIVE_KEYS_RAW)


def _is_sensitive_key(key: str) -> bool:
    """So khớp key nhạy cảm không phân biệt hoa/thường và dấu gạch.

    Set phía trên cũng đã chuẩn hoá theo đúng quy tắc này, nên hai bên luôn
    cùng một ngôn ngữ — không còn entry nào "viết một kiểu, tra kiểu khác".
    """
    return _norm_key(key) in SENSITIVE_KEYS


def _resolve_keys(keys: Iterable[str] | None) -> frozenset[str]:
    """Chuẩn hoá cả set truyền vào, để caller tự do viết ``x-api-key``."""
    if keys is None:
        return SENSITIVE_KEYS
    return frozenset(_norm_key(k) for k in keys)


class Redactor:
    """
    Utility class — tất cả methods đều static, không cần instantiate.

    Dùng:
        safe = Redactor.redact_dict(payload)
        safe_headers = Redactor.redact_headers(headers)
    """

    REDACTED = "***REDACTED***"
    # url-encode sẽ biến "***" thành "%2A%2A%2A", khiến log khó đọc và giấu
    # dạng giá trị gốc. Dùng sentinel không cần encode.
    REDACTED_QS = "REDACTED"

    @staticmethod
    def redact_url(url: str) -> str:
        """Redact các query param nhạy cảm trong URL.

        Cần cho client HMAC (DNSE, KBS): credential nằm TRONG query string kiểu
        ``?api_key=...&signature=...``. Log URL nguyên văn ở level INFO là rò
        credential — mà log thường bị gom lại, lưu lâu, hoặc chuyển tiếp đi nơi khác.

        Args:
            url: URL có thể chứa query string.

        Returns:
            URL đã thay giá trị param nhạy cảm bằng ``***REDACTED***``.
        """
        if not url or "?" not in url:
            return url
        try:
            parts = urlsplit(url)
        except ValueError:
            return url
        if not parts.query:
            return url

        pairs = parse_qsl(parts.query, keep_blank_values=True)
        redacted = [
            (key, Redactor.REDACTED_QS if _is_sensitive_key(key) else value)
            for key, value in pairs
        ]
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(redacted), parts.fragment)
        )

    @staticmethod
    def redact_dict(
        data: dict[str, Any],
        keys: frozenset[str] | Iterable[str] | None = SENSITIVE_KEYS,
        _depth: int = 0,
        _max_depth: int = 10,
    ) -> dict[str, Any]:
        """
        Trả về bản sao dict với các key nhạy cảm đã thay bằng REDACTED.

        - Đi qua ``_is_sensitive_key`` như mọi chỗ khác, nên dict/header/url dùng
          chung một quy tắc. Trước đây chỗ này tự so ``k.lower() in keys``, lệch
          với phần còn lại của module và bỏ sót ``api-key``.
        - Xử lý nested dict đệ quy (tối đa 10 cấp).
        - Không mutate dict gốc.
        - Giữ nguyên value không phải dict/list.
        """
        if _depth > _max_depth:
            return data

        lookup = _resolve_keys(keys)
        result: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(k, str) and _norm_key(k) in lookup:
                result[k] = Redactor.REDACTED
            elif isinstance(v, dict) and _depth < _max_depth:
                result[k] = Redactor.redact_dict(v, lookup, _depth + 1, _max_depth)
            elif isinstance(v, list):
                result[k] = [
                    Redactor.redact_dict(item, lookup, _depth + 1, _max_depth)
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
        Redact mọi header nhạy cảm, giữ nguyên tên key.

        Trước đây chỉ so ``authorization``, nên ``Trading-Token``, ``X-Api-Key``
        và ``X-Signature`` — đúng những thứ client gửi đi — lộ nguyên văn vào
        log.
        """
        return {
            k: (Redactor.REDACTED if isinstance(k, str) and _is_sensitive_key(k) else v)
            for k, v in headers.items()
        }

    @staticmethod
    def mask_account_no(account_no: str) -> str:
        """
        Mask số tài khoản — chỉ hiện 4 ký tự cuối.
        Ví dụ: '0123456789' → '******6789'
        """
        if len(account_no) <= 4:
            return "****"
        return "*" * (len(account_no) - 4) + account_no[-4:]
