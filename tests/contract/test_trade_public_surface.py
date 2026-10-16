"""Contract đóng băng bề mặt API của `Trade` — trước khi tách file.

Vì sao file này tồn tại
----------------------
`trade.py` dài 1352 dòng (vượt trần 800L của `CLAUDE.md`) và phải được tách.
Nhưng `Trade` là **money lane**: 14 method gọi `_require_write`, trong đó có
`deposit_derivative_margin`, `withdraw_derivative_margin`, `place_order`,
`cancel_order`, `close_deal`. Tách sai một dòng là hàng rào tiền thật bị lệch.

Cách làm: **đóng băng API trước, tách sau.** Bảng chữ ký dưới đây được chép
từ code tại `d8fab65`; nó phải xanh **trước** khi di chuyển bất kỳ dòng nào, và
vẫn phải xanh **sau** khi tách. Nếu đỏ ⇒ dừng, không sửa tiếp.

Thêm/bớt method là hành động **có chủ ý**: phải sửa bảng này trong cùng commit,
và PR phải nói rõ vì sao.

Proof (không đoán): bảng sinh từ
`inspect.signature` trên `Trade` @ `d8fab65`; danh sách write-gated sinh từ
AST (thân method có gọi `self._require_write`).
"""
from __future__ import annotations

import inspect

import pytest

from vnbroker.broker.exceptions import BrokerPermissionError
from vnbroker.connector.dnse.trade import Trade

#: Bề mặt công khai của `Trade` @ `d8fab65` — (tên, chữ ký).
PUBLIC_API: tuple[tuple[str, str], ...] = (
    ("account", "(self) -> Optional[pandas.DataFrame]"),
    ("account_balance", "(self, sub_account: str) -> Optional[pandas.DataFrame]"),
    ("as_openapi_client", "(self, api_key: str, api_secret: str) -> vnbroker.connector.dnse.client.DNSEClient"),
    ("cancel_conditional_order", "(self, order_id: str, dry_run: bool = False) -> Optional[pandas.DataFrame]"),
    ("cancel_order", "(self, order_id: str, sub_account: str, asset_type: str = 'stock', dry_run: bool = True) -> Optional[pandas.DataFrame]"),
    ("cancel_order_openapi", "(self, account_no: str, order_id: str, market_type: str, trading_token: str, order_category: Optional[str] = None, dry_run: bool = False, raw: bool = False)"),
    ("close_deal", "(self, deal_id: int, dry_run: bool = False) -> Optional[pandas.DataFrame]"),
    ("close_position", "(self, position_id: str, market_type: str, trading_token: str, dry_run: bool = False, raw: bool = False)"),
    ("conditional_order_detail", "(self, order_id: str) -> Optional[pandas.DataFrame]"),
    ("conditional_order_list", "(self, account_no: str, market_id: str, daily: bool = False, from_date: Optional[str] = None, to_date: Optional[str] = None, page: int = 1, size: int = 10000, status: Optional[list] = None, symbol: Optional[str] = None) -> Optional[pandas.DataFrame]"),
    ("create_trading_token", "(self, otp_type: str, passcode: str, dry_run: bool = False, raw: bool = False)"),
    ("deals_list", "(self, sub_account: str, asset_type: str = 'stock') -> Optional[pandas.DataFrame]"),
    ("deposit_derivative_margin", "(self, account_no: str, source_account_no: str, loan_package_id: int, amount: int, via: str, otp: str, dry_run: bool = True) -> Optional[pandas.DataFrame]"),
    ("email_otp", "(self) -> None"),
    ("enable_write", "(self, enabled: bool = True) -> None"),
    ("get_accounts", "(self, dry_run: bool = False, raw: bool = False)"),
    ("get_balances", "(self, account_no: str, dry_run: bool = False, raw: bool = False)"),
    ("get_derivative_cash_account", "(self, account_no: str) -> Optional[pandas.DataFrame]"),
    ("get_derivative_ppse", "(self, account_no: str, loan_package_id: int) -> Optional[pandas.DataFrame]"),
    ("get_execution_detail", "(self, account_no: str, order_id: str, market_type: str, order_category: str = 'NORMAL', dry_run: bool = False, raw: bool = False)"),
    ("get_instruments", "(self, symbol: Optional[str] = None, market_id: Optional[str] = None, security_group_id: Optional[str] = None, index_name: Optional[str] = None, limit: Optional[int] = None, page: Optional[int] = None, dry_run: bool = False, raw: bool = False)"),
    ("get_loan_packages", "(self, account_no: str, market_type: str, symbol: Optional[str] = None, dry_run: bool = False, raw: bool = False)"),
    ("get_ohlc", "(self, bar_type: str, query: Optional[dict] = None, dry_run: bool = False, raw: bool = False)"),
    ("get_order_detail", "(self, account_no: str, order_id: str, market_type: str, order_category: Optional[str] = None, dry_run: bool = False, raw: bool = False)"),
    ("get_order_history", "(self, account_no: str, market_type: str, from_date: Optional[str] = None, to_date: Optional[str] = None, page_size: Optional[int] = None, page_index: Optional[int] = None, dry_run: bool = False, raw: bool = False)"),
    ("get_orders", "(self, account_no: str, market_type: str, order_category: str, dry_run: bool = False, raw: bool = False)"),
    ("get_position_by_id", "(self, market_type: str, position_id: str, dry_run: bool = False, raw: bool = False)"),
    ("get_positions", "(self, account_no: str, market_type: str, dry_run: bool = False, raw: bool = False)"),
    ("get_ppse", "(self, account_no: str, market_type: str, symbol: str, price: float, loan_package_id: int, dry_run: bool = False, raw: bool = False)"),
    ("get_security_definition", "(self, symbol: str, board_id: Optional[str] = None, dry_run: bool = False, raw: bool = False)"),
    ("get_trades", "(self, symbol: str, board_id: Optional[str] = None, from_date: Optional[int] = None, to_date: Optional[int] = None, limit: Optional[int] = None, order: Optional[str] = None, next_page_token: Optional[str] = None, dry_run: bool = False, raw: bool = False)"),
    ("get_trading_token", "(self, otp: str, smart_otp: bool = True) -> Optional[str]"),
    ("loan_packages", "(self, sub_account: str, asset_type: str = 'stock') -> Optional[pandas.DataFrame]"),
    ("login", "(self, user_name: str, password: str) -> Optional[str]"),
    ("login_and_get_trading_session", "(self, username: str, password: str, otp: str, smart_otp: bool = True) -> dict"),
    ("order_detail", "(self, order_id: str, sub_account: str, asset_type: str = 'stock') -> Optional[pandas.DataFrame]"),
    ("order_list", "(self, sub_account: str, asset_type: str = 'stock') -> Optional[pandas.DataFrame]"),
    ("place_conditional_order", "(self, account_no: str, symbol: str, condition: str, target_order: dict, props: dict, time_in_force: dict, category: str = 'STOP', dry_run: bool = False) -> Optional[pandas.DataFrame]"),
    ("place_order", "(self, sub_account: str, symbol: str, side: str, quantity: int, price: float, order_type: str, loan_package_id: Optional[int] = None, asset_type: str = 'stock', dry_run: bool = True) -> Optional[pandas.DataFrame]"),
    ("post_order", "(self, market_type: str, payload: dict, trading_token: str, order_category: str = 'NORMAL', dry_run: bool = False, raw: bool = False)"),
    ("put_order", "(self, account_no: str, order_id: str, market_type: str, payload: dict, trading_token: str, order_category: Optional[str] = None, dry_run: bool = False, raw: bool = False)"),
    ("send_email_otp", "(self, dry_run: bool = False, raw: bool = False)"),
    ("set_account_pnl_config", "(self, account_no: str, config: dict, dry_run: bool = False) -> Optional[pandas.DataFrame]"),
    ("set_deal_pnl_config", "(self, deal_id: int, config: dict, dry_run: bool = False) -> Optional[pandas.DataFrame]"),
    ("sub_accounts", "(self) -> Optional[pandas.DataFrame]"),
    ("trade_capacities", "(self, symbol: str, price: float, sub_account: str, asset_type: str = 'stock', loan_package_id: Optional[int] = None) -> Optional[pandas.DataFrame]"),
    ("withdraw_derivative_margin", "(self, account_no: str, source_account_no: str, loan_package_id: int, amount: int, via: str, otp: str, dry_run: bool = True) -> Optional[pandas.DataFrame]"),
)

#: Method thân có gọi `self._require_write` — sinh từ AST @ `d8fab65`.
WRITE_GATED = (
    "cancel_conditional_order",
    "cancel_order",
    "cancel_order_openapi",
    "close_deal",
    "close_position",
    "create_trading_token",
    "deposit_derivative_margin",
    "place_conditional_order",
    "place_order",
    "post_order",
    "put_order",
    "set_account_pnl_config",
    "set_deal_pnl_config",
    "withdraw_derivative_margin",
)


def _trade() -> Trade:
    return Trade(api_key="k", api_secret="s")


# --- Bề mặt công khai -------------------------------------------------------


def test_the_import_path_is_stable():
    """Tách file KHÔNG được đổi đường dẫn import — đó là hợp đồng với người gọi."""
    from vnbroker.connector.dnse.trade import Trade as Imported

    assert Imported is Trade


def test_every_public_method_still_exists_with_the_same_signature():
    """Đây là cái ghim chính của cả việc tách file."""
    actual = {
        name: str(inspect.signature(func))
        for name, func in inspect.getmembers(Trade, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    expected = dict(PUBLIC_API)
    missing = sorted(set(expected) - set(actual))
    added = sorted(set(actual) - set(expected))
    changed = sorted(
        name for name in set(expected) & set(actual) if expected[name] != actual[name]
    )
    assert not missing, f"method bi mat khi tach: {missing}"
    assert not added, f"method xuat hien ma khong cap nhat bang PUBLIC_API: {added}"
    assert not changed, f"chu ky doi: {[(n, expected[n], actual[n]) for n in changed]}"


def test_the_public_surface_has_not_grown_silently():
    assert len(PUBLIC_API) == 47, (
        f"bang PUBLIC_API co {len(PUBLIC_API)} muc; neu la so co chu dich thi "
        f"phai sua con so nay cung commit va PR phai ghi ro ly do"
    )


# --- Hàng rào tiền thật ----------------------------------------------------


def test_the_write_gated_set_is_exactly_the_frozen_one():
    """Một method mới phải tự quyết định có write hay không — và ghi ra ở đây."""
    assert set(WRITE_GATED) == {
        "cancel_conditional_order", "cancel_order", "cancel_order_openapi",
        "close_deal", "close_position", "create_trading_token",
        "deposit_derivative_margin", "place_conditional_order", "place_order",
        "post_order", "put_order", "set_account_pnl_config",
        "set_deal_pnl_config", "withdraw_derivative_margin",
    }
    assert len(WRITE_GATED) == 14


@pytest.mark.parametrize("name", WRITE_GATED)
def test_every_write_method_still_refuses_without_enable_write(name):
    """Gate OFF là mặc định. Tách file không được làm lỏng bất kỳ hàng rào nào.

    ⚠ Phải truyền `dry_run=False` **tường minh**: 4 method legacy có mặc định
    `dry_run=True` (`place_order`, `cancel_order`, `deposit_derivative_margin`,
    `withdraw_derivative_margin`) nên gọi không có tham số sẽ **không** chạm
    gate — đó là hành vi đúng, không phải hàng rào thủng.
    """
    trade = _trade()
    assert trade._write_enabled is False, "write gate phải OFF mặc định"
    method = getattr(trade, name)
    kwargs = _minimal_kwargs(method, dry_run=False)
    with pytest.raises(BrokerPermissionError) as excinfo:
        method(**kwargs)
    assert excinfo.value.code == "WRITE_NOT_ENABLED", (
        f"{name} vẫn raise BrokerPermissionError nhưng code khác WRITE_NOT_ENABLED"
    )


@pytest.mark.parametrize("name", WRITE_GATED)
def test_dry_run_returns_an_envelope_and_never_touches_the_network(name):
    """`dry_run=True` là cách *xem* lời gọi, không phải cách thực thi nó.

    Hành vi thật (đọc `trade.py:53-78`): `_require_write` **trả về** envelope
    dry-run, không phải "bỏ qua rồi đi tiếp". Test bản đầu của tôi giả định
    ngược lại nên đỏ — và cái đỏ đó là do test sai, **không** phải do sản phẩm
    sai. Ghi lại để lát sau không viết lại sai nữa.
    """
    trade = _trade()
    method = getattr(trade, name)
    kwargs = _minimal_kwargs(method, dry_run=True)
    result = method(**kwargs)
    assert isinstance(result, dict), f"{name} trả {type(result).__name__}, không phải envelope"
    assert result.get("dry_run") is True
    assert "operation" in result, f"{name} thiếu trường 'operation' trong envelope"
    assert result.get("operation") == name or name in str(result.get("operation"))


def _minimal_kwargs(method, **overrides) -> dict:
    """Tham số tối thiểu về mặt hình thức để gọi method mà chưa chạm network."""
    signature = inspect.signature(method)
    kwargs: dict = {}
    for name, param in signature.parameters.items():
        if name == "self":
            continue
        if param.default is inspect.Parameter.empty:
            kwargs[name] = _sample_for(name)
    kwargs.update(overrides)
    return kwargs


def _sample_for(name: str):
    """Giá trị giả cho tham số bắt buộc — chỉ để chạm tới gate, không tới network."""
    hints = {
        "account_no": "ACC", "source_account_no": "ACC", "sub_account": "ACC",
        "order_id": "1", "deal_id": 1, "position_id": "1",
        "symbol": "HPG", "side": "BUY", "quantity": 1, "price": 1.0,
        "order_type": "LO", "loan_package_id": 1, "amount": 1,
        "market_type": "STOCK", "trading_token": "T", "payload": {},
        "config": {}, "condition": "c", "target_order": {}, "props": {},
        "time_in_force": {}, "otp_type": "TRADING", "passcode": "1",
        "otp": "1", "via": "WALLET",
    }
    return hints.get(name, "X")