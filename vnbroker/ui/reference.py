"""
vnbroker.ui.reference — Reference: hồ sơ, niêm yết, tra cứu mã.

Mỏng: delegate về vnbroker.common.data. Không logic wire mới.
"""

from __future__ import annotations

from vnbroker.common.data import Company, Listing


class Reference:
    """
    Nhóm dữ liệu tham chiếu (hồ sơ doanh nghiệp, danh sách mã).

    Example:
        >>> ref = Reference(source="KBS")
        >>> prof = ref.company("SSI").profile()
    """

    def __init__(self, source: str = "KBS", show_log: bool = True) -> None:
        self.source = source
        self.show_log = show_log

    def company(self, symbol: str) -> Company:
        """
        Truy cập hồ sơ doanh nghiệp theo mã.

        Returns:
            Company đã gắn symbol + source (profile/shareholders/...).
        """
        return Company(symbol, source=self.source, show_log=self.show_log)

    def listing(self) -> Listing:
        """
        Truy cập danh sách mã toàn thị trường.

        Returns:
            Listing đã gắn source (all_symbols/symbols_by_*...).
        """
        return Listing(source=self.source, show_log=self.show_log)
