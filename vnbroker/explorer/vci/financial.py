"""
Module quản lý thông tin báo cáo tài chính từ nguồn dữ liệu VCI.

VCI đã chuyển hoàn toàn từ GraphQL sang REST API vào ngày 26/04/2026.
REST endpoint: https://iq.vietcap.com.vn/api/iq-insight-service

Output format chuẩn hoá tương thích KBS:
  Columns: item | item_en | item_id | <period1> | <period2> | ...
  Period labels: "YYYY" (năm) hoặc "YYYY-QN" (quý)
  df.attrs: {symbol, source, report_type, period, periods}
"""

import requests
import pandas as pd
from packaging import version
from typing import Dict, List, Optional, Union

from .const import (
    _FINANCIAL_REPORT_PERIOD_MAP,
    _IQ_FINANCE_REPORT,
    _VCIQ_URL,
    RATIO_COLUMN_MAP_EN,
    RATIO_COLUMN_MAP_VI,
    RATIO_COLUMN_MAP_SNAKE,
    SUPPORTED_LANGUAGES,
)
from vnbroker.core.utils import client
from vnbroker.core.utils.client import ProxyConfig
from vnbroker.core.utils.execution import optimize_execution
from vnbroker.core.utils.logger import get_logger
from vnbroker.core.utils.parser import get_asset_type
from vnbroker.core.utils.user_agent import get_headers
from vnbroker.core.utils.validation import validate_symbol

logger = get_logger(__name__)


def _safe_infer_objects(df: pd.DataFrame) -> pd.DataFrame:
    """Tự động gọi infer_objects phù hợp với version pandas."""
    if version.parse(pd.__version__) >= version.parse("2.1.0"):
        return df.infer_objects(copy=False)
    else:
        return df.infer_objects()


class Finance:
    """
    Truy xuất thông tin báo cáo tài chính của một công ty theo mã chứng khoán từ nguồn dữ liệu VCI.

    Tham số:
        - symbol (str): Mã chứng khoán của công ty cần truy xuất thông tin.
        - period (str): Chu kỳ báo cáo tài chính cần truy xuất. Mặc định là 'quarter'.
        - get_all (bool): Trả về tất cả các trường dữ liệu hoặc chỉ các trường chọn lọc. Mặc định là True.
        - show_log (bool): Hiển thị thông tin log hoặc không. Mặc định là True.
    """

    def __init__(
        self,
        symbol: str,
        period: Optional[str] = "quarter",
        get_all: Optional[bool] = True,
        show_log: Optional[bool] = True,
        proxy_config: Optional[ProxyConfig] = None,
        proxy_mode: Optional[str] = None,
        proxy_list: Optional[List[str]] = None,
    ):
        """Khởi tạo đối tượng Finance với các tham số cho việc truy xuất dữ liệu báo cáo tài chính."""
        self.symbol = validate_symbol(symbol)
        self.asset_type = get_asset_type(self.symbol)
        self.headers = get_headers(data_source="VCI")
        self.show_log = show_log
        self.base_url = _VCIQ_URL
        self.data_source = "VCI"

        self._handshake()

        # Handle proxy configuration
        if proxy_config is None:
            p_mode = proxy_mode if proxy_mode else "try"
            req_mode = "direct"
            if proxy_mode == "auto" or (proxy_list and len(proxy_list) > 0):
                req_mode = "proxy"
            self.proxy_config = ProxyConfig(
                proxy_mode=p_mode,
                proxy_list=proxy_list,
                request_mode=req_mode,
            )
        else:
            self.proxy_config = proxy_config

        if not show_log:
            logger.setLevel("CRITICAL")

        # Validate input for period
        if period not in ["year", "quarter"]:
            raise ValueError("Kỳ báo cáo tài chính không hợp lệ. Chỉ chấp nhận 'year' hoặc 'quarter'.")

        # If asset_type is not stock, raise error
        if self.asset_type not in ["stock"]:
            raise ValueError("Mã chứng khoán không hợp lệ. Chỉ cổ phiếu mới có thông tin.")

        self.period = _FINANCIAL_REPORT_PERIOD_MAP.get(period)
        self.get_all = get_all
        self.com_type_code = self._get_company_type()

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _handshake(self) -> None:
        """Khởi tạo kết nối / session cookie với VCI priceboard."""
        url = "https://trading.vietcap.com.vn/priceboard"
        try:
            session = requests.Session()
            session.headers.update(self.headers)
            session.get(url, timeout=10)
            self.headers.update(session.cookies.get_dict())
        except Exception as e:
            if self.show_log:
                logger.warning(f"Handshake thất bại: {e}")

    def _get_company_type(self) -> str:
        """
        Lấy mã loại công ty từ phân loại ngành ICB4.

        Returns:
            str: 'CT' (công ty), 'CK' (chứng khoán), 'NH' (ngân hàng), 'BH' (bảo hiểm).
        """
        try:
            from vnbroker.explorer.vci.listing import Listing

            df_listing = Listing(random_agent=False, show_log=False).symbols_by_industries()
            if not df_listing.empty:
                df_match = df_listing[
                    (df_listing["symbol"] == self.symbol) & (df_listing["icb_level"] == 4)
                ]
                if not df_match.empty:
                    return df_match["com_type_code"].iloc[0]
        except Exception as e:
            logger.warning(
                f"Không lấy được loại công ty của {self.symbol} từ VCI API. "
                f"Sử dụng mặc định 'CT'. Chi tiết: {e}"
            )
        return "CT"

    def _send(self, url: str, params: Optional[dict] = None, show_log: bool = False) -> dict:
        """Gửi GET request đến VCI REST API."""
        return client.send_request(
            url=url,
            headers=self.headers,
            method="GET",
            params=params or {},
            payload=None,
            show_log=show_log,
            proxy_list=self.proxy_config.proxy_list,
            proxy_mode=self.proxy_config.proxy_mode,
            request_mode=self.proxy_config.request_mode,
        )

    @staticmethod
    def duplicated_columns_handling(df_or_mapping, target_col_name=None):
        """Xử lý tên cột trùng lặp trong DataFrame hoặc mapping DataFrame."""
        if target_col_name is not None:
            duplicated_subset = df_or_mapping[df_or_mapping[target_col_name].duplicated()].copy()
            non_duplicated_subset = df_or_mapping[~df_or_mapping[target_col_name].duplicated()].copy()
            duplicated_subset[target_col_name] = (
                df_or_mapping["name"] + " - " + df_or_mapping["field_name"]
            )
            return pd.concat([non_duplicated_subset, duplicated_subset])
        else:
            df = df_or_mapping.copy()
            duplicate_mask = df.columns.duplicated(keep=False)
            duplicated_col_names = df.columns[duplicate_mask].unique()
            if len(duplicated_col_names) > 0:
                new_columns = df.columns.tolist()
                for col_name in duplicated_col_names:
                    indices = [i for i, name in enumerate(new_columns) if name == col_name]
                    for idx in indices[1:]:
                        new_col_name = f"_{col_name}"
                        suffix_count = 1
                        while new_col_name in new_columns:
                            new_col_name = f"{'_' * (suffix_count + 1)}{col_name}"
                            suffix_count += 1
                        new_columns[idx] = new_col_name
                df.columns = new_columns
            return df

    # ──────────────────────────────────────────────────────────────────────────
    # REST API data fetching
    # ──────────────────────────────────────────────────────────────────────────

    def _get_ratio_dict(
        self,
        lang: str = "vi",
        format: str = "dict",
        style: str = "readable",
        show_log: Optional[bool] = False,
    ) -> Union[pd.DataFrame, Dict]:
        """
        Lấy từ điển ánh xạ cho tất cả các chỉ số tài chính từ VCI REST API.

        Tham số:
            - lang (str): Ngôn ngữ ('vi' hoặc 'en'). Mặc định là 'vi'.
            - format (str): Định dạng trả về ('dict' hoặc 'dataframe'). Mặc định là 'dict'.
            - style (str): Phong cách ('readable' hoặc 'code'). Mặc định là 'readable'.
            - show_log (bool): Hiển thị log. Mặc định là False.

        Returns:
            Union[pd.DataFrame, Dict]: Dữ liệu ánh xạ tùy theo tham số format.
        """
        if lang not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Ngôn ngữ '{lang}' không hợp lệ. Chỉ chấp nhận {', '.join(SUPPORTED_LANGUAGES)}."
            )

        url = f"{self.base_url}/v1/company/{self.symbol}/financial-statement/metrics"

        if show_log:
            logger.debug(f"Requesting financial metrics from {url}")

        response_data = self._send(url, show_log=show_log)
        data = response_data.get("data")

        if data is None:
            raise ValueError(
                f"Không nhận được dữ liệu metadata từ VCI cho mã {self.symbol}."
            )

        combine_ls = []
        for key in data.keys():
            df = pd.DataFrame(data[key])
            df["report_name"] = key
            df = df[["report_name", "field", "parent", "titleEn", "titleVi", "fullTitleVi", "fullTitleEn"]]
            combine_ls.append(df)

        df = pd.concat(combine_ls)
        df = df.rename(
            columns={
                "field": "field_name",
                "titleVi": "name",
                "titleEn": "en_name",
                "fullTitleVi": "full_name",
                "fullTitleEn": "en_full_name",
            }
        )

        if format == "dict":
            if lang == "vi":
                return df.set_index("field_name")["name"].to_dict()
            elif lang == "en":
                return df.set_index("field_name")["en_name"].to_dict()
        else:
            return df

    def _get_report(
        self,
        report_type: Optional[str] = None,
        lang: Optional[str] = "en",
        show_log: Optional[bool] = False,
        mode: Optional[str] = "final",
        style: Optional[str] = "readable",
        get_all: Optional[bool] = False,
        period: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """Lấy dữ liệu báo cáo tài chính thô hoặc đã ánh xạ từ VCI REST API."""
        # Baseline limit
        effective_limit = limit if limit is not None else 4

        if report_type not in _IQ_FINANCE_REPORT.keys():
            raise ValueError(
                f"Loại báo cáo không hợp lệ: '{report_type}'. Hỗ trợ: {', '.join(_IQ_FINANCE_REPORT.keys())}"
            )

        report_section = _IQ_FINANCE_REPORT[report_type]

        if report_section == "RATIO":
            url = f"{self.base_url}/v1/company/{self.symbol}/statistics-financial"
            params = {}
        else:
            url = f"{self.base_url}/v1/company/{self.symbol}/financial-statement"
            params = {"section": report_section}

        if show_log:
            logger.debug(f"Requesting financial report from {url}. params: {params}")

        response_data = self._send(url, params=params, show_log=show_log)
        data = response_data.get("data")

        if data is None:
            raise ConnectionError(
                f"Không nhận được dữ liệu (data) từ VCI cho mã {self.symbol} tại section {report_section}. "
                "VCI có thể yêu cầu xác thực hoặc đã thay đổi endpoint."
            )

        # Filter only requested period type
        effective_period = period if period else self.period
        target_key = "years" if effective_period in ["year", "Y"] else "quarters"

        if report_section == "RATIO":
            combined_df = pd.DataFrame(data)
            # For annual view: keep only Q4 records (year-end) to get 1 row per year
            if effective_period in ["year", "Y"] and "quarter" in combined_df.columns:
                combined_df = combined_df[combined_df["quarter"] == 4].copy()
            # Sort by year descending (most recent first)
            year_col = "yearReport" if "yearReport" in combined_df.columns else ("year" if "year" in combined_df.columns else None)
            if year_col:
                combined_df = combined_df.sort_values(year_col, ascending=False).reset_index(drop=True)
        else:
            period_data = data.get(target_key, [])
            if period_data:
                combined_df = pd.DataFrame(period_data)
                combined_df["report_period"] = target_key[:-1]
            else:
                combined_df = pd.DataFrame()

        # Apply limit
        if not combined_df.empty and len(combined_df) > effective_limit:
            combined_df = combined_df.head(effective_limit)

        if mode == "final":
            return self._ratio_mapping(
                report_df=combined_df,
                lang=lang,
                style=style,
                get_all=get_all,
                show_log=show_log,
                period_type=effective_period,
                report_type=report_type,
            )
        elif mode == "raw":
            return combined_df

    def _ratio_mapping(
        self,
        report_df: pd.DataFrame,
        lang: Optional[str] = "vi",
        style: str = "readable",
        get_all: Optional[bool] = False,
        show_log: Optional[bool] = False,
        period_type: Optional[str] = None,
        report_type: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Chuyển đổi DataFrame thô (period=rows, fields=cols) sang định dạng chuẩn:
        items làm rows, periods làm columns — tương thích với KBS output.

        Output columns: item | item_en | item_id | <period1> | <period2> | ...
        """
        if report_type and report_type.upper() == "RATIO":
            vi_dict = RATIO_COLUMN_MAP_VI
            en_dict = RATIO_COLUMN_MAP_EN
            snake_dict = RATIO_COLUMN_MAP_SNAKE
        else:
            # Get metadata mapping for both languages
            meta_df = self._get_ratio_dict(format="dataframe", show_log=show_log)
            vi_dict = meta_df.set_index("field_name")["name"].to_dict()
            en_dict = meta_df.set_index("field_name")["en_name"].to_dict()
            snake_dict = None

        # Identify which columns are items vs metadata
        item_cols = [col for col in report_df.columns if col in vi_dict]

        # Create period labels if not already present
        if "period" not in report_df.columns:
            y_col = (
                "year"
                if "year" in report_df.columns
                else ("yearReport" if "yearReport" in report_df.columns else None)
            )
            q_col = (
                "quarter"
                if "quarter" in report_df.columns
                else ("lengthReport" if "lengthReport" in report_df.columns else None)
            )

            if y_col and q_col:
                def fmt_period(row):
                    try:
                        y = int(row[y_col])
                        q = int(row[q_col])
                        return (
                            f"{y}-Q{q}"
                            if q < 5 and period_type in ["quarter", "Q"]
                            else f"{y}"
                        )
                    except Exception:  # noqa: BLE001
                        return "N/A"

                report_df["period"] = report_df.apply(fmt_period, axis=1)
            elif y_col:
                report_df["period"] = report_df[y_col].astype(str)
            elif "report_period" in report_df.columns:
                report_df["period"] = report_df["report_period"]

        # We want to return Items as rows and Periods as columns (match KBS)
        if "period" in report_df.columns:
            cols_to_keep = ["period"] + item_cols
            processed_df = report_df[cols_to_keep].copy()

            # Set period as index then transpose
            processed_df = processed_df.set_index("period").T

            # Now rows are items (field codes). Add readable labels.
            processed_df.index.name = "item_id"
            processed_df = processed_df.reset_index()

            processed_df["item"] = processed_df["item_id"].map(vi_dict)
            processed_df["item_en"] = processed_df["item_id"].map(en_dict)

            # Normalize item_id to snake_case
            if snake_dict:
                processed_df["item_id"] = processed_df["item_id"].map(
                    lambda x: snake_dict.get(x, x)
                )
            else:
                try:
                    from vnbroker.core.utils.field.handler import FieldHandler

                    field_handler = FieldHandler()
                    processed_df["item_id"] = processed_df["item_en"].apply(
                        lambda x: field_handler.normalize_field_name(x, language="en")
                        if pd.notna(x)
                        else x
                    )
                except ImportError:
                    pass

            # Reorder columns: metadata first, then periods
            period_cols = [
                c for c in processed_df.columns if c not in ["item", "item_en", "item_id"]
            ]
            processed_df = processed_df[["item", "item_en", "item_id"] + period_cols]

            return processed_df

        return report_df

    def _get_financial_report(
        self,
        report_type: str,
        period: Optional[str] = None,
        lang: Optional[str] = "en",
        mode: Optional[str] = "final",
        style: Optional[str] = "readable",
        get_all: Optional[bool] = False,
        dropna: Optional[bool] = True,
        show_log: Optional[bool] = False,
        limit: Optional[int] = None,
        display_mode=None,
    ) -> pd.DataFrame:
        """Cổng truy xuất báo cáo tài chính nội bộ."""
        effective_period = period if period else self.period

        df = self._get_report(
            report_type=report_type,
            lang=lang,
            mode=mode,
            style=style,
            get_all=get_all,
            show_log=show_log,
            limit=limit,
            period=effective_period,
        )

        if df.empty:
            return df

        if dropna:
            saved_attrs = dict(df.attrs)
            meta_cols = [c for c in ("item", "item_en", "item_id") if c in df.columns]
            # Deduplicate data_cols to avoid quadratic column explosion from duplicate period labels
            seen, data_cols = set(), []
            for c in df.columns:
                if c not in set(meta_cols) and c not in seen:
                    seen.add(c)
                    data_cols.append(c)
            df_filled = df[data_cols].fillna(0)
            def _col_has_nonzero(col):
                s = df_filled[col]
                if isinstance(s, pd.DataFrame):
                    s = s.iloc[:, 0]
                return pd.to_numeric(s, errors='coerce').fillna(0).any()
            non_zero = [c for c in data_cols if _col_has_nonzero(c)]
            df = df[meta_cols + non_zero].copy()
            df = _safe_infer_objects(df.fillna(0))
            df.attrs.update(saved_attrs)

        # Apply display_mode filter (KBS-compatible column selection)
        df = self._apply_display_mode(df, display_mode, lang)

        # Attach metadata attrs
        period_str = "year" if effective_period in ("Y", "year") else "quarter"
        period_cols = [c for c in df.columns if c not in {"item", "item_en", "item_id"}]
        df.attrs.update({
            "symbol": self.symbol,
            "source": self.data_source,
            "report_type": report_type,
            "period": period_str,
            "periods": period_cols,
        })

        return df

    @staticmethod
    def _apply_display_mode(df: pd.DataFrame, display_mode, lang: Optional[str]) -> pd.DataFrame:
        """
        Lọc cột theo display_mode để tương thích với KBS FieldDisplayMode.

        - display_mode='std' hoặc FieldDisplayMode.STD → [item, item_id] + periods
        - display_mode='all' hoặc FieldDisplayMode.ALL → [item, item_en, item_id] + periods
        - display_mode='vi' → [item, item_id] + periods  (backward compat)
        - display_mode='en' → [item_en renamed to item, item_id] + periods
        - None → [item, item_en, item_id] + periods (full)
        """
        if display_mode is None and lang is None:
            return df

        try:
            from vnbroker.explorer.kbs.financial import FieldDisplayMode
            if isinstance(display_mode, FieldDisplayMode):
                dm_str = display_mode.value if hasattr(display_mode, "value") else str(display_mode)
            else:
                dm_str = str(display_mode).lower() if display_mode else None
        except ImportError:
            dm_str = str(display_mode).lower() if display_mode else None

        if dm_str in ("std", "fielddisplaymode.std"):
            keep = ["item", "item_id"]
        elif dm_str in ("all", "fielddisplaymode.all", "none"):
            return df  # keep all meta cols
        elif dm_str == "vi":
            keep = ["item", "item_id"]
        elif dm_str == "en":
            # Keep item_en as display name, drop item
            if "item_en" in df.columns:
                df = df.copy()
                df = df.drop(columns=["item"], errors="ignore")
                df = df.rename(columns={"item_en": "item"})
            return df
        else:
            return df  # unknown → return as-is

        data_cols = [c for c in df.columns if c not in {"item", "item_en", "item_id"}]
        present_keep = [c for c in keep if c in df.columns]
        return df[present_keep + data_cols].copy()

    # ──────────────────────────────────────────────────────────────────────────
    # Public methods
    # ──────────────────────────────────────────────────────────────────────────

    @optimize_execution("VCI")
    def balance_sheet(
        self,
        period: Optional[str] = None,
        dropna: Optional[bool] = True,
        show_log: Optional[bool] = False,
        display_mode=None,
    ) -> pd.DataFrame:
        """
        Trích xuất dữ liệu bảng cân đối kế toán từ nguồn VCI REST API.

        Tham số:
            - period (str): Kỳ báo cáo ('year' hoặc 'quarter'). Mặc định lấy theo cấu hình khởi tạo.
            - dropna (bool): Loại bỏ các cột có tất cả giá trị bằng 0. Mặc định là True.
            - show_log (bool): Hiển thị thông tin log. Mặc định là False.
            - display_mode: Chế độ hiển thị cột (tương thích KBS FieldDisplayMode). Mặc định None.

        Returns:
            pd.DataFrame: Bảng cân đối kế toán với columns [item, item_en, item_id, period...].
        """
        return self._get_financial_report(
            "balance_sheet",
            period=period,
            lang="en",  # Default to English, lang parameter removed per roadmap
            dropna=dropna,
            show_log=show_log,
            display_mode=display_mode,
        )

    @optimize_execution("VCI")
    def income_statement(
        self,
        period: Optional[str] = None,
        dropna: Optional[bool] = True,
        show_log: Optional[bool] = False,
        display_mode=None,
    ) -> pd.DataFrame:
        """
        Trích xuất báo cáo kết quả kinh doanh từ nguồn VCI REST API.

        Tham số:
            - period (str): Kỳ báo cáo ('year' hoặc 'quarter').
            - dropna (bool): Loại bỏ các cột 0.
            - show_log (bool): Hiển thị log.
            - display_mode: Chế độ hiển thị cột (tương thích KBS FieldDisplayMode).

        Returns:
            pd.DataFrame: Báo cáo kết quả kinh doanh.
        """
        return self._get_financial_report(
            "income_statement",
            period=period,
            lang="en",  # Default to English, lang parameter removed per roadmap
            dropna=dropna,
            show_log=show_log,
            display_mode=display_mode,
        )

    @optimize_execution("VCI")
    def cash_flow(
        self,
        period: Optional[str] = None,
        dropna: Optional[bool] = True,
        show_log: Optional[bool] = False,
        display_mode=None,
    ) -> pd.DataFrame:
        """
        Trích xuất báo cáo lưu chuyển tiền tệ từ nguồn VCI REST API.

        Tham số:
            - period (str): Kỳ báo cáo ('year' hoặc 'quarter').
            - dropna (bool): Loại bỏ các cột 0.
            - show_log (bool): Hiển thị log.
            - display_mode: Chế độ hiển thị cột (tương thích KBS FieldDisplayMode).

        Returns:
            pd.DataFrame: Báo cáo lưu chuyển tiền tệ.
        """
        return self._get_financial_report(
            "cash_flow",
            period=period,
            lang="en",  # Default to English, lang parameter removed per roadmap
            dropna=dropna,
            show_log=show_log,
            display_mode=display_mode,
        )

    @optimize_execution("VCI")
    def ratio(
        self,
        period: Optional[str] = None,
        dropna: Optional[bool] = True,
        show_log: Optional[bool] = False,
        display_mode=None,
    ) -> pd.DataFrame:
        """
        Trích xuất các chỉ số tài chính (Financial Ratios) từ nguồn VCI REST API.

        Tham số:
            - period (str): Kỳ báo cáo ('year' hoặc 'quarter').
            - dropna (bool): Loại bỏ các cột 0.
            - show_log (bool): Hiển thị log.
            - display_mode: Chế độ hiển thị cột (tương thích KBS FieldDisplayMode).

        Returns:
            pd.DataFrame: Bảng các chỉ số tài chính.
        """
        return self._get_financial_report(
            "ratio",
            period=period,
            lang="en",  # Default to English, lang parameter removed per roadmap
            dropna=dropna,
            show_log=show_log,
            display_mode=display_mode,
        )

    @optimize_execution("VCI")
    def financial_ratios(self, *args, **kwargs) -> pd.DataFrame:
        """Alias tương thích ngược cho ratio()."""
        return self.ratio(*args, **kwargs)


# Register provider
from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401

ProviderRegistry.register("financial", "vci", Finance)
