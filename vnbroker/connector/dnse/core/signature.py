from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timezone
from urllib import parse
from uuid import uuid4


def format_date_header(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    return value.strftime("%a, %d %b %Y %H:%M:%S %z")


def _digest_for_algorithm(algorithm: str):
    if algorithm == "hmac-sha256":
        return hashlib.sha256
    if algorithm == "hmac-sha384":
        return hashlib.sha384
    if algorithm == "hmac-sha512":
        return hashlib.sha512
    return hashlib.sha1


def build_signature(
    secret: str,
    method: str,
    path: str,
    date_value: str,
    algorithm: str,
    nonce: str | None = None,
    header_name: str = "Date",
) -> tuple[str, str]:
    header_key = header_name.lower()
    headers = f"(request-target) {header_key}"
    signature_string = (
        f"(request-target): {method.lower()} {path}\n{header_key}: {date_value}"
    )
    if nonce:
        signature_string += f"\nnonce: {nonce}"

    mac = hmac.new(
        secret.encode("utf-8"),
        signature_string.encode("utf-8"),
        _digest_for_algorithm(algorithm),
    )
    encoded = base64.b64encode(mac.digest()).decode("utf-8")
    escaped = parse.quote(encoded, safe="")
    return headers, escaped


def build_signature_header(
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    algorithm: str = "hmac-sha256",
    hmac_nonce_enabled: bool = True,
    date_header_name: str = "Date",
) -> tuple[str, str]:
    date_value = format_date_header()
    nonce = uuid4().hex if hmac_nonce_enabled else None
    headers_list, signature = build_signature(
        secret=api_secret,
        method=method,
        path=path,
        date_value=date_value,
        algorithm=algorithm,
        nonce=nonce,
        header_name=date_header_name,
    )
    signature_header = (
        f'Signature keyId="{api_key}",algorithm="{algorithm}",'
        f'headers="{headers_list}",signature="{signature}"'
    )
    if nonce:
        signature_header += f',nonce="{nonce}"'
    return date_value, signature_header
