"""History module for TCBS."""

import pandas as pd
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Union, List
from datetime import datetime, timedelta
from vnbroker.core.utils.execution import optimize_execution
from vnbroker.core.utils.interval import normalize_interval
from .const import (
    _BASE_URL, NYX_PATH, _INTERVAL_MAP,
    _OHLC_MAP, _OHLC_DTYPE, _INTRADAY_MAP, _INTRADAY_COLUMNS, _INTRADAY_DTYPE,
    _INDEX_MAPPING
)
from vnbroker.core.models import TickerModel
from vnbroker.core.utils.logger import get_logger
from vnbroker.core.utils.market import trading_hours
from vnbroker.core.utils.parser import get_asset_type
from vnbroker.core.utils.validation import validate_symbol
from vnbroker.core.utils import client, transform, validation
from vnbroker.core.utils.lookback import get_start_date_from_lookback, interpret_lookback_length
from .auth import get_tcbs_headers
from vnbroker.core.adaptive_controller import (
    AdaptiveController,
    get_global_pressure,
    _env_bool,
    _env_float,
    _env_int,
)

logger = get_logger(__name__)

_TCBS_ADAPTIVE_ENABLED_ENV = "vnbroker_TCBS_ADAPTIVE_CONCURRENCY"
_TCBS_ADAPTIVE_START_ENV = "vnbroker_TCBS_ADAPTIVE_START_CONCURRENCY"
_TCBS_ADAPTIVE_MIN_ENV = "vnbroker_TCBS_ADAPTIVE_MIN_CONCURRENCY"
_TCBS_ADAPTIVE_STEP_UP_ENV = "vnbroker_TCBS_ADAPTIVE_STEP_UP"
_TCBS_ADAPTIVE_STEP_DOWN_ENV = "vnbroker_TCBS_ADAPTIVE_STEP_DOWN"
_TCBS_ADAPTIVE_FAIL_THRESHOLD_ENV = "vnbroker_TCBS_ADAPTIVE_FAIL_THRESHOLD"
_TCBS_ADAPTIVE_P95_HIGH_ENV = "vnbroker_TCBS_ADAPTIVE_P95_HIGH_SECONDS"
_TCBS_ADAPTIVE_P95_LOW_ENV = "vnbroker_TCBS_ADAPTIVE_P95_LOW_SECONDS"


# TimeFrame to interval key mapping
# Standard format: m/1m=minute, h/1H=hour, d/1D=day, w/1W=week, M/1M=month
_TIMEFRAME_MAP = {
    '1m': '1m',
    '5m': '5m',
    '15m': '15m',
    '30m': '30m',
    '1H': '1H',
    '1D': '1D',
    '1W': '1W',
    '1M': '1M'
}

class Quote:
    """
    TCBS data source for fetching stock market data, accommodating
    requests with large date ranges.
    """

    def __init__(
        self,
        symbol: str,
        random_agent: bool = False,
        show_log: bool = True,
        proxy_mode: str = "try",
        proxy_list: Optional[list] = None,
        auth_token: Optional[str] = None,
    ):
        """Initialize the Quote object with the given symbol."""
        symbol = validate_symbol(symbol)
        self.data_source = 'TCBS'
        self._history = None  # Cache for backwards compatibility
        self.base_url = _BASE_URL
        self.auth_token = auth_token
        self.headers = get_tcbs_headers(
            random_agent=random_agent,
            auth_token=auth_token,
        )
        self.interval_map = _INTERVAL_MAP
        self.show_log = show_log
        self.proxy_mode = proxy_mode
        self.proxy_list = proxy_list

        # Handle INDEX symbols using shared validation
        if 'INDEX' in symbol:
            self.symbol = validation.validate_symbol(
                symbol,
                _INDEX_MAPPING
            )
        else:
            self.symbol = symbol

        # Get asset type using existing utility
        self.asset_type = get_asset_type(symbol)

        if not show_log:
            logger.setLevel('CRITICAL')
    
    def _input_validation(
        self,
        start: Optional[str],
        end: Optional[str],
        interval: Optional[str]
    ) -> TickerModel:
        """Validate input data using shared validation utilities."""
        # Validate required parameters (start can now be None if length/count_back provided)
        if not end:
            raise ValueError("Vui lòng cung cấp ngày kết thúc (end)")
        if not interval:
            raise ValueError("Vui lòng cung cấp khung thời gian (interval)")

        # Normalize interval to standard format
        timeframe = normalize_interval(interval)

        # Map TimeFrame values to TCBS interval keys
        interval_key = _TIMEFRAME_MAP.get(timeframe.value)
        if interval_key is None or interval_key not in self.interval_map:
            msg = (
                f"Giá trị interval không hợp lệ: {interval}. "
                f"Vui lòng chọn: {', '.join(self.interval_map.keys())}"
            )
            raise ValueError(msg)

        # Create ticker model with normalized interval
        ticker = TickerModel(
            symbol=self.symbol,
            start=start,
            end=end,
            interval=interval_key
        )

        return ticker
    
    def _long_history(
        self,
        start: str,
        end: Optional[str],
        show_log: bool = False,
        asset_type: Optional[str] = None,
        _skip_long_check: bool = True
    ) -> pd.DataFrame:
        """
        Truy xuất dữ liệu lịch sử dài hạn từ TCBS cho khung
        thời gian ngày
        """
        if not end:
            end = datetime.now().strftime("%Y-%m-%d")

        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")

        combined_data = []
        current_start = start_date

        # Process each year chunk moving forward from start date
        while current_start <= end_date:
            try:
                # Calculate end date for this chunk
                next_year_date = datetime(
                    current_start.year + 1,
                    current_start.month,
                    1
                )
                year_end = min(
                    next_year_date - timedelta(days=1),
                    end_date
                )

                # Format dates as strings
                year_start_str = current_start.strftime("%Y-%m-%d")
                year_end_str = year_end.strftime("%Y-%m-%d")

                if show_log:
                    msg = (
                        f"Fetching chunk from {year_start_str} "
                        f"to {year_end_str}"
                    )
                    logger.info(msg)

                # Fetch data for this year chunk
                try:
                    data = self.history(
                        start=year_start_str,
                        end=year_end_str,
                        interval="1D",
                        show_log=show_log,
                        asset_type=asset_type,
                        _skip_long_check=True,
                        # Pass defaults or instance configs here if needed,
                        # currently history uses instance defaults if not provided
                    )
                    combined_data.append(data)
                except Exception as e:
                    msg = (
                        f"Dữ liệu không tồn tại từ "
                        f"{year_start_str} đến {year_end_str}: {e}"
                    )
                    logger.error(msg)

                # Move to next year's start
                current_start = next_year_date

            except Exception as e:
                logger.error(f"Error processing year chunk: {str(e)}")
                # Move forward by a year even if an error occurs
                current_start = datetime(
                    current_start.year + 1,
                    current_start.month,
                    1
                )

        # If no data was found, raise an error
        if not combined_data:
            raise ValueError(
                f"Không tìm thấy dữ liệu cho {self.symbol} "
                f"từ {start} đến {end}"
            )

        # Combine all chunks
        df = pd.concat(combined_data, ignore_index=True)

        # Filter to ensure we only get data in the requested range
        df = df[(df['time'] >= start) & (df['time'] <= end)]

        return df

    @optimize_execution("TCBS")
    def history(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: Optional[str] = "1D",
        show_log: bool = False,
        count_back: Optional[int] = 365,
        asset_type: Optional[str] = None,
        _skip_long_check: bool = False,
        length: Optional[Union[str, int]] = None,
        proxy_mode: Optional[str] = None,
        proxy_list: Optional[list] = None,
        parallel: bool = False,
        symbols: Optional[List[str]] = None,
        max_concurrency: int = 16,
        adaptive_concurrency: Optional[bool] = None,
    ) -> Union[pd.DataFrame, List[pd.DataFrame], str]:
        """
        Tham số:
            - start (tùy chọn): thời gian bắt đầu lấy dữ liệu.
              Bắt buộc nếu không có length hoặc count_back.
            - end (tùy chọn): thời gian kết thúc lấy dữ liệu.
              Mặc định là None (ngày hiện tại).
            - interval (tùy chọn): Khung thời gian. Mặc định "1D".
            - length (tùy chọn): Khoảng thời gian phân tích (vd: '3M', 150, '150').
              Nhận giá trị chuỗi (vd 3M), số ngày (int/str), hoặc số bars (vd '100b').
            - count_back (tùy chọn): Số lượng nến (bars) cần lấy.
            - show_log (tùy chọn): Hiển thị log.
            - asset_type (tùy chọn): Loại tài sản (stock, index,
              derivative). Mặc định là None (tự xác định).
            - _skip_long_check (tùy chọn): Bỏ qua kiểm tra thời
              gian dài để tránh đệ quy vô hạn. Mặc định là False.
        """
        if parallel or symbols:
            target_symbols = symbols or [self.symbol]
            return Quote.fetch_multiple(
                symbols=target_symbols,
                start=start,
                end=end,
                interval=interval,
                show_log=show_log,
                count_back=count_back,
                length=length,
                proxy_mode=proxy_mode,
                proxy_list=proxy_list,
                max_concurrency=max_concurrency,
                adaptive_concurrency=adaptive_concurrency,
            )

        # Calculate start if not provided
        if start is None:
            # Check if length defines bars
            if length is not None:
                bars_from_len, len_remainder = interpret_lookback_length(length)
                if bars_from_len is not None:
                    count_back = bars_from_len
                    length = None
                else:
                    length = len_remainder
            
            if length is not None:
                start = get_start_date_from_lookback(
                    lookback_length=length,
                    end_date=end
                )
            elif count_back is not None:
                start = get_start_date_from_lookback(
                    bars=count_back,
                    interval=interval,
                    end_date=end
                )
            else:
                raise ValueError(
                    "Tham số 'start' là bắt buộc nếu không cung cấp "
                    "'length' hoặc 'count_back'."
                )

        # Validate inputs
        if end is None:
            end = datetime.now().strftime("%Y-%m-%d")

        ticker = self._input_validation(start, end, interval)
        
        if count_back is None:
            count_back = 365

        if asset_type is None:
            asset_type = self.asset_type

        # calculate days between start and end
        start_time = datetime.strptime(ticker.start, "%Y-%m-%d")
        end_time_str = ticker.end if ticker.end else (
            datetime.now().strftime("%Y-%m-%d")
        )
        end_time = datetime.strptime(end_time_str, "%Y-%m-%d")

        # validate if the end date is not earlier than the start date
        if end_time < start_time:
            raise ValueError(
                "Thời gian kết thúc không thể sớm hơn "
                "thời gian bắt đầu."
            )

        days = (end_time - start_time).days

        # Normalize interval for API endpoint selection
        timeframe = normalize_interval(ticker.interval)
        interval_key = _TIMEFRAME_MAP.get(timeframe.value)
        if interval_key is None:
            raise ValueError(
                f"Invalid timeframe value: {timeframe.value}"
            )

        # TCBS iFlash OpenAPI does not support multi-day daily OHLC bars
        if interval_key in ["1D", "1W", "1M"] and days > 0:
            raise NotImplementedError(
                "TCBS iFlash OpenAPI does not support historical multi-day daily/weekly/monthly OHLC bars. "
                "TCBS OpenAPI only provides intraday tick data for the current session. "
                "For historical daily/weekly/monthly OHLC data, please use source='VCI' or source='KBS' "
                "(e.g., vn.quote(symbol, source='VCI').history(...)). "
                "For intraday data on TCBS, use interval='1m', '5m', or quote.intraday()."
            )

        # Only check for long date ranges if not explicitly skipped
        if not _skip_long_check and days > 365:
            return self._long_history(start, end, show_log, asset_type)
        else:
            # For the new iFlash OpenAPI, OHLC bars endpoint is not available
            # We can only compute single-session OHLC from intraday data
            if interval_key in ["1D", "1W", "1M"]:
                if show_log:
                    logger.info(f"Computing single session OHLC from intraday data for {self.symbol}")
                return self._compute_ohlc_from_intraday(start, end, interval_key, show_log)
            elif interval_key in ["1m", "5m", "15m", "30m", "1H"]:
                # For intraday intervals, return the raw intraday data
                if show_log:
                    logger.info(f"Fetching intraday data for {self.symbol}")
                return self.intraday(page_size=count_back, show_log=show_log)
            else:
                raise ValueError(f"Unsupported interval: {interval_key}")
        
    def _as_df(
        self,
        history_data: Dict,
        asset_type: str,
        floating: Optional[int] = 2
    ) -> pd.DataFrame:
        """
        Backward compatibility method that delegates to shared
        data_transform utility
        """
        from vnbroker.core.utils import transform

        # Use the shared transformation utility
        return transform.ohlc_to_df(
            data=history_data,
            column_map=_OHLC_MAP,
            dtype_map=_OHLC_DTYPE,
            asset_type=asset_type,
            symbol=self.symbol,
            source=self.data_source,
            interval="1D"  # Default for long history
        )

    def _compute_ohlc_from_intraday(
        self,
        start: str,
        end: str,
        interval_key: str,
        show_log: bool = False,
    ) -> pd.DataFrame:
        """
        Compute single-session OHLC data from intraday tick data using /nyx/v1/intraday endpoint.
        
        Since TCBS iFlash OpenAPI does not provide daily OHLC bars directly,
        this method computes a single session's bar from current intraday tick data.
        
        Args:
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            interval_key: Interval key (1D, 1W, 1M)
            show_log: Whether to show log messages.
            
        Returns:
            DataFrame with OHLC data.
        """
        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")
        if start_date != end_date:
            raise NotImplementedError(
                "TCBS iFlash OpenAPI does not support multi-day historical daily/weekly/monthly OHLC bars. "
                "TCBS OpenAPI only provides intraday tick data for the current session. "
                "For historical daily/weekly/monthly OHLC data, please use source='VCI' or source='KBS' "
                "(e.g., vn.quote(symbol, source='VCI').history(...)). "
                "For intraday data on TCBS, use interval='1m', '5m', or quote.intraday()."
            )

        if interval_key not in ["1D", "1W", "1M"]:
            if show_log:
                logger.warning(f"OHLC computation for interval {interval_key} not implemented, using 1D")
        
        all_intraday = []
        date_str = start_date.strftime("%Y-%m-%d")
        try:
            page = 0
            day_data = []
            while True:
                params = {
                    'page': page,
                    'size': 100,
                    'headIndex': -1
                }
                url = f"{self.base_url}{NYX_PATH}/intraday/{self.symbol}/his/paging"
                
                response = client.send_request(
                    url=url,
                    headers=self.headers,
                    method="GET",
                    params=params,
                    show_log=show_log,
                )
                
                records = response.get("data", []) if isinstance(response, dict) else response
                if not records:
                    break
                
                for record in records:
                    record_time = record.get("t")
                    if record_time:
                        try:
                            # Validate time format; grouping date comes from start_date
                            pd.to_datetime(record_time, format='%H:%M:%S').time()
                            record["_date"] = start_date.date()
                            day_data.append(record)
                        except Exception as e:
                            if show_log:
                                logger.debug(f"Error parsing time '{record_time}': {e}")
                            pass
                
                if len(records) < 100:
                    break
                page += 1
            
            all_intraday.extend(day_data)
            
        except Exception as exc:
            if show_log:
                logger.error(f"Error fetching intraday for {date_str}: {exc}")
            if "401" in str(exc) or "Unauthorized" in str(exc):
                raise ConnectionError(
                    "TCBS iFlash OpenAPI requires valid JWT token. "
                    "Get JWT token by exchanging API key + OTP via "
                    "POST /gaia/v1/oauth2/openapi/token, then set "
                    "TCBS_AUTH_TOKEN=<JWT> environment variable."
                )
            raise
        
        if not all_intraday:
            if show_log:
                logger.warning(f"No intraday data found for {self.symbol} from {start} to {end}")
            empty_df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
            empty_df = transform.normalize_ohlc_prices(
                empty_df,
                asset_type=self.asset_type,
                columns=["open", "high", "low", "close"],
            )
            empty_df.attrs["symbol"] = self.symbol
            empty_df.attrs["source"] = self.data_source
            empty_df.attrs["interval"] = interval_key
            return empty_df
        
        # Convert to DataFrame
        df = pd.DataFrame(all_intraday)
        df = df.rename(columns=_INTRADAY_COLUMNS)
        
        # Convert data types
        for col in ("price", "volume"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        if "time" in df.columns:
            # TCBS intraday time format is 'HH:MM:SS' - combine with date from filtering
            df["time"] = pd.to_datetime(df["time"], format='%H:%M:%S', errors="coerce")
        
        # Drop rows with invalid data
        df = df.dropna(subset=["time", "price"])
        if df.empty:
            return pd.DataFrame()
        
        # Use the stored date for grouping (added during filtering)
        if "_date" in df.columns:
            df["date"] = df["_date"]
        else:
            # Fallback: use time date
            df["date"] = df["time"].dt.date
        
        ohlc_df = df.groupby("date").agg(
            open=("price", "first"),
            high=("price", "max"),
            low=("price", "min"),
            close=("price", "last"),
            volume=("volume", "sum")
        ).reset_index()
        
        # Rename date to time for consistency
        ohlc_df = ohlc_df.rename(columns={"date": "time"})
        
        # Convert time to datetime string format
        ohlc_df["time"] = pd.to_datetime(ohlc_df["time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # Normalize via single entry point (asset-type rule in transform).
        ohlc_df = transform.normalize_ohlc_prices(
            ohlc_df,
            asset_type=self.asset_type,
            columns=["open", "high", "low", "close"],
        )
        
        # Add metadata
        ohlc_df.attrs['symbol'] = self.symbol
        ohlc_df.attrs['source'] = self.data_source
        ohlc_df.attrs['interval'] = interval_key
        
        if show_log:
            logger.info(f"Computed {len(ohlc_df)} OHLC bars from intraday data for {self.symbol}")
        
        return ohlc_df

    @classmethod
    def fetch_multiple(
        cls,
        symbols: List[str],
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: Optional[str] = "1D",
        show_log: Optional[bool] = False,
        count_back: Optional[int] = None,
        floating: Optional[int] = 2,
        length: Optional[Union[str, int]] = None,
        max_concurrency: int = 16,
        adaptive_concurrency: Optional[bool] = None,
        proxy_mode: Optional[str] = None,
        proxy_list: Optional[list] = None,
    ) -> List[pd.DataFrame]:
        if not symbols:
            return []

        safe_max_workers = max(1, max_concurrency)
        enable_adaptive = (
            adaptive_concurrency
            if adaptive_concurrency is not None
            else _env_bool(_TCBS_ADAPTIVE_ENABLED_ENV, default=False)
        )
        min_workers = _env_int(_TCBS_ADAPTIVE_MIN_ENV, default=2, min_value=1)
        min_workers = min(min_workers, safe_max_workers)
        step_up = _env_int(_TCBS_ADAPTIVE_STEP_UP_ENV, default=1, min_value=1)
        step_down = _env_int(_TCBS_ADAPTIVE_STEP_DOWN_ENV, default=2, min_value=1)
        fail_threshold = _env_float(
            _TCBS_ADAPTIVE_FAIL_THRESHOLD_ENV,
            default=0.2,
            min_value=0.0,
            max_value=1.0,
        )
        p95_high_seconds = _env_float(
            _TCBS_ADAPTIVE_P95_HIGH_ENV,
            default=1.5,
            min_value=0.01,
            max_value=None,
        )
        p95_low_seconds = _env_float(
            _TCBS_ADAPTIVE_P95_LOW_ENV,
            default=0.5,
            min_value=0.01,
            max_value=None,
        )
        if p95_low_seconds > p95_high_seconds:
            p95_low_seconds = p95_high_seconds

        # Apply cross-provider pressure: halve cap when global stress is active.
        pressure_mul = get_global_pressure().multiplier
        safe_max_workers = max(min_workers, int(safe_max_workers * pressure_mul))
        if enable_adaptive:
            start_default = max(min_workers, safe_max_workers // 2)
            worker_count = _env_int(
                _TCBS_ADAPTIVE_START_ENV,
                default=start_default,
                min_value=min_workers,
            )
            worker_count = min(worker_count, safe_max_workers)
        else:
            worker_count = safe_max_workers

        results: List[pd.DataFrame] = []
        cursor = 0

        def _run_one(symbol: str) -> tuple[Optional[pd.DataFrame], float]:
            started = time.perf_counter()
            quote = cls(
                symbol=symbol,
                show_log=show_log,
                proxy_mode=proxy_mode,
                proxy_list=proxy_list,
            )
            try:
                frame = quote.history(
                    start=start,
                    end=end,
                    interval=interval,
                    show_log=show_log,
                    count_back=count_back,
                    length=length,
                    proxy_mode=proxy_mode,
                    proxy_list=proxy_list,
                    _skip_long_check=False,
                )
                if isinstance(frame, pd.DataFrame):
                    return frame, time.perf_counter() - started
                return None, time.perf_counter() - started
            except Exception as exc:
                logger.debug("fetch_multiple %s failed: %s", symbol, exc)
                return None, time.perf_counter() - started

        # Fast path: single pool for all symbols when adaptive is off
        # (avoids create/destroy executor per batch).
        if not enable_adaptive:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                batch_results = list(executor.map(_run_one, symbols))
            results = [item for item, _ in batch_results if item is not None]
            get_global_pressure().record_batch(len(symbols), len(symbols) - len(results))
            return results

        while cursor < len(symbols):
            batch_symbols = symbols[cursor:cursor + worker_count]
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                batch_results = list(executor.map(_run_one, batch_symbols))

            success_items = [item for item, _ in batch_results if item is not None]
            batch_latencies = [elapsed for _, elapsed in batch_results]
            if len(batch_latencies) >= 2:
                batch_p95_seconds = statistics.quantiles(batch_latencies, n=100)[94]
            elif batch_latencies:
                batch_p95_seconds = batch_latencies[0]
            else:
                batch_p95_seconds = 0.0

            results.extend(success_items)
            error_count = len(batch_symbols) - len(success_items)
            get_global_pressure().record_batch(len(batch_symbols), error_count)

            if enable_adaptive:
                worker_count = AdaptiveController.compute(
                    current=worker_count,
                    batch_size=len(batch_symbols),
                    success_count=len(success_items),
                    max_concurrency=safe_max_workers,
                    min_concurrency=min_workers,
                    step_up=step_up,
                    step_down=step_down,
                    fail_threshold=fail_threshold,
                    batch_p95_seconds=batch_p95_seconds,
                    p95_high_seconds=p95_high_seconds,
                    p95_low_seconds=p95_low_seconds,
                )
            cursor += len(batch_symbols)

        return results

    @optimize_execution("TCBS")
    def intraday(
        self,
        page_size: Optional[int] = 100,
        page: Optional[int] = 0,
        show_log: bool = False
    ) -> pd.DataFrame:
        """
        Truy xuất dữ liệu khớp lệnh của mã chứng khoán bất kỳ
        từ nguồn dữ liệu TCBS
        """
        # Handle None defaults
        if page_size is None:
            page_size = 100
        if page is None:
            page = 0

        market_status = trading_hours("HOSE")
        if (
            market_status['is_trading_hour'] is False and
            market_status['data_status'] == 'preparing'
        ):
            raise ValueError(
                f"{market_status['time']}: Dữ liệu khớp lệnh "
                f"không thể truy cập trong thời gian chuẩn bị "
                f"phiên mới. Vui lòng quay lại sau."
            )

        # Validate input
        if self.symbol is None:
            raise ValueError(
                "Vui lòng nhập mã chứng khoán cần truy xuất "
                "khi khởi tạo Trading Class."
            )

        # warning if page_size is greater than 30_000
        if page_size > 30_000:
            logger.warning(
                "Bạn đang yêu cầu truy xuất quá nhiều dữ liệu, "
                "điều này có thể gây lỗi quá tải."
            )

        # Fetch data
        combined_data = []
        total_pages = (
            (page_size // 100) +
            (1 if page_size % 100 != 0 else 0)
        )

        for i in range(total_pages):
            current_size = min(100, page_size - 100 * i)
            url = (
                f'{self.base_url}{NYX_PATH}/intraday/'
                f'{self.symbol}/his/paging'
            )
            params = {
                'page': page + i,
                'size': current_size,
                'headIndex': -1
            }

            # Make request
            try:
                response = client.send_request(
                    url=url,
                    headers=self.headers,
                    method="GET",
                    params=params,
                    show_log=show_log
                )
            except Exception as exc:
                # Check for 401 Unauthorized - need valid JWT token
                if "401" in str(exc) or "Unauthorized" in str(exc):
                    raise ConnectionError(
                        "TCBS iFlash OpenAPI requires valid JWT token. "
                        "Get JWT token by exchanging API key + OTP via "
                        "POST /gaia/v1/oauth2/openapi/token, then set "
                        "TCBS_AUTH_TOKEN=<JWT> environment variable."
                    )
                raise

            data = response.get('data', [])
            combined_data.extend(data)

        # Transform data using shared utility
        df = transform.intraday_to_df(
            data=combined_data,
            column_map=_INTRADAY_MAP,
            dtype_map=_INTRADAY_DTYPE,
            symbol=self.symbol,
            asset_type=self.asset_type,
            source=self.data_source
        )

        # Reduce the time index by 7 hours to match GMT+7 timezone
        df['time'] = df['time'] - pd.Timedelta(hours=7)

        return df


# Register TCBS Quote provider
from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401
ProviderRegistry.register('quote', 'tcbs', Quote)


