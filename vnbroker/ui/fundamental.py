"""
vnbroker.ui.fundamental — Fundamental: báo cáo tài chính, chỉ số.

Mỏng: delegate về vnbroker.common.data.Finance. Không logic wire mới.
"""

from __future__ import annotations

from vnbroker.common.data import Finance


class Fundamental:
    """
    Nhóm dữ liệu cơ bản doanh nghiệp.

    Example:
        >>> fa = Fundamental(source="KBS")
        >>> bs = fa.equity("SSI").balance_sheet(period="year")
    """

    def __init__(self, source: str = "KBS", show_log: bool = True) -> None:
        self.source = source
        self.show_log = show_log

    def equity(self, symbol: str) -> Finance:
        """
        Truy cập tài chính doanh nghiệp theo mã.

        Returns:
            Finance đã gắn symbol + source
            (balance_sheet/income_statement/cash_flow/ratio).
        """
        return Finance(symbol, source=self.source, show_log=self.show_log)
