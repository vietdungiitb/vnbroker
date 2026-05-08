import os
from typing import Optional

from vnbroker.core.utils import client
from vnbroker.core.utils.user_agent import get_headers


TCBS_OPENAPI_PRODUCTION_URL = "https://openapi.tcbs.com.vn"


def resolve_auth_token(auth_token: Optional[str] = None) -> Optional[str]:
    if auth_token:
        return auth_token
    return os.getenv("vnbroker_TCBS_AUTH_TOKEN") or os.getenv("TCBS_AUTH_TOKEN")


def resolve_openapi_api_key(api_key: Optional[str] = None) -> Optional[str]:
    if api_key:
        return api_key
    return (
        os.getenv("vnbroker_TCBS_OPENAPI_API_KEY")
        or os.getenv("TCBS_OPENAPI_API_KEY")
        or os.getenv("vnbroker_TCBS_API_KEY")
        or os.getenv("TCBS_API_KEY")
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