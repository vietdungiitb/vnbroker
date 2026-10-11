"""Quote module for VCI data source."""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from datetime import datetime
from typing import Any, List, Optional, Union

import pandas as pd
from vnbroker.core.utils.execution import optimize_execution

from vnbroker.core.models import TickerModel
from vnbroker.core.utils import async_send_request
from vnbroker.core.utils.client import ProxyConfig, RequestMode, send_request
from vnbroker.core.utils.interval import normalize_interval
from vnbroker.core.utils.logger import get_logger
from vnbroker.core.utils.lookback import (
    get_start_date_from_lookback,
    interpret_lookback_length,
)
from vnbroker.core.utils.market import trading_hours
from vnbroker.core.utils.parser import convert_time_flexible, get_asset_type
from vnbroker.core.utils.transform import intraday_to_df, normalize_price_columns, ohlc_to_df
from vnbroker.core.utils.user_agent import get_headers
from vnbroker.core.utils.validation import validate_symbol
from vnbroker.core.utils.proxy_manager import proxy_manager
from vnbroker.core.adaptive_controller import (
    AdaptiveController,
    get_global_pressure,
    _env_int,
    _env_float,
    _env_bool,
)

from .const import (
    _INDEX_MAPPING,
    _INTERVAL_MAP,
    _INTRADAY_DTYPE,
    _INTRADAY_MAP,
    _INTRADAY_URL,
    _OHLC_DTYPE,
    _OHLC_MAP,
    _PRICE_DEPTH_MAP,
    _RESAMPLE_MAP,
    _TRADING_URL,
)

logger = get_logger(__name__)

_ADAPTIVE_ENABLED_ENV = "vnbroker_VCI_ADAPTIVE_CONCURRENCY"
_ADAPTIVE_START_ENV = "vnbroker_VCI_ADAPTIVE_START_CONCURRENCY"
_ADAPTIVE_MIN_ENV = "vnbroker_VCI_ADAPTIVE_MIN_CONCURRENCY"
_ADAPTIVE_STEP_UP_ENV = "vnbroker_VCI_ADAPTIVE_STEP_UP"
_ADAPTIVE_STEP_DOWN_ENV = "vnbroker_VCI_ADAPTIVE_STEP_DOWN"
_ADAPTIVE_FAIL_THRESHOLD_ENV = "vnbroker_VCI_ADAPTIVE_FAIL_THRESHOLD"
_ADAPTIVE_P95_HIGH_ENV = "vnbroker_VCI_ADAPTIVE_P95_HIGH_SECONDS"
_ADAPTIVE_P95_LOW_ENV = "vnbroker_VCI_ADAPTIVE_P95_LOW_SECONDS"

_TIMEFRAME_MAP = {
    "1D": "1D",
    "1H": "1H",
    "1W": "1W",
    "1M": "1M",
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
}


class Quote:
    """Fetch VCI historical, intraday, and depth quote data."""

    def __init__(
        self,
        symbol: str,
        random_agent: bool = False,
        proxy_config: Optional[ProxyConfig] = None,
        show_log: bool = True,
        proxy_mode: Optional[str] = None,
        proxy_list: Optional[List[str]] = None,
    ):
        self.symbol = validate_symbol(symbol)
        self.data_source = "VCI"
        self.asset_type = get_asset_type(self.symbol)
        self.base_url = _TRADING_URL
        self.headers = get_headers(data_source=self.data_source, random_agent=random_agent)
        self.interval_map = _INTERVAL_MAP
        self.show_log = show_log

        if proxy_config is None:
            p_mode = proxy_mode if proxy_mode else "try"
            req_mode = "proxy" if (proxy_mode == "auto" or proxy_list) else "direct"
            self.proxy_config = ProxyConfig(
                proxy_mode=p_mode,
                proxy_list=proxy_list,
                request_mode=req_mode,
            )
        else:
            self.proxy_config = proxy_config

        if not show_log:
            logger.setLevel("CRITICAL")

        if "INDEX" in self.symbol:
            self.symbol = self._index_validation()

    def _index_validation(self) -> str:
        if self.symbol not in _INDEX_MAPPING:
            valid_indices = ", ".join(_INDEX_MAPPING.keys())
            raise ValueError(
                f"Khong tim thay ma chung khoan {self.symbol}. "
                f"Cac gia tri hop le: {valid_indices}"
            )
        return _INDEX_MAPPING[self.symbol]

    def _input_validation(self, start: str, end: Optional[str], interval: Optional[str]) -> tuple[TickerModel, str, str]:
        timeframe = normalize_interval(interval)
        ticker = TickerModel(symbol=self.symbol, start=start, end=end, interval=str(timeframe))

        interval_key = _TIMEFRAME_MAP.get(timeframe.value)
        if interval_key is None or interval_key not in self.interval_map:
            valid_intervals = ", ".join(self.interval_map.keys())
            raise ValueError(
                f"Gia tri interval khong hop le: {interval}. Vui long chon: {valid_intervals}"
            )

        return ticker, interval_key, timeframe.value

    def _resolve_dates(
        self,
        start: Optional[str],
        end: Optional[str],
        interval: str,
        count_back: Optional[int],
        length: Optional[Union[str, int]],
    ) -> tuple[str, str, Optional[int]]:
        resolved_end = end or datetime.now().strftime("%Y-%m-%d")
        resolved_count_back = count_back
        resolved_length = length

        if start is None and resolved_length is not None:
            bars_from_len, remaining_length = interpret_lookback_length(resolved_length)
            if bars_from_len is not None:
                resolved_count_back = bars_from_len
                resolved_length = None
            else:
                resolved_length = remaining_length

        if start is None:
            if resolved_length is not None:
                start = get_start_date_from_lookback(
                    lookback_length=resolved_length,
                    end_date=resolved_end,
                )
            elif resolved_count_back is not None:
                start = get_start_date_from_lookback(
                    bars=resolved_count_back,
                    interval=interval,
                    end_date=resolved_end,
                )
            else:
                start = get_start_date_from_lookback(
                    lookback_days=365,
                    end_date=resolved_end,
                )

        return start, resolved_end, resolved_count_back

    @staticmethod
    def _extract_data_list(response: Any) -> List[dict]:
        if isinstance(response, list):
            return response

        if not isinstance(response, dict):
            return []

        data = response.get("data")
        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            for key in ("items", "candles", "ohlc", "bars"):
                value = data.get(key)
                if isinstance(value, list):
                    return value

        for value in response.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value

        return []

    @staticmethod
    def _parse_datetime(value: str, is_end: bool = False) -> datetime:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            dt = datetime.strptime(value, "%Y-%m-%d")
            if is_end:
                dt = dt + pd.Timedelta(days=1)
            return dt

    def _estimate_count_back(self, interval_value: str, start_time: datetime, end_time: datetime, count_back: Optional[int]) -> int:
        if count_back is not None:
            return count_back

        business_days = pd.bdate_range(start=start_time, end=end_time)
        if interval_value == "ONE_DAY":
            return len(business_days) + 1
        if interval_value == "ONE_HOUR":
            return int(len(business_days) * 5 + 1)
        if interval_value == "ONE_MINUTE":
            return int(len(business_days) * 255 + 1)
        return 1000

    def _build_history_payload(
        self,
        interval_key: str,
        start: str,
        end: str,
        count_back: Optional[int],
    ) -> dict:
        start_time = self._parse_datetime(start)
        end_time = self._parse_datetime(end, is_end=True)

        if start_time > end_time:
            raise ValueError("Thoi gian bat dau khong the lon hon thoi gian ket thuc.")

        interval_value = self.interval_map[interval_key]
        auto_count_back = self._estimate_count_back(interval_value, start_time, end_time, count_back)

        return {
            "timeFrame": interval_value,
            "symbols": [self.symbol],
            "to": int(end_time.timestamp()),
            "countBack": auto_count_back,
        }

    @staticmethod
    def _normalize_ohlc_response(response: Any) -> List[dict]:
        data = Quote._extract_data_list(response)
        if not data:
            return []

        first = data[0] if isinstance(data, list) and data else None
        if isinstance(first, dict) and isinstance(first.get("o"), list):
            try:
                t_values = first.get("t", [])
                o_values = first.get("o", [])
                h_values = first.get("h", [])
                l_values = first.get("l", [])
                c_values = first.get("c", [])
                v_values = first.get("v", [])
                min_len = min(
                    len(t_values),
                    len(o_values),
                    len(h_values),
                    len(l_values),
                    len(c_values),
                    len(v_values),
                )
                return [
                    {
                        "t": t_values[idx],
                        "o": o_values[idx],
                        "h": h_values[idx],
                        "l": l_values[idx],
                        "c": c_values[idx],
                        "v": v_values[idx],
                    }
                    for idx in range(min_len)
                ]
            except Exception:
                # BL-6: payload hỏng là lỗi xử lý, phải ném ra để tầng trên
                # nhìn thấy — không biến thành danh sách rỗng (trông như
                # "không có phiên giao dịch"). Nhánh `if not data` ở trên
                # vẫn giữ cho ca rỗng thật.
                raise

        return data

    async def history_async(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: Optional[str] = "1D",
        show_log: Optional[bool] = False,
        count_back: Optional[int] = None,
        floating: Optional[int] = 2,
        length: Optional[Union[str, int]] = None,
    ) -> pd.DataFrame:
        start, end, count_back = self._resolve_dates(start, end, interval or "1D", count_back, length)
        ticker, interval_key, normalized_interval = self._input_validation(start, end, interval)

        url = f"{self.base_url}chart/OHLCChart/gap-chart"
        payload = self._build_history_payload(
            interval_key=interval_key,
            start=ticker.start,
            end=ticker.end or end,
            count_back=count_back,
        )

        request_mode = self.proxy_config.request_mode
        if isinstance(request_mode, str):
            request_mode = RequestMode(request_mode)

        proxy_pool = self.proxy_config.proxy_list
        if request_mode == RequestMode.PROXY and proxy_pool is None:
            proxy_pool = proxy_manager.get_proxy_pool(size=16)
        response = await async_send_request(
            url=url,
            headers=self.headers,
            method="POST",
            payload=payload,
            proxy_idx=abs(hash(self.symbol)),
            proxy_list=proxy_pool,
            proxy_mode=self.proxy_config.proxy_mode,
            show_log=show_log or self.show_log,
        )

        data = self._normalize_ohlc_response(response)
        if not data:
            empty_df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
            return normalize_price_columns(
                empty_df,
                columns=["open", "high", "low", "close"],
                source_unit="VND",
                floating=floating or 2,
            )

        df = ohlc_to_df(
            data=data,
            column_map=_OHLC_MAP,
            dtype_map=_OHLC_DTYPE,
            asset_type=self.asset_type,
            symbol=self.symbol,
            source=self.data_source,
            interval=normalized_interval,
            floating=floating or 2,
            resample_map=_RESAMPLE_MAP,
        )

        if count_back is not None:
            df = df.tail(count_back).reset_index(drop=True)

        return df

    @classmethod
    async def fetch_multiple(
        cls,
        symbols: List[str],
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: Optional[str] = "1D",
        show_log: bool = False,
        count_back: Optional[int] = None,
        floating: int = 2,
        length: Optional[Union[str, int]] = None,
        max_concurrency: int = 24,
        proxy_list: Optional[List[str]] = None,
        proxy_mode: Optional[str] = None,
        adaptive_concurrency: Optional[bool] = None,
    ) -> List[pd.DataFrame]:
        shared_proxy_pool = proxy_list
        if proxy_mode == "auto" and shared_proxy_pool is None:
            shared_proxy_pool = proxy_manager.get_proxy_pool(
                size=max(8, min(max_concurrency, 32))
            )

        async def _run_one(symbol: str) -> tuple[Optional[pd.DataFrame], float]:
            started = time.perf_counter()
            quote = cls(
                symbol=symbol,
                show_log=show_log,
                proxy_mode=proxy_mode,
                proxy_list=shared_proxy_pool,
            )
            try:
                frame = await quote.history_async(
                    start=start,
                    end=end,
                    interval=interval,
                    show_log=show_log,
                    count_back=count_back,
                    floating=floating,
                    length=length,
                )
                return frame, time.perf_counter() - started
            except Exception as exc:
                if show_log:
                    logger.warning("Fetch failed for %s: %s", symbol, exc)
                return None, time.perf_counter() - started

        if not symbols:
            return []

        enable_adaptive = (
            adaptive_concurrency
            if adaptive_concurrency is not None
            else _env_bool(_ADAPTIVE_ENABLED_ENV, default=False)
        )
        min_concurrency = _env_int(_ADAPTIVE_MIN_ENV, default=4, min_value=1)
        step_up = _env_int(_ADAPTIVE_STEP_UP_ENV, default=2, min_value=1)
        step_down = _env_int(_ADAPTIVE_STEP_DOWN_ENV, default=3, min_value=1)
        fail_threshold = _env_float(
            _ADAPTIVE_FAIL_THRESHOLD_ENV,
            default=0.2,
            min_value=0.0,
            max_value=1.0,
        )
        p95_high_seconds = _env_float(
            _ADAPTIVE_P95_HIGH_ENV,
            default=1.2,
            min_value=0.01,
            max_value=None,
        )
        p95_low_seconds = _env_float(
            _ADAPTIVE_P95_LOW_ENV,
            default=0.35,
            min_value=0.01,
            max_value=None,
        )
        if p95_low_seconds > p95_high_seconds:
            p95_low_seconds = p95_high_seconds

        safe_max_concurrency = max(1, max_concurrency)
        min_concurrency = min(min_concurrency, safe_max_concurrency)
        # Apply cross-provider pressure: halve cap when global stress is active.
        pressure_mul = get_global_pressure().multiplier
        safe_max_concurrency = max(min_concurrency, int(safe_max_concurrency * pressure_mul))
        if enable_adaptive:
            start_default = max(min_concurrency, safe_max_concurrency // 2)
            current_window = _env_int(
                _ADAPTIVE_START_ENV,
                default=start_default,
                min_value=min_concurrency,
            )
            current_window = min(current_window, safe_max_concurrency)
        else:
            current_window = safe_max_concurrency

        results: List[pd.DataFrame] = []
        cursor = 0
        while cursor < len(symbols):
            batch_symbols = symbols[cursor:cursor + current_window]
            batch_results = await asyncio.gather(
                *[_run_one(symbol) for symbol in batch_symbols]
            )
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
                current_window = AdaptiveController.compute(
                    current=current_window,
                    batch_size=len(batch_symbols),
                    success_count=len(success_items),
                    max_concurrency=safe_max_concurrency,
                    min_concurrency=min_concurrency,
                    step_up=step_up,
                    step_down=step_down,
                    fail_threshold=fail_threshold,
                    batch_p95_seconds=batch_p95_seconds,
                    p95_high_seconds=p95_high_seconds,
                    p95_low_seconds=p95_low_seconds,
                )
            cursor += len(batch_symbols)

        return results

    @optimize_execution("VCI")
    def history(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: Optional[str] = "1D",
        to_df: Optional[bool] = True,
        show_log: Optional[bool] = False,
        count_back: Optional[int] = None,
        floating: Optional[int] = 2,
        length: Optional[Union[str, int]] = None,
        get_all: Optional[bool] = False,
        parallel: bool = False,
        symbols: Optional[List[str]] = None,
        max_concurrency: int = 24,
    ) -> Union[pd.DataFrame, List[pd.DataFrame], str]:
        """Fetch historical OHLC data with optional parallel multi-symbol mode."""
        if parallel or symbols:
            target_symbols = symbols or [self.symbol]
            try:
                return asyncio.run(
                    Quote.fetch_multiple(
                        symbols=target_symbols,
                        start=start,
                        end=end,
                        interval=interval,
                        show_log=bool(show_log),
                        count_back=count_back,
                        floating=floating or 2,
                        length=length,
                        max_concurrency=max_concurrency,
                    )
                )
            except RuntimeError as exc:
                raise RuntimeError(
                    "Cannot call sync parallel history inside an active event loop. "
                    "Use await Quote.fetch_multiple(...) or await history_async(...)."
                ) from exc

        start, end, count_back = self._resolve_dates(start, end, interval or "1D", count_back, length)
        ticker, interval_key, normalized_interval = self._input_validation(start, end, interval)

        url = f"{self.base_url}chart/OHLCChart/gap-chart"
        payload = self._build_history_payload(
            interval_key=interval_key,
            start=ticker.start,
            end=ticker.end or end,
            count_back=count_back,
        )

        response = send_request(
            url=url,
            headers=self.headers,
            method="POST",
            payload=payload,
            show_log=show_log or self.show_log,
            proxy_list=self.proxy_config.proxy_list,
            proxy_mode=self.proxy_config.proxy_mode,
            request_mode=self.proxy_config.request_mode,
        )

        data = self._normalize_ohlc_response(response)
        if not data:
            empty_df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
            return normalize_price_columns(
                empty_df,
                columns=["open", "high", "low", "close"],
                source_unit="VND",
                floating=floating or 2,
            )

        df = ohlc_to_df(
            data=data,
            column_map=_OHLC_MAP,
            dtype_map=_OHLC_DTYPE,
            asset_type=self.asset_type,
            symbol=self.symbol,
            source=self.data_source,
            interval=normalized_interval,
            floating=floating or 2,
            resample_map=_RESAMPLE_MAP,
        )

        if count_back is not None:
            df = df.tail(count_back).reset_index(drop=True)

        if not to_df:
            return json.dumps(df.to_dict(orient="records"), ensure_ascii=False, default=str)

        return df

    @optimize_execution("VCI")
    def intraday(
        self,
        page_size: Optional[int] = 100,
        page: Optional[int] = 1,
        to_df: Optional[bool] = True,
        get_all: Optional[bool] = False,
        last_time: Optional[Union[str, int, float]] = None,
        last_time_format: Optional[str] = None,
        show_log: bool = False,
    ) -> Union[pd.DataFrame, str]:
        """Fetch intraday matched trade data."""
        if page not in (None, 1):
            raise NotImplementedError("VCI intraday không hỗ trợ pagination theo page; hãy dùng last_time để phân trang.")

        if self.asset_type == "index":
            raise ValueError(f"Du lieu intraday khong duoc ho tro cho chi so {self.symbol}.")

        market_status = trading_hours("HOSE")
        if not market_status["is_trading_hour"] and market_status["data_status"] == "preparing":
            raise ValueError(
                f"{market_status['time']}: Du lieu khop lenh khong the truy cap trong thoi gian chuan bi phien moi."
            )

        if page_size and page_size > 30_000:
            logger.warning("Ban dang yeu cau truy xuat qua nhieu du lieu, dieu nay co the gay qua tai.")

        parsed_last_time = convert_time_flexible(last_time, last_time_format)
        url = f"{self.base_url}{_INTRADAY_URL}/LEData/getAll"
        payload = {
            "symbol": self.symbol,
            "limit": page_size,
            "truncTime": parsed_last_time,
        }

        response = send_request(
            url=url,
            headers=self.headers,
            method="POST",
            payload=payload,
            show_log=show_log or self.show_log,
            proxy_list=self.proxy_config.proxy_list,
            proxy_mode=self.proxy_config.proxy_mode,
            request_mode=self.proxy_config.request_mode,
        )

        data = response.get("data", []) if isinstance(response, dict) else response
        if isinstance(data, dict):
            data = data.get("items", [])

        df = intraday_to_df(
            data=data if isinstance(data, list) else [],
            column_map=_INTRADAY_MAP,
            dtype_map=_INTRADAY_DTYPE,
            symbol=self.symbol,
            asset_type=self.asset_type,
            source=self.data_source,
        )

        if not to_df:
            return json.dumps(df.to_dict(orient="records"), ensure_ascii=False, default=str)

        return df

    @optimize_execution("VCI")
    def price_depth(self, show_log: bool = False) -> pd.DataFrame:
        """Fetch order-book depth data for current symbol."""
        url = f"{self.base_url}{_INTRADAY_URL}/LEData/getPriceBoardDetail"
        payload = {"symbol": self.symbol}

        response = send_request(
            url=url,
            headers=self.headers,
            method="POST",
            payload=payload,
            show_log=show_log or self.show_log,
            proxy_list=self.proxy_config.proxy_list,
            proxy_mode=self.proxy_config.proxy_mode,
            request_mode=self.proxy_config.request_mode,
        )

        raw_data: List[dict] = []
        if isinstance(response, dict):
            if isinstance(response.get("data"), list):
                raw_data = response["data"]
            elif isinstance(response.get("data"), dict):
                for value in response["data"].values():
                    if isinstance(value, list) and value and isinstance(value[0], dict):
                        raw_data = value
                        break

        if not raw_data:
            empty_df = pd.DataFrame(columns=list(_PRICE_DEPTH_MAP.values()))
            return normalize_price_columns(
                empty_df,
                columns=["price"],
                source_unit="VND",
                floating=2,
            )

        df = pd.DataFrame(raw_data)
        keep_cols = [col for col in _PRICE_DEPTH_MAP.keys() if col in df.columns]
        if not keep_cols:
            empty_df = pd.DataFrame(columns=list(_PRICE_DEPTH_MAP.values()))
            return normalize_price_columns(
                empty_df,
                columns=["price"],
                source_unit="VND",
                floating=2,
            )

        df = df[keep_cols].rename(columns=_PRICE_DEPTH_MAP)

        for col in ("price", "acc_volume", "acc_buy_volume", "acc_sell_volume", "acc_undefined_volume"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if "price" in df.columns and self.asset_type not in {"index", "derivative"}:
            df = normalize_price_columns(
                df,
                columns=["price"],
                source_unit="VND",
                floating=2,
            )

        return df


from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401

ProviderRegistry.register("quote", "vci", Quote)
