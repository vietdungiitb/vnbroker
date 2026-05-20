"""
vnbroker.broker.tcbs.market — TCBSMarketService: market data (public + auth modes).

Endpoints (TCBS iFlash Open API v1.0.0):
  GET /tartarus/v1/tickerCommons?tickers=FPT,VNM   → get_ticker_info()
  GET /tartarus/v1/tickerSnaps?index=1             → get_ticker_snaps()
  GET /tartarus/v1/putThroughSnaps?floor=1         → get_put_through_snaps()
  GET /nyx/v1/intraday/{ticker}/his/paging         → get_intraday_history()
  GET /nyx/v1/intraday/{ticker}/bsa?type=all       → get_bsa()
  GET /nyx/v1/intraday/{ticker}/bsa-ext            → get_bsa_15m()
  GET /nyx/v1/intraday/{ticker}/bsa-month          → get_bsa_month()
  GET /tartarus/v1/derivatives                     → get_derivatives_info()

MODES:
  - public: session=None → không gửi Authorization header.
  - auth:   session != None → gửi Bearer JWT từ session.token.
"""
from __future__ import annotations

import logging
from typing import Optional, Union

import pandas as pd
import requests

from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerNetworkError,
    BrokerRateLimitError,
    BrokerSessionExpiredError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.session import BrokerSession

_logger = logging.getLogger("vnbroker.broker.tcbs.market")

_PATHS = {
    "ticker_commons": "/tartarus/v1/tickerCommons",
    "ticker_snaps": "/tartarus/v1/tickerSnaps",
    "put_through_snaps": "/tartarus/v1/putThroughSnaps",
    "intraday_history": "/nyx/v1/intraday/{ticker}/his/paging",
    "bsa": "/nyx/v1/intraday/{ticker}/bsa",
    "bsa_ext": "/nyx/v1/intraday/{ticker}/bsa-ext",
    "bsa_month": "/nyx/v1/intraday/{ticker}/bsa-month",
    "derivatives": "/tartarus/v1/derivatives",
}

# SupplyAndDemand15mResponse schema
_BSA_15M_COLUMNS = {
    "bu": "buy_volume",
    "bms": "accum_buy",
    "bup": "buy_pct",
    "sd": "sell_volume",
    "sms": "accum_sell",
    "sdp": "sell_pct",
    "bsr": "buy_sell_ratio",
    "t": "time",
    "s": "price",
}

# PriceMatchingHistoryResponse schema
_INTRADAY_COLUMNS = {
    "p": "price",
    "v": "volume",
    "cp": "change",
    "rcp": "change_pct",
    "a": "action",      # "Buy up" | "Sell down"
    "ba": "accum_buy",
    "sa": "accum_sell",
    "hl": "is_highlight",  # True nếu > 200M
    "t": "time",
}


class TCBSMarketService:
    """
    Market data service cho TCBS broker.

    Hỗ trợ cả public mode (session=None) và auth mode (session có JWT).
    """

    def __init__(
        self,
        config: TCBSCredentialConfig,
        session: Optional[BrokerSession] = None,
    ) -> None:
        self._config = config
        self._session = session

    # ── Ticker info ───────────────────────────────────────────────────────────

    def get_ticker_info(
        self,
        tickers: Optional[str | list[str]] = None,
        index: Optional[int] = None,
        raw: bool = False,
    ) -> Union[pd.DataFrame, list]:
        """
        GET /tartarus/v1/tickerCommons?tickers=FPT,VNM
                                    OR ?index=1

        Lấy thông tin cơ bản về cổ phiếu/chỉ số.

        Args:
            tickers: Chuỗi "FPT,VNM" hoặc list ["FPT", "VNM"].
            index: Chỉ số (1=HOSE, 2=HNX, 3=UPCOM, ...) — dùng thay cho tickers.

        Returns DataFrame với các cột từ TickerCommonResponse.
        """
        if not tickers and index is None:
            raise BrokerValidationError(
                message="Phải cung cấp tickers hoặc index.",
                code="MISSING_PARAMS",
            )
        params: dict = {}
        if tickers is not None:
            if isinstance(tickers, list):
                params["tickers"] = ",".join(t.upper() for t in tickers)
            else:
                params["tickers"] = tickers.upper()
        if index is not None:
            params["index"] = index

        data = self._get(_PATHS["ticker_commons"], params=params)

        if raw:
            return data

        records = data if isinstance(data, list) else data.get("data", [data])
        if not records:
            return pd.DataFrame()
        return pd.DataFrame(records)

    def get_ticker_snaps(
        self,
        index: int = 1,
        raw: bool = False,
    ) -> Union[pd.DataFrame, list]:
        """
        GET /tartarus/v1/tickerSnaps?index=1

        Snapshot giá hiện tại cho tất cả mã trong sàn/chỉ số.
        index: 1=HOSE, 2=HNX, 3=UPCOM.
        """
        data = self._get(_PATHS["ticker_snaps"], params={"index": index})
        if raw:
            return data
        records = data if isinstance(data, list) else data.get("data", [])
        return pd.DataFrame(records) if records else pd.DataFrame()

    def get_put_through_snaps(
        self,
        floor: int = 1,
        raw: bool = False,
    ) -> Union[pd.DataFrame, list]:
        """
        GET /tartarus/v1/putThroughSnaps?floor=1

        Snapshot giao dịch thỏa thuận (put-through) theo sàn.
        floor: 1=HOSE, 2=HNX, 3=UPCOM.
        """
        data = self._get(_PATHS["put_through_snaps"], params={"floor": floor})
        if raw:
            return data
        records = data if isinstance(data, list) else data.get("data", [])
        return pd.DataFrame(records) if records else pd.DataFrame()

    # ── Intraday data ─────────────────────────────────────────────────────────

    def get_intraday_history(
        self,
        ticker: str,
        page: int = 0,
        size: int = 100,
        head_index: Optional[int] = None,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /nyx/v1/intraday/{ticker}/his/paging

        Lịch sử khớp lệnh trong ngày (PriceMatchingHistoryResponse).

        DataFrame columns (raw=False):
            price (float64), volume (Int64), change (float64), change_pct (float64),
            action (str), accum_buy (Int64), accum_sell (Int64),
            is_highlight (bool), time (str)
        """
        if not ticker or not ticker.strip():
            raise BrokerValidationError(
                message="ticker không được để trống.",
                code="INVALID_TICKER",
            )
        params: dict = {"page": page, "size": size}
        if head_index is not None:
            params["headIndex"] = head_index

        path = _PATHS["intraday_history"].format(ticker=ticker.upper())
        data = self._get(path, params=params)

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else data
        if not records:
            return pd.DataFrame(columns=list(_INTRADAY_COLUMNS.values()))

        df = pd.DataFrame(records)
        df = df.rename(columns=_INTRADAY_COLUMNS)
        for col in ("price", "change", "change_pct"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        for col in ("volume", "accum_buy", "accum_sell"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        return df

    def get_bsa(
        self,
        ticker: str,
        bsa_type: str = "all",
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /nyx/v1/intraday/{ticker}/bsa?type=all

        Buy/Sell Analysis — phân tích mua/bán theo mã.

        Args:
            bsa_type: "all" | "buy" | "sell".
        """
        if not ticker or not ticker.strip():
            raise BrokerValidationError(
                message="ticker không được để trống.",
                code="INVALID_TICKER",
            )
        path = _PATHS["bsa"].format(ticker=ticker.upper())
        data = self._get(path, params={"type": bsa_type})

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else data
        return pd.DataFrame(records) if records else pd.DataFrame()

    def get_bsa_15m(
        self,
        ticker: str,
        time_window: int = 15,
        bsa_type: str = "all",
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /nyx/v1/intraday/{ticker}/bsa-ext?timeWindow=15&tWindow=15&type=all

        Buy/Sell Analysis theo từng phiên 15 phút (SupplyAndDemand15mResponse).

        DataFrame columns (raw=False):
            time (str), price (float64),
            buy_volume (Int64), accum_buy (Int64), buy_pct (float64),
            sell_volume (Int64), accum_sell (Int64), sell_pct (float64),
            buy_sell_ratio (float64)
        """
        if not ticker or not ticker.strip():
            raise BrokerValidationError(
                message="ticker không được để trống.",
                code="INVALID_TICKER",
            )
        path = _PATHS["bsa_ext"].format(ticker=ticker.upper())
        params = {"timeWindow": time_window, "tWindow": time_window, "type": bsa_type}
        data = self._get(path, params=params)

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else data
        if not records:
            return pd.DataFrame(columns=list(_BSA_15M_COLUMNS.values()))

        df = pd.DataFrame(records)
        df = df.rename(columns=_BSA_15M_COLUMNS)
        for col in ("price", "buy_pct", "sell_pct", "buy_sell_ratio"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        for col in ("buy_volume", "accum_buy", "sell_volume", "accum_sell"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        return df

    def get_bsa_month(
        self,
        ticker: str,
        bsa_type: str = "all",
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /nyx/v1/intraday/{ticker}/bsa-month?timeWindow=1M&type=all

        Buy/Sell Analysis tổng hợp theo tháng.
        """
        if not ticker or not ticker.strip():
            raise BrokerValidationError(
                message="ticker không được để trống.",
                code="INVALID_TICKER",
            )
        path = _PATHS["bsa_month"].format(ticker=ticker.upper())
        data = self._get(path, params={"timeWindow": "1M", "type": bsa_type})

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else data
        return pd.DataFrame(records) if records else pd.DataFrame()

    # ── Derivatives info ──────────────────────────────────────────────────────

    def get_derivatives_info(
        self,
        raw: bool = False,
    ) -> Union[pd.DataFrame, list]:
        """
        GET /tartarus/v1/derivatives

        Danh sách hợp đồng phái sinh đang niêm yết.
        """
        data = self._get(_PATHS["derivatives"])
        if raw:
            return data
        records = data if isinstance(data, list) else data.get("data", [])
        return pd.DataFrame(records) if records else pd.DataFrame()

    # ── Internal HTTP ─────────────────────────────────────────────────────────

    def _get(self, path: str, params: Optional[dict] = None) -> dict | list:
        """
        Gửi GET request. Public mode: không gửi Authorization.
        Auth mode: gửi Bearer JWT từ session.
        """
        url = self._config.base_url.rstrip("/") + path
        headers: dict = {}

        if self._session is not None:
            try:
                token = self._session.token
            except BrokerSessionExpiredError:
                raise
            if token:
                headers["Authorization"] = f"Bearer {token}"

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
            if self._session is not None:
                self._session.revoke()
            raise BrokerAuthError(
                message="Token hết hạn hoặc không hợp lệ.",
                code="TOKEN_EXPIRED",
                http_status=401,
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
