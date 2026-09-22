"""
vnbroker.broker.ssi.market — SSIMarketService: OHLC, index, securities, master data.

  GET /api/v3/data/ohlc             → get_ohlc (gom 13 biến thể SDK theo timeframe)
  GET /api/v3/data/indexList        → get_indexes
  GET /api/v3/data/indexSummary     → get_index_summary/get_board_summary
  GET /api/v3/data/securitiesByBoard → get_securities_info
  GET /api/v3/data/securitiesSummary → get_securities_summary
  GET /api/v3/data/masterdata       → get_master_data (tự gom pages)
  GET /api/v3/data/ohlc/download   → download_ohlc: NotImplementedError (như SDK)

RULE: Read-only. Giá VND giữ nguyên. Date "YYYY/MM/DD".
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from vnbroker.broker.exceptions import BrokerValidationError
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.ssi import _paths
from vnbroker.broker.ssi._enums import Board, Timeframe, safe_parse
from vnbroker.broker.ssi._transport import SSIHttpClient
from vnbroker.broker.ssi._utils import (
    require_non_empty,
    to_float,
    to_int,
    today_date_str,
    validate_ssi_date,
)

_logger = logging.getLogger("vnbroker.broker.ssi.market")

_OHLC_COLUMNS = [
    "symbol",
    "trading_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "value",
]

_INDEX_COLUMNS = ["index", "index_name", "board"]

_INDEX_SUMMARY_COLUMNS = [
    "trading_date",
    "index_value",
    "index_change",
    "index_change_percent",
    "total_trade",
    "total_trade_value",
    "total_match",
    "total_match_value",
    "total_deal",
    "total_deal_value",
    "total_advance_stock",
    "total_decline_stock",
    "total_steady_stock",
    "total_ceiling_stock",
    "total_floor_stock",
    "total_prop_buy",
    "total_prop_buy_value",
    "total_prop_sell",
    "total_prop_sell_value",
]

_SEC_INFO_COLUMNS = [
    "symbol",
    "board",
    "index",
    "symbol_name_vi",
    "symbol_name_en",
    "lot_size",
    "listed_shares",
    "icb_code",
    "icb_name",
    "maturity_date",
    "first_trading_date",
    "last_trading_date",
    "cw_underlying_symbol",
    "cw_exercise_price",
    "cw_execution_ratio",
    "open_interest",
    "settlement_price",
    "i_index",
    "i_nav",
]

_SEC_SUMMARY_COLUMNS = [
    "symbol",
    "trading_date",
    "open",
    "high",
    "low",
    "close",
    "average",
    "price_change",
    "price_change_percent",
    "total_match",
    "total_match_value",
    "total_buy",
    "total_trade_buy",
    "total_sell",
    "total_trade_sell",
    "total_foreign_buy",
    "total_foreign_buy_value",
    "total_foreign_sell",
    "total_foreign_sell_value",
    "remain_foreign_room",
    "total_foreign_room",
    "total_deal",
    "total_deal_value",
    "open_interest",
    "settlement_price",
]

_MASTER_COLUMNS = [
    "board",
    "symbol",
    "trading_date",
    "ceiling",
    "floor",
    "ref_price",
]


class SSIMarketService:
    """Read-only market data cho SSI broker."""

    def __init__(
        self,
        config: SSICredentialConfig,
        session: BrokerSession,
        transport: SSIHttpClient,
    ) -> None:
        self._config = config
        self._session = session
        self._transport = transport

    # ── OHLC ─────────────────────────────────────────────────────────────

    def get_ohlc(
        self,
        symbol: str,
        timeframe: str = "1d",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 1,
        size: int = 1000,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Any]]:
        """
        Nến OHLCV: gom 13 biến thể SDK (1m/3m/5m/15m/1h intraday + 8 historical).

        Args:
            timeframe: "1m"|"3m"|"5m"|"15m"|"1h"|"1d"|"1w"|"1M".
            from_date/to_date: None → hôm nay (intraday).
        """
        symbol = require_non_empty(symbol, "symbol").upper()
        tf = safe_parse(Timeframe, (timeframe or "").strip())
        if tf is None:
            raise BrokerValidationError(
                message=f"timeframe không hỗ trợ: {timeframe!r}. "
                "Dùng 1m/3m/5m/15m/1h/1d/1w/1M.",
                code="INVALID_TIMEFRAME",
                http_status=400,
            )
        today = today_date_str()
        from_date = validate_ssi_date(from_date, "from_date") if from_date else today
        to_date = validate_ssi_date(to_date, "to_date") if to_date else today
        _ = self._session.token
        data = self._transport.request(
            "GET",
            _paths.EP_DATA_OHLC,
            params={
                "symbol": symbol,
                "from": from_date,
                "to": to_date,
                "timeFrame": tf.value,
                "pageIndex": _page(page),
                "pageSize": _page_size(size, 1000),
            },
        )
        records = _data_list(data)
        if raw:
            return records
        if not records:
            return pd.DataFrame(columns=_OHLC_COLUMNS)
        rows = [
            {
                "symbol": str(r.get("symbol", symbol)),
                "trading_date": str(r.get("tradingDate", "")),
                "open": to_float(r.get("open")),
                "high": to_float(r.get("high")),
                "low": to_float(r.get("low")),
                "close": to_float(r.get("close")),
                "volume": to_int(r.get("volume")),
                "value": to_float(r.get("value")),
            }
            for r in records
        ]
        df = pd.DataFrame(rows, columns=_OHLC_COLUMNS)
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype("Int64")
        for col in ("open", "high", "low", "close", "value"):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        return df

    def download_ohlc(self, symbol: str) -> None:
        """Bulk download — server SDK chưa hỗ trợ (NotImplemented như SDK gốc)."""
        _ = (symbol,)
        raise NotImplementedError("SSI chưa hỗ trợ bulk OHLC download.")

    # ── Indexes ──────────────────────────────────────────────────────────

    def get_indexes(
        self, board: Optional[str] = None, raw: bool = False
    ) -> Union[pd.DataFrame, List[Any]]:
        """GET /api/v3/data/indexList — toàn bộ hoặc theo sàn."""
        parsed_board: Optional[Board] = None
        if board is not None:
            parsed_board = safe_parse(Board, board.strip().upper())
            if parsed_board is None:
                raise BrokerValidationError(
                    message=f"board không hỗ trợ: {board!r}. "
                    "Dùng HOSE/HNX/UPCOM/DERIVATIVES.",
                    code="INVALID_BOARD",
                    http_status=400,
                )
        _ = self._session.token
        params = {"board": parsed_board.value} if parsed_board else {}
        data = self._transport.request("GET", _paths.EP_DATA_INDEX_LIST, params=params)
        records = data if isinstance(data, list) else _data_list(data)
        if raw:
            return records
        rows = [
            {
                "index": str(r.get("index", "")),
                "index_name": str(r.get("indexName", "")),
                "board": str(r.get("board", "")),
            }
            for r in records
        ]
        df = pd.DataFrame(rows, columns=_INDEX_COLUMNS)
        if not df.empty:
            df["board"] = df["board"].astype("category")
        return df

    def get_index_summary(
        self,
        index: str,
        trading_date: Optional[str] = None,
        raw: bool = False,
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """GET /api/v3/data/indexSummary — summary chỉ số (mới nhất/kèm ngày)."""
        index = require_non_empty(index, "index").upper()
        if trading_date is not None:
            trading_date = validate_ssi_date(trading_date, "trading_date")
        return self._summary({"index": index, "tradingDate": trading_date}, raw)

    def get_board_summary(
        self,
        board: str,
        trading_date: Optional[str] = None,
        raw: bool = False,
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """GET /api/v3/data/indexSummary — summary theo sàn."""
        parsed = safe_parse(Board, (board or "").strip().upper())
        if parsed is None:
            raise BrokerValidationError(
                message=f"board không hỗ trợ: {board!r}.",
                code="INVALID_BOARD",
                http_status=400,
            )
        if trading_date is not None:
            trading_date = validate_ssi_date(trading_date, "trading_date")
        return self._summary({"board": parsed.value, "tradingDate": trading_date}, raw)

    def _summary(
        self, filters: Dict[str, Any], raw: bool
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        _ = self._session.token
        params = {k: v for k, v in filters.items() if v is not None}
        data = self._transport.request(
            "GET", _paths.EP_DATA_INDEX_SUMMARY, params=params
        )
        records = data if isinstance(data, list) else _data_list(data)
        if raw:
            return records[0] if records else {}
        if not records:
            return pd.DataFrame(columns=_INDEX_SUMMARY_COLUMNS)
        rec = records[0]
        row = {
            "trading_date": str(rec.get("tradingDate", "")),
            "index_value": to_float(rec.get("indexValue")),
            "index_change": to_float(rec.get("indexChange")),
            "index_change_percent": to_float(rec.get("indexChangePercentage")),
            "total_trade": to_int(rec.get("totalTrade")),
            "total_trade_value": to_float(rec.get("totalTradeValue")),
            "total_match": to_int(rec.get("totalMatch")),
            "total_match_value": to_float(rec.get("totalMatchValue")),
            "total_deal": to_int(rec.get("totalDeal")),
            "total_deal_value": to_float(rec.get("totalDealValue")),
            "total_advance_stock": to_int(rec.get("totalAdvanceStock")),
            "total_decline_stock": to_int(rec.get("totalDeclineStock")),
            "total_steady_stock": to_int(rec.get("totalNoChangeStock")),
            "total_ceiling_stock": to_int(rec.get("totalCeilingStock")),
            "total_floor_stock": to_int(rec.get("totalFloorStock")),
            "total_prop_buy": to_int(rec.get("totalPropBuy")),
            "total_prop_buy_value": to_float(rec.get("totalPropBuyValue")),
            "total_prop_sell": to_int(rec.get("totalPropSell")),
            "total_prop_sell_value": to_float(rec.get("totalPropSellValue")),
        }
        df = pd.DataFrame([row], columns=_INDEX_SUMMARY_COLUMNS)
        int_cols = {
            "total_trade",
            "total_match",
            "total_deal",
            "total_advance_stock",
            "total_decline_stock",
            "total_steady_stock",
            "total_ceiling_stock",
            "total_floor_stock",
            "total_prop_buy",
            "total_prop_sell",
        }
        for col in _INDEX_SUMMARY_COLUMNS:
            if col == "trading_date":
                continue
            numeric = pd.to_numeric(df[col], errors="coerce")
            df[col] = (
                numeric.astype("Int64")
                if col in int_cols
                else numeric.astype("float64")
            )
        return df

    # ── Securities info / summary ────────────────────────────────────────

    def get_securities_info(
        self,
        symbol: Optional[str] = None,
        board: Optional[str] = None,
        index: Optional[str] = None,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Any]]:
        """GET /api/v3/data/securitiesByBoard — cần ≥1 filter."""
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = require_non_empty(symbol, "symbol").upper()
        if board:
            parsed = safe_parse(Board, board.strip().upper())
            if parsed is None:
                raise BrokerValidationError(
                    message=f"board không hỗ trợ: {board!r}.",
                    code="INVALID_BOARD",
                    http_status=400,
                )
            params["board"] = parsed.value
        if index:
            params["index"] = require_non_empty(index, "index").upper()
        if not params:
            raise BrokerValidationError(
                message="Cần ít nhất 1 filter: symbol, board hoặc index.",
                code="MISSING_FILTER",
                http_status=400,
            )
        _ = self._session.token
        data = self._transport.request(
            "GET", _paths.EP_DATA_SECURITIES_BY_BOARD, params=params
        )
        records = data if isinstance(data, list) else _data_list(data)
        if raw:
            return records
        if not records:
            return pd.DataFrame(columns=_SEC_INFO_COLUMNS)
        rows = [_sec_info_row(r) for r in records]
        df = pd.DataFrame(rows, columns=_SEC_INFO_COLUMNS)
        for col in ("lot_size", "listed_shares"):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        for col in (
            "cw_exercise_price",
            "cw_execution_ratio",
            "open_interest",
            "settlement_price",
            "i_index",
            "i_nav",
        ):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        df["board"] = df["board"].astype("category")
        return df

    def get_securities_summary(
        self,
        symbol: Optional[str] = None,
        index: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Any]]:
        """GET /api/v3/data/securitiesSummary — cần symbol hoặc index."""
        if not symbol and not index:
            raise BrokerValidationError(
                message="Cần symbol hoặc index.",
                code="MISSING_FILTER",
                http_status=400,
            )
        today = today_date_str()
        from_date = validate_ssi_date(from_date, "from_date") if from_date else today
        to_date = validate_ssi_date(to_date, "to_date") if to_date else today
        _ = self._session.token
        params: Dict[str, Any] = {"from": from_date, "to": to_date}
        if symbol:
            params["symbol"] = symbol.strip().upper()
        if index:
            params["index"] = index.strip().upper()
        data = self._transport.request(
            "GET", _paths.EP_DATA_SECURITIES_SUMMARY, params=params
        )
        records = _data_list(data)
        if raw:
            return records
        if not records:
            return pd.DataFrame(columns=_SEC_SUMMARY_COLUMNS)
        rows = [_sec_summary_row(r) for r in records]
        df = pd.DataFrame(rows, columns=_SEC_SUMMARY_COLUMNS)
        for col in (
            "total_match",
            "total_buy",
            "total_sell",
            "total_foreign_buy",
            "total_foreign_sell",
            "remain_foreign_room",
            "total_foreign_room",
            "total_deal",
        ):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        for col in [
            c
            for c in _SEC_SUMMARY_COLUMNS
            if c
            not in (
                "symbol",
                "trading_date",
                "total_match",
                "total_buy",
                "total_sell",
                "total_foreign_buy",
                "total_foreign_sell",
                "remain_foreign_room",
                "total_foreign_room",
                "total_deal",
            )
        ]:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        return df

    # ── Master data ──────────────────────────────────────────────────────

    def get_master_data(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Any]]:
        """
        GET /api/v3/data/masterdata — trần/sàn/TC toàn sàn, TỰ GOM hết pages.
        Query dùng key HOA From/To theo wire-spec.
        """
        today = today_date_str()
        from_date = validate_ssi_date(from_date, "from_date") if from_date else today
        to_date = validate_ssi_date(to_date, "to_date") if to_date else today
        _ = self._session.token
        items: List[Dict[str, Any]] = []
        page, pages_count, size = 1, 1, 1000
        while page <= pages_count:
            data = self._transport.request(
                "GET",
                _paths.EP_DATA_MASTER_DATA,
                params={
                    "From": from_date,
                    "To": to_date,
                    "pageIndex": page,
                    "pageSize": size,
                },
            )
            records = _data_list(data)
            items.extend(records)
            try:
                pages_count = (
                    int(data.get("pagesCount", 1)) if isinstance(data, dict) else 1
                )
            except (ValueError, TypeError):
                pages_count = 1
            page += 1
        if raw:
            return items
        if not items:
            return pd.DataFrame(columns=_MASTER_COLUMNS)
        rows = [
            {
                "board": str(r.get("board", "")),
                "symbol": str(r.get("symbol", "")),
                "trading_date": str(r.get("tradingDate", "")),
                "ceiling": to_float(r.get("ceiling")),
                "floor": to_float(r.get("floor")),
                "ref_price": to_float(r.get("refPrice")),
            }
            for r in items
        ]
        df = pd.DataFrame(rows, columns=_MASTER_COLUMNS)
        for col in ("ceiling", "floor", "ref_price"):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        df["board"] = df["board"].astype("category")
        return df


# ── Helpers ──────────────────────────────────────────────────────────────


def _page(value: int) -> int:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 1
        else 1
    )


def _page_size(value: int, default: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 1000:
        return value
    return default


def _data_list(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        records = data.get("data", [])
        if isinstance(records, list):
            return [r for r in records if isinstance(r, dict)]
    return []


def _sec_info_row(r: Dict[str, Any]) -> Dict[str, Any]:
    board = safe_parse(Board, str(r.get("board", "")).upper())
    return {
        "symbol": str(r.get("symbol", "")),
        "board": board.value if board else str(r.get("board", "")),
        "index": str(r.get("index", "") or ""),
        "symbol_name_vi": str(r.get("symbolNameVi", "") or ""),
        "symbol_name_en": str(r.get("symbolNameEn", "") or ""),
        "lot_size": to_int(r.get("lotSize")),
        "listed_shares": to_int(r.get("listedShare")),
        "icb_code": str(r.get("icbCode", "") or ""),
        "icb_name": str(r.get("icbName", "") or ""),
        "maturity_date": str(r.get("maturityDate", "") or ""),
        "first_trading_date": str(r.get("firstTradingDate", "") or ""),
        "last_trading_date": str(r.get("lastTradingDate", "") or ""),
        "cw_underlying_symbol": str(r.get("cwUnderlyingSymbol", "") or ""),
        "cw_exercise_price": to_float(r.get("cwExercisePrice")),
        "cw_execution_ratio": to_float(r.get("cwExecutionRatio")),
        "open_interest": to_float(r.get("openInterest")),
        "settlement_price": to_float(r.get("settlementPrice")),
        "i_index": to_float(r.get("iIndex")),
        "i_nav": to_float(r.get("iNav")),
    }


def _sec_summary_row(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "symbol": str(r.get("symbol", "")),
        "trading_date": str(r.get("tradingDate", "")),
        "open": to_float(r.get("open")),
        "high": to_float(r.get("high")),
        "low": to_float(r.get("low")),
        "close": to_float(r.get("close")),
        "average": to_float(r.get("average")),
        "price_change": to_float(r.get("priceChange")),
        "price_change_percent": to_float(r.get("priceChangePercentage")),
        "total_match": to_int(r.get("totalMatch")),
        "total_match_value": to_float(r.get("totalMatchValue")),
        "total_buy": to_int(r.get("totalBuy")),
        "total_trade_buy": to_float(r.get("totalTradeBuy")),
        "total_sell": to_int(r.get("totalSell")),
        "total_trade_sell": to_float(r.get("totalTradeSell")),
        "total_foreign_buy": to_int(r.get("totalForeignBuy")),
        "total_foreign_buy_value": to_float(r.get("totalForeignBuyValue")),
        "total_foreign_sell": to_int(r.get("totalForeignSell")),
        "total_foreign_sell_value": to_float(r.get("totalForeignSellValue")),
        "remain_foreign_room": to_int(r.get("remainForeignRoom")),
        "total_foreign_room": to_int(r.get("totalForeignRoom")),
        "total_deal": to_int(r.get("totalDeal")),
        "total_deal_value": to_float(r.get("totalDealValue")),
        "open_interest": to_float(r.get("openInterest")),
        "settlement_price": to_float(r.get("settlementPrice")),
    }
