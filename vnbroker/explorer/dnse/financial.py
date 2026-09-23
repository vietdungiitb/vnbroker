"""
Deprecated shim — use vnbroker.explorer.dnse.finance.DNSEFinance instead.

DNSE là nền tảng giao dịch chứng khoán, không cung cấp dữ liệu
báo cáo tài chính doanh nghiệp. Module này giữ lại để tương thích
import cũ; mọi logic nằm ở finance.DNSEFinance (trả empty DF có schema).
"""

import warnings

from vnbroker.explorer.dnse.finance import DNSEFinance

warnings.warn(
    "vnbroker.explorer.dnse.financial.Finance is deprecated; "
    "use vnbroker.explorer.dnse.finance.DNSEFinance instead.",
    DeprecationWarning,
    stacklevel=2,
)


class Finance(DNSEFinance):
    """Deprecated alias of DNSEFinance (empty-DF fallback)."""
