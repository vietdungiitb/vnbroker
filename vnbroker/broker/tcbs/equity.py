"""
vnbroker.broker.tcbs.equity — TCBSEquityService: read + write equity.

READ endpoints:
  GET /gaia/v1/openapi/account/{accountNo}/orders
  GET /gaia/v1/openapi/account/{accountNo}/orders/{orderId}
  GET /gaia/v1/openapi/account/{accountNo}/orders/history
  GET /gaia/v1/openapi/account/{accountNo}/executions
  GET /gaia/v1/openapi/account/{accountNo}/portfolio/holdings

WRITE endpoints (dry_run=True mặc định, @write_gate bắt buộc):
  POST   /gaia/v1/openapi/account/{accountNo}/orders          → place_order()
  PUT    /gaia/v1/openapi/account/{accountNo}/orders/{orderId} → modify_order()
  DELETE /gaia/v1/openapi/account/{accountNo}/orders/{orderId} → cancel_order()

SECURITY RULES:
  - pinCode KHÔNG được log. Redacted trong dry_run output.
  - request_id bắt buộc cho mọi write call (idempotency).
  - Dùng requests trực tiếp. KHÔNG dùng core/utils/client.
"""
from __future__ import annotations

import logging
from typing import Optional, Union

import pandas as pd
import requests

from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerNetworkError,
    BrokerOrderError,
    BrokerPermissionError,
    BrokerRateLimitError,
    BrokerSessionExpiredError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.security.guards import write_gate
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.tcbs.account import _validate_account_no

_logger = logging.getLogger("vnbroker.broker.tcbs.equity")

_PATHS = {
    "orders": "/aion/v1/accounts/{accountNo}/orders",
    "order_detail": "/aion/v1/accounts/{accountNo}/orders/{orderID}",
    "order_history": "/aion/v1/accounts/{accountNo}/orders/history",
    "matching_details": "/aion/v1/accounts/{accountNo}/matching-details",
    "se": "/aion/v1/accounts/{accountNo}/se",
    "place_order": "/akhlys/v1/accounts/{accountNo}/orders",
    "modify_order": "/akhlys/v1/accounts/{accountNo}/orders/{orderId}",
    "cancel_orders": "/akhlys/v1/accounts/{accountNo}/cancel-orders",
    # market enrichment (dùng trong get_holdings)
    "ticker_commons": "/tartarus/v1/tickerCommons",
}

# OrderInfo schema từ /aion/v1/accounts/{accountNo}/orders
_ORDER_COLUMNS = {
    "orderID": "order_id",
    "symbol": "symbol",
    "execType": "side",      # NB=buy, NS=sell
    "priceType": "order_type",
    "orderQtty": "quantity",
    "execQtty": "filled_quantity",
    "price": "price",
    "status": "status",
    "txdate": "tx_date",
    "txtime": "tx_time",
}

# CommandMatchInformationDetailResponse
_EXECUTION_COLUMNS = {
    "orderId": "order_id",
    "side": "side",          # B=buy, S=sell
    "symbol": "symbol",
    "quoteQtty": "quote_quantity",
    "quotePrice": "quote_price",
    "tradeId": "trade_id",
    "executionId": "execution_id",
    "qtty": "executed_quantity",
    "price": "executed_price",
    "tradeDate": "trade_date",
    "tradeTime": "trade_time",
}

# StockHoldingInfo schema từ SeInfoDTO.stock[]
_HOLDING_COLUMNS = {
    "symbol": "symbol",
    "secType": "sec_type",
    "availableTrading": "available_quantity",
    "t0": "t0",
    "t1": "t1",
    "t2": "t2",
    "t3": "t3",
    "mortgaged": "mortgaged",
    "averageCost": "average_cost",
    "currentPrice": "market_price",
    "unrealizedPnl": "unrealized_pnl",
    "unrealizedPnlPercent": "unrealized_pnl_pct",
}


class TCBSEquityService:
    """Read-only equity service: danh sách lệnh, lịch sử khớp, holdings."""

    def __init__(
        self,
        config: TCBSCredentialConfig,
        session: BrokerSession,
    ) -> None:
        self._config = config
        self._session = session

    # ── Orders ────────────────────────────────────────────────────────────────

    def get_orders(
        self,
        account_no: str,
        size: int = 100,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /aion/v1/accounts/{accountNo}/orders

        Trả về sổ lệnh trong ngày. TCBS không hỗ trợ phân trang trên endpoint này.

        Args:
            size: Số lượng lệnh tối đa (mặc định 100).

        DataFrame columns (raw=False):
            order_id, symbol, side (category: NB/NS),
            order_type (category: LO/ATO/ATC/MP…),
            quantity (Int64), filled_quantity (Int64),
            price (float64), status (category),
            tx_date (str), tx_time (str)
        """
        _validate_account_no(account_no)
        path = _PATHS["orders"].format(accountNo=account_no)
        data = self._get(path, params={"size": size})

        if raw:
            return data

        # OrderSearchResponse: {object, pageSize, pageIndex, totalCount, data: [OrderInfo]}
        records = data.get("data", []) if isinstance(data, dict) else data
        df = _build_order_df(records)
        return df

    def get_order_history(
        self,
        account_no: str,
        from_date: str = "",
        to_date: str = "",
        size: int = 100,
        symbol: str = "",
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /aion/v1/accounts/{accountNo}/orders/history

        Trả về lịch sử lệnh trong khoảng thời gian.

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            from_date: Ngày bắt đầu (YYYY-MM-DD).
            to_date: Ngày kết thúc (YYYY-MM-DD).
            size: Số lượng lệnh tối đa (mặc định 100).
            symbol: Lọc theo mã chứng khoán (tùy chọn).
            raw: True → trả về dict nguyên gốc.

        DataFrame columns (raw=False):
            order_id, symbol, side (category: NB/NS),
            order_type (category: LO/ATO/ATC/MP…),
            quantity (Int64), filled_quantity (Int64),
            price (float64), status (category),
            tx_date (str), tx_time (str)
        """
        _validate_account_no(account_no)
        path = _PATHS["order_history"].format(accountNo=account_no)
        params = {"size": size}
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        if symbol:
            params["symbol"] = symbol.upper()
        data = self._get(path, params=params)

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else data
        df = _build_order_df(records)
        return df

    def get_order_detail(
        self,
        account_no: str,
        order_id: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /aion/v1/accounts/{accountNo}/orders/{orderID}
        """
        _validate_account_no(account_no)
        if not order_id or not order_id.strip():
            raise BrokerValidationError(
                message="order_id không được để trống.",
                code="INVALID_ORDER_ID",
            )
        path = _PATHS["order_detail"].format(accountNo=account_no, orderID=order_id)
        data = self._get(path)

        if raw:
            return data

        # Handle both paginated response {data: [...]} and flat response {...}
        if isinstance(data, dict) and "data" in data:
            records = data.get("data", [])
        else:
            records = [data] if data else []
        
        if not records:
            return pd.DataFrame(columns=list(_ORDER_COLUMNS.values()))
        df = _build_order_df(records)
        return df

    # ── Executions (matching details) ─────────────────────────────────────────

    def get_executions(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /aion/v1/accounts/{accountNo}/matching-details

        DataFrame columns (raw=False):
            order_id, trade_id, execution_id, symbol,
            side (category: B/S),
            quote_quantity (Int64), quote_price (float64),
            executed_quantity (Int64), executed_price (float64),
            trade_date (str), trade_time (str),
            fee (float64)
        """
        _validate_account_no(account_no)
        path = _PATHS["matching_details"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        # CommandMatchInformationResponse: {object, totalCount, pageSize, pageIndex, data: [...]}
        records = data.get("data", []) if isinstance(data, dict) else data
        if not records:
            return pd.DataFrame(columns=list(_EXECUTION_COLUMNS.values()) + ["fee"])

        df = pd.DataFrame(records)
        df = df.rename(columns=_EXECUTION_COLUMNS)
        df = _ensure_columns(df, list(_EXECUTION_COLUMNS.values()) + ["fee"])
        if "side" in df.columns:
            df["side"] = df["side"].astype("category")
        for col in ("quote_price", "executed_price"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        for col in ("quote_quantity", "executed_quantity"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        if "fee" in df.columns:
            df["fee"] = pd.to_numeric(df["fee"], errors="coerce").astype("int64")

        return df

    # ── Holdings ──────────────────────────────────────────────────────────────

    def get_holdings(
        self,
        account_no: str,
        enrich_prices: bool = True,
        raw: bool = False,
    ) -> Union[pd.DataFrame, list]:
        """
        GET /aion/v1/accounts/{accountNo}/se

        Trả về danh mục cổ phiếu (SeInfoDTO.stock[]). Nếu enrich_prices=True,
        tự động gọi /tartarus/v1/tickerCommons để bổ sung giá thị trường.

        DataFrame columns (raw=False):
            symbol, sec_type (str),
            available_quantity (Int64), t0 (Int64), t1 (Int64), t2 (Int64), t3 (Int64),
            mortgaged (Int64),
            average_cost (float64), market_price (float64),
            unrealized_pnl (float64), unrealized_pnl_pct (float64)
        """
        _validate_account_no(account_no)
        path = _PATHS["se"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        # SeInfoDTO: {object, accountNo, custodyID, fullName, stock: [StockHoldingInfo]}
        stock_list = data.get("stock", []) if isinstance(data, dict) else data
        if not stock_list:
            return pd.DataFrame(columns=list(_HOLDING_COLUMNS.values()))

        df = pd.DataFrame(stock_list)
        df = df.rename(columns=_HOLDING_COLUMNS)
        df = _ensure_columns(df, _HOLDING_COLUMNS.values())

        for col in ("available_quantity", "t0", "t1", "t2", "t3", "mortgaged"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        for col in ("average_cost", "market_price", "unrealized_pnl", "unrealized_pnl_pct"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

        if enrich_prices and not df.empty:
            symbols = ",".join(df["symbol"].dropna().tolist())
            try:
                price_data = self._get(
                    _PATHS["ticker_commons"],
                    params={"tickers": symbols},
                )
                price_records = price_data if isinstance(price_data, list) else price_data.get("data", [])
                price_map = {
                    r.get("symbol", ""): float(r.get("matchPrice") or r.get("refPrice") or 0)
                    for r in price_records
                    if isinstance(r, dict)
                }
                df["market_price"] = df["symbol"].map(price_map).astype("float64")
            except Exception as exc:
                _logger.warning("get_holdings: bỏ qua enrich_prices — %s", exc)

        return df

    # ── Write methods (dry_run=True default) ────────────────────────────────
    # Pattern: validation chạy TRƯỚC write_gate check.
    # Public method validate → delegate sang @write_gate internal method.

    def place_order(
        self,
        account_no: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float,
        pin_code: str,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict:
        """
        POST /akhlys/v1/accounts/{accountNo}/orders

        Args:
            side: 'BUY' hoặc 'SELL' (được map sang 'NB'/'NS' theo spec).
            order_type: 'LO', 'ATO', 'ATC', 'MP', 'MTL', 'MOK', 'MAK', 'PLO'.
            price: Giá tính theo đơn vị đồng (float).
            pin_code: Mã PIN giao dịch (bắt buộc theo TCBS spec).
            request_id: ID idempotency key (bắt buộc theo TCBS spec).
            dry_run: True (default) → không gửi HTTP, trả về dry_run dict.
                     False → gửi thực. Yêu cầu session.enable_write() trước.

        Returns:
            {'error': '0', 'message': '...', 'orderId': '...'} khi dry_run=False.
        """
        _validate_account_no(account_no)
        _validate_order_input(symbol, side, order_type, quantity, price, request_id)
        return self._gated_place_order(
            account_no, symbol, side, order_type, quantity, price, pin_code, request_id,
            dry_run=dry_run,
        )

    @write_gate
    def _gated_place_order(
        self,
        account_no: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float,
        pin_code: str,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict:
        exec_type = "NB" if side.upper() == "BUY" else "NS"
        payload = {
            "symbol": symbol.upper(),
            "execType": exec_type,
            "priceType": order_type.upper(),
            "quantity": quantity,
            "price": int(price),
            "pinCode": pin_code,
            "requestId": request_id,
        }
        url = self._config.base_url.rstrip("/") + _PATHS["place_order"].format(accountNo=account_no)
        return self._post(url, payload)

    def modify_order(
        self,
        account_no: str,
        order_id: str,
        quantity: int,
        price: float,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict:
        """
        PUT /akhlys/v1/accounts/{accountNo}/orders/{orderId}

        Args:
            price: Giá mới (float, đơn vị đồng).
            quantity: Khối lượng mới.
            request_id: ID idempotency key (bắt buộc theo TCBS spec).
        """
        _validate_account_no(account_no)
        if not order_id or not order_id.strip():
            raise BrokerValidationError(
                message="order_id không được để trống.",
                code="INVALID_ORDER_ID",
            )
        if quantity <= 0:
            raise BrokerValidationError(
                message="quantity phải > 0.",
                code="INVALID_QUANTITY",
            )
        if price < 0:
            raise BrokerValidationError(
                message="price phải >= 0.",
                code="INVALID_PRICE",
            )
        if not request_id or not request_id.strip():
            raise BrokerValidationError(
                message="request_id là bắt buộc cho write methods (idempotency key).",
                code="MISSING_REQUEST_ID",
            )
        return self._gated_modify_order(account_no, order_id, quantity, price, request_id, dry_run=dry_run)

    @write_gate
    def _gated_modify_order(
        self,
        account_no: str,
        order_id: str,
        quantity: int,
        price: float,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict:
        payload = {
            "quantity": quantity,
            "price": int(price),
            "requestId": request_id,
        }
        url = self._config.base_url.rstrip("/") + _PATHS["modify_order"].format(
            accountNo=account_no, orderId=order_id
        )
        return self._put(url, payload)

    def cancel_order(
        self,
        account_no: str,
        order_id: str,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict:
        """
        PUT /akhlys/v1/accounts/{accountNo}/cancel-orders

        Body: {ordersList: [{orderID: order_id}], requestId: request_id}
        Hỗ trợ huỷ nhiều lệnh: truyền list order_id qua cancel_orders().
        """
        _validate_account_no(account_no)
        if not order_id or not order_id.strip():
            raise BrokerValidationError(
                message="order_id không được để trống.",
                code="INVALID_ORDER_ID",
            )
        if not request_id or not request_id.strip():
            raise BrokerValidationError(
                message="request_id là bắt buộc cho write methods (idempotency key).",
                code="MISSING_REQUEST_ID",
            )
        return self._gated_cancel_order(account_no, [order_id], request_id, dry_run=dry_run)

    def cancel_orders(
        self,
        account_no: str,
        order_ids: list[str],
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict:
        """
        PUT /akhlys/v1/accounts/{accountNo}/cancel-orders

        Huỷ nhiều lệnh cùng lúc.
        """
        _validate_account_no(account_no)
        if not order_ids:
            raise BrokerValidationError(
                message="order_ids không được rỗng.",
                code="INVALID_ORDER_ID",
            )
        if not request_id or not request_id.strip():
            raise BrokerValidationError(
                message="request_id là bắt buộc cho write methods (idempotency key).",
                code="MISSING_REQUEST_ID",
            )
        return self._gated_cancel_order(account_no, order_ids, request_id, dry_run=dry_run)

    @write_gate
    def _gated_cancel_order(
        self,
        account_no: str,
        order_ids: list[str],
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict:
        payload = {
            "ordersList": [{"orderID": oid} for oid in order_ids],
            "requestId": request_id,
        }
        url = self._config.base_url.rstrip("/") + _PATHS["cancel_orders"].format(accountNo=account_no)
        return self._put(url, payload)

    # ── Internal HTTP ────────────────────────────────────────────────────────

    def _get(self, path: str, params: Optional[dict] = None) -> dict | list:
        try:
            token = self._session.token
        except BrokerSessionExpiredError:
            raise

        if not token:
            raise BrokerPermissionError(
                message="Session chưa được xác thực.",
                code="NOT_AUTHENTICATED",
                http_status=403,
            )

        url = self._config.base_url.rstrip("/") + path
        headers = {"Authorization": f"Bearer {token}"}

        try:
            resp = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=self._config.timeout_seconds,
            )
        except requests.exceptions.Timeout as exc:
            raise BrokerNetworkError(
                message=f"Timeout khi gọi {path}.",
                code="NETWORK_TIMEOUT",
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise BrokerNetworkError(
                message=f"Lỗi mạng: {type(exc).__name__}",
                code="NETWORK_ERROR",
            ) from exc

        if resp.status_code == 401:
            self._session.revoke()
            raise BrokerAuthError(
                message="Token hết hạn hoặc không hợp lệ.",
                code="TOKEN_EXPIRED",
                http_status=401,
            )
        if resp.status_code == 403:
            raise BrokerPermissionError(
                message="Không đủ quyền truy cập.",
                code="FORBIDDEN",
                http_status=403,
            )
        if resp.status_code == 429:
            raise BrokerRateLimitError(
                message="Vượt rate limit TCBS.",
                code="RATE_LIMIT",
                http_status=429,
            )
        if resp.status_code == 400:
            raise BrokerValidationError(
                message=f"Request không hợp lệ: {resp.text[:200]}",
                code="BAD_REQUEST",
                http_status=400,
            )
        if resp.status_code >= 500:
            raise BrokerNetworkError(
                message=f"TCBS server error {resp.status_code}.",
                code="SERVER_ERROR",
                http_status=resp.status_code,
            )

        return resp.json()

    def _post(self, url: str, payload: dict) -> dict:
        return self._write_request("POST", url, payload)

    def _put(self, url: str, payload: dict) -> dict:
        return self._write_request("PUT", url, payload)

    def _write_request(self, method: str, url: str, payload: dict) -> dict:
        """
        Gửi write request. pinCode và Authorization KHÔNG được log.
        """
        try:
            token = self._session.token
        except BrokerSessionExpiredError:
            raise

        headers = {"Authorization": f"Bearer {token}"}

        try:
            resp = requests.request(
                method,
                url,
                json=payload,
                headers=headers,
                timeout=self._config.timeout_seconds,
            )
        except requests.exceptions.Timeout as exc:
            raise BrokerNetworkError(
                message=f"Timeout khi gọi {method} {url}.",
                code="NETWORK_TIMEOUT",
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise BrokerNetworkError(
                message=f"Lỗi mạng: {type(exc).__name__}",
                code="NETWORK_ERROR",
            ) from exc

        if resp.status_code == 401:
            self._session.revoke()
            raise BrokerAuthError(
                message="Token hết hạn hoặc không hợp lệ.",
                code="TOKEN_EXPIRED",
                http_status=401,
            )
        if resp.status_code == 403:
            raise BrokerPermissionError(
                message="Không đủ quyền thực thi lệnh.",
                code="FORBIDDEN",
                http_status=403,
            )
        if resp.status_code == 422:
            raise BrokerOrderError(
                message=f"Lỗi nghiệp vụ lệnh: {resp.text[:200]}",
                code="ORDER_REJECTED",
                http_status=422,
            )
        if resp.status_code == 429:
            raise BrokerRateLimitError(
                message="Vượt rate limit TCBS.",
                code="RATE_LIMIT",
                http_status=429,
            )
        if resp.status_code == 400:
            raise BrokerValidationError(
                message=f"Request không hợp lệ: {resp.text[:200]}",
                code="BAD_REQUEST",
                http_status=400,
            )
        if resp.status_code >= 500:
            raise BrokerNetworkError(
                message=f"TCBS server error {resp.status_code}.",
                code="SERVER_ERROR",
                http_status=resp.status_code,
            )

        return resp.json()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _build_order_df(records: list) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=list(_ORDER_COLUMNS.values()))
    df = pd.DataFrame(records)
    df = df.rename(columns=_ORDER_COLUMNS)
    df = _ensure_columns(df, _ORDER_COLUMNS.values())
    for col in ("side", "order_type", "status"):
        if col in df.columns:
            df[col] = df[col].astype("category")
    for col in ("price",):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    for col in ("quantity", "filled_quantity"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


def _ensure_columns(df: pd.DataFrame, columns) -> pd.DataFrame:
    """Đảm bảo DataFrame có đủ các columns, thêm NaN nếu thiếu."""
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    return df


_VALID_PRICE_TYPES = frozenset({"LO", "ATO", "ATC", "PLO", "MP", "MTL", "MOK", "MAK"})


def _validate_order_input(
    symbol: str,
    side: str,
    order_type: str,
    quantity: int,
    price: float,
    request_id: str,
) -> None:
    """Validate đầu vào cho place_order theo TCBS iFlash spec."""
    if not symbol or not symbol.strip():
        raise BrokerValidationError(
            message="symbol không được để trống.",
            code="INVALID_SYMBOL",
        )
    if side.upper() not in ("BUY", "SELL"):
        raise BrokerValidationError(
            message="side phải là 'BUY' hoặc 'SELL'.",
            code="INVALID_SIDE",
        )
    if order_type.upper() not in _VALID_PRICE_TYPES:
        raise BrokerValidationError(
            message=f"order_type không hợp lệ. Hỗ trợ: {', '.join(sorted(_VALID_PRICE_TYPES))}.",
            code="INVALID_ORDER_TYPE",
        )
    if quantity <= 0:
        raise BrokerValidationError(
            message="quantity phải > 0.",
            code="INVALID_QUANTITY",
        )
    if price < 0:
        raise BrokerValidationError(
            message="price phải >= 0.",
            code="INVALID_PRICE",
        )
    if not request_id or not request_id.strip():
        raise BrokerValidationError(
            message="request_id là bắt buộc cho write methods (idempotency key).",
            code="MISSING_REQUEST_ID",
        )

