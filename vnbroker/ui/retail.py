"""
vnbroker.ui.retail — Retail UI: giá vàng, tỷ giá (kế thừa common.retail.Retail).

Không logic mới — alias rõ namespace vnbroker.ui cho Unified UI.
"""

from __future__ import annotations

from vnbroker.common.retail import (
    BTMC_COLUMNS,
    BTMC_SOURCE,
    SJC_COLUMNS,
    SJC_SOURCE,
    VCB_COLUMNS,
    VCB_SOURCE,
    Retail as CommonRetail,
)

__all__ = [
    "Retail",
    "CommonRetail",
    "SJC_SOURCE",
    "BTMC_SOURCE",
    "VCB_SOURCE",
    "SJC_COLUMNS",
    "BTMC_COLUMNS",
    "VCB_COLUMNS",
]


class Retail(CommonRetail):
    """
    Nhóm dữ liệu bán lẻ (kế thừa toàn bộ common.retail.Retail).

    Example:
        >>> retail = Retail()
        >>> sjc = retail.gold(source="sjc")
    """
