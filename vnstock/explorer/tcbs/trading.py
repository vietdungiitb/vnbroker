"""
Module quản lý các thông tin về giao dịch chứng khoán từ nguồn dữ liệu TCBS.
"""

import pandas as pd
from typing import List, Dict, Optional
from vnstock.core.utils import client
from vnstock.core.utils.parser import get_asset_type
from vnstock.core.utils.validation import validate_symbol
from vnstock.core.utils.logger import get_logger
from vnstock.core.utils.execution import optimize_execution
from vnstock.core.utils.transform import normalize_price_columns
from .const import _BASE_URL, _STOCKS_URL, _PRICE_BOARD_COLS_MAP, _PRICE_BOARD_STD_COLS, _PRICE_BOARD_EXT_COLS
from .auth import get_tcbs_headers

logger = get_logger(__name__)

_PRICE_BOARD_PRICE_COLUMNS_RAW = [
    'cp',
    'ma20',
    'ma50',
    'ma100',
    'hp1m',
    'hp3m',
    'hp1y',
    'lp1m',
    'lp3m',
    'lp1y',
    'hmp',
]


class Trading:
    """
    Truy xuất dữ liệu giao dịch của mã chứng khoán từ nguồn dữ liệu TCBS.
    
    Tham số:
        - symbol (str): Mã chứng khoán mặc định.
        - random_agent (bool): Sử dụng user-agent ngẫu nhiên hoặc không. Mặc định là False.
        - show_log (bool): Hiển thị thông tin log hoặc không. Mặc định là True.
    """
    def __init__(self, symbol: Optional[str], random_agent: bool = False,
                 show_log: Optional[bool] = True,
                 auth_token: Optional[str] = None):
        """
        Khởi tạo đối tượng Trading với các tham số cho việc truy xuất dữ liệu.
        """
        self.symbol = validate_symbol(symbol)
        self.asset_type = get_asset_type(self.symbol)
        self.show_log = show_log
        self.base_url = _BASE_URL
        self.auth_token = auth_token
        self.headers = get_tcbs_headers(
            random_agent=random_agent,
            auth_token=auth_token,
        )

        if not show_log:
            logger.setLevel('CRITICAL')
        
    @optimize_execution("TCBS")
    def price_board(self, symbol_ls: List[str], std_columns: Optional[bool] = True, 
                    show_log: bool = False,
                    price_unit: Optional[str] = None) -> pd.DataFrame:
        """
        Truy xuất thông tin bảng giá của các mã chứng khoán tuỳ chọn từ nguồn dữ liệu TCBS.
        
        Tham số:
            - symbol_ls (List[str]): Danh sách các mã chứng khoán cần truy xuất thông tin.
            - std_columns (bool): Sử dụng danh sách cột tiêu chuẩn hoặc mở rộng. Mặc định là True.
            - show_log (bool): Hiển thị thông tin log hoặc không. Mặc định là False.
            
        Returns:
            Thông tin bảng giá dưới dạng DataFrame.
        """
        symbols = ",".join(symbol_ls)
        url = f'{self.base_url}/{_STOCKS_URL}/v1/stock/second-tc-price'
        
        # Use centralized API client instead of direct requests
        try:
            response_data = client.send_request(
                url=url,
                headers=self.headers,
                method="GET",
                params={"tickers": symbols},
                show_log=show_log
            )
            
            # Process response data
            data = response_data['data']
            df = pd.DataFrame(data)
            
            # Drop columns named seq
            df.drop(columns=['seq'], inplace=True, errors='ignore')
            
            # Select columns based on the std_columns parameter
            if std_columns:
                df = df[_PRICE_BOARD_STD_COLS]
            else:
                df = df[_PRICE_BOARD_EXT_COLS]

            df = normalize_price_columns(
                df,
                columns=_PRICE_BOARD_PRICE_COLUMNS_RAW,
                source_unit='VND',
                floating=None,
                target_unit=price_unit,
            )

            # Rename columns according to the mapping
            df = df.rename(columns=_PRICE_BOARD_COLS_MAP)
            
            # Add source metadata
            df.source = 'TCBS'

            # Return DataFrame
            return df
                
        except Exception as e:
            # Better error handling with logging
            logger.error(f"Error processing price board data: {e}")
            empty_df = pd.DataFrame()
            return normalize_price_columns(
                empty_df,
                columns=_PRICE_BOARD_PRICE_COLUMNS_RAW,
                source_unit='VND',
                floating=None,
                target_unit=price_unit,
            )


# Register provider
from vnstock.core.registry import ProviderRegistry  # noqa: E402, F401
ProviderRegistry.register('trading', 'tcbs', Trading)
