from __future__ import annotations

from typing import Any

from vnbroker.connector.dnse.core.http_client import DNSEHttpClient


class MarketService:
    def __init__(self, http: DNSEHttpClient):
        self._http = http

    def get_security_definition(
        self,
        symbol: str,
        board_id: str | None = None,
        dry_run: bool = False,
    ):
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
        """Get trading working dates.
        
        Note: DNSE OpenAPI does not have a dedicated working-dates endpoint.
        Returns empty list - use instruments endpoint with date filtering if needed.
        """
        return ({"dates": []}, None)  # Return tuple (body, raw) for consistency

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
    ):
        # Correct path: /price/{symbol}/trades  (symbol is path param, not query param)
        path = f"/price/{symbol}/trades"
        query: dict = {}
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
        return self._http.request("GET", path, query=query or None, dry_run=dry_run)

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
        """
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
        time: int,
        board_id: str | None = None,
        dry_run: bool = False,
    ) -> tuple[int | None, Any]:
        """Phân bổ khối lượng theo giá (Lớp A). Path theo SDK `client.py:304`.

        `time` là **bắt buộc** — SDK khai nó là tham số vị trí không có default
        (`client.py:298`). Giữ nguyên để chặn những request chắc chắn bị từ chối.
        """
        query: dict[str, object] = {"time": time}
        if board_id is not None:
            query["boardId"] = board_id
        return self._http.request(
            "GET",
            f"/price/{symbol}/trades/volume-profile",
            query=query,
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


