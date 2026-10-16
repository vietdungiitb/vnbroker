"""Nguồn sự thật cho ``BrokerRegistry.capabilities()`` — VNBROKER-REQ-001/003.

Vì sao cần
----------
Phía tiêu thụ (vninvest) cần biết method nào **thật**, method nào **đã gỡ**,
mà không có API chính thức. Trước đây cách duy nhất là gọi thử và bắt
``NotImplementedError`` — tức fail-open: chạy tới đâu biết tới đó, và "không
ném exception" không phải "có dữ liệu".

Ba điều chỉnh so với AC gốc của REQ, mỗi cái một lý do đo được
----------------------------------------------------------------------------
**1. Phải phủ cả 3 lane, không chỉ 2.** ``BrokerRegistry`` chỉ đăng ký
``tcbs``/``ssi``; ``DNSEClient`` nằm ở ``connector/dnse`` và **không** phải
``BaseBrokerClient``, nên không thể đăng ký vào registry mà không nói dối kiểu
dữ liệu (``_providers: Dict[str, Type[BaseBrokerClient]]``). Vậy nên bảng lane
ở đây liệt kê cả 3, còn ``BrokerRegistry`` chỉ là một cách gọi tiện.

**2. Dựng ở cấp class, không instantiate.** AC viết *"gọi trên 3 lane không
cần credential"*, nhưng ``DNSEClient.__init__`` **bắt buộc** ``api_key`` và
``api_secret``. Instantiate để xem capability thì vô lý ngay từ đầu. Ở đây
chỉ introspect class, nên không cần credential và không tạo side effect.

**3. Danh mục lấy từ class cụ thể.** ``BaseBrokerClient`` chỉ có 4 method
công khai (``authenticate``, ``close``, ``get_account_balance``,
``get_account_list``). Dựng danh mục từ lớp cơ sở sẽ làm mất 66/70 method của
TCBS.

Từ điều chỉnh (1) và (2) suy ra một điều nữa: provider **đã đăng ký** và
provider **có trong bảng lane** là hai khái niệm khác nhau, và
``vnbroker/broker/__init__.py:46-57`` đang nuốt lỗi import bằng
``except Exception: pass``. Nên ``capabilities()`` báo rõ cả hai trạng thái
thay vì để người đọc tự đoán.

Nguyên tắc bất di bất dịch
--------------------------
*Mọi khẳng định trong bảng lane phải kiểm được bằng test.* Lý do ghi kèm là
bằng chứng trích dẫn được; một claim hỏng thì test đỏ trước khi nó thành lời
hứa sai với phía tiêu thụ.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, Final, cast

# --- Từ điển reason_code ----------------------------------------------------

#: Path không có trong tài liệu chính thức của provider nên đã bị gỡ khỏi
#: vnbroker. ``reason_code`` đi kèm **giá trị là chính path đó**, để người
#: đọc tự tra được thay vì phải tin.
PATH_REMOVED_NOT_IN_SPEC: Final = "PATH_REMOVED_NOT_IN_SPEC"

#: Provider chưa có API cho tính năng này (chưa phải giới hạn của vnbroker).
PROVIDER_NO_API: Final = "PROVIDER_NO_API"


@dataclass(frozen=True)
class LaneSpec:
    """Mô tả một lane broker.

    Attributes:
        client: Đường dẫn ``module:ClassName``. Để **chuỗi** chứ không import
            thẳng: import lúc nạp module sẽ kéo theo cả ``requests``/``pandas``
            và tạo vòng import với ``vnbroker.broker``. Xem
            ``_resolve_client()``.
        unsupported: method công khai nhưng không dùng được, kèm lý do.
        features: tính năng cấp sản phẩm, tách khỏi danh mục method vì nó
            trả lời "provider có làm được không", không phải "tao có hàm
            này không".
    """

    client: str
    unsupported: dict[str, str] = field(default_factory=dict)
    features: dict[str, dict[str, object]] = field(default_factory=dict)
    registered: bool = True


def _tcbs_unsupported() -> dict[str, str]:
    """18 method đã gỡ, đọc thẳng từ bảng gốc — không chép lại danh sách.

    Chép lại là cách chắc chắn nhất để hai danh sách lệch nhau, mà REQ yêu
    cầu *"đúng 100%"*.
    """
    from vnbroker.broker.tcbs import account as account_mod
    from vnbroker.broker.tcbs import equity as equity_mod

    removed: dict[str, str] = {}
    for module in (equity_mod, account_mod):
        for name, path in module._REMOVED_PATHS.items():
            removed[name] = f"{PATH_REMOVED_NOT_IN_SPEC}:{path}"
    return removed


#: Bảng 3 lane. Đây là SSOT cho ``capabilities()``.
LANES: Final[dict[str, LaneSpec]] = {
    "tcbs": LaneSpec(
        client="vnbroker.broker.tcbs.client:TCBSBrokerClient",
        unsupported=_tcbs_unsupported(),
        features={
            # REQ-003(a): không provider nào có API watchlist của user.
            "watchlist": {
                "supported": False,
                "reason_code": PROVIDER_NO_API,
                "note": (
                    "TCBS không công bố API watchlist của user trong tài liệu "
                    "chính thức. `explorer/tcbs/tcbs_compatibility.py:296` có "
                    "một hàm tên là `get_watchlist` nhưng nó POST "
                    "`/ligo/v1/watchlist/preview` và trả kết quả của bộ lọc "
                    "(screener preview), KHÔNG phải danh sách mà người dùng đã "
                    "lưu — và không có create/update/delete."
                ),
            },
            # Bằng chứng chéo cho REQ-002, ghim thành capability để không phải
            # đo lại bằng mắt.
            "order_history_multi_day": {
                "supported": False,
                "reason_code": PATH_REMOVED_NOT_IN_SPEC,
                "note": (
                    "TCBS OpenAPI 1.0.0 không có endpoint lịch sử lệnh theo "
                    "khoảng ngày. `get_orders()` và `get_executions()` "
                    "(/aion/v1/accounts/{accountNo}/matching-details) trong spec "
                    "không khai báo tham số truy vấn nào ngoài `accountNo`. "
                    "Endpoint có `fromDate/toDate` trong spec là "
                    "`/erebos/v2/digital/trans-hist-cashStatements` — dòng tiền, "
                    "không phải lệnh. Endpoint lệnh duy nhất có phân trang là "
                    "`/khronos/v1/order/in-day`."
                ),
            },
        },
    ),
    "ssi": LaneSpec(
        client="vnbroker.broker.ssi.client:SSIBrokerClient",
        features={
            "watchlist": {
                "supported": False,
                "reason_code": PROVIDER_NO_API,
                "note": "SSI FastConnect không có API watchlist của user.",
            },
            "order_history_multi_day": {
                "supported": True,
                "reason_code": None,
                "note": (
                    "`get_order_history(account_no, from_date, to_date)` — "
                    "signature thật, đọc bằng `inspect`."
                ),
            },
        },
    ),
    "dnse": LaneSpec(
        client="vnbroker.connector.dnse.client:DNSEClient",
        registered=False,
        features={
            "watchlist": {
                "supported": False,
                "reason_code": PROVIDER_NO_API,
                "note": "DNSE OpenAPI không có API watchlist của user.",
            },
            "order_history_multi_day": {
                "supported": True,
                "reason_code": None,
                "note": (
                    "`get_order_history(account_no, market_type, from_date, "
                    "to_date, page_size, page_index)` — signature thật. "
                    "`from_date`/`to_date` là date string `yyyy-MM-dd`; "
                    "production bắt buộc CẢ HAI vế (thiếu một ⇒ "
                    "`400 from is required` / `400 to is required`), nên "
                    "truyền đúng một vế sẽ raise DNSEValidationError trước khi "
                    "gửi. `get_orders` tự điền `pageIndex=1` vì production "
                    "bắt buộc nó."
                ),
            },
        },
    ),
}


def _resolve_client(spec: LaneSpec) -> type[Any]:
    """Nạp class theo đường dẫn ``module:ClassName``."""
    module_name, _, class_name = spec.client.partition(":")
    resolved: Any = getattr(import_module(module_name), class_name)
    return cast("type[Any]", resolved)


def _public_methods(client: type) -> list[str]:
    return sorted(
        name
        for name, func in inspect.getmembers(client, predicate=inspect.isfunction)
        if not name.startswith("_")
    )


def capabilities(provider: str) -> dict[str, object]:
    """Mô tả một lane broker ở dạng máy đọc được. Không cần credential.

    Args:
        provider: ``"tcbs"`` | ``"ssi"`` | ``"dnse"`` (không phân biệt hoa/thường).

    Returns:
        ``{version, provider, registered, methods, features}``:

        * ``version`` — :data:`vnbroker.__version__`. Đặt ở đây để phía
          tiêu thụ phát hiện cache cũ mà không cần import thêm.
        * ``registered`` — provider có trong ``BrokerRegistry`` không. DNSE
          ``False`` vì nó không phải ``BaseBrokerClient``; đây là *thông tin*,
          không phải lỗi, và tách nó khỏi "có method hay không".
        * ``methods`` — mọi method công khai của client, kèm
          ``{supported, reason_code}``.
        * ``features`` — tính năng cấp sản phẩm (watchlist, order history
          nhiều ngày...), cùng hình dạng ``{supported, reason_code, note}``.

    Raises:
        KeyError: provider không thuộc bảng lane, kèm danh sách hợp lệ.
    """
    from vnbroker import __version__
    from vnbroker.broker.registry import BrokerRegistry

    key = provider.strip().lower()
    spec = LANES.get(key)
    if spec is None:
        raise KeyError(
            f"Lane broker '{provider}' không có trong bảng capability. "
            f"Đã biết: {', '.join(sorted(LANES))}"
        )

    client = _resolve_client(spec)
    methods = {
        name: {
            "supported": name not in spec.unsupported,
            "reason_code": spec.unsupported.get(name),
        }
        for name in _public_methods(client)
    }
    return {
        "version": __version__,
        "provider": key,
        "registered": spec.registered and BrokerRegistry.is_registered(key),
        "methods": methods,
        "features": {name: dict(value) for name, value in spec.features.items()},
    }
