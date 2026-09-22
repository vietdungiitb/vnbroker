"""
vnbroker.ui.registry — cây API tĩnh + tra cứu docstring cho Unified UI.

Tĩnh và deterministic (không inspect động) để snapshot test được.
Khi cây API cố ý đổi: sửa API_TREE + fixture tests/fixtures/ui/api_tree.txt
bằng tay, ghi lý do vào commit message.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Dict

from vnbroker.common import data as _data
from vnbroker.common import retail as _retail

API_TREE: Dict[str, Dict[str, str]] = {
    "Market": {
        "equity(symbol) -> Quote": "Giá cổ phiếu: history/intraday/price_depth.",
    },
    "Reference": {
        "company(symbol) -> Company": "Hồ sơ doanh nghiệp: profile/shareholders/....",
        "listing() -> Listing": "Danh sách mã: all_symbols/symbols_by_....",
    },
    "Fundamental": {
        "equity(symbol) -> Finance": "Tài chính: balance_sheet/income_statement/cash_flow/ratio.",
    },
    "Retail": {
        "gold(source, date) -> DataFrame": "Giá vàng SJC/BTMC.",
        "exchange_rate(date) -> DataFrame": "Tỷ giá Vietcombank.",
    },
}

_DOC_TARGETS: Dict[str, Callable[..., Any]] = {
    "Market.equity.history": _data.Quote.history,
    "Market.equity.intraday": _data.Quote.intraday,
    "Market.equity.price_depth": _data.Quote.price_depth,
    "Reference.company.profile": _data.Company.profile,
    "Reference.company.shareholders": _data.Company.shareholders,
    "Reference.listing.all_symbols": _data.Listing.all_symbols,
    "Fundamental.equity.balance_sheet": _data.Finance.balance_sheet,
    "Fundamental.equity.income_statement": _data.Finance.income_statement,
    "Fundamental.equity.cash_flow": _data.Finance.cash_flow,
    "Fundamental.equity.ratio": _data.Finance.ratio,
    "Retail.gold": _retail.Retail.gold,
    "Retail.exchange_rate": _retail.Retail.exchange_rate,
}


def render_api_tree() -> str:
    """Render cây API thành text (dùng cho show_api + snapshot test)."""
    lines = ["vnbroker.ui"]
    groups = list(API_TREE.items())
    for gi, (group, methods) in enumerate(groups):
        prefix = "└── " if gi == len(groups) - 1 else "├── "
        lines.append(f"{prefix}{group}")
        items = list(methods.items())
        for mi, (sig, desc) in enumerate(items):
            sub = "    └── " if gi == len(groups) - 1 else "│   └── "
            lines.append(f"{sub}{sig}: {desc}")
            _ = mi
    return "\n".join(lines) + "\n"


def show_api() -> None:
    """In cây API Unified UI ra stdout."""
    print(render_api_tree(), end="")


def show_doc(topic: str) -> None:
    """
    In docstring của 1 API theo dotted path (vd "Market.equity.history").

    Raises:
        KeyError: topic không có trong registry (message liệt kê key hợp lệ).
    """
    target = _DOC_TARGETS.get(topic)
    if target is None:
        valid = ", ".join(sorted(_DOC_TARGETS))
        raise KeyError(f"Unknown topic {topic!r}. Valid: {valid}")
    print(inspect.getdoc(target) or "")
