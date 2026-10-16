"""Đọc nhiều ``marketType`` trong một lần gọi — tường minh, có nhãn, fail-closed.

Tách khỏi :mod:`vnbroker.connector.dnse.client` vì file đó đã 675 dòng trước
khi thêm (ngân sách 800). Cùng cách làm với ``EquityWriteMixin`` bên
``broker/tcbs/equity.py``.

Vì sao cần
----------
``marketType`` là tham số **bắt buộc** của DNSE, và tập giá trị hợp lệ là
``{STOCK, DERIVATIVE}`` (xem :mod:`vnbroker.connector.dnse.constants`). Nên
muốn xem hết vị thế thì buộc phải hỏi từng market.

Cách làm sai đã đo ở phía vninvest::

    for market_type in ("ALL", "STOCK", "EQUITY"):
        try:
            raw = client.get_positions(..., market_type=market_type)
            break        # lần đầu không raise là break
        except Exception:
            ...

Giá trị sai thường bị server trả **HTTP 200 + body rỗng**, tức không raise,
tức ``break`` ngay ở ``ALL``: ``STOCK``/``EQUITY`` không bao giờ chạy và kết
quả là "không có vị thế nào" — một kết luận sai, im lặng. Đây là L-R01 ở dạng
đọc dữ liệu.

Cách đúng ở đây: hỏi **tất cả** market, gắn nhãn ``market_type`` lên từng
dòng để không thể lẫn, và để lỗi nổi lên thay vì trả bảng thiếu dữ liệu.
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

import pandas as pd

from vnbroker.connector.dnse.constants import MARKET_TYPES, validate_market_type

#: Cột nhãn market gắn vào mỗi dòng của các method ``*_all_markets``.
MARKET_TYPE_COLUMN = "market_type"


class MultiMarketMixin:
    """Các method đọc gộp nhiều market cho :class:`~vnbroker.connector.dnse.client.DNSEClient`.

    Mixin gọi lại chính các method single-market của client
    (``get_positions`` / ``get_order_history``) nên không có đường HTTP riêng:
    validate ``marketType`` và write gate vẫn đi qua một chỗ duy nhất.
    """

    @staticmethod
    def _collect_markets(
        fetch: Callable[[str], Any],
        market_types: Sequence[str] | None,
    ) -> pd.DataFrame:
        """Gọi ``fetch`` cho từng market, gộp kết quả, gắn nhãn từng dòng.

        Fail-closed: lỗi ở bất kỳ market nào nổi lên nguyên vẹn. Bảng "đúng
        một phần" tệ hơn lỗi tường minh — người đọc không có cách nào biết
        mình đang thiếu bao nhiêu (L-R01).

        Cột ``market_type`` luôn tồn tại, kể cả khi một market không có dòng
        nào, để kết quả không bao giờ mất dấu vết của việc nó đã được hỏi.
        """
        targets = (
            sorted(MARKET_TYPES)
            if market_types is None
            else [validate_market_type(m) for m in market_types]
        )
        frames: list[pd.DataFrame] = []
        for market in targets:
            result = fetch(market)
            frame = result if isinstance(result, pd.DataFrame) else _as_frame(result)
            frame = frame.copy()
            frame[MARKET_TYPE_COLUMN] = market
            frames.append(frame)
        if not frames:
            return pd.DataFrame(columns=[MARKET_TYPE_COLUMN])
        return pd.concat(frames, ignore_index=True)

    def get_positions_all_markets(
        self,
        account_no: str,
        market_types: Sequence[str] | None = None,
        dry_run: bool = False,
    ) -> pd.DataFrame:
        """Danh sách vị thế của MỌI market, mỗi dòng tự mang nhãn market.

        Args:
            account_no: Số tài khoản DNSE.
            market_types: Market cần hỏi. Mặc định toàn bộ
                :data:`~vnbroker.connector.dnse.constants.MARKET_TYPES`.
            dry_run: Chuyển tiếp xuống từng lần gọi.

        Returns:
            DataFrame các dòng của mọi market, có cột ``market_type``. Market
            không có dữ liệu thì không thêm dòng nào, cột vẫn còn.

        Raises:
            DNSEValidationError: ``market_types`` chứa giá trị không hợp lệ —
                ném ra **trước** khi hỏi market nào cả
                (``error_code="INVALID_MARKET_TYPE"``).
            DNSEBaseError: lỗi mạng/xác thực từ bất kỳ market nào.
        """
        return self._collect_markets(
            lambda market: self.get_positions(  # type: ignore[attr-defined]
                account_no=account_no, market_type=market, dry_run=dry_run
            ),
            market_types,
        )

    def get_order_history_all_markets(
        self,
        account_no: str,
        from_date: str,
        to_date: str,
        market_types: Sequence[str] | None = None,
        page_size: int | None = None,
        page_index: int | None = None,
        dry_run: bool = False,
    ) -> pd.DataFrame:
        """Lịch sử lệnh của MỌI market trong khoảng ngày, mỗi dòng có nhãn.

        Cùng lý do và cùng cơ chế với :meth:`get_positions_all_markets`.

        Args:
            account_no: Số tài khoản DNSE.
            from_date: Ngày bắt đầu, ``YYYY-MM-DD``.
            to_date: Ngày kết thúc, ``YYYY-MM-DD``.
            market_types: Market cần hỏi; mặc định toàn bộ ``MARKET_TYPES``.
            page_size: ``None`` = không gửi tham số phân trang.
            page_index: ``None`` = không gửi tham số phân trang.
            dry_run: Chuyển tiếp xuống từng lần gọi.

        Returns:
            DataFrame có cột ``market_type``.

        Raises:
            DNSEValidationError: ``market_types`` chứa giá trị không hợp lệ.
            DNSEBaseError: lỗi từ bất kỳ market nào.
        """
        return self._collect_markets(
            lambda market: self.get_order_history(  # type: ignore[attr-defined]
                account_no=account_no,
                market_type=market,
                from_date=from_date,
                to_date=to_date,
                page_size=page_size,
                page_index=page_index,
                dry_run=dry_run,
            ),
            market_types,
        )


def _as_frame(payload: Any) -> pd.DataFrame:
    """Ép payload về DataFrame qua đúng hàm chuẩn hoá của client."""
    from vnbroker.connector.dnse.client import DNSEClient

    return DNSEClient.normalize_payload(payload)
