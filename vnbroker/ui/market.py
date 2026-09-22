"""
vnbroker.ui.market — Market: truy cập dữ liệu thị trường, không cần biết source.

Mỏng: delegate về vnbroker.common.data. Không logic wire mới.
"""

from __future__ import annotations

from vnbroker.common.data import Quote


class Market:
    """
    Nhóm dữ liệu thị trường (giá, bảng giá).

    Example:
        >>> mkt = Market(source="KBS")
        >>> hist = mkt.equity("SSI").history(start="2026-01-01")
    """

    def __init__(self, source: str = "KBS", show_log: bool = True) -> None:
        self.source = source
        self.show_log = show_log

    def equity(self, symbol: str) -> Quote:
        """
        Truy cập giá cổ phiếu theo mã.

        Returns:
            Quote đã gắn symbol + source (history/intraday/price_depth).
        """
        return Quote(symbol, self.source, show_log=self.show_log)
