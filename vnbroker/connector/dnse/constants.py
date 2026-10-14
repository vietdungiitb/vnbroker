"""Giá trị hợp lệ cho tham số truy vấn của DNSE OpenAPI.

VNBROKER-REQ-004 (2026-10-14): ``marketType`` là tham số **bắt buộc** ở mọi
method đọc/ghi vị thế và danh sách gặp trong vnbroker. Trước đây nó là ``str``
trần, không validate, không tài liệu hoá ⇒ phía tiêu thụ phải đoán.

Tập giá trị và chỗ bằng chứng
---------------------------
``MARKET_TYPES`` — đếm bằng script trên toàn repo (docs + code + notebook)
ngày 2026-10-14 cho đúng **hai** giá trị, không có giá trị thứ ba:

===========  =====================================================
Giá trị      Bằng chứng trong repo
===========  =====================================================
``STOCK``    ``docs/COMPARE_DNSE_SDK.md:16`` — ví dụ của doc chính
             thức: ``client.post_order(market_type="STOCK", ...)``;
             ``docs/PLAN_TIER1_ROUND2.md:29-33`` và
             ``docs/HANDOFF_DNSE_ROUND2_20261009.md:36``.
``DERIVATIVE``  ``docs/DERIVATIVES_API_RESEARCH.md:58,76`` —
             ``POST /accounts/orders?marketType=DERIVATIVE``.
===========  =====================================================

``ORDER_CATEGORIES`` — ``docs/NORMALISATION_POLICY.md:146``:
``orderCategory`` (``NORMAL``/``STOP``/``OCO``).

⚠ **Spec chưa được ghim trong repo.** DNSE không có file OpenAPI commit kèm
sha256 (khác TCBS — ``docs/references/openapi-v1.0.0.json`` có sha256 do
``scripts/verify_tcbs_coverage.py`` khoá). Vì vậy hai tập ở trên là **tập đã
dùng và đã tài liệu hoá**, không phải enum do server công bố. Thêm giá trị mới
chỉ khi có bằng chứng; nếu DNSE công bố enum chính thức thì thay cả tập này
và bỏ chú thích ở đây.

Hành vi khi sai
---------------
Giá trị không thuộc tập ⇒ ``DNSEValidationError`` với ``error_code`` cụ thể
(``INVALID_MARKET_TYPE`` / ``INVALID_ORDER_CATEGORY``), **ném ra trước khi có
byte nào đi ra**. Đây là chủ ý: tham số sai thường được server trả HTTP 200 +
body rỗng, và "thử lần lượt cho đến khi hết cách" là cách fail-open tệ nhất
(L-R01). Thà sai cụ thể còn hơn im lặng trả rỗng.

Chuẩn hoá: cắt khoảng trắng + upper-case trước khi kiểm tra — nới lỏng hình
thức, siết nội dung.
"""
from __future__ import annotations

from typing import Final

from vnbroker.connector.dnse.core.errors import DNSEValidationError

#: Giá trị hợp lệ của tham số truy vấn ``marketType``.
MARKET_TYPES: Final[frozenset[str]] = frozenset({"STOCK", "DERIVATIVE"})

#: Giá trị hợp lệ của tham số truy vấn ``orderCategory``.
ORDER_CATEGORIES: Final[frozenset[str]] = frozenset({"NORMAL", "STOP", "OCO"})


def _normalise(value: str) -> str:
    return value.strip().upper() if isinstance(value, str) else ""


def _reject(value: object, allowed: frozenset[str], code: str, param: str) -> None:
    options = ", ".join(sorted(allowed))
    raise DNSEValidationError(
        message=(
            f"{param}={value!r} không hợp lệ. Giá trị được hỗ trợ: {options}. "
            f"Giá trị sai thường khiến server trả HTTP 200 kèm body rỗng — "
            f"nên vnbroker chặn trước khi gửi thay vì để bạn đoán bằng cách thử."
        ),
        error_code=code,
        status_code=400,
    )


def validate_market_type(value: str) -> str:
    """Kiểm tra ``marketType``; trả về giá trị đã chuẩn hoá.

    Raises:
        DNSEValidationError: khi ``value`` không thuộc :data:`MARKET_TYPES`.
            ``error_code == "INVALID_MARKET_TYPE"``.
    """
    normalised = _normalise(value)
    if normalised not in MARKET_TYPES:
        _reject(value, MARKET_TYPES, "INVALID_MARKET_TYPE", "marketType")
    return normalised


def validate_order_category(value: str | None) -> str | None:
    """Kiểm tra ``orderCategory``; ``None`` đi qua (tham số tuỳ chọn).

    Raises:
        DNSEValidationError: khi ``value`` không thuộc
            :data:`ORDER_CATEGORIES`. ``error_code ==
            "INVALID_ORDER_CATEGORY"``.
    """
    if value is None:
        return None
    normalised = _normalise(value)
    if normalised not in ORDER_CATEGORIES:
        _reject(value, ORDER_CATEGORIES, "INVALID_ORDER_CATEGORY", "orderCategory")
    return normalised


def validate_query(query: dict[str, object] | None) -> dict[str, object] | None:
    """Kiểm tra mọi tham số truy vấn đã biết, trả về bản đã chuẩn hoá.

    Hàm này là **choke point** của ``DNSEHttpClient.request()``. Đặt kiểm tra ở
    đây thay vì rải theo từng method vì lý do chính thức của write gate ngay
    cùng tệp (``core/http_client.py:31-42``): rải theo method thì "thêm một
    endpoint là thêm một lỗ hổng"; ở choke point thì không có gì để quên.
    """
    if not query:
        return query
    validated = dict(query)
    if "marketType" in validated:
        validated["marketType"] = validate_market_type(str(validated["marketType"]))
    if "orderCategory" in validated:
        category = validated["orderCategory"]
        validated["orderCategory"] = (
            None if category is None else validate_order_category(str(category))
        )
    return validated
