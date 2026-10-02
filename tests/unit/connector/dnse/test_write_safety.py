"""P0-2: mọi đường GHI của connector/dnse phải có `dry_run` và `write_gate`.

Bối cảnh
--------
`vnbroker/connector/dnse/trade.py` có hai nhóm hàm:

- **Đọc** (`get_accounts`, `get_balances`, `get_orders`…): có tham số ``dry_run``
  với mặc định ``False`` — vô hại vì không thay đổi trạng thái.
- **Ghi** (``place_order``, ``cancel_order``, ``deposit_derivative_margin``,
  ``withdraw_derivative_margin``): **không có** ``dry_run``, **không có**
  ``@write_gate`` → gửi thật ngay lập tức.

Việc gửi tiền/rút tiền không có hàng rào là rủi ro mất tiền thật: một lệnh gõ
sai là tiền đi luôn.

Hợp đồng:
1. Mọi hàm ghi có ``dry_run: bool = True`` (mặc định AN TOÀN).
2. ``dry_run=True`` → KHÔNG gọi network.
3. Có ``@write_gate`` để phải ``session.enable_write()`` mới thực thi.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from vnbroker.connector.dnse.trade import Trade

ROOT = Path(__file__).resolve().parents[4]
TRADE_PY = ROOT / "vnbroker" / "connector" / "dnse" / "trade.py"

# Hàm GHI — thay đổi trạng thái tiền/lệnh ở phía broker.
WRITE_METHODS = [
    "place_order",
    "cancel_order",
    "deposit_derivative_margin",
    "withdraw_derivative_margin",
]


# ------------------------------------------------- kiểm tra bằng source


def _write_method_names() -> set[str]:
    """Tên các hàm ghi tìm thấy ở AST (không phụ thuộc runtime)."""
    tree = ast.parse(TRADE_PY.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "Trade":
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(item.name)
    return names


@pytest.mark.parametrize("method", WRITE_METHODS)
def test_write_method_exists(method: str) -> None:
    assert method in _write_method_names(), f"Không tìm thấy {method} trong Trade"


@pytest.mark.parametrize("method", WRITE_METHODS)
def test_write_method_has_dry_run_default_true(method: str) -> None:
    """Hàm ghi phải có `dry_run` MẶC ĐỊNH True."""
    fn = getattr(Trade, method)
    sig = inspect.signature(fn)

    assert "dry_run" in sig.parameters, (
        f"{method} thiếu tham số `dry_run` — lệnh gửi thật ngay không có hàng rào."
    )
    default = sig.parameters["dry_run"].default
    assert default is True, (
        f"{method}: dry_run mặc định là {default!r}, phải là True "
        f"(an toàn — người dùng phải CHỦ ĐỘNG bật mới gửi thật)."
    )


@pytest.mark.parametrize("method", WRITE_METHODS)
def test_write_method_guards_before_any_network_call(method: str) -> None:
    """Guard phải chạy TRƯỚC mọi network call — không phải ở câu lệnh đầu tiên.

    Thứ tự đúng: validate input → guard `dry_run` → network. Nếu guard đặt quá
    muộn (sau khi đã dựng URL / đọc token) thì vẫn OK, nhưng nếu đặt quá sớm
    (trước validation) thì dry-run sẽ trả envelope "OK" cho input mà lúc gửi
    thật chắc chắn raise — tức dry-run nói dối. Cả hai chiều đều phải tránh.

    Vì vậy test này kiểm tra vị trí TƯƠNG ĐỐI: `_require_write` phải xuất hiện
    trước mọi câu lệnh có khả năng chạm network (`requests.*`, `url =`).
    """
    tree = ast.parse(TRADE_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "Trade":
            continue
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if item.name != method:
                continue

            body = list(item.body)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]

            guard_at = None
            network_at = None
            for offset, stmt in enumerate(body):
                if guard_at is None and _calls_require_write(stmt):
                    guard_at = offset
                if network_at is None and _may_hit_network(stmt):
                    network_at = offset

            assert guard_at is not None, (
                f"{method}: không gọi `_require_write` — lệnh gửi thật không hàng rào."
            )
            assert network_at is None or guard_at < network_at, (
                f"{method}: guard ở câu {guard_at} nhưng câu {network_at} đã có thể "
                f"chạm network — phải guard trước mọi network call."
            )
            return
    pytest.fail(f"Không tìm thấy {method}")


def _calls_require_write(stmt: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "_require_write"
        for n in ast.walk(stmt)
    )


def _may_hit_network(stmt: ast.AST) -> bool:
    """Câu lệnh có khả năng chạm network không (requests.*, url=, .post/.get)."""
    for n in ast.walk(stmt):
        if isinstance(n, ast.Attribute) and n.attr in {"get", "post", "put", "delete"}:
            return True
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == "url":
                    return True
    return False


# ------------------------------------------------- hành vi runtime


def test_dry_run_does_not_call_network() -> None:
    """dry_run=True (mặc định) → trả envelope, KHÔNG chạm network."""
    trade = Trade(api_key="k", api_secret="s")
    calls: list[str] = []

    class GuardSession:
        def request(self, *a, **kw):  # requests.Session.request
            calls.append("requests")
            raise AssertionError("Không được gọi mạng khi dry_run")

    # Chặn mọi lối ra: cả requests lẫn openapi client.
    import requests as _rq

    orig_get, orig_post = _rq.get, _rq.post
    _rq.get = _rq.post = lambda *a, **kw: calls.append("http") or GuardSession().request()

    try:
        result = trade.place_order(
            sub_account="123",
            symbol="ACB",
            side="buy",
            quantity=100,
            price=10.0,
            order_type="LO",
        )
    finally:
        _rq.get, _rq.post = orig_get, orig_post

    assert calls == [], f"Không được gọi network khi dry_run, thực tế: {calls}"
    assert result is not None
    assert result.get("dry_run") is True, (
        f"Kết quả dry_run phải nêu rõ dry_run=True: {result}"
    )
    assert result.get("operation") == "place_order"


@pytest.mark.parametrize("method,kwargs", [
    ("cancel_order", {"order_id": "X", "sub_account": "1"}),
    ("deposit_derivative_margin", {
        "account_no": "1", "source_account_no": "2", "loan_package_id": 1,
        "amount": 1000, "via": "app", "otp": "123456"}),
    ("withdraw_derivative_margin", {
        "account_no": "1", "source_account_no": "2", "loan_package_id": 1,
        "amount": 1000, "via": "app", "otp": "123456"}),
])
def test_dry_run_blocks_every_write_path(method: str, kwargs: dict) -> None:
    """Mọi đường ghi — kể cả nạp/rút ký quỹ — phải chặn ở dry_run."""
    trade = Trade(api_key="k", api_secret="s")
    result = getattr(trade, method)(**kwargs)

    assert result.get("dry_run") is True, f"{method} không chặn ở dry_run: {result}"
    assert result.get("operation") == method


def test_write_requires_explicit_enable_write() -> None:
    """dry_run=False mà chưa enable_write() → ném lỗi, KHÔNG gửi."""
    from vnbroker.broker.exceptions import BrokerPermissionError

    trade = Trade(api_key="k", api_secret="s")
    # Mặc định KHÔNG được bật.
    assert trade._write_enabled is False

    with pytest.raises(BrokerPermissionError):
        trade.place_order(
            sub_account="123", symbol="ACB", side="buy",
            quantity=100, price=10.0, order_type="LO", dry_run=False,
        )


def test_enable_write_is_opt_in() -> None:
    """enable_write() chỉ khiến phép; dry_run vẫn là mặc định an toàn."""
    trade = Trade(api_key="k", api_secret="s")
    assert trade._write_enabled is False

    trade.enable_write()
    assert trade._write_enabled is True

    # dry_run mặc định vẫn chặn — enable_write không tự gửi lệnh.
    result = trade.place_order(
        sub_account="123", symbol="ACB", side="buy",
        quantity=100, price=10.0, order_type="LO",
    )
    assert result.get("dry_run") is True
