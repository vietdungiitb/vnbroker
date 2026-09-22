"""
vnbroker.broker.ssi.money — SSIMoneyService: số dư, PPMMR, sức mua/bán.

  GET /api/v3/trading/accountBalance → get_balance/get_derivative_balance
  GET /api/v3/trading/ppmmrAccount   → get_ppmmr/get_derivative_ppmmr (full columns)
  GET /api/v3/trading/maxBuySell     → get_max_buy_sell[_at_market_price]

RULE: Read-only. Tiền VND giữ nguyên (không chia 1000 ngầm).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from vnbroker.broker.exceptions import BrokerValidationError
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.ssi import _paths
from vnbroker.broker.ssi._transport import SSIHttpClient
from vnbroker.broker.ssi._utils import require_non_empty, require_positive, to_float
from vnbroker.core.utils.parser import camel_to_snake

_logger = logging.getLogger("vnbroker.broker.ssi.money")

_EQUITY_BALANCE_COLUMNS = [
    "account_no",
    "account_balance",
    "total_debt",
    "withdrawable",
    "on_hold_cash",
    "sell_unmatched",
    "sell_t0",
    "sell_t1",
    "sell_t2",
    "buy_unmatched",
    "buy_t0",
    "buy_t1",
    "buy_t2",
    "advance_cash_t0",
    "advance_cash_t1",
    "dividend",
]

_DERIV_BALANCE_COLUMNS = [
    "account_no",
    "account_balance",
    "fee",
    "commission",
    "floating_pl",
    "trading_pl",
    "total_pl",
    "withdrawable",
    "cash_ssi",
    "cash_vsdc",
]

_MAX_BUY_SELL_COLUMNS = [
    "account_no",
    "symbol",
    "max_buy_quantity",
    "max_sell_quantity",
    "margin_ratio",
    "purchase_power",
]


class SSIMoneyService:
    """Read-only money service cho SSI broker."""

    def __init__(
        self,
        config: SSICredentialConfig,
        session: BrokerSession,
        transport: SSIHttpClient,
    ) -> None:
        self._config = config
        self._session = session
        self._transport = transport

    # ── Balance ──────────────────────────────────────────────────────────

    def get_balance(
        self, account_no: str, raw: bool = False
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """
        GET /api/v3/trading/accountBalance — phần equity.

        Returns:
            DataFrame 1 row (raw=False) với cột _EQUITY_BALANCE_COLUMNS (float64).
        """
        account_no = require_non_empty(account_no, "accountNo")
        _ = self._session.token
        data = self._transport.request(
            "GET",
            _paths.EP_ACCOUNT_BALANCE,
            params={
                "clientId": self.require_client_id(),
                "accountNo": account_no,
            },
        )
        if raw:
            return data if isinstance(data, dict) else {}
        equity = data.get("equity") if isinstance(data, dict) else None
        if not isinstance(equity, dict):
            _logger.warning("SSI balance: thiếu phần equity cho %s", account_no)
            return pd.DataFrame(columns=_EQUITY_BALANCE_COLUMNS)
        row = _snake_row(equity, _EQUITY_BALANCE_COLUMNS, account_no)
        df = pd.DataFrame([row], columns=_EQUITY_BALANCE_COLUMNS)
        for col in _EQUITY_BALANCE_COLUMNS[1:]:
            df[col] = df[col].astype("float64")
        return df

    def get_derivative_balance(
        self, account_no: str, raw: bool = False
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """GET /api/v3/trading/accountBalance — phần derivative."""
        account_no = require_non_empty(account_no, "accountNo")
        _ = self._session.token
        data = self._transport.request(
            "GET",
            _paths.EP_ACCOUNT_BALANCE,
            params={
                "clientId": self.require_client_id(),
                "accountNo": account_no,
            },
        )
        if raw:
            return data if isinstance(data, dict) else {}
        deriv = data.get("derivative") if isinstance(data, dict) else None
        if not isinstance(deriv, dict):
            _logger.warning("SSI balance: thiếu phần derivative cho %s", account_no)
            return pd.DataFrame(columns=_DERIV_BALANCE_COLUMNS)
        row = _snake_row(deriv, _DERIV_BALANCE_COLUMNS, default_account=account_no)
        df = pd.DataFrame([row], columns=_DERIV_BALANCE_COLUMNS)
        for col in _DERIV_BALANCE_COLUMNS[1:]:
            df[col] = df[col].astype("float64")
        return df

    # ── PPMMR (full columns, không lược) ─────────────────────────────────

    def get_ppmmr(
        self, account_no: str, raw: bool = False
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """GET /api/v3/trading/ppmmrAccount — phần equity, giữ TOÀN BỘ cột."""
        return self._ppmmr_side(account_no, "equity", raw)

    def get_derivative_ppmmr(
        self, account_no: str, raw: bool = False
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """GET /api/v3/trading/ppmmrAccount — phần derivative, giữ TOÀN BỘ cột."""
        return self._ppmmr_side(account_no, "derivative", raw)

    def _ppmmr_side(
        self, account_no: str, side: str, raw: bool
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        account_no = require_non_empty(account_no, "accountNo")
        _ = self._session.token
        data = self._transport.request(
            "GET", _paths.EP_ACCOUNT_PPMMR, params={"accountNo": account_no}
        )
        if raw:
            return data if isinstance(data, dict) else {}
        section = data.get(side) if isinstance(data, dict) else None
        if not isinstance(section, dict) or not section:
            _logger.warning("SSI PPMMR: thiếu phần %s cho %s", side, account_no)
            return pd.DataFrame()
        row = {camel_to_snake(k): v for k, v in section.items()}
        row["account_no"] = str(section.get("accountNo", account_no))
        df = pd.DataFrame([row])
        for col in df.columns:
            if col == "account_no":
                continue
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        return df

    # ── Max buy/sell ─────────────────────────────────────────────────────

    def get_max_buy_sell(
        self,
        account_no: str,
        symbol: str,
        price: Optional[Union[int, float]] = None,
        raw: bool = False,
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """
        GET /api/v3/trading/maxBuySell.

        Args:
            price: None → giá thị trường (at_market_price).
        """
        account_no = require_non_empty(account_no, "accountNo")
        symbol = require_non_empty(symbol, "symbol").upper()
        _ = self._session.token
        params: Dict[str, Any] = {"accountNo": account_no, "symbol": symbol}
        if price is not None:
            require_positive(price, "price")
            params["price"] = f"{price}"
        data = self._transport.request(
            "GET", _paths.EP_TRADING_MAX_BUY_SELL, params=params
        )
        if raw:
            return data if isinstance(data, dict) else {}
        rec = data if isinstance(data, dict) else {}
        row = {
            "account_no": str(rec.get("accountNo", account_no)),
            "symbol": symbol,
            "max_buy_quantity": to_float(rec.get("maxBuyQty")),
            "max_sell_quantity": to_float(rec.get("maxSellQty")),
            "margin_ratio": str(rec.get("marginRatio", "")),
            "purchase_power": str(rec.get("purchasePower", "")),
        }
        df = pd.DataFrame([row], columns=_MAX_BUY_SELL_COLUMNS)
        df["max_buy_quantity"] = df["max_buy_quantity"].astype("Int64")
        df["max_sell_quantity"] = df["max_sell_quantity"].astype("Int64")
        return df

    def get_max_buy_sell_at_market_price(
        self, account_no: str, symbol: str, raw: bool = False
    ) -> Union[pd.DataFrame, Dict[str, Any]]:
        """Sức mua/bán theo giá thị trường (không truyền price)."""
        return self.get_max_buy_sell(account_no, symbol, price=None, raw=raw)

    # ── Private ──────────────────────────────────────────────────────────

    def require_client_id(self) -> str:
        """client_id bắt buộc cho balance/positions (dùng chung với portfolio)."""
        client_id = (self._config.client_id or "").strip()
        if not client_id:
            raise BrokerValidationError(
                message="Thiếu client_id SSI (cần cho balance/positions).",
                code="CLIENT_ID_REQUIRED",
                http_status=400,
            )
        return client_id


def _snake_row(
    source: Dict[str, Any], columns: List[str], default_account: str
) -> Dict[str, Any]:
    """Map key server (camelCase, vd floatingPL) → snake_case qua camel_to_snake."""
    snake = {camel_to_snake(str(k)): v for k, v in source.items()}
    row: Dict[str, Any] = {"account_no": str(snake.get("account_no", default_account))}
    for col in columns[1:]:
        row[col] = to_float(snake.get(col))
    return row
