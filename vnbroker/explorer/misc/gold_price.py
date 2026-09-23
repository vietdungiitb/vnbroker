import logging
import os
import requests
import pandas as pd
from datetime import datetime
from typing import Optional
from vnbroker.config import Config
from vnbroker.core.utils.user_agent import get_headers
from vnbroker.core.utils.execution import optimize_execution

_logger = logging.getLogger(__name__)

_BTMC_DEFAULT_KEY = "3kd8ub1llcg9t45hnoh8hmn7t5kc2v"


def _btmc_default_url() -> str:
    key = os.getenv("BTMC_API_KEY", _BTMC_DEFAULT_KEY)
    return f"http://api.btmc.vn/api/BTMCAPI/getpricebtmc?key={key}"


@optimize_execution("MISC")
def sjc_gold_price(date: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    Truy xuất giá vàng từ trang chủ SJC.

    Args:
        - date: Ngày tra cứu, mặc định là None để lấy ngày hiện tại.
                Nhập giá trị tùy chọn, định dạng YYYY-mm-dd, ví dụ 2025-01-15.
                Dữ liệu có sẵn từ ngày 2/1/2016.

    Returns:
        - Pandas DataFrame chứa thông tin giá vàng nếu thành công, ngược lại trả về None.
    """
    # Set URL
    url = "https://sjc.com.vn/GoldPrice/Services/PriceService.ashx"

    # Define the minimum allowed date
    min_date = datetime(2016, 1, 2)

    # Convert date to required format DD/MM/YYYY
    if date is None:
        input_date = datetime.now().date()
    else:
        try:
            input_date = datetime.strptime(date, "%Y-%m-%d")
            if input_date < min_date:
                raise ValueError("Ngày tra cứu phải từ 2/1/2016 trở đi.")
        except ValueError:
            raise ValueError(
                "Định dạng ngày không hợp lệ. Vui lòng nhập theo định dạng YYYY-mm-dd."
            )

    # Format date for the API request
    formatted_date = input_date.strftime("%d/%m/%Y")

    # Prepare request payload and headers
    payload = f"method=GetSJCGoldPriceByDate&toDate={formatted_date}"
    headers = get_headers(data_source="SJC", random_agent=False)

    # Send request
    response = requests.post(
        url, headers=headers, data=payload, timeout=Config.REQUEST_TIMEOUT
    )

    # Handle response
    if response.status_code == 200:
        data = response.json()
        if not data.get("success"):
            _logger.warning("SJC: Không thể truy xuất dữ liệu từ API.")
            return None

        gold_data = data.get("data", [])
        if not gold_data:
            _logger.warning("SJC: Không có dữ liệu trả về từ API.")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(gold_data)
        df = df[["TypeName", "BranchName", "BuyValue", "SellValue"]]
        df.columns = ["name", "branch", "buy_price", "sell_price"]

        # Add date column as datetime type
        df["date"] = input_date

        # Ensure numerical columns are correctly formatted
        df["buy_price"] = df["buy_price"].astype(float)
        df["sell_price"] = df["sell_price"].astype(float)

        return df
    else:
        _logger.warning(
            "SJC: Không thể kết nối đến API. Mã trạng thái: %s", response.status_code
        )
        return None


@optimize_execution("MISC")
def btmc_goldprice(
    url: Optional[str] = None,
) -> pd.DataFrame:
    """Parse dữ liệu giá vàng từ API JSON Bảo Tín Minh Châu.

    Args:
        url: Đường dẫn đến API JSON. None → dùng BTMC_API_KEY env
            hoặc key mặc định (backward-compat).

    Returns:
        DataFrame chứa dữ liệu giá vàng.
    """
    if url is None:
        url = _btmc_default_url()
    response = requests.get(url, timeout=Config.REQUEST_TIMEOUT)
    json_data = response.json()
    data_list = json_data["DataList"]["Data"]

    data = []
    for item in data_list:
        row_number = item["@row"]
        n_key = f"@n_{row_number}"
        k_key = f"@k_{row_number}"
        h_key = f"@h_{row_number}"
        pb_key = f"@pb_{row_number}"
        ps_key = f"@ps_{row_number}"
        pt_key = f"@pt_{row_number}"
        d_key = f"@d_{row_number}"
        data.append(
            {
                "name": item.get(n_key, ""),
                "karat": item.get(k_key, ""),
                "gold_content": item.get(h_key, ""),
                "buy_price": item.get(pb_key, ""),
                "sell_price": item.get(ps_key, ""),
                "world_price": item.get(pt_key, ""),
                "time": item.get(d_key, ""),
            }
        )
    df = pd.DataFrame(data)
    # Ép số trước khi sort để tránh sort lexicographic trên string.
    for _col in ("buy_price", "sell_price", "world_price"):
        if _col in df.columns:
            df[_col] = pd.to_numeric(df[_col], errors="coerce")
    if "sell_price" in df.columns:
        df = df.sort_values(by=["sell_price"], ascending=False)
    return df
