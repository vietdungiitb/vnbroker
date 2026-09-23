import base64
import datetime
import logging
import warnings
from io import BytesIO
from typing import Optional

import pandas as pd
import requests

from vnbroker.config import Config
from vnbroker.core.utils.execution import optimize_execution
from vnbroker.core.utils.parser import camel_to_snake

warnings.filterwarnings(
    "ignore", message="Workbook contains no default style, apply openpyxl's default"
)

_logger = logging.getLogger(__name__)


@optimize_execution("MISC")
def vcb_exchange_rate(date: str = "2023-12-26") -> Optional[pd.DataFrame]:
    """
    Get exchange rate from Vietcombank for a specific date.

    Parameters:
        date (str): Date in format YYYY-MM-DD. If left blank, the current date will be used.
    """
    if date == "":
        date = datetime.datetime.now().strftime("%Y-%m-%d")
    else:
        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(
                f"Incorrect date format {date!r}. Should be YYYY-MM-DD."
            ) from exc

    url = f"https://www.vietcombank.com.vn/api/exchangerates/exportexcel?date={date}"
    response = requests.get(url, timeout=Config.REQUEST_TIMEOUT)
    if response.status_code == 200:
        json_data = response.json()
        excel_data = base64.b64decode(json_data["Data"])  # Decode base64 data
        columns = ["CurrencyCode", "CurrencyName", "Buy Cash", "Buy Transfer", "Sell"]
        df = pd.read_excel(BytesIO(excel_data), sheet_name="ExchangeRate")
        df.columns = columns
        df = df.iloc[2:-4]
        df["date"] = date
        df.columns = [camel_to_snake(col) for col in df.columns]
        return df
    else:
        _logger.warning(
            "VCB: Unable to fetch data. Status=%s Details=%s",
            response.status_code,
            response.text,
        )
        return None
