"""
vnbroker.broker.ssi.portfolio — SSIPortfolioService: vị thế, sổ lệnh, snapshot.

  GET /api/v3/trading/position   → get_equity_positions/get_derivative_positions
  GET /api/v3/trading/orderBook  → get_today_orders/get_historical_orders

portfolio_snapshot(): map tường minh SSI → TCBSPortfolioEngine (cấm silent no-op):
  symbol←symbol, quantity←quantity, average_cost←costPrice,
  current_price←market_prices map (thiếu → NaN + warning),
  market_value/unrealized_pnl tự tính. Rỗng → dict zero tường minh + warning.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, Optional, Union

import pandas as pd

from vnbroker.broker.exceptions import BrokerValidationError
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.ssi import _paths
from vnbroker.broker.ssi._enums import OrderStatus, OrderType, parse_side, safe_parse
from vnbroker.broker.ssi._transport import SSIHttpClient
from vnbroker.broker.ssi._utils import (
    require_non_empty,
    to_float,
    to_int,
    validate_ssi_date,
)
from vnbroker.broker.ssi.money import SSIMoneyService
from vnbroker.broker.tcbs.portfolio import TCBSPortfolioEngine

_logger = logging.getLogger("vnbroker.broker.ssi.portfolio")

_POSITION_COLUMNS = [
    "account_no",
    "symbol",
    "quantity",
    "sellable_quantity",
    "buying_quantity",
    "selling_quantity",
    "mortgage_quantity",
    "average_cost",
    "t1_sell_quantity",
    "t2_sell_quantity",
]

_DERIV_POSITION_COLUMNS = [
    "account_no",
    "symbol",
    "long",
    "short",
    "net",
    "bid_avg_price",
    "ask_avg_price",
    "trade_price",
    "floating_pl",
    "trading_pl",
    "state",
]

_ORDER_COLUMNS = [
    "account_no",
    "order_id",
    "client_request_id",
    "symbol",
    "side",
    "order_type",
    "quantity",
    "filled_quantity",
    "os_quantity",
    "cancel_quantity",
    "price",
    "avg_price",
    "status",
    "input_time",
    "modify_time",
    "message",
]


class SSIPortfolioService:
    """Read-only portfolio service cho SSI broker."""

    def __init__(
        self,
        config: SSICredentialConfig,
        session: BrokerSession,
        transport: SSIHttpClient,
    ) -> None:
        self._config = config
        self._session = session
        self._transport = transport
        self._money = SSIMoneyService(config, session, transport)

    # ── Positions ────────────────────────────────────────────────────────

    def get_equity_positions(
        self, account_no: str, raw: bool = False
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """
        GET /api/v3/trading/position — phần equity.

        Returns:
            DataFrame columns: _POSITION_COLUMNS (quantity Int64, giá float64).
        """
        account_no = require_non_empty(account_no, "accountNo")
        data = self._positions_payload(account_no)
        if raw:
            return data
        records = data.get("equity") if isinstance(data, dict) else None
        if not isinstance(records, list) or not records:
            return pd.DataFrame(columns=_POSITION_COLUMNS)
        rows = [_equity_row(r, account_no) for r in records if isinstance(r, dict)]
        df = pd.DataFrame(rows, columns=_POSITION_COLUMNS)
        for col in (
            "quantity",
            "sellable_quantity",
            "buying_quantity",
            "selling_quantity",
            "mortgage_quantity",
            "t1_sell_quantity",
            "t2_sell_quantity",
        ):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        df["average_cost"] = pd.to_numeric(df["average_cost"], errors="coerce").astype(
            "float64"
        )
        return df

    def get_derivative_positions(
        self, account_no: str, open_only: bool = False, raw: bool = False
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """
        GET /api/v3/trading/position — phần derivative (open + closed).

        Args:
            open_only: True → chỉ vị thế mở.
        """
        account_no = require_non_empty(account_no, "accountNo")
        data = self._positions_payload(account_no)
        if raw:
            return data
        deriv = data.get("derivative") if isinstance(data, dict) else None
        frames: List[pd.DataFrame] = []
        if isinstance(deriv, dict):
            if not open_only:
                frames.append(
                    _deriv_frame(deriv.get("derClosePositions"), account_no, "CLOSED")
                )
            frames.append(
                _deriv_frame(deriv.get("derOpenPositions"), account_no, "OPEN")
            )
        if not frames:
            return pd.DataFrame(columns=_DERIV_POSITION_COLUMNS)
        df = pd.concat(frames, ignore_index=True)
        if "state" in df.columns:
            df["state"] = df["state"].astype("category")
        return df

    def _positions_payload(self, account_no: str) -> Dict[str, Any]:
        _ = self._session.token
        data = self._transport.request(
            "GET",
            _paths.EP_POSITIONS,
            params={
                "clientId": self._money.require_client_id(),
                "accountNo": account_no,
            },
        )
        return data if isinstance(data, dict) else {}

    # ── Orders ───────────────────────────────────────────────────────────

    def get_today_orders(
        self, account_no: str, raw: bool = False
    ) -> Union[pd.DataFrame, List[Any]]:
        """GET /api/v3/trading/orderBook — from=to=hôm nay."""
        from vnbroker.broker.ssi._utils import today_date_str

        today = today_date_str()
        return self.get_historical_orders(account_no, today, today, raw=raw)

    def get_historical_orders(
        self, account_no: str, from_date: str, to_date: str, raw: bool = False
    ) -> Union[pd.DataFrame, List[Any]]:
        """
        GET /api/v3/trading/orderBook — sổ lệnh theo khoảng ngày YYYY/MM/DD.

        Returns:
            DataFrame columns _ORDER_COLUMNS (side BUY/SELL, status = mã gốc).
        """
        account_no = require_non_empty(account_no, "accountNo")
        from_date = validate_ssi_date(from_date, "from_date")
        to_date = validate_ssi_date(to_date, "to_date")
        _ = self._session.token
        data = self._transport.request(
            "GET",
            _paths.EP_ORDER_HISTORY,
            params={
                "accountNo": account_no,
                "from": from_date,
                "to": to_date,
                "pageIndex": 1,
                "pageSize": 1000,
            },
        )
        if raw:
            records = data.get("orderList", []) if isinstance(data, dict) else []
            return records if isinstance(records, list) else []
        records = data.get("orderList", []) if isinstance(data, dict) else []
        if not isinstance(records, list) or not records:
            return pd.DataFrame(columns=_ORDER_COLUMNS)
        rows = [_order_row(r, account_no) for r in records if isinstance(r, dict)]
        df = pd.DataFrame(rows, columns=_ORDER_COLUMNS)
        for col in (
            "quantity",
            "filled_quantity",
            "os_quantity",
            "cancel_quantity",
        ):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        for col in ("price", "avg_price"):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        for col in ("side", "order_type", "status"):
            df[col] = df[col].astype("category")
        return df

    # ── Snapshot (map tường minh → engine) ───────────────────────────────

    def portfolio_snapshot(
        self,
        account_no: str,
        market_prices: Optional[Mapping[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Tổng hợp snapshot: positions + balance → TCBSPortfolioEngine.

        Map tường minh SSI → engine:
          symbol←symbol, quantity←quantity, average_cost←costPrice,
          current_price←market_prices map, market_value=current_price*quantity,
          unrealized_pnl=(current_price-average_cost)*quantity.

        Args:
            market_prices: {SYMBOL: giá hiện tại}. Thiếu mã → NaN + warning
                           (không bao giờ trả rỗng lặng lẽ).

        Returns:
            dict portfolio_summary + key "holdings" (DataFrame enriched).
        """
        account_no = require_non_empty(account_no, "accountNo")
        prices = {str(k).upper(): float(v) for k, v in (market_prices or {}).items()}
        positions = self.get_equity_positions(account_no)
        assert isinstance(positions, pd.DataFrame)
        if positions.empty:
            _logger.warning("SSI snapshot: không có vị thế cho %s", account_no)
            return _zero_summary()

        df = positions.copy()
        df["current_price"] = df["symbol"].map(prices).astype("float64")
        missing = df.loc[df["current_price"].isna(), "symbol"].tolist()
        if missing:
            _logger.warning(
                "SSI snapshot: thiếu giá thị trường cho %s — PnL NaN.",
                sorted(set(missing)),
            )
        df["market_value"] = df["current_price"] * df["quantity"]
        df["unrealized_pnl"] = (df["current_price"] - df["average_cost"]) * df[
            "quantity"
        ]
        enriched = TCBSPortfolioEngine.holdings_snapshot(df)

        balance = self._money.get_balance(account_no)
        assert isinstance(balance, pd.DataFrame)
        adapted = _adapt_balance(balance, enriched)
        summary = TCBSPortfolioEngine.portfolio_summary(enriched, adapted)
        summary["holdings"] = enriched
        return summary


def _equity_row(record: Dict[str, Any], account_no: str) -> Dict[str, Any]:
    return {
        "account_no": str(record.get("accountNo", account_no)),
        "symbol": str(record.get("symbol", "")),
        "quantity": to_int(record.get("quantity")),
        "sellable_quantity": to_int(record.get("sellableQuantity")),
        "buying_quantity": to_int(record.get("buyingQuantity")),
        "selling_quantity": to_int(record.get("sellingQuantity")),
        "mortgage_quantity": to_int(record.get("mortgageQuantity")),
        "average_cost": to_float(record.get("costPrice")),
        "t1_sell_quantity": to_int(record.get("t1SellQuantity")),
        "t2_sell_quantity": to_int(record.get("t2SellQuantity")),
    }


def _deriv_frame(records: Any, account_no: str, state: str) -> pd.DataFrame:
    if not isinstance(records, list) or not records:
        return pd.DataFrame(columns=_DERIV_POSITION_COLUMNS)
    rows = [
        {
            "account_no": str(r.get("accountNo", account_no)),
            "symbol": str(r.get("symbol", "")),
            "long": to_int(r.get("long")),
            "short": to_int(r.get("short")),
            "net": to_int(r.get("net")),
            "bid_avg_price": to_float(r.get("bidAvgPrice")),
            "ask_avg_price": to_float(r.get("askAvgPrice")),
            "trade_price": to_float(r.get("tradePrice")),
            "floating_pl": to_float(r.get("floatingPL")),
            "trading_pl": to_float(r.get("tradingPL")),
            "state": state,
        }
        for r in records
        if isinstance(r, dict)
    ]
    df = pd.DataFrame(rows, columns=_DERIV_POSITION_COLUMNS)
    for col in ("long", "short", "net"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in (
        "bid_avg_price",
        "ask_avg_price",
        "trade_price",
        "floating_pl",
        "trading_pl",
    ):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def _order_row(record: Dict[str, Any], account_no: str) -> Dict[str, Any]:
    try:
        side = parse_side(str(record.get("side", ""))).name
    except BrokerValidationError:
        side = str(record.get("side", ""))
    order_type = safe_parse(OrderType, record.get("orderType"))
    status = safe_parse(OrderStatus, record.get("orderStatus"))
    return {
        "account_no": str(record.get("accountNo", account_no)),
        "order_id": str(record.get("orderId", "")),
        "client_request_id": str(record.get("clientRequestId", "")),
        "symbol": str(record.get("symbol", "")),
        "side": side,
        "order_type": order_type.name
        if order_type
        else str(record.get("orderType", "")),
        "quantity": to_int(record.get("quantity")),
        "filled_quantity": to_int(record.get("filledQuantity")),
        "os_quantity": to_int(record.get("osQuantity")),
        "cancel_quantity": to_int(record.get("cancelQuantity")),
        "price": to_float(record.get("price")),
        "avg_price": to_float(record.get("avgPrice")),
        "status": status.name if status else str(record.get("orderStatus", "")),
        "input_time": str(record.get("inputTime", "")),
        "modify_time": str(record.get("modifiedTime", "")),
        "message": str(record.get("message", "")),
    }


def _adapt_balance(balance_df: pd.DataFrame, holdings_df: pd.DataFrame) -> pd.DataFrame:
    """Map SSI balance → schema portfolio_summary (total_asset/stock_value/...)."""
    mv_col = (
        holdings_df["market_value"]
        if "market_value" in holdings_df.columns
        else pd.Series(dtype="float64")
    )
    stock_value = float(pd.to_numeric(mv_col, errors="coerce").fillna(0.0).sum())
    if balance_df.empty:
        cash, debt = 0.0, 0.0
    else:
        row = balance_df.iloc[0]
        cash = float(row.get("withdrawable", 0) or 0)
        debt = float(row.get("total_debt", 0) or 0)
    return pd.DataFrame(
        [
            {
                "total_asset": stock_value + cash,
                "stock_value": stock_value,
                "cash_balance": cash,
                "debt_balance": debt,
            }
        ]
    )


def _zero_summary() -> Dict[str, Any]:
    return {
        "total_asset": 0.0,
        "stock_value": 0.0,
        "cash_balance": 0.0,
        "debt_balance": 0.0,
        "num_positions": 0,
        "total_unrealized_pnl": 0.0,
        "top_holding": None,
        "holdings": pd.DataFrame(),
    }
