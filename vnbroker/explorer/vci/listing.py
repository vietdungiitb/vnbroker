"""Listing module."""

# Đồ thị giá, đồ thị dư mua dư bán, đồ thị mức giá vs khối lượng, thống kê hành vi thị tường
from typing import Optional, List
from .const import _GROUP_CODE, _TRADING_URL, _GROUP_CODE_MAPPING, _VCI_INDEX_MAPPING
import pandas as pd
from vnbroker.core.utils.parser import camel_to_snake
from vnbroker.core.utils.logger import get_logger
from vnbroker.core.utils.user_agent import get_headers
from vnbroker.core.utils.client import send_request, ProxyConfig
from vnbroker.core.utils.transform import drop_cols_by_pattern, reorder_cols
from vnbroker.common import indices as market_indices
from vnbroker.core.utils.execution import optimize_execution
from vnbroker.core.utils.cache import cached_listing, cached_industry
logger = get_logger(__name__)

class Listing:
    """Cấu hình truy cập dữ liệu lịch sử giá chứng khoán từ VCI."""

    def __init__(self, random_agent: Optional[bool] = False, show_log: Optional[bool] = False,
                 proxy_config: Optional[ProxyConfig] = None,
                 proxy_mode: Optional[str] = None,
                 proxy_list: Optional[List[str]] = None):
        self.data_source = 'VCI'
        self.base_url = _TRADING_URL
        self.headers = get_headers(data_source=self.data_source, random_agent=random_agent)
        self.show_log = show_log

        # Handle proxy configuration
        if proxy_config is None:
            # Create ProxyConfig from individual arguments
            p_mode = proxy_mode if proxy_mode else 'try'
            # If user asks for 'auto' or provides list, set request_mode to PROXY
            req_mode = 'direct'
            if proxy_mode == 'auto' or (proxy_list and len(proxy_list) > 0):
                req_mode = 'proxy'
                
            self.proxy_config = ProxyConfig(
                proxy_mode=p_mode,
                proxy_list=proxy_list,
                request_mode=req_mode
            )
        else:
            self.proxy_config = proxy_config

        if not show_log:
            logger.setLevel('CRITICAL')

    @cached_listing()
    @optimize_execution("VCI")
    def all_symbols(self, show_log: Optional[bool] = False) -> pd.DataFrame:
        """Truy xuất danh sách toàn bộ mã và tên các cổ phiếu trên thị trường Việt Nam.

        Args:
            show_log: Hiển thị thông tin log giúp debug dễ dàng. Mặc định là False.
        """
        df = self.symbols_by_exchange(show_log=show_log)
        df = df.query('type == "STOCK"').reset_index(drop=True)
        df = df[['symbol', 'organ_name']]

        return df
        
    @cached_industry()
    @optimize_execution("VCI")
    def symbols_by_industries(self, lang: str = 'vi', show_log: Optional[bool] = False) -> pd.DataFrame:
        """
        Truy xuất thông tin phân ngành icb của các mã cổ phiếu trên thị trường Việt Nam.

        Tham số:
            - lang (tùy chọn): Ngôn ngữ hiển thị. Mặc định là 'vi'.
            - show_log (tùy chọn): Hiển thị thông tin log giúp debug dễ dàng. Mặc định là False.

        Note:
            VCI đã chuyển từ GraphQL sang REST endpoint kể từ 26/04/2026.
        """
        if lang not in ['vi', 'en']:
            raise ValueError("Tham số lang phải là 'vi' hoặc 'en'.")

        lang_code = '1' if lang == 'vi' else '2'
        url = f"https://iq.vietcap.com.vn/api/iq-insight-service/v2/company/search-bar?language={lang_code}"

        # Use the send_request utility from api_client
        json_data = send_request(
            url=url,
            headers=self.headers,
            method="GET",
            show_log=show_log,
            proxy_list=self.proxy_config.proxy_list,
            proxy_mode=self.proxy_config.proxy_mode,
            request_mode=self.proxy_config.request_mode
        )

        if not json_data or "data" not in json_data or json_data["data"] is None:
            raise ValueError(
                "Không nhận được dữ liệu (data) từ VCI. Có thể API đã thay đổi cấu trúc."
            )

        if show_log:
            logger.info('Truy xuất thành công dữ liệu danh sách phân ngành icb.')

        parsed_data = []
        for company in json_data["data"]:
            symbol = company.get("code")
            organ_name = company.get("name")
            com_type_code = company.get("comTypeCode")

            for level in range(1, 5):
                icb_key = f"icbLv{level}"
                if icb_key in company and company[icb_key] is not None:
                    parsed_data.append(
                        {
                            "symbol": symbol,
                            "organ_name": organ_name,
                            "com_type_code": com_type_code,
                            "icb_level": level,
                            "icb_code": company[icb_key].get("code"),
                            "icb_name": company[icb_key].get("name"),
                        }
                    )

        df = pd.DataFrame(parsed_data)

        if not df.empty:
            df = df[df["icb_code"].notna() & (df["icb_code"] != "")]
            df = df.sort_values(by=["symbol", "icb_level"]).reset_index(drop=True)
            df = df[["symbol", "organ_name", "com_type_code", "icb_level", "icb_code", "icb_name"]]

        df.source = "VCI"
        return df

    @cached_listing()
    @optimize_execution("VCI")
    def symbols_by_exchange(self, lang: str = 'vi', show_log: Optional[bool] = False,
                            get_all: Optional[bool] = False) -> pd.DataFrame:
        """
        Truy xuất thông tin niêm yết theo sàn của các mã cổ phiếu trên thị trường Việt Nam.

        Tham số:
            - lang (tùy chọn): Ngôn ngữ hiển thị. Mặc định là 'vi'.
            - show_log (tùy chọn): Hiển thị thông tin log giúp debug dễ dàng. Mặc định là False.
        """
        if lang not in ['vi', 'en']:
            raise ValueError("Tham số lang phải là 'vi' hoặc 'en'.")

        url = self.base_url.rstrip('/') + '/price/symbols/getAll'
        
        # Use the send_request utility from api_client
        try:
            json_data = send_request(
                url=url,
                headers=self.headers,
                method="GET",
                payload=None,
                show_log=show_log,
                proxy_list=self.proxy_config.proxy_list,
                proxy_mode=self.proxy_config.proxy_mode,
                request_mode=self.proxy_config.request_mode
            )
        except ConnectionError as e:
            # Handle case where API returns empty or invalid response
            error_msg = str(e)
            if "Expecting value" in error_msg or "JSON" in error_msg:
                raise ValueError(f"VCI API returned empty or invalid response. URL: {url}. Error: {error_msg}")
            raise

        # Handle case where API returns data wrapped in "data" key or directly as list
        if json_data is None:
            raise ValueError("Không tìm thấy dữ liệu. Vui lòng kiểm tra lại.")
        
        # If response is a dict with "data" key, extract it
        if isinstance(json_data, dict) and "data" in json_data:
            json_data = json_data["data"]
        
        # If still a dict, it might be an error response
        if isinstance(json_data, dict):
            raise ValueError(f"Không nhận được dữ liệu (data) từ VCI. Response: {json_data}")

        if show_log:
            logger.info(f'Truy xuất dữ liệu thành công cho {len(json_data)} mã.')

        df = pd.DataFrame(json_data)

        if df.empty:
            df.source = "VCI"
            return df

        df.columns = [camel_to_snake(col) for col in df.columns]
        df = df.rename(columns={'board': 'exchange'})
        df = reorder_cols(df, ['symbol', 'exchange', 'type'], position='first')
        df = df.drop(columns=['id'], errors='ignore')

        if get_all:
            df.source = "VCI"
            return df

        if lang == 'vi':
            df = drop_cols_by_pattern(df, ['en_'])
        else:
            df = df.drop(columns=['organ_name', 'organ_short_name'], errors='ignore')
            # rename columns for those contain 'en_' with 'en_' removed
            df.columns = [col.replace('en_', '') for col in df.columns]

        # Set metadata attributes
        df.source = "VCI"
        return df

    @cached_industry()
    @optimize_execution("VCI")
    def industries_icb(self, show_log: Optional[bool] = False) -> pd.DataFrame:
        """
        Truy xuất thông tin phân ngành icb của các mã cổ phiếu trên thị trường Việt Nam.

        Tham số:
            - show_log (tùy chọn): Hiển thị thông tin log giúp debug dễ dàng. Mặc định là False.

        Note:
            VCI đã chuyển từ GraphQL sang REST endpoint kể từ 26/04/2026.
        """
        url = "https://iq.vietcap.com.vn/api/iq-insight-service/v1/sectors/icb-codes"

        # Use the send_request utility from api_client
        json_data = send_request(
            url=url,
            headers=self.headers,
            method="GET",
            show_log=show_log,
            proxy_list=self.proxy_config.proxy_list,
            proxy_mode=self.proxy_config.proxy_mode,
            request_mode=self.proxy_config.request_mode
        )

        if not json_data:
            raise ValueError("Không tìm thấy dữ liệu. Vui lòng kiểm tra lại.")

        if "data" not in json_data or json_data["data"] is None:
            raise ValueError(
                "Không nhận được dữ liệu (data) từ VCI. Có thể API đã thay đổi cấu trúc."
            )

        if show_log:
            logger.info('Truy xuất thành công dữ liệu danh sách phân ngành icb.')

        df = pd.DataFrame(json_data["data"])
        df = df.rename(
            columns={
                "name": "icb_code",
                "viSector": "icb_name",
                "enSector": "en_icb_name",
                "icbLevel": "level",
            }
        )

        if not df.empty:
            df = df[["icb_name", "en_icb_name", "icb_code", "level"]]
            df = df.sort_values(by=["icb_code"]).reset_index(drop=True)

        df.source = "VCI"
        return df

    @optimize_execution("VCI")
    def symbols_by_group(self, group: str = 'VN30', show_log: Optional[bool] = False) -> pd.Series:
        """
        Truy xuất danh sách các mã cổ phiếu theo tên nhóm trên thị trường Việt Nam.

        Tham số:
            - group (tùy chọn): Tên nhóm cổ phiếu. Mặc định là 'VN30'.
            - show_log (tùy chọn): Hiển thị thông tin log. Mặc định là False.
        """
        if group not in _GROUP_CODE and group.upper() not in _GROUP_CODE_MAPPING and group.upper() not in _VCI_INDEX_MAPPING:
            valid_keys = list(_GROUP_CODE_MAPPING.keys()) + list(_VCI_INDEX_MAPPING.keys())
            raise ValueError(f"Invalid group '{group}'. Must be one of {valid_keys}")

        standardized = group.upper()
        if standardized in _VCI_INDEX_MAPPING:
            vci_group = _VCI_INDEX_MAPPING[standardized]
        else:
            vci_group = _GROUP_CODE_MAPPING.get(standardized, group)
        url = self.base_url.rstrip('/') + f'/price/symbols/getByGroup?group={vci_group}'

        # Use the send_request utility from api_client
        json_data = send_request(
            url=url,
            headers=self.headers,
            method="GET",
            payload=None,
            show_log=show_log,
            proxy_list=self.proxy_config.proxy_list,
            proxy_mode=self.proxy_config.proxy_mode,
            request_mode=self.proxy_config.request_mode
        )

        if show_log:
            logger.info('Truy xuất thành công dữ liệu danh sách mã theo nhóm.')

        df = pd.DataFrame(json_data)

        if not json_data:
            raise ValueError("JSON data is empty or not provided.")
        # Set metadata attributes
        df.source = "VCI"
        return df['symbol']

    @optimize_execution("VCI")
    @cached_listing(ttl_seconds=86400)
    def all_future_indices(self, show_log: Optional[bool] = False) -> pd.Series:
        return self.symbols_by_group(group='FU_INDEX', show_log=show_log)

    @optimize_execution("VCI")
    def all_government_bonds(self, show_log: Optional[bool] = False) -> pd.Series:
        return self.symbols_by_group(group='FU_BOND', show_log=show_log)

    @optimize_execution("VCI")
    def all_covered_warrant(self, show_log: Optional[bool] = False) -> pd.Series:
        return self.symbols_by_group(group='CW', show_log=show_log)

    @optimize_execution("VCI")
    def all_bonds(self, show_log: Optional[bool] = False) -> pd.Series:
        return self.symbols_by_group(group='BOND', show_log=show_log)

    @optimize_execution("VCI")
    def all_etf(self, show_log: Optional[bool] = False) -> pd.Series:
        return self.symbols_by_group(group='ETF', show_log=show_log)

    @optimize_execution("VCI")
    def get_supported_groups(self) -> pd.DataFrame:
        category_map = {
            'HOSE': 'Sàn giao dịch',
            'HNX': 'Sàn giao dịch',
            'UPCOM': 'Sàn giao dịch',
            'VN30': 'Chỉ số VN',
            'VNMidCap': 'Chỉ số VN',
            'VNSmallCap': 'Chỉ số VN',
            'VNAllShare': 'Chỉ số VN',
            'VN100': 'Chỉ số VN',
            'HNX30': 'Chỉ số VN',
            'ETF': 'ETF/Quỹ',
            'FU_INDEX': 'Phái sinh',
            'FU_BOND': 'Trái phiếu',
            'BOND': 'Trái phiếu',
            'CW': 'Chứng quyền',
        }
        data = [
            {
                'group_name': name,
                'group_code': name,
                'category': category_map.get(name, 'Khác'),
                'description': f'VCI supported group {name}',
            }
            for name in _GROUP_CODE
        ]
        df = pd.DataFrame(data)
        df.attrs['source'] = self.data_source
        return df

    # =========================================================================
    # STANDARDIZED MARKET INDICES (Wrapper functions)
    # =========================================================================
    # Provide access to standardized indices across all data sources
    # (VCI, etc.). Sector indices include mapping to ICB
    # sector_id for industry filtering and analysis.

    def all_indices(self) -> pd.DataFrame:
        """
        Lấy danh sách tất cả các chỉ số tiêu chuẩn hóa với thông tin đầy đủ.

        Returns:
            pd.DataFrame: Columns [symbol, name, description, full_name,
                                   group, index_id, sector_id (for sectors)]
        """
        return market_indices.get_all_indices()

    def indices_by_group(self, group: str) -> Optional[pd.DataFrame]:
        """
        Lấy danh sách chỉ số theo nhóm tiêu chuẩn hóa.

        Args:
            group: Tên nhóm (VD: 'HOSE Indices', 'Sector Indices', etc.)

        Returns:
            pd.DataFrame: Danh sách chỉ số trong nhóm hoặc None
                          (Sector indices include sector_id mapping)
        """
        return market_indices.get_indices_by_group(group)


# Register provider
from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401
ProviderRegistry.register('listing', 'vci', Listing)
