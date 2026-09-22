"""
vnbroker.broker.ssi._signing — RSA PKCS#1 v1.5/SHA-256 signing (stdlib-only) + nanoid.

Port từ ssi-sdk-python utils/crypto.py + utils/id_generator.py (allowlist §3 plan):
thuần toán, không dính runtime SDK. Không cần dependency mới.
private_key = base64 của XML RSA key chứa <Modulus> và <D>.
"""

from __future__ import annotations

import base64
import hashlib
from math import ceil, log
from os import urandom
from xml.etree.ElementTree import fromstring

from vnbroker.broker.exceptions import BrokerValidationError

# DER prefix cho SHA-256 AlgorithmIdentifier (PKCS#1 v1.5 DigestInfo header).
_SHA256_DER_PREFIX = bytes(
    [
        0x30,
        0x31,
        0x30,
        0x0D,
        0x06,
        0x09,
        0x60,
        0x86,
        0x48,
        0x01,
        0x65,
        0x03,
        0x04,
        0x02,
        0x01,
        0x05,
        0x00,
        0x04,
        0x20,
    ]
)

_NANOID_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_NANOID_SIZE = 20


def get_rsa_key(private_key: str) -> tuple[int, int]:
    """
    Parse base64-XML RSA key → (modulus n, private exponent d).

    Raises:
        BrokerValidationError: key rỗng/không parse được.
    """
    if not private_key or not private_key.strip():
        raise BrokerValidationError(
            message="private_key rỗng — write SSI yêu cầu private_key (RSA base64-XML).",
            code="MISSING_PRIVATE_KEY",
            http_status=400,
        )
    try:
        key_bytes = base64.b64decode(private_key.strip().encode("utf-8"))
        root = fromstring(key_bytes.decode("utf-8"))
    except Exception as exc:
        raise BrokerValidationError(
            message="private_key không phải base64-XML RSA hợp lệ.",
            code="INVALID_PRIVATE_KEY",
            http_status=400,
        ) from exc

    def _get_int(tag: str) -> int:
        node = root.find(tag)
        if node is None or not node.text:
            raise BrokerValidationError(
                message=f"private_key thiếu tag <{tag}>.",
                code="INVALID_PRIVATE_KEY",
                http_status=400,
            )
        return int.from_bytes(base64.b64decode(node.text), byteorder="big")

    return _get_int("Modulus"), _get_int("D")


def rsa_sign_hex(data: str, private_key: str) -> str:
    """
    Ký chuỗi UTF-8 bằng RSA PKCS#1 v1.5/SHA-256, trả hex signature.

    Dùng cho header X-Signature của mọi write SSI (place/modify/cancel, FCO).
    """
    n, d = get_rsa_key(private_key)
    digest = hashlib.sha256(data.encode("utf-8")).digest()
    digest_info = _SHA256_DER_PREFIX + digest
    key_len = (n.bit_length() + 7) // 8
    pad_len = key_len - len(digest_info) - 3
    if pad_len < 8:
        raise BrokerValidationError(
            message="RSA key quá ngắn cho SHA-256 PKCS#1 v1.5.",
            code="INVALID_PRIVATE_KEY",
            http_status=400,
        )
    padded = b"\x00\x01" + b"\xff" * pad_len + b"\x00" + digest_info
    m = int.from_bytes(padded, byteorder="big")
    s = pow(m, d, n)
    return s.to_bytes(key_len, byteorder="big").hex()


def generate_request_id(
    alphabet: str = _NANOID_ALPHABET, size: int = _NANOID_SIZE
) -> str:
    """Sinh client request ID ngẫu nhiên kiểu nanoid (mặc định 20 ký tự)."""
    alphabet_len = len(alphabet)
    mask = 1
    if alphabet_len > 1:
        mask = (2 << int(log(alphabet_len - 1) / log(2))) - 1
    step = int(ceil(1.6 * mask * size / alphabet_len))

    result = ""
    while True:
        random_bytes = bytearray(urandom(step))
        for byte in random_bytes:
            random_byte = byte & mask
            if random_byte < alphabet_len:
                result += alphabet[random_byte]
                if len(result) == size:
                    return result
