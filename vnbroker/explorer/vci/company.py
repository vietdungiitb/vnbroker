"""
Module quản lý thông tin công ty từ nguồn dữ liệu VCI (REST API).

VCI đã chuyển hoàn toàn từ GraphQL sang REST API vào ngày 26/04/2026.
REST endpoint: https://iq.vietcap.com.vn/api/iq-insight-service
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
from vnbroker.core.utils import client
from vnbroker.core.utils.client import ProxyConfig
from vnbroker.core.utils.logger import get_logger
from vnbroker.core.utils.parser import camel_to_snake, get_asset_type
from vnbroker.core.utils.transform import drop_cols_by_pattern
from vnbroker.core.utils.user_agent import get_headers
from vnbroker.core.utils.execution import optimize_execution
from .const import _VCI_COMPANY_URL, _VCIQ_URL

logger = get_logger(__name__)


class Company:
    """
    Class (lớp) quản lý các thông tin liên quan đến công ty từ nguồn dữ liệu VCI.

    Tham số:
    - symbol (str): Mã chứng khoán của công ty cần truy xuất thông tin.
    - random_agent (bool): Sử dụng user-agent ngẫu nhiên hoặc không. Mặc định là False.
    - show_log (bool): Hiển thị thông tin log hoặc không. Mặc định là False.
    """

    def __init__(
        self,
        symbol: str = None,
        random_agent: bool = False,
        show_log: Optional[bool] = False,
        proxy_config: Optional[ProxyConfig] = None,
        proxy_mode: Optional[str] = None,
        proxy_list: Optional[List[str]] = None,
    ):
        """ Khởi tạo đối tượng Company với các tham số cho việc truy xuất dữ liệu. """
        self.symbol = symbol.upper() if symbol else ""
        self.asset_type = get_asset_type(self.symbol) if symbol else "stock"
        if symbol and self.asset_type not in ["stock"]:
            raise ValueError(
                "Mã chứng khoán không hợp lệ. Chỉ cổ phiếu mới có thông tin."
            )
        self.headers = get_headers(data_source="VCI", random_agent=random_agent)
        self.show_log = show_log
        self.base_url = _VCI_COMPANY_URL
        if not show_log:
            logger.setLevel("CRITICAL")

        if proxy_config is None:
            p_mode = proxy_mode if proxy_mode else "try"
            req_mode = "direct"
            if proxy_mode == "auto" or (proxy_list and len(proxy_list) > 0):
                req_mode = "proxy"
            self.proxy_config = ProxyConfig(
                proxy_mode=p_mode, proxy_list=proxy_list, request_mode=req_mode
            )
        else:
            self.proxy_config = proxy_config

    def _fetch_company_details(self) -> Dict:
        url = f"{self.base_url}/details?ticker={self.symbol}"
        if self.show_log:
            logger.debug(f"Requesting company details for {self.symbol} from {url}")
        response_data = client.send_request(
            url=url, headers=self.headers, method="GET", show_log=self.show_log
        )
        return response_data.get("data", {})

    def _fetch_shareholders(self) -> Dict:
        url = f"{self.base_url}/{self.symbol}/shareholder-structure"
        if self.show_log:
            logger.debug(
                f"Requesting shareholder structure for {self.symbol} from {url}"
            )
        response_data = client.send_request(
            url=url, headers=self.headers, method="GET", show_log=self.show_log
        )
        return response_data.get("data", {})

    def _fetch_shareholder_list(self) -> Dict:
        url = f"{self.base_url}/{self.symbol}/shareholder"
        if self.show_log:
            logger.debug(f"Requesting shareholder list for {self.symbol} from {url}")
        response_data = client.send_request(
            url=url, headers=self.headers, method="GET", show_log=self.show_log
        )
        return response_data.get("data", [])

    def _fetch_relationships(self) -> Dict:
        url = f"{self.base_url}/{self.symbol}/relationship"
        if self.show_log:
            logger.debug(f"Requesting relationships for {self.symbol} from {url}")
        response_data = client.send_request(
            url=url, headers=self.headers, method="GET", show_log=self.show_log
        )
        return response_data.get("data", {})

    def _fetch_news_events(
        self, from_date: str = None, to_date: str = None, event_codes: str = None
    ) -> List:
        if from_date is None:
            from_date = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
        if to_date is None:
            to_date = datetime.now().strftime("%Y%m%d")
        if event_codes is None:
            event_codes = "DIV,ISS"
        url = f"{_VCIQ_URL}/v1/news-events-for-chart?ticker={self.symbol}&fromDate={from_date}&toDate={to_date}&languageId=1&eventCode={event_codes}"
        if self.show_log:
            logger.debug(f"Requesting news and events for {self.symbol} from {url}")
        response_data = client.send_request(
            url=url, headers=self.headers, method="GET", show_log=self.show_log
        )
        return response_data.get("data", [])

    def _fetch_news(
        self, from_date: str = None, to_date: str = None, page: int = 0, size: int = 50
    ) -> List:
        if from_date is None:
            from_date = (datetime.now() - timedelta(days=365 * 10)).strftime("%Y%m%d")
        if to_date is None:
            to_date = datetime.now().strftime("%Y%m%d")
        url = f"{_VCIQ_URL}/v1/news?ticker={self.symbol}&fromDate={from_date}&toDate={to_date}&languageId=1&page={page}&size={size}"
        if self.show_log:
            logger.debug(f"Requesting news for {self.symbol} from {url}")
        response_data = client.send_request(
            url=url, headers=self.headers, method="GET", show_log=self.show_log
        )
        data = response_data.get("data", {})
        if isinstance(data, dict):
            return data.get("content", [])
        return []

    @optimize_execution("VCI")
    def overview(self) -> pd.DataFrame:
        data = self._fetch_company_details()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame([data])
        df.columns = [camel_to_snake(col) for col in df.columns]
        df = drop_cols_by_pattern(df, ["__typename", "ticker", "en_"])
        if "update_date" in df.columns and df["update_date"].dtype in [int, float]:
            df["update_date"] = pd.to_datetime(
                df["update_date"], unit="ms"
            ).dt.strftime("%Y-%m-%d")
        df.insert(0, "symbol", self.symbol)
        return df

    @optimize_execution("VCI")
    def shareholders(self, mode: str = "summary") -> pd.DataFrame:
        if mode == "summary":
            data = self._fetch_shareholders()
            if not data:
                return pd.DataFrame()
            df = pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame([data])
            df.columns = [camel_to_snake(col) for col in df.columns]
            df = drop_cols_by_pattern(df, ["__typename", "ticker", "en_"])
            if "update_date" in df.columns and df["update_date"].dtype in [int, float]:
                df["update_date"] = pd.to_datetime(
                    df["update_date"], unit="ms"
                ).dt.strftime("%Y-%m-%d")
            rename_map = {}
            if "owner_full_name" in df.columns:
                rename_map["owner_full_name"] = "share_holder"
            if "percentage" in df.columns:
                rename_map["percentage"] = "share_own_percent"
            if rename_map:
                df = df.rename(columns=rename_map)
            return df
        elif mode == "detailed":
            data = self._fetch_shareholder_list()
            if not data:
                return pd.DataFrame()
            df = pd.DataFrame(data)
            df.columns = [camel_to_snake(col) for col in df.columns]
            df = drop_cols_by_pattern(
                df,
                [
                    "__typename",
                    "ticker",
                    "en_",
                    "owner_type",
                    "owner_code",
                    "position_name",
                    "public_date",
                ],
            )
            rename_map = {
                "owner_name": "share_holder",
                "percentage": "share_own_percent",
            }
            rename_dict = {k: v for k, v in rename_map.items() if k in df.columns}
            if rename_dict:
                df = df.rename(columns=rename_dict)
            df.insert(0, "symbol", self.symbol)
            standard_columns = [
                "symbol",
                "share_holder",
                "quantity",
                "share_own_percent",
                "update_date",
            ]
            existing_cols = [col for col in standard_columns if col in df.columns]
            df = df[existing_cols]
            return df
        else:
            raise ValueError(f"Invalid mode: {mode}. Use 'summary' or 'detailed'")

    @optimize_execution("VCI")
    def officers(self, filter_by: str = "working") -> pd.DataFrame:
        if filter_by not in ["working", "resigned", "all"]:
            raise ValueError(
                "filter_by chỉ nhận giá trị 'working' hoặc 'resigned' hoặc 'all'"
            )
        data = self._fetch_shareholder_list()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame([data])
        df.columns = [camel_to_snake(col) for col in df.columns]
        if "owner_type" in df.columns:
            df = df[df["owner_type"] == "INDIVIDUAL"]
        if "position_name" in df.columns:
            df = df[df["position_name"].notna()]
        df = drop_cols_by_pattern(
            df, ["en_", "__", "owner_code", "owner_type", "public_date"]
        )
        rename_map = {
            "owner_name": "officer_name",
            "position_name": "officer_position",
            "percentage": "officer_own_percent",
            "quantity": "officer_own_quantity",
        }
        rename_dict = {k: v for k, v in rename_map.items() if k in df.columns}
        if rename_dict:
            df = df.rename(columns=rename_dict)
        df.insert(0, "symbol", self.symbol)
        if "update_date" in df.columns and df["update_date"].dtype in [int, float]:
            df["update_date"] = pd.to_datetime(
                df["update_date"], unit="ms"
            ).dt.strftime("%Y-%m-%d")
        standard_columns = [
            "symbol",
            "officer_name",
            "officer_position",
            "officer_own_percent",
            "officer_own_quantity",
            "update_date",
        ]
        existing_cols = [col for col in standard_columns if col in df.columns]
        df = df[existing_cols]
        return df

    @optimize_execution("VCI")
    def subsidiaries(self, filter_by: str = "all") -> pd.DataFrame:
        if filter_by not in ["all", "subsidiary", "affiliate"]:
            raise ValueError(
                "filter_by chỉ nhận giá trị 'all', 'subsidiary' hoặc 'affiliate'"
            )
        data = self._fetch_relationships()
        if not data:
            return pd.DataFrame()
        subsidiaries = data.get("subsidiaries", [])
        affiliates = data.get("affiliates", [])
        if filter_by == "subsidiary":
            items = subsidiaries
        elif filter_by == "affiliate":
            items = affiliates
        else:
            items = subsidiaries + affiliates
        if not items:
            return pd.DataFrame()
        df = pd.DataFrame(items)
        df.columns = [camel_to_snake(col) for col in df.columns]
        df = drop_cols_by_pattern(df, ["en_", "__typename"])
        if "type" in df.columns:
            df = df.rename(columns={"type": "relationship_type"})
        df.insert(0, "symbol", self.symbol)
        return df

    @optimize_execution("VCI")
    def news(
        self, from_date: str = None, to_date: str = None, page: int = 0, size: int = 50
    ) -> pd.DataFrame:
        data = self._fetch_news(from_date, to_date, page, size)
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df.columns = [camel_to_snake(col) for col in df.columns]
        df = drop_cols_by_pattern(df, ["__typename", "en_"])
        if "public_date" in df.columns and df["public_date"].dtype in [int, float]:
            df["public_date"] = pd.to_datetime(
                df["public_date"], unit="ms"
            ).dt.strftime("%Y-%m-%d")
        df.insert(0, "symbol", self.symbol)
        return df

    @optimize_execution("VCI")
    def events(
        self, from_date: str = None, to_date: str = None, event_codes: str = None
    ) -> pd.DataFrame:
        data = self._fetch_news_events(from_date, to_date, event_codes)
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df.columns = [camel_to_snake(col) for col in df.columns]
        df = drop_cols_by_pattern(df, ["__typename", "en_"])
        date_columns = ["public_date", "issue_date", "record_date", "exright_date"]
        for col in date_columns:
            if col in df.columns and df[col].dtype in [int, float]:
                df[col] = pd.to_datetime(df[col], unit="ms").dt.strftime("%Y-%m-%d")
        df.insert(0, "symbol", self.symbol)
        return df

    @optimize_execution("VCI")
    def corporate_actions(
        self,
        from_date: str = None,
        to_date: str = None,
        event_codes: str = "DIV,ISS",
    ) -> pd.DataFrame:
        """Structured corporate actions with numeric fields (additive to events()).

        Unlike events(), this returns the stable contract schema from
        ``vnbroker.common.corporate_actions``. Amounts are parsed from
        ``event_title_vi``; ESOP / unparseable rows stay ``unparsed`` and are
        never guessed (audit C-02). Two rows on the same ex_date are kept.
        """
        from vnbroker.common.corporate_actions import normalize_events

        data = self._fetch_news_events(from_date, to_date, event_codes)
        return normalize_events(data, self.symbol)

    @optimize_execution("VCI")
    def insider_deals(
        self,
        page: int = 1,
        page_size: int = 10,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Compatibility alias for standardized company API.
        VCI does not currently provide insider trading data via REST API.
        Returns empty DataFrame with standard schema.

        Args:
            page: Page number. Default 1.
            page_size: Records per page. Default 10.
            show_log: Show debug log.

        Returns:
            Empty DataFrame with standard insider trading columns.
        """
        if self.show_log or show_log:
            logger.warning(
                "VCI Company.insider_deals() called - VCI does not support insider trading endpoint. "
                "Returning empty DataFrame. Use KBS for insider trading data."
            )
        # Return empty DataFrame with standard columns
        return pd.DataFrame(columns=[
            "symbol", "officer_name", "officer_position", "trade_date",
            "trade_type", "volume", "price", "value", "ownership_after"
        ])


from vnbroker.core.registry import ProviderRegistry  # noqa: E402
ProviderRegistry.register("company", "vci", Company)
