from __future__ import annotations

from datetime import datetime
from typing import Any

from vnbroker.connector.dnse.core.errors import DNSEValidationError
from vnbroker.connector.dnse.core.http_client import DNSEHttpClient
from vnbroker.connector.dnse.core.time_utils import (
    VIETNAM_TZ,
    is_same_vn_day,
    vn_day_bounds,
)

#: Ghi nhắc đơn vị, dùng chung cho cả 5 method phân trang. Đo production
#: 2026-10-16: milliseconds trả `400 range exceeds maximum time range`.
_SECONDS_NOTE = (
    "`from_date`/`to_date` là unix **GIÂY** (không phải milliseconds — "
    "truyền milliseconds sẽ bị server trả 400)."
)

#: Định dạng ngày mà một số endpoint DNSE yêu cầu (khác unix giây của
#: price endpoints). Đo production 2026-10-16:
#: `400 invalid param 'time', expected format yyyy-MM-dd`.
_DATE_FORMAT = "%Y-%m-%d"


def _require_date_string(value: object, param: str) -> str:
    """Chặn số nguyên ở cửa một endpoint chỉ nhận chuỗi ngày.

    Không có kiểu nào ở đây tự bắt được lỗi: `time: int` là hợp lệ về mặt Python
    và lại là cách mọi người mặc định nghĩ khi thấy một con số thời gian. Vì vậy
    phải kiểm nội dung, không chỉ kiểu.
    """
    if isinstance(value, str):
        try:
            datetime.strptime(value.strip(), _DATE_FORMAT)
        except ValueError as exc:
            raise DNSEValidationError(
                message=(
                    f"{param}={value!r} không phải ngày đúng định dạng "
                    f"'{_DATE_FORMAT}'. DNSE yêu cầu CHUỖI NGÀY cho tham số này "
                    f"— ví dụ '2026-10-16' — KHÔNG phải unix giây."
                ),
                error_code="INVALID_TIME_FORMAT",
                status_code=400,
            ) from exc
        return value.strip()

    raise DNSEValidationError(
        message=(
            f"{param}={value!r} sai kiểu ({type(value).__name__}). Tham số này "
            f"phải là CHUỖI NGÀY '{_DATE_FORMAT}', ví dụ '2026-10-16' — không "
            f"phải unix giây. Gửi số nguyên sẽ bị server trả "
            f"`400 invalid param '{param}', expected format {_DATE_FORMAT}`."
        ),
        error_code="INVALID_TIME_FORMAT",
        status_code=400,
    )


class MarketService:
    def __init__(self, http: DNSEHttpClient):
        self._http = http

    def get_security_definition(
        self,
        symbol: str,
        board_id: str | None = None,
        dry_run: bool = False,
    ):
        """Định nghĩa mã bảo chứng. Path theo SDK `client.py:256`.

        ⚠ **`board_id` chưa tài liệu hoá — đừng đoán giá trị.**

        Đo production 2026-10-16: gọi **không** kèm `board_id` ⇒ **200**;
        kèm `board_id` bất kể giá trị nào trong 24 ứng viên đã thử (`HOSE`,
        `HOSE_STOCK`, `HNX`, `HNX_STOCK`, `UPCOM`, `HOSE.ETF`, `HOSE_INDEX`,
        `HOSE.DERIVATIVE`, `DOWNNEX`, `ETF`, `STOCK`, `0`–`5`, …) ⇒ **500
        Internal error**. Tức là tham số này thực tế **không dùng được**, chứ
        không phải "thiếu thì lỗi".

        Repo có manh mối (`connector/dnse/websocket.py:19,278` dùng mã kiểu
        `G1`/`STO.G1` cho kênh WS) nhưng chưa thử được với REST — xem
        `scripts/probe_dnse_readonly.py`, mục `D10`. **Không** thêm tập giá trị
        đoán vào đây: bịa enum tạo cảm giác an toàn giả (L-P06). Khi DNSE công bố,
        cập nhật cả docstring này.
        """
        query = {"boardId": board_id} if board_id else None
        return self._http.request(
            "GET",
            f"/price/{symbol}/secdef",
            query=query,
            dry_run=dry_run,
        )

    def get_ohlc(self, bar_type: str, query: dict | None = None, dry_run: bool = False):
        merged_query = dict(query or {})
        # Allow user to specify type (STOCK, DERIVATIVE, INDEX), default to STOCK
        if "type" not in merged_query:
            merged_query["type"] = "STOCK"
        # bar_type is the resolution (e.g., "1D", "D", "1", "5", "15", "30", "60")
        merged_query["resolution"] = bar_type
        return self._http.request("GET", "/price/ohlc", query=merged_query, dry_run=dry_run)

    def get_close_price(self, symbol: str, dry_run: bool = False):
        """Get latest closing price for a symbol."""
        return self._http.request("GET", f"/price/{symbol}/close", dry_run=dry_run)

    def get_latest_trade(self, symbol: str, dry_run: bool = False):
        """Get most recent trade for a symbol."""
        # DNSE uses /price/{symbol}/trades/latest (not /latest-trade)
        return self._http.request("GET", f"/price/{symbol}/trades/latest", dry_run=dry_run)

    def get_working_dates(self, dry_run: bool = False):
        """Ngày giao dịch. Path: `GET /market/working-dates` (SDK `client.py:447-451`).

        ⚠ **Đính chính một kết luận sai đã có trong chính file này.** Docstring cũ
        ghi *"DNSE OpenAPI does not have a dedicated working-dates endpoint"* và
        method trả `({"dates": []}, None)` — một tuple cố ý đảo, khiến
        `_resolve_output` unpack nhầm và người gọi nhận `None` mà không có request
        nào đi ra. Đó là "thành công rỗng": trông như server nói không có ngày
        giao dịch, trong khi thật ra chưa ai hỏi (L-R01).

        Đo production 2026-10-16 (không VPN): `200`, `{"workingDates": [...257]}`
        ⇒ endpoint **có thật**. Vậy nên sửa path, không xoá method.

        Không gửi `marketType`: đo cho thấy thêm tham số đó trả `404`.
        """
        return self._http.request("GET", "/market/working-dates", dry_run=dry_run)

    def get_trades(
        self,
        symbol: str,
        board_id: str | None = None,
        from_date: int | None = None,
        to_date: int | None = None,
        limit: int | None = None,
        order: str | None = None,
        next_page_token: str | None = None,
        dry_run: bool = False,
    ) -> tuple[int | None, Any]:
        """Giao dịch khớp lệnh. Path theo SDK: `/price/{symbol}/trades`.

        Dùng chung `_history_query` với 4 method kia — trước đây method này dựng
        dict thủ công trong khi những method khác gọi helper, nên một thay đổi tên
        key chỉ đạt được nửa bộ method.

        """ + _SECONDS_NOTE
        return self._http.request(
            "GET",
            f"/price/{symbol}/trades",
            query=self._history_query(
                board_id, from_date, to_date, limit, order, next_page_token
            )
            or None,
            dry_run=dry_run,
        )

    @staticmethod
    def _history_query(
        board_id: str | None = None,
        from_date: int | None = None,
        to_date: int | None = None,
        limit: int | None = None,
        order: str | None = None,
        next_page_token: str | None = None,
    ) -> dict[str, object]:
        """Query dùng chung cho các endpoint phân trang theo thời gian.

        Tên key lấy từ SDK `dnse-tech/openapi-sdk` `python/dnse/api/client.py:331-343`
        — `boardId` / `from` / `to` / `limit` / `order` / `nextPageToken`.
        """
        query: dict[str, object] = {}
        if board_id is not None:
            query["boardId"] = board_id
        if from_date is not None:
            query["from"] = from_date
        if to_date is not None:
            query["to"] = to_date
        if limit is not None:
            query["limit"] = limit
        if order is not None:
            query["order"] = order
        if next_page_token is not None:
            query["nextPageToken"] = next_page_token
        return query

    def get_quotes(
        self,
        symbol: str,
        board_id: str | None = None,
        from_date: int | None = None,
        to_date: int | None = None,
        limit: int | None = None,
        order: str | None = None,
        next_page_token: str | None = None,
        dry_run: bool = False,
    ) -> tuple[int | None, Any]:
        """Nội giá (Lớp A) — chuẩn hoá về form chung của vnbroker.

        Path theo SDK `client.py:346`: `GET /price/{symbol}/quotes`.

        ⚠ Cảnh báo đã đo: server gửi `bid[].qtty` / `offer[].qtty` (tài liệu ghi
        `quantity`). Map sang `quantity` sẽ **im lặng trả 0 khối lượng**.
        Chi tiết: `docs/NORMALISATION_POLICY.md` §3.1.
        """
        return self._http.request(
            "GET",
            f"/price/{symbol}/quotes",
            query=self._history_query(
                board_id, from_date, to_date, limit, order, next_page_token
            ) or None,
            dry_run=dry_run,
        )

    def get_latest_quote(
        self,
        symbol: str,
        board_id: str | None = None,
        dry_run: bool = False,
    ) -> tuple[int | None, Any]:
        """Báo giá mới nhất. Path theo SDK `client.py:424`.

        Chỉ nhận `board_id` — SDK **không** có from/to cho endpoint này, nên cũng
        không thêm. Thêm tham số không có trong SDK là tự đoán.
        """
        return self._http.request(
            "GET",
            f"/price/{symbol}/quotes/latest",
            query={"boardId": board_id} if board_id else None,
            dry_run=dry_run,
        )

    def get_expected_price(
        self,
        symbol: str,
        board_id: str | None = None,
        from_date: int | None = None,
        to_date: int | None = None,
        limit: int | None = None,
        order: str | None = None,
        next_page_token: str | None = None,
        dry_run: bool = False,
    ) -> tuple[int | None, Any]:
        """Giá kỳ vọng. Path theo SDK `client.py:309`."""
        return self._http.request(
            "GET",
            f"/price/{symbol}/expected-price",
            query=self._history_query(
                board_id, from_date, to_date, limit, order, next_page_token
            ) or None,
            dry_run=dry_run,
        )

    def get_foreign_trading(
        self,
        symbol: str,
        board_id: str | None = None,
        from_date: int | None = None,
        to_date: int | None = None,
        limit: int | None = None,
        order: str | None = None,
        next_page_token: str | None = None,
        dry_run: bool = False,
    ) -> tuple[int | None, Any]:
        """Khối lượng giao dịch nước ngoài (Lớp B — giữ nguyên định dạng DNSE).

        Path theo SDK `client.py:351`: `GET /price/{symbol}/foreign-trading`.
        """
        return self._http.request(
            "GET",
            f"/price/{symbol}/foreign-trading",
            query=self._history_query(
                board_id, from_date, to_date, limit, order, next_page_token
            ) or None,
            dry_run=dry_run,
        )

    def get_market_index(
        self,
        index_name: str,
        from_date: int | None = None,
        to_date: int | None = None,
        limit: int | None = None,
        order: str | None = None,
        next_page_token: str | None = None,
        dry_run: bool = False,
    ) -> tuple[int | None, Any]:
        """Chỉ số thị trường. Path theo SDK `client.py`:
        `GET /price/{index_name}/market-index`. Chú ý tham số là **index_name**,
        không phải `symbol` — SDK không có `boardId` cho endpoint này.

        """ + _SECONDS_NOTE + """

        **Giới hạn đo được:** server chỉ nhận cửa sổ **cùng một ngày lịch** theo
        giờ Việt Nam; `from` hôm trước, `to` hôm nay trả
        `400 from and to must be in the same date`. Việc đó bị chặn ở đây, trước
        khi có byte nào đi ra (L-R01) — lỗi tham số bị server trả thành 400 buộc
        người gọi đoán, còn chặn sớm thì thông điệp nói rõ cửa sổ hợp lệ.

        Raises:
            DNSEValidationError: khi ``from_date``/``to_date`` rơi vào hai ngày
                khác nhau. ``error_code == "MARKET_INDEX_RANGE_NOT_SAME_DAY"``.
        """
        if not is_same_vn_day(from_date, to_date):
            from_day, to_day = vn_day_bounds(from_date or to_date or 0)
            raise DNSEValidationError(
                message=(
                    "get_market_index chỉ nhận cửa sổ trong MỘT ngày lịch giờ VN: "
                    f"from/to của bạn rơi vào hai ngày khác nhau. Hãy gọi riêng "
                    f"từng ngày — ví dụ ngày "
                    f"{datetime.fromtimestamp(from_day, VIETNAM_TZ):%Y-%m-%d} là "
                    f"[{from_day}, "
                    f"{datetime.fromtimestamp(to_day, VIETNAM_TZ):%Y-%m-%d}"
                    f" 23:59:59] = [{from_day}, {to_day}]."
                ),
                error_code="MARKET_INDEX_RANGE_NOT_SAME_DAY",
                status_code=400,
            )
        return self._http.request(
            "GET",
            f"/price/{index_name}/market-index",
            query=self._history_query(
                None, from_date, to_date, limit, order, next_page_token
            ) or None,
            dry_run=dry_run,
        )

    def get_trades_volume_profile(
        self,
        symbol: str,
        time: str,
        board_id: str,
        dry_run: bool = False,
    ) -> tuple[int | None, Any]:
        """Phân bổ khối lượng theo giá (Lớp A). Path theo SDK `client.py:304`.

        ⚠ **`time` là DATE STRING `yyyy-MM-dd`, không phải unix giây.** Đo
        production 2026-10-16: `time=1700` ⇒
        `400 invalid param 'time', expected format yyyy-MM-dd`. Đây là chỗ dễ
        nhầm nhất của connector, vì 4 method phân trang kia đều nhận unix giây.

        ⚠ **`board_id` bắt buộc.** Đo: thiếu `boardId` ⇒
        `400 missing param 'boardId'`. Chặn ở đây thay vì để server trả 400
        (L-R01).

        ⚠ **`board_id` chưa tài liệu hoá.** 24 ứng viên đã thử (kể cả `HOSE`) đều
        trả `404 not found boardId` — server tra cứu một bảng mà ta chưa biết
        nội dung. `explorer/dnse/listing.py:29` cho thấy `/instruments` **trả cột
        `boardId`**, tức từ điển có thể lấy từ chính server thay vì đoán; xem
        `scripts/probe_dnse_readonly.py`, mục `D10`. **Chưa** thêm enum đoán (L-P06).

        Raises:
            DNSEValidationError: khi ``time`` không phải chuỗi ngày hợp lệ.
                ``error_code == "INVALID_TIME_FORMAT"``.
        """
        _require_date_string(time, "time")
        return self._http.request(
            "GET",
            f"/price/{symbol}/trades/volume-profile",
            query={"time": time, "boardId": board_id},
            dry_run=dry_run,
        )

    def get_instruments(
        self,
        symbol: str | None = None,
        market_id: str | None = None,
        security_group_id: str | None = None,
        index_name: str | None = None,
        limit: int | None = None,
        page: int | None = None,
        dry_run: bool = False,
    ):
        """Danh mục chứng khoán. Path theo SDK `client.py:391`.

        ⚠ **`market_id` chưa tài liệu hoá — đừng đoán giá trị.**

        Đo production 2026-10-16: mọi ứng viên đã thử (`HOSE`, `STOCK`,
        `HOSE_STOCK`, `HNX`, `UPCOM`, `VN`, `VNINDEX`, `DERIVATIVE`, `0`–`5`, …)
        ⇒ `400 ... 'MarketId' failed on the 'oneof' tag`. Lỗi `'oneof'` là của
        *validator* Go và **nghĩa là server biết có một tập giá trị** — nhưng nó
        không liệt kê tập đó trong body lỗi, và SDK không công bố. Chưa đọc được
        `payload` đầy đủ ở lần đo (xem `scripts/probe_dnse_readonly.py`, mục
        `D11`) ⇒ kết luận hiện tại là **CHƯA CHẮC**, không phải "đã hết cách".

        Gọi không kèm `market_id` hoạt động bình thường (đo 200).
        """
        query = {}
        if symbol is not None:
            query["symbol"] = symbol
        if market_id is not None:
            query["marketId"] = market_id
        if security_group_id is not None:
            query["securityGroupId"] = security_group_id
        if index_name is not None:
            query["indexName"] = index_name
        if limit is not None:
            query["limit"] = limit
        if page is not None:
            query["page"] = page
        return self._http.request(
            "GET",
            "/instruments",
            query=(query if query else None),
            dry_run=dry_run,
        )


