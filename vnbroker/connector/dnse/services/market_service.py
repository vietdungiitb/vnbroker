from __future__ import annotations

from datetime import datetime
from typing import Any

from vnbroker.connector.dnse.core.errors import DNSEValidationError
from vnbroker.connector.dnse.core.http_client import DNSEHttpClient
from vnbroker.connector.dnse.core.time_utils import (
    VIETNAM_TZ,
    is_same_vn_day,
    to_unix_seconds,
    vn_day_bounds,
)

#: Ghi nháº¯c Ä‘Æ¡n vá»‹, dÃ¹ng chung cho cáº£ 5 method phÃ¢n trang. Äo production
#: 2026-10-16: milliseconds tráº£ `400 range exceeds maximum time range`.
_SECONDS_NOTE = (
    "`from_date`/`to_date` lÃ  unix **GIÃ‚Y** (khÃ´ng pháº£i milliseconds â€” "
    "truyá»n milliseconds sáº½ bá»‹ server tráº£ 400)."
)

#: Äá»‹nh dáº¡ng ngÃ y mÃ  má»™t sá»‘ endpoint DNSE yÃªu cáº§u (khÃ¡c unix giÃ¢y cá»§a
#: price endpoints). Äo production 2026-10-16:
#: `400 invalid param 'time', expected format yyyy-MM-dd`.
_DATE_FORMAT = "%Y-%m-%d"


def _require_date_string(value: object, param: str) -> str:
    """Cháº·n sá»‘ nguyÃªn á»Ÿ cá»­a má»™t endpoint chá»‰ nháº­n chuá»—i ngÃ y.

    KhÃ´ng cÃ³ kiá»ƒu nÃ o á»Ÿ Ä‘Ã¢y tá»± báº¯t Ä‘Æ°á»£c lá»—i: `time: int` lÃ  há»£p lá»‡ vá» máº·t Python
    vÃ  láº¡i lÃ  cÃ¡ch má»i ngÆ°á»i máº·c Ä‘á»‹nh nghÄ© khi tháº¥y má»™t con sá»‘ thá»i gian. VÃ¬ váº­y
    pháº£i kiá»ƒm ná»™i dung, khÃ´ng chá»‰ kiá»ƒu.
    """
    if isinstance(value, str):
        try:
            datetime.strptime(value.strip(), _DATE_FORMAT)
        except ValueError as exc:
            raise DNSEValidationError(
                message=(
                    f"{param}={value!r} khÃ´ng pháº£i ngÃ y Ä‘Ãºng Ä‘á»‹nh dáº¡ng "
                    f"'{_DATE_FORMAT}'. DNSE yÃªu cáº§u CHUá»–I NGÃ€Y cho tham sá»‘ nÃ y "
                    f"â€” vÃ­ dá»¥ '2026-10-16' â€” KHÃ”NG pháº£i unix giÃ¢y."
                ),
                error_code="INVALID_TIME_FORMAT",
                status_code=400,
            ) from exc
        return value.strip()

    raise DNSEValidationError(
        message=(
            f"{param}={value!r} sai kiá»ƒu ({type(value).__name__}). Tham sá»‘ nÃ y "
            f"pháº£i lÃ  CHUá»–I NGÃ€Y '{_DATE_FORMAT}', vÃ­ dá»¥ '2026-10-16' â€” khÃ´ng "
            f"pháº£i unix giÃ¢y. Gá»­i sá»‘ nguyÃªn sáº½ bá»‹ server tráº£ "
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
        """Äá»‹nh nghÄ©a mÃ£ báº£o chá»©ng. Path theo SDK `client.py:256`.

        âš  **`board_id` chÆ°a tÃ i liá»‡u hoÃ¡ â€” Ä‘á»«ng Ä‘oÃ¡n giÃ¡ trá»‹.**

        Äo production 2026-10-16: gá»i **khÃ´ng** kÃ¨m `board_id` â‡’ **200**;
        kÃ¨m `board_id` báº¥t ká»ƒ giÃ¡ trá»‹ nÃ o trong **10** á»©ng viÃªn Ä‘Ã£ thá»­ cho
        endpoint nÃ y (`HOSE`, `HOSE_STOCK`, `HNX`, `HNX_STOCK`, `UPCOM`,
        `HOSE.ETF`, `HOSE_INDEX`, `HOSE.DERIVATIVE`, `DOWNNEX`, `ETF`) â‡’ **500
        Internal error**. Tá»©c lÃ  tham sá»‘ nÃ y thá»±c táº¿ **khÃ´ng dÃ¹ng Ä‘Æ°á»£c**, chá»©
        khÃ´ng pháº£i "thiáº¿u thÃ¬ lá»—i".

        Repo cÃ³ manh má»‘i (`connector/dnse/websocket.py:19,278` dÃ¹ng mÃ£ kiá»ƒu
        `G1`/`STO.G1` cho kÃªnh WS) nhÆ°ng chÆ°a thá»­ Ä‘Æ°á»£c vá»›i REST â€” xem
        `scripts/probe_dnse_readonly.py`, má»¥c `D10`. **KhÃ´ng** thÃªm táº­p giÃ¡ trá»‹
        Ä‘oÃ¡n vÃ o Ä‘Ã¢y: bá»‹a enum táº¡o cáº£m giÃ¡c an toÃ n giáº£ (L-P06). Khi DNSE cÃ´ng bá»‘,
        cáº­p nháº­t cáº£ docstring nÃ y.
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
        """NgÃ y giao dá»‹ch. Path: `GET /market/working-dates` (SDK `client.py:447-451`).

        âš  **ÄÃ­nh chÃ­nh má»™t káº¿t luáº­n sai Ä‘Ã£ cÃ³ trong chÃ­nh file nÃ y.** Docstring cÅ©
        ghi *"DNSE OpenAPI does not have a dedicated working-dates endpoint"* vÃ 
        method tráº£ `({"dates": []}, None)` â€” má»™t tuple cá»‘ Ã½ Ä‘áº£o, khiáº¿n
        `_resolve_output` unpack nháº§m vÃ  ngÆ°á»i gá»i nháº­n `None` mÃ  khÃ´ng cÃ³ request
        nÃ o Ä‘i ra. ÄÃ³ lÃ  "thÃ nh cÃ´ng rá»—ng": trÃ´ng nhÆ° server nÃ³i khÃ´ng cÃ³ ngÃ y
        giao dá»‹ch, trong khi tháº­t ra chÆ°a ai há»i (L-R01).

        Äo production 2026-10-16 (khÃ´ng VPN): `200`, `{"workingDates": [...257]}`
        â‡’ endpoint **cÃ³ tháº­t**. Váº­y nÃªn sá»­a path, khÃ´ng xoÃ¡ method.

        KhÃ´ng gá»­i `marketType`: Ä‘o cho tháº¥y thÃªm tham sá»‘ Ä‘Ã³ tráº£ `404`.
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
        """Giao dá»‹ch khá»›p lá»‡nh. Path theo SDK: `/price/{symbol}/trades`.

        DÃ¹ng chung `_history_query` vá»›i 4 method kia â€” trÆ°á»›c Ä‘Ã¢y method nÃ y dá»±ng
        dict thá»§ cÃ´ng trong khi nhá»¯ng method khÃ¡c gá»i helper, nÃªn má»™t thay Ä‘á»•i tÃªn
        key chá»‰ Ä‘áº¡t Ä‘Æ°á»£c ná»­a bá»™ method.

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
        """Query dÃ¹ng chung cho cÃ¡c endpoint phÃ¢n trang theo thá»i gian.

        TÃªn key láº¥y tá»« SDK `dnse-tech/openapi-sdk` `python/dnse/api/client.py:331-343`
        â€” `boardId` / `from` / `to` / `limit` / `order` / `nextPageToken`.

        `from_date`/`to_date` Ä‘Æ°á»£c Ä‘Æ°a qua `to_unix_seconds`, nÃªn **milliseconds
        cÅ©ng cháº¡y Ä‘Æ°á»£c**. ÄÃ³ lÃ  chá»— cháº·n Ä‘o Ä‘Æ°á»£c lá»—i D8: cÃ¹ng má»™t cáº·p tham sá»‘,
        milliseconds tráº£ `400 range exceeds maximum time range` cÃ²n giÃ¢y tráº£ 200.
        GiÃ¡ trá»‹ Ä‘Ã£ lÃ  giÃ¢y thÃ¬ Ä‘i qua nguyÃªn váº¹n, nÃªn Ä‘Ã¢y lÃ  chuáº©n hoÃ¡ chá»© khÃ´ng
        pháº£i Ã©p kiá»ƒu.
        """
        query: dict[str, object] = {}
        if board_id is not None:
            query["boardId"] = board_id
        if from_date is not None:
            query["from"] = to_unix_seconds(from_date)
        if to_date is not None:
            query["to"] = to_unix_seconds(to_date)
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
        """Ná»™i giÃ¡ (Lá»›p A) â€” chuáº©n hoÃ¡ vá» form chung cá»§a vnbroker.

        Path theo SDK `client.py:346`: `GET /price/{symbol}/quotes`.

        âš  Cáº£nh bÃ¡o Ä‘Ã£ Ä‘o: server gá»­i `bid[].qtty` / `offer[].qtty` (tÃ i liá»‡u ghi
        `quantity`). Map sang `quantity` sáº½ **im láº·ng tráº£ 0 khá»‘i lÆ°á»£ng**.
        Chi tiáº¿t: `docs/NORMALISATION_POLICY.md` Â§3.1.
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
        """BÃ¡o giÃ¡ má»›i nháº¥t. Path theo SDK `client.py:424`.

        Chá»‰ nháº­n `board_id` â€” SDK **khÃ´ng** cÃ³ from/to cho endpoint nÃ y, nÃªn cÅ©ng
        khÃ´ng thÃªm. ThÃªm tham sá»‘ khÃ´ng cÃ³ trong SDK lÃ  tá»± Ä‘oÃ¡n.
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
        """GiÃ¡ ká»³ vá»ng. Path theo SDK `client.py:309`."""
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
        """Khá»‘i lÆ°á»£ng giao dá»‹ch nÆ°á»›c ngoÃ i (Lá»›p B â€” giá»¯ nguyÃªn Ä‘á»‹nh dáº¡ng DNSE).

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
        """Chá»‰ sá»‘ thá»‹ trÆ°á»ng. Path theo SDK `client.py`:
        `GET /price/{index_name}/market-index`. ChÃº Ã½ tham sá»‘ lÃ  **index_name**,
        khÃ´ng pháº£i `symbol` â€” SDK khÃ´ng cÃ³ `boardId` cho endpoint nÃ y.

        """ + _SECONDS_NOTE + """

        **Giá»›i háº¡n Ä‘o Ä‘Æ°á»£c:** server chá»‰ nháº­n cá»­a sá»• **cÃ¹ng má»™t ngÃ y lá»‹ch** theo
        giá» Viá»‡t Nam; `from` hÃ´m trÆ°á»›c, `to` hÃ´m nay tráº£
        `400 from and to must be in the same date`. Viá»‡c Ä‘Ã³ bá»‹ cháº·n á»Ÿ Ä‘Ã¢y, trÆ°á»›c
        khi cÃ³ byte nÃ o Ä‘i ra (L-R01) â€” lá»—i tham sá»‘ bá»‹ server tráº£ thÃ nh 400 buá»™c
        ngÆ°á»i gá»i Ä‘oÃ¡n, cÃ²n cháº·n sá»›m thÃ¬ thÃ´ng Ä‘iá»‡p nÃ³i rÃµ cá»­a sá»• há»£p lá»‡.

        Raises:
            DNSEValidationError: khi ``from_date``/``to_date`` rÆ¡i vÃ o hai ngÃ y
                khÃ¡c nhau. ``error_code == "MARKET_INDEX_RANGE_NOT_SAME_DAY"``.
        """
        if not is_same_vn_day(from_date, to_date):
            # `from_date or to_date` SAI: `0` lÃ  falsy nÃªn from_date=0 sáº½ rÆ¡i
            # sang to_date vÃ  thÃ´ng bÃ¡o nháº§m ngÃ y. Pháº£i so vá»›i None.
            anchor = from_date if from_date is not None else to_date
            from_day, to_day = vn_day_bounds(anchor if anchor is not None else 0)
            raise DNSEValidationError(
                message=(
                    "get_market_index chá»‰ nháº­n cá»­a sá»• trong Má»˜T ngÃ y lá»‹ch giá» VN: "
                    f"from/to cá»§a báº¡n rÆ¡i vÃ o hai ngÃ y khÃ¡c nhau. HÃ£y gá»i riÃªng "
                    f"tá»«ng ngÃ y â€” vÃ­ dá»¥ ngÃ y "
                    f"{datetime.fromtimestamp(from_day, VIETNAM_TZ):%Y-%m-%d} lÃ  "
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
        """PhÃ¢n bá»• khá»‘i lÆ°á»£ng theo giÃ¡ (Lá»›p A). Path theo SDK `client.py:304`.

        âš  **`time` lÃ  DATE STRING `yyyy-MM-dd`, khÃ´ng pháº£i unix giÃ¢y.** Äo
        production 2026-10-16: `time=1700` â‡’
        `400 invalid param 'time', expected format yyyy-MM-dd`. ÄÃ¢y lÃ  chá»— dá»…
        nháº§m nháº¥t cá»§a connector, vÃ¬ 4 method phÃ¢n trang kia Ä‘á»u nháº­n unix giÃ¢y.

        âš  **`board_id` báº¯t buá»™c.** Äo: thiáº¿u `boardId` â‡’
        `400 missing param 'boardId'`. Cháº·n á»Ÿ Ä‘Ã¢y thay vÃ¬ Ä‘á»ƒ server tráº£ 400
        (L-R01).

        âš  **`board_id` chÆ°a tÃ i liá»‡u hoÃ¡.** 24 á»©ng viÃªn Ä‘Ã£ thá»­ (ká»ƒ cáº£ `HOSE`) Ä‘á»u
        tráº£ `404 not found boardId` â€” server tra cá»©u má»™t báº£ng mÃ  ta chÆ°a biáº¿t
        ná»™i dung. `explorer/dnse/listing.py:29` cho tháº¥y `/instruments` **tráº£ cá»™t
        `boardId`**, tá»©c tá»« Ä‘iá»ƒn cÃ³ thá»ƒ láº¥y tá»« chÃ­nh server thay vÃ¬ Ä‘oÃ¡n; xem
        `scripts/probe_dnse_readonly.py`, má»¥c `D10`. **ChÆ°a** thÃªm enum Ä‘oÃ¡n (L-P06).

        Raises:
            DNSEValidationError: khi ``time`` khÃ´ng pháº£i chuá»—i ngÃ y há»£p lá»‡.
                ``error_code == "INVALID_TIME_FORMAT"``.
        """
        _require_date_string(time, "time")
        return self._http.request(
            "GET",
            f"/price/{symbol}/trades/volume-profile",
            query={
                "time": _require_date_string(time, "time"),
                "boardId": board_id,
            },
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
        """Danh má»¥c chá»©ng khoÃ¡n. Path theo SDK `client.py:391`.

        âš  **`market_id` chÆ°a tÃ i liá»‡u hoÃ¡ â€” Ä‘á»«ng Ä‘oÃ¡n giÃ¡ trá»‹.**

        Äo production 2026-10-16: má»i á»©ng viÃªn Ä‘Ã£ thá»­ (`HOSE`, `STOCK`,
        `HOSE_STOCK`, `HNX`, `UPCOM`, `VN`, `VNINDEX`, `DERIVATIVE`, `0`â€“`5`, â€¦)
        â‡’ `400 ... 'MarketId' failed on the 'oneof' tag`. Lá»—i `'oneof'` lÃ  cá»§a
        *validator* Go vÃ  **nghÄ©a lÃ  server biáº¿t cÃ³ má»™t táº­p giÃ¡ trá»‹** â€” nhÆ°ng nÃ³
        khÃ´ng liá»‡t kÃª táº­p Ä‘Ã³ trong body lá»—i, vÃ  SDK khÃ´ng cÃ´ng bá»‘. ChÆ°a Ä‘á»c Ä‘Æ°á»£c
        `payload` Ä‘áº§y Ä‘á»§ á»Ÿ láº§n Ä‘o (xem `scripts/probe_dnse_readonly.py`, má»¥c
        `D11`) â‡’ káº¿t luáº­n hiá»‡n táº¡i lÃ  **CHÆ¯A CHáº®C**, khÃ´ng pháº£i "Ä‘Ã£ háº¿t cÃ¡ch".

        Gá»i khÃ´ng kÃ¨m `market_id` hoáº¡t Ä‘á»™ng bÃ¬nh thÆ°á»ng (Ä‘o 200).
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


