import os
from typing import Optional

from vnbroker.core.utils import client
from vnbroker.core.utils.user_agent import get_headers


TCBS_OPENAPI_PRODUCTION_URL = "https://openapi.tcbs.com.vn"

#: Biến chứa JWT thật của iFlash OpenAPI.
#:
#: `TCBS_AUTH_TOKEN` **không** phải JWT — nó là mã 48 ký tự của API riêng
#: (OpenAPI key/OTP exchange), và server trả `401
#: {"code":"validate.token.error"}` khi dùng nó làm Bearer cho
#: `/tartarus/*`. Đo live 2026-10-10 trên 4 endpoint: 401 ở cả 4 với token
#: 48 ký tự, 200 (và dữ liệu thật) với JWT 1290 ký tự.
TCBS_JWT_ENV_VARS: tuple[str, ...] = (
    "vnbroker_TCBS_JWT_TOKEN",
    "TCBS_JWT_TOKEN",
)

#: Biến chứa mã **không phải** JWT. Chỉ dùng làm fallback cuối cùng.
TCBS_NON_JWT_ENV_VARS: tuple[str, ...] = (
    "vnbroker_TCBS_AUTH_TOKEN",
    "TCBS_AUTH_TOKEN",
)


def _first_env(names: tuple[str, ...]) -> Optional[str]:
    """Giá trị đầu tiên tồn tại và **không rỗng** trong ``names``.

    Khoảng trắng thuần bị coi là không có: một biến rỗng thường là hệ quả của
    một dòng `KEY=` sốt trong `.env`, và dùng nó còn tệ hơn là không có token.
    """
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def resolve_auth_token(auth_token: Optional[str] = None) -> Optional[str]:
    """Bearer token cho endpoint read-only của iFlash OpenAPI.

    Thứ tự ưu tiên:

    1. ``auth_token`` truyền vào (người gọi đã biết mình đang làm gì);
    2. ``TCBS_JWT_TOKEN`` — token thật, đo được là chạy được;
    3. ``TCBS_AUTH_TOKEN`` — chỉ để tương thích ngược. Token này **không**
       phải JWT và bị server từ chối; giữ làm fallback để không làm hỏng
       hành vi cũ, nhưng đừng gọi nó là "token hợp lệ".
    """
    if auth_token and auth_token.strip():
        return auth_token.strip()
    return _first_env(TCBS_JWT_ENV_VARS) or _first_env(TCBS_NON_JWT_ENV_VARS)


def resolve_openapi_api_key(api_key: Optional[str] = None) -> Optional[str]:
    if api_key:
        return api_key
    return _first_env(
        (
            "vnbroker_TCBS_OPENAPI_API_KEY",
            "TCBS_OPENAPI_API_KEY",
            "vnbroker_TCBS_API_KEY",
            "TCBS_API_KEY",
        )
    )


def resolve_openapi_base_url(base_url: Optional[str] = None) -> str:
    return (
        base_url
        or os.getenv("vnbroker_TCBS_OPENAPI_BASE_URL")
        or os.getenv("TCBS_OPENAPI_BASE_URL")
        or TCBS_OPENAPI_PRODUCTION_URL
    ).rstrip("/")


def request_openapi_token(
    otp: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    show_log: bool = False,
) -> str:
    resolved_api_key = resolve_openapi_api_key(api_key)
    if not resolved_api_key:
        raise ValueError(
            "Missing TCBS OpenAPI API key. Pass api_key or set "
            "vnbroker_TCBS_OPENAPI_API_KEY/TCBS_OPENAPI_API_KEY."
        )
    if not otp:
        raise ValueError("Missing OTP for TCBS OpenAPI token exchange.")

    url = (
        f"{resolve_openapi_base_url(base_url)}"
        "/gaia/v1/oauth2/openapi/token"
    )
    response = client.send_request(
        url=url,
        headers=get_headers(data_source="TCBS"),
        method="POST",
        payload={"apiKey": resolved_api_key, "otp": otp},
        show_log=show_log,
    )

    token = response.get("token")
    if token:
        return token

    code = response.get("code")
    message = response.get("message", "Token exchange failed.")
    if code:
        raise ConnectionError(
            f"TCBS OpenAPI token exchange failed: {code} - {message}"
        )
    raise ConnectionError(f"TCBS OpenAPI token exchange failed: {message}")


def get_tcbs_headers(
    random_agent: bool = False,
    auth_token: Optional[str] = None,
):
    token = resolve_auth_token(auth_token)
    return get_headers(
        data_source="TCBS",
        random_agent=random_agent,
        authorization=token,
    )