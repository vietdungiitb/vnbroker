"""
vnbroker.ui — Unified UI: truy cập dữ liệu theo nhóm, không cần biết source.

    from vnbroker.ui import Market, Reference, Fundamental, Retail, show_api, show_doc
"""

from vnbroker.ui.fundamental import Fundamental
from vnbroker.ui.market import Market
from vnbroker.ui.reference import Reference
from vnbroker.ui.registry import show_api, show_doc
from vnbroker.ui.retail import Retail

__all__ = [
    "Market",
    "Reference",
    "Fundamental",
    "Retail",
    "show_api",
    "show_doc",
]
