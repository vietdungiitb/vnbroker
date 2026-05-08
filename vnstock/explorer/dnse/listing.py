"""
vnstock/explorer/dnse/listing.py

DNSE Listing provider - liệt kê các mã chứng khoán từ DNSE LightSpeed OpenAPI.
"""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd

from vnstock.core.utils.logger import get_logger

logger = get_logger(__name__)

# Mapping cột instruments API → tên chuẩn
_INSTRUMENT_COLUMN_MAP: dict[str, str] = {
    "symbol": "symbol",
    "marketId": "exchange",
    "market_id": "exchange",
    "securityGroupId": "security_group",
    "security_group_id": "security_group",
    "name": "organ_name",
    "shortName": "short_name",
    "short_name": "short_name",
    "boardId": "board_id",
    "board_id": "board_id",
    "type": "type",
    "status": "status",
    "lot": "lot_size",
    "lotSize": "lot_size",
}


class DNSEListing:
    """
    DNSE Listing provider.

    Lấy danh sách chứng khoán từ DNSE LightSpeed OpenAPI.
    Cần DNSE_API_KEY và DNSE_API_SECRET.

    Ví dụ:
        >>> lst = DNSEListing(api_key="...", api_secret="...")
        >>> df = lst.all_symbols()
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        show_log: bool = False,
        **kwargs,
    ):
        from vnstock.connector.dnse.client import DNSEClient

        self.show_log = show_log
        resolved_key = api_key or os.environ.get("DNSE_API_KEY", "")
        resolved_secret = api_secret or os.environ.get("DNSE_API_SECRET", "")

        if not resolved_key or not resolved_secret:
            raise ValueError(
                "DNSE cần api_key và api_secret. "
                "Đặt biến môi trường DNSE_API_KEY và DNSE_API_SECRET hoặc truyền trực tiếp. "
                "Đăng ký tại: https://developers.dnse.com.vn/"
            )

        self._client = DNSEClient(
            api_key=resolved_key,
            api_secret=resolved_secret,
            show_log=show_log,
        )
        self._market = self._client._market

    def _fetch_instruments(
        self,
        market_id: Optional[str] = None,
        security_group_id: Optional[str] = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """Gọi API lấy danh sách instruments từ DNSE."""
        try:
            _, body = self._market.get_instruments(
                market_id=market_id,
                security_group_id=security_group_id,
                limit=limit,
            )
        except Exception as exc:
            logger.warning("DNSE get_instruments lỗi: %s", exc)
            return pd.DataFrame()

        if body is None:
            return pd.DataFrame()

        records: list = []
        if isinstance(body, list):
            records = body
        elif isinstance(body, dict):
            for key in ("instruments", "data", "items", "securities"):
                val = body.get(key)
                if isinstance(val, list):
                    records = val
                    break
            if not records:
                records = [body] if body else []

        if not records:
            return pd.DataFrame()

        df = pd.json_normalize(records)
        df.rename(
            columns={k: v for k, v in _INSTRUMENT_COLUMN_MAP.items() if k in df.columns},
            inplace=True,
        )
        return df

    def all_symbols(self, show_log: Optional[bool] = None) -> pd.DataFrame:
        """
        Trả về danh sách toàn bộ mã chứng khoán từ DNSE.

        Trả về:
            pd.DataFrame với cột: symbol, organ_name, exchange, ...
        """
        df = self._fetch_instruments()
        if df.empty:
            return df

        # Đổi tên để khớp format chuẩn vnstock
        for raw_col, std_col in [("name", "organ_name"), ("marketId", "exchange")]:
            if raw_col in df.columns and std_col not in df.columns:
                df.rename(columns={raw_col: std_col}, inplace=True)

        if show_log or self.show_log:
            logger.info("DNSE all_symbols: %d mã tổng", len(df))
        return df.reset_index(drop=True)

    def symbols_by_exchange(
        self,
        exchange: str = "ALL",
        show_log: Optional[bool] = None,
    ) -> pd.DataFrame:
        """
        Lọc danh sách chứng khoán theo sàn.

        Tham số:
            exchange (str): 'HOSE', 'HNX', 'UPCOM', 'ALL'. Mặc định 'ALL'.

        Trả về:
            pd.DataFrame
        """
        market_id = None if exchange.upper() == "ALL" else exchange.upper()
        df = self._fetch_instruments(market_id=market_id)
        if show_log or self.show_log:
            logger.info("DNSE symbols_by_exchange(%s): %d mã", exchange, len(df))
        return df.reset_index(drop=True)

    def symbols_by_group(
        self,
        group: str,
        show_log: Optional[bool] = None,
    ) -> pd.DataFrame:
        """
        Lọc danh sách chứng khoán theo nhóm/ngành.

        Tham số:
            group (str): Mã nhóm chứng khoán theo DNSE.

        Trả về:
            pd.DataFrame
        """
        df = self._fetch_instruments(security_group_id=group)
        if show_log or self.show_log:
            logger.info("DNSE symbols_by_group(%s): %d mã", group, len(df))
        return df.reset_index(drop=True)

    def indices(self, show_log: Optional[bool] = None) -> pd.DataFrame:
        """
        Trả về danh sách các chỉ số (index) từ DNSE.

        Trả về:
            pd.DataFrame
        """
        try:
            _, body = self._market.get_instruments(index_name="all")
        except Exception as exc:
            logger.warning("DNSE indices lỗi: %s", exc)
            # Thử lấy từ danh sách chung và lọc index
            df = self._fetch_instruments()
            if "type" in df.columns:
                return df[df["type"].str.upper() == "INDEX"].reset_index(drop=True)
            return pd.DataFrame()

        if body is None:
            return pd.DataFrame()

        records: list = []
        if isinstance(body, list):
            records = body
        elif isinstance(body, dict):
            for key in ("instruments", "data", "items", "indices"):
                val = body.get(key)
                if isinstance(val, list):
                    records = val
                    break

        if not records:
            return pd.DataFrame()

        df = pd.json_normalize(records)
        df.rename(
            columns={k: v for k, v in _INSTRUMENT_COLUMN_MAP.items() if k in df.columns},
            inplace=True,
        )
        return df.reset_index(drop=True)

    def symbols_by_industries(self, show_log: Optional[bool] = None) -> pd.DataFrame:
        """Compatibility fallback: DNSE không có phân nhóm ngành riêng."""
        if show_log or self.show_log:
            logger.info("DNSE symbols_by_industries fallback to all_symbols")
        return self.all_symbols(show_log=show_log)

    def industries_icb(self, show_log: Optional[bool] = None) -> pd.DataFrame:
        """Compatibility fallback: DNSE không cung cấp ICB hierarchy."""
        if show_log or self.show_log:
            logger.info("DNSE industries_icb fallback to empty DataFrame")
        return pd.DataFrame()

    def all_future_indices(self, show_log: Optional[bool] = None) -> pd.DataFrame:
        """Compatibility fallback to indices()."""
        return self.indices(show_log=show_log)

    def all_covered_warrant(self, show_log: Optional[bool] = None) -> pd.DataFrame:
        """Compatibility fallback: DNSE không có covered warrant riêng trong scope này."""
        if show_log or self.show_log:
            logger.info("DNSE all_covered_warrant fallback to empty DataFrame")
        return pd.DataFrame()

    def all_bonds(self, show_log: Optional[bool] = None) -> pd.DataFrame:
        """Compatibility fallback: DNSE bond listing chưa được map trong scope này."""
        if show_log or self.show_log:
            logger.info("DNSE all_bonds fallback to empty DataFrame")
        return pd.DataFrame()

    def all_government_bonds(self, show_log: Optional[bool] = None) -> pd.DataFrame:
        """Compatibility fallback: DNSE government bond listing chưa được map trong scope này."""
        if show_log or self.show_log:
            logger.info("DNSE all_government_bonds fallback to empty DataFrame")
        return pd.DataFrame()
