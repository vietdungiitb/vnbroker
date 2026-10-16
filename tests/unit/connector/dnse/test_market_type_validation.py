"""``marketType`` phải fail-closed, không được trả response rỗng im lặng.

VNBROKER-REQ-004: ``DNSEClient.get_positions(account_no, market_type)`` bắt
buộc ``market_type`` nhưng không tài liệu hoá tập giá trị hợp lệ, nên phía
vninvest phải *đoán mù* rồi thử lần lượt ``ALL / STOCK / EQUITY``.

Cơ chế đoán đó không chỉ chậm — nó **sai kiểu fail-open**:

    for market_type in ("ALL", "STOCK", "EQUITY"):
        try:
            raw = client.get_order_history(..., market_type=market_type)
            break          # <- lần đầu không raise là break, kể cả khi rỗng
        except Exception:
            ...

``ALL`` trả HTTP 200 với body rỗng ⇒ ``break`` ngay, ``STOCK``/``EQUITY``
không bao giờ được gọi, và caller nhận ``[]`` — tức **HTTP 200 là thất bại
nghiệp vụ** (L-R01). Đo lại 2026-10-14 với stub trả DataFrame rỗng:
``market_type actually called: ['ALL']``.

Vì vậy ở đây ta **không** thêm một vòng retry nữa. Ta chặn ngay tại chỗ:
giá trị sai ⇒ ném lỗi có mã, trước cả khi có một byte nào đi ra.

Vị trí đặt kiểm tra cũng là một quyết định: ``DNSEHttpClient.request()`` là
choke point mọi request đi qua — đúng lập luận mà chính write gate của repo
này dùng (``http_client.py:31-42``: *"adding a guard per method reproduces that
bug: one endpoint added is one hole"*).
"""
from __future__ import annotations

import inspect

import pytest
import requests

from vnbroker.connector.dnse.client import DNSEClient
from vnbroker.connector.dnse.constants import (
    MARKET_TYPES,
    ORDER_CATEGORIES,
    validate_market_type,
    validate_order_category,
)
from vnbroker.connector.dnse.core.errors import DNSEValidationError

# --- Tập giá trị: ghim theo bằng chứng trong repo, không đoán bừa ------------

def test_market_types_are_exactly_the_two_documented_values():
    """Nguồn: `docs/COMPARE_DNSE_SDK.md:16` (``market_type="STOCK"`` trong ví
    dụ của doc chính thức) + `docs/DERIVATIVES_API_RESEARCH.md:58,76`
    (``marketType=DERIVATIVE``). Đếm bằng script trên toàn repo 2026-10-14 ra
    đúng 2 giá trị này, không có giá trị thứ ba.

    Test này ĐỎ nếu ai thêm giá trị mà không kèm bằng chứng — đúng ý nghĩa
    "giam chặt theo tài liệu", không phải "cấm thêm".
    """
    assert set(MARKET_TYPES) == {"STOCK", "DERIVATIVE"}


def test_order_categories_match_the_normalisation_policy():
    """Nguồn: `docs/NORMALISATION_POLICY.md:146`."""
    assert set(ORDER_CATEGORIES) == {"NORMAL", "STOP", "OCO"}


# --- Hành vi khi sai giá trị ------------------------------------------------

def test_valid_value_passes_through_unchanged():
    assert validate_market_type("STOCK") == "STOCK"
    assert validate_market_type("DERIVATIVE") == "DERIVATIVE"


def test_value_is_normalised_before_validation():
    """Chấp nhận khác biệt chữ hoa/thường và khoảng trắng thừa, nhưng KHÔNG
    chấp nhận giá trị lạ — nới lỏng hình thức, siết nội dung."""
    assert validate_market_type("stock") == "STOCK"
    assert validate_market_type("stock ") == "STOCK"
    assert validate_market_type("  Derivative  ") == "DERIVATIVE"


@pytest.mark.parametrize("bad", ["ALL", "EQUITY", "", "STOCKS", "None", "stock-x"])
def test_invalid_value_raises_a_coded_error(bad):
    with pytest.raises(DNSEValidationError) as excinfo:
        validate_market_type(bad)
    assert excinfo.value.error_code == "INVALID_MARKET_TYPE"


def test_invalid_value_message_names_the_valid_ones():
    """Lỗi phải tự mô tả cách sửa — người đọc không mở tài liệu được."""
    with pytest.raises(DNSEValidationError) as excinfo:
        validate_market_type("ALL")
    message = str(excinfo.value)
    assert "STOCK" in message and "DERIVATIVE" in message


def test_invalid_order_category_raises_its_own_code():
    with pytest.raises(DNSEValidationError) as excinfo:
        validate_order_category("PARTIAL")
    assert excinfo.value.error_code == "INVALID_ORDER_CATEGORY"


def test_order_category_is_optional():
    """`order_category` là tuỳ chọn ở vài method; ``None`` phải đi qua, không
    phải là giá trị sai."""
    assert validate_order_category(None) is None


# --- Bằng chứng fail-closed: KHÔNG có byte nào đi ra ------------------------

class _NoEgress:
    """Bất kỳ request nào đi ra đều làm test đỏ, kèm lý do."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __enter__(self) -> "_NoEgress":
        self._original = requests.Session.request
        guard = self

        def _spy(self, method, url, *args, **kwargs):
            guard.calls.append(f"{method} {url}")
            raise AssertionError(
                f"request đã đi ra dù marketType sai: {method} {url}"
            )

        requests.Session.request = _spy  # type: ignore[method-assign]
        return self

    def __exit__(self, *exc) -> None:
        requests.Session.request = self._original  # type: ignore[method-assign]


def test_invalid_market_type_never_reaches_the_network():
    """REQ-004 nói rõ: *"truyền sai giá trị nhận lỗi có mã (không phải
    response rỗng im lặng)"*. Nửa "không phải response rỗng" chỉ được chứng
    minh bằng cách chứng minh **không có request nào được gửi**."""
    client = DNSEClient(api_key="k", api_secret="s")
    with _NoEgress():
        with pytest.raises(DNSEValidationError) as excinfo:
            client.get_positions(account_no="0123456789", market_type="ALL")
    assert excinfo.value.error_code == "INVALID_MARKET_TYPE"


# --- Phủ kín: MỌI method công khai nhận marketType đều phải chặn ------------

def _public_methods_with_market_type(cls) -> list[str]:
    return sorted(
        name
        for name, func in inspect.getmembers(cls, predicate=inspect.isfunction)
        if not name.startswith("_")
        and "market_type" in inspect.signature(func).parameters
    )


def test_the_client_really_does_expose_many_market_type_methods():
    """Guard cho chính bộ test: nếu số method bằng 0 hoặc 1 thì test phía dưới
    chỉ là ảo — đo lại trước mỗi lần đổi bề mặt API."""
    names = _public_methods_with_market_type(DNSEClient)
    assert len(names) >= 10, names


@pytest.mark.parametrize("name", _public_methods_with_market_type(DNSEClient))
def test_every_market_type_method_rejects_an_invalid_value(name):
    method = getattr(DNSEClient(api_key="k", api_secret="s"), name)
    # Chỉ điền tham số bắt buộc. Giá trị giả ở đây là cố ý: kiểm tra marketType
    # phải ném ra TRƯỚC khi tham số kia được dùng, nên chúng không được chạm tới.
    required = {
        param: "x"
        for param, spec in inspect.signature(method).parameters.items()
        if param not in ("market_type", "dry_run", "raw") and spec.default is inspect.Parameter.empty
    }
    with _NoEgress():
        with pytest.raises(DNSEValidationError) as excinfo:
            method(market_type="ALL", **required)
    assert excinfo.value.error_code == "INVALID_MARKET_TYPE"


# --- REQ-004 còn yêu cầu: docstring phải liệt kê giá trị -------------------

def test_get_positions_docstring_lists_the_valid_values():
    """REQ-004 nêu đích danh ``get_positions``. Docstring không có tập giá
    trị thì người đọc lại phải đoán — tức yêu cầu chưa đạt."""
    doc = DNSEClient.get_positions.__doc__ or ""
    for value in sorted(MARKET_TYPES):
        assert value in doc, f"get_positions.__doc__ chưa liệt kê {value}"


def test_get_positions_docstring_documents_the_error_behaviour():
    doc = (DNSEClient.get_positions.__doc__ or "").upper()
    assert "INVALID_MARKET_TYPE" in doc
