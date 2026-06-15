"""
Listing module cho nguồn dữ liệu TCBS.

Sử dụng TCBS ligo watchlist preview API để truy xuất danh sách mã chứng khoán.
API: POST _BASE_URL/ligo/v1/watchlist/preview
     Response: {"searchData": {"pageContent": [{"t": symbol, "exchangeName": ..., ...}]}}
"""
from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from vnbroker.core.utils import client
from vnbroker.core.utils.execution import optimize_execution
from vnbroker.core.utils.logger import get_logger
from vnbroker.core.utils.parser import camel_to_snake
from .auth import get_tcbs_headers
from .const import _BASE_URL

logger = get_logger(__name__)

_WATCHLIST_URL = f"{_BASE_URL}/ligo/v1/watchlist/preview"

_GROUP_CODE: Dict[str, str] = {
    "VN30": "VN30",
    "VN100": "VN100",
    "VNMIDCAP": "VNMidCap",
    "VNSMALLCAP": "VNSmallCap",
    "VNSI": "VNSI",
    "VNX50": "VNX50",
    "VNXALL": "VNXALL",
    "HNX30": "HNX30",
    "ETF": "ETF",
    "CW": "CW",
    "BOND": "BOND",
    "HOSE": "HOSE",
    "HNX": "HNX",
    "UPCOM": "UPCOM",
    "FU_INDEX": "FU_INDEX",
}


class Listing:
    """
    Truy xuất danh sách mã chứng khoán từ nguồn dữ liệu TCBS.

    Sử dụng TCBS ligo API (screener) để lấy danh sách cổ phiếu theo sàn/nhóm.

    Args:
        random_agent: Sử dụng user-agent ngẫu nhiên. Mặc định False.
        show_log: Hiển thị log debug. Mặc định False.
        auth_token: JWT token (không bắt buộc cho listing công khai).
    """

    def __init__(
        self,
        random_agent: bool = False,
        show_log: bool = False,
        auth_token: Optional[str] = None,
    ):
        self.data_source = "TCBS"
        self.base_url = _BASE_URL
        self.headers = get_tcbs_headers(random_agent=random_agent, auth_token=auth_token)
        self.show_log = show_log
        if not show_log:
            logger.setLevel("CRITICAL")

    # ── Public methods ──────────────────────────────────────────────────────

    @optimize_execution("TCBS")
    def all_symbols(self, show_log: Optional[bool] = False) -> pd.DataFrame:
        """
        Truy xuất danh sách toàn bộ mã cổ phiếu niêm yết trên HOSE, HNX, UPCOM.

        Returns:
            DataFrame với 2 cột: symbol, organ_name.
        """
        df = self.symbols_by_exchange(lang="vi", show_log=show_log)
        if df.empty:
            return pd.DataFrame(columns=["symbol", "organ_name"])
        result = df[["symbol", "organ_name"]].copy()
        result.attrs["source"] = self.data_source
        return result

    @optimize_execution("TCBS")
    def symbols_by_exchange(
        self,
        lang: str = "vi",
        get_all: bool = False,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Truy xuất danh sách mã chứng khoán theo sàn giao dịch.

        Args:
            lang: Ngôn ngữ tên công ty ('vi' hoặc 'en'). Mặc định 'vi'.
            get_all: Trả về tất cả cột từ API. Mặc định False.
            show_log: Hiển thị log. Mặc định False.

        Returns:
            DataFrame với các cột: symbol, organ_name, exchange, type (nếu có).
        """
        raw = self._call_watchlist(
            filters=[{"key": "exchangeName", "value": "HOSE,HNX,UPCOM", "operator": "="}],
            size=10000,
            show_log=show_log,
        )
        if not raw:
            return pd.DataFrame(columns=["symbol", "organ_name", "exchange"])

        df = pd.DataFrame(raw)
        df.columns = [camel_to_snake(c) for c in df.columns]

        # Chuẩn hoá tên cột về schema chung
        rename_map = {
            "t": "symbol",
            "exchange_name": "exchange",
            "company_name": "organ_name",
            "en_company_name": "en_organ_name",
            "type_name": "type",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        if get_all:
            df.attrs["source"] = self.data_source
            return df

        keep = [c for c in ["symbol", "organ_name", "en_organ_name", "exchange", "type"] if c in df.columns]
        df = df[keep]

        if lang != "vi" and "en_organ_name" in df.columns:
            df = df.drop(columns=["organ_name"], errors="ignore")
            df = df.rename(columns={"en_organ_name": "organ_name"})
        elif "en_organ_name" in df.columns:
            df = df.drop(columns=["en_organ_name"])

        df.attrs["source"] = self.data_source
        if show_log:
            logger.info(f"Truy xuất thành công {len(df)} mã chứng khoán theo sàn.")
        return df

    @optimize_execution("TCBS")
    def symbols_by_industries(
        self,
        lang: str = "vi",
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Truy xuất danh sách mã theo ngành (TCBS industry classification).

        Args:
            lang: Ngôn ngữ tên ngành ('vi' hoặc 'en'). Mặc định 'vi'.
            show_log: Hiển thị log. Mặc định False.

        Returns:
            DataFrame với các cột: symbol, organ_name, industry.
        """
        if lang not in ("vi", "en"):
            raise ValueError("Tham số lang phải là 'vi' hoặc 'en'.")

        raw = self._call_watchlist(
            filters=[{"key": "exchangeName", "value": "HOSE,HNX,UPCOM", "operator": "="}],
            size=10000,
            show_log=show_log,
        )
        if not raw:
            df = pd.DataFrame(columns=["symbol", "organ_name", "industry"])
            df.attrs["source"] = self.data_source
            return df

        df = pd.DataFrame(raw)
        df.columns = [camel_to_snake(c) for c in df.columns]

        rename_map = {
            "t": "symbol",
            "company_name": "organ_name",
            "industry_name": "industry",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        keep = [c for c in ["symbol", "organ_name", "industry"] if c in df.columns]
        df = df[keep].drop_duplicates().reset_index(drop=True)
        df.attrs["source"] = self.data_source
        return df

    @optimize_execution("TCBS")
    def industries_icb(self, show_log: Optional[bool] = False) -> pd.DataFrame:
        """
        TCBS không cung cấp ICB classification.

        Raises:
            NotImplementedError: Luôn raise.
        """
        raise NotImplementedError(
            "TCBS không cung cấp ICB classification chuẩn. "
            "Sử dụng symbols_by_industries() để lấy mã theo ngành TCBS."
        )

    @optimize_execution("TCBS")
    def symbols_by_group(
        self,
        group: str = "VN30",
        show_log: Optional[bool] = False,
    ) -> pd.Series:
        """
        Truy xuất danh sách mã cổ phiếu theo nhóm chỉ số.

        Args:
            group: Tên nhóm (VN30, VN100, HOSE, HNX, UPCOM, ETF, CW, BOND, FU_INDEX, ...).
            show_log: Hiển thị log. Mặc định False.

        Returns:
            Series chứa mã chứng khoán theo nhóm.

        Raises:
            ValueError: Nếu tên nhóm không hợp lệ.
        """
        upper = group.upper()
        if upper not in _GROUP_CODE:
            raise ValueError(
                f"Nhóm không hợp lệ: '{group}'. "
                f"Sử dụng get_supported_groups() để xem danh sách."
            )

        tcbs_group = _GROUP_CODE[upper]

        # Exchange-based groups → dùng exchangeName filter
        if upper in ("HOSE", "HNX", "UPCOM"):
            raw = self._call_watchlist(
                filters=[{"key": "exchangeName", "value": tcbs_group, "operator": "="}],
                size=5000,
                show_log=show_log,
            )
        else:
            # Index/group-based → dùng indexName filter
            raw = self._call_watchlist(
                filters=[{"key": "indexName", "value": tcbs_group, "operator": "="}],
                size=5000,
                show_log=show_log,
            )

        if not raw:
            s = pd.Series([], name="symbol", dtype="object")
            s.attrs["source"] = self.data_source
            s.attrs["group"] = group
            return s

        df = pd.DataFrame(raw)
        df.columns = [camel_to_snake(c) for c in df.columns]
        sym_col = "t" if "t" in df.columns else "symbol"
        s = df[sym_col].rename("symbol").reset_index(drop=True)
        s.attrs["source"] = self.data_source
        s.attrs["group"] = group
        if show_log:
            logger.info(f"Truy xuất {len(s)} mã theo nhóm '{group}'.")
        return s

    @optimize_execution("TCBS")
    def all_future_indices(self, show_log: Optional[bool] = False) -> pd.Series:
        """Truy xuất danh sách mã phái sinh hợp đồng tương lai."""
        return self.symbols_by_group(group="FU_INDEX", show_log=show_log)

    @optimize_execution("TCBS")
    def all_covered_warrant(self, show_log: Optional[bool] = False) -> pd.Series:
        """Truy xuất danh sách mã chứng quyền."""
        return self.symbols_by_group(group="CW", show_log=show_log)

    @optimize_execution("TCBS")
    def all_bonds(self, show_log: Optional[bool] = False) -> pd.Series:
        """Truy xuất danh sách mã trái phiếu doanh nghiệp."""
        return self.symbols_by_group(group="BOND", show_log=show_log)

    @optimize_execution("TCBS")
    def all_etf(self, show_log: Optional[bool] = False) -> pd.Series:
        """Truy xuất danh sách mã quỹ ETF."""
        return self.symbols_by_group(group="ETF", show_log=show_log)

    @optimize_execution("TCBS")
    def all_government_bonds(self, show_log: Optional[bool] = False) -> pd.Series:
        """
        TCBS không phân biệt trái phiếu chính phủ riêng.

        Raises:
            NotImplementedError: Luôn raise.
        """
        raise NotImplementedError(
            "TCBS không cung cấp danh sách trái phiếu chính phủ riêng. "
            "Sử dụng all_bonds() để lấy trái phiếu doanh nghiệp."
        )

    def get_supported_groups(self) -> pd.DataFrame:
        """
        Liệt kê tất cả các nhóm được hỗ trợ bởi symbols_by_group().

        Returns:
            DataFrame với các cột: group_name, category, description.
        """
        group_info: List[tuple] = [
            ("VN30", "Chỉ số VN", "30 cổ phiếu vốn hóa lớn nhất & thanh khoản tốt nhất HOSE"),
            ("VN100", "Chỉ số VN", "100 cổ phiếu có vốn hoá lớn nhất HOSE"),
            ("VNMIDCAP", "Chỉ số VN", "Mid-Cap Index"),
            ("VNSMALLCAP", "Chỉ số VN", "Small-Cap Index"),
            ("VNSI", "Chỉ số VN", "Vietnam Small-Cap Index"),
            ("VNX50", "Chỉ số VN", "50 cổ phiếu vốn hóa lớn nhất HOSE và HNX"),
            ("VNXALL", "Chỉ số VN", "Tất cả cổ phiếu trên HOSE và HNX"),
            ("HNX30", "Chỉ số VN", "30 cổ phiếu hàng đầu HNX"),
            ("HOSE", "Sàn giao dịch", "Sở Giao dịch Chứng khoán TP. HCM"),
            ("HNX", "Sàn giao dịch", "Sở Giao dịch Chứng khoán Hà Nội"),
            ("UPCOM", "Sàn giao dịch", "Thị trường UPCoM"),
            ("ETF", "Quỹ", "Exchange-Traded Fund"),
            ("CW", "Chứng quyền", "Covered Warrant"),
            ("BOND", "Trái phiếu", "Trái phiếu doanh nghiệp"),
            ("FU_INDEX", "Phái sinh", "Hợp đồng tương lai chỉ số"),
        ]
        df = pd.DataFrame(group_info, columns=["group_name", "category", "description"])
        df.attrs["source"] = self.data_source
        return df

    # ── Internal helpers ────────────────────────────────────────────────────

    def _call_watchlist(
        self,
        filters: List[dict],
        size: int = 1000,
        show_log: Optional[bool] = False,
    ) -> List[dict]:
        """
        Gọi TCBS ligo watchlist preview endpoint và trả về pageContent list.

        Returns:
            List[dict] — danh sách record, rỗng nếu request thất bại.
        """
        payload = {"tcbsID": None, "filters": filters, "size": size}
        try:
            response = client.send_request(
                url=_WATCHLIST_URL,
                headers=self.headers,
                method="POST",
                payload=payload,
                show_log=show_log,
            )
        except Exception as exc:
            if show_log:
                logger.error(f"Lỗi khi gọi TCBS watchlist API: {exc}")
            return []

        if not response:
            return []
        search_data = response.get("searchData", {})
        if not search_data:
            return []
        return search_data.get("pageContent") or []


# Register provider
from vnbroker.core.registry import ProviderRegistry
ProviderRegistry.register("listing", "tcbs", Listing)
