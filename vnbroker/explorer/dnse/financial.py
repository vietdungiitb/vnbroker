"""
Module báo cáo tài chính cho nguồn dữ liệu DNSE.

DNSE là nền tảng giao dịch chứng khoán, không cung cấp dữ liệu
báo cáo tài chính doanh nghiệp (bảng cân đối kế toán, kết quả kinh doanh,
lưu chuyển tiền tệ). Vui lòng sử dụng nguồn KBS hoặc TCBS thay thế.
"""


class Finance:
    """
    Lớp truy cập dữ liệu tài chính từ DNSE.

    Lưu ý: DNSE không hỗ trợ báo cáo tài chính doanh nghiệp.
    Hãy sử dụng nguồn KBS hoặc TCBS để lấy dữ liệu tài chính.

    Ví dụ thay thế:
        >>> from vnbroker.explorer.kbs.financial import Finance
        >>> f = Finance('ACB')
        >>> df = f.income_statement(period='year')
    """

    _NOT_SUPPORTED_MSG = (
        "DNSE không hỗ trợ dữ liệu báo cáo tài chính doanh nghiệp. "
        "Vui lòng sử dụng nguồn KBS hoặc TCBS thay thế.\n"
        "  Ví dụ: from vnbroker.explorer.kbs.financial import Finance"
    )

    def __init__(self, symbol: str, **kwargs):
        raise NotImplementedError(self._NOT_SUPPORTED_MSG)

    def income_statement(self, *args, **kwargs):
        raise NotImplementedError(self._NOT_SUPPORTED_MSG)

    def balance_sheet(self, *args, **kwargs):
        raise NotImplementedError(self._NOT_SUPPORTED_MSG)

    def cash_flow(self, *args, **kwargs):
        raise NotImplementedError(self._NOT_SUPPORTED_MSG)

    def financial_ratios(self, *args, **kwargs):
        raise NotImplementedError(self._NOT_SUPPORTED_MSG)
