"""
vnbroker.common.retail — Retail facade: giá vàng (SJC/BTMC) + tỷ giá (VCB).

Wiring lại explorer/misc sẵn có với:
  - validate fail-sớm (date YYYY-MM-DD; SJC min 2016-01-02; source hợp lệ),
  - chuẩn hóa output (DataFrame đúng schema + cột/attrs "source", không None),
  - ngữ nghĩa lỗi rõ: exception mạng/wire → RuntimeError prefix nguồn;
    API trả rỗng → DataFrame rỗng (phân biệt "lỗi" vs "không dữ liệu"),
  - chặn print legacy của explorer (redirect stdout → logger.debug).

Scope OUT plan v3.3: không sửa logic wire trong explorer/misc.
"""

from __future__ import annotations

import contextlib
import io
import logging
from datetime import datetime
from typing import Any, List, Optional

import pandas as pd

_logger = logging.getLogger(__name__)

SJC_SOURCE = "SJC"
BTMC_SOURCE = "BTMC"
VCB_SOURCE = "VCB"
_VALID_SOURCES = ("sjc", "btmc")

SJC_MIN_DATE = "2016-01-02"
DATE_FMT = "%Y-%m-%d"

SJC_COLUMNS = ["name", "branch", "buy_price", "sell_price", "date", "source"]
BTMC_COLUMNS = [
    "name",
    "karat",
    "gold_content",
    "buy_price",
    "sell_price",
    "world_price",
    "time",
    "source",
]
VCB_COLUMNS = [
    "currency_code",
    "currency_name",
    "buy_cash",
    "buy_transfer",
    "sell",
    "date",
    "source",
]


class Retail:
    """
    Dữ liệu bán lẻ: vàng SJC/BTMC, tỷ giá Vietcombank.

    Example:
        >>> retail = Vnbroker().retail()
        >>> sjc = retail.gold(source="sjc", date="2026-01-15")
        >>> fx = retail.exchange_rate()
    """

    def __init__(self, show_log: bool = True) -> None:
        self.show_log = show_log
        if not show_log:
            _logger.setLevel(logging.CRITICAL)

    def gold(self, source: str = "sjc", date: Optional[str] = None) -> pd.DataFrame:
        """
        Giá vàng theo nguồn.

        Args:
            source: "sjc" (theo ngày) hoặc "btmc" (hiện tại, bỏ qua date).
            date: "YYYY-MM-DD"; None/"" = hôm nay. SJC yêu cầu >= 2016-01-02.

        Returns:
            DataFrame schema SJC/BTMC + cột "source"; rỗng đúng schema khi
            API không có dữ liệu. Không bao giờ None.

        Raises:
            ValueError: source/date không hợp lệ.
            RuntimeError: lỗi mạng/wire (prefix "SJC: "/BTMC: ").
        """
        key = (source or "").strip().lower()
        if key not in _VALID_SOURCES:
            raise ValueError(
                f"source phải là một trong {list(_VALID_SOURCES)}. Nhận: {source!r}"
            )
        if key == "sjc":
            day = _validate_date(date, "date")
            if day < SJC_MIN_DATE:
                raise ValueError(
                    f"SJC chỉ có dữ liệu từ {SJC_MIN_DATE} trở đi. Nhận: {day}"
                )
            from vnbroker.explorer.misc.gold_price import sjc_gold_price

            try:
                with _suppress_print():
                    result = sjc_gold_price(date=day)
            except Exception as exc:
                raise RuntimeError(f"SJC: lỗi truy xuất giá vàng: {exc}") from exc
            return _normalize(result, SJC_COLUMNS, SJC_SOURCE)
        # btmc: bỏ qua date (documented)
        from vnbroker.explorer.misc.gold_price import btmc_goldprice

        try:
            with _suppress_print():
                result = btmc_goldprice()
        except KeyError as exc:
            # Explorer sort_values KeyError khi DataList.Data rỗng:
            # coi như API trả rỗng → DataFrame rỗng (hợp đồng §2 plan).
            _logger.debug("BTMC: dữ liệu rỗng (%s).", exc)
            return _normalize(None, BTMC_COLUMNS, BTMC_SOURCE)
        except Exception as exc:
            raise RuntimeError(f"BTMC: lỗi truy xuất giá vàng: {exc}") from exc
        return _normalize(result, BTMC_COLUMNS, BTMC_SOURCE)

    def exchange_rate(self, date: Optional[str] = None) -> pd.DataFrame:
        """
        Tỷ giá Vietcombank theo ngày.

        Args:
            date: "YYYY-MM-DD"; None/"" = hôm nay.

        Returns:
            DataFrame schema VCB + cột "source"; rỗng đúng schema khi lỗi/API rỗng.

        Raises:
            ValueError: date sai format.
            RuntimeError: lỗi mạng/wire (prefix "VCB: ").
        """
        day = _validate_date(date, "date")
        from vnbroker.explorer.misc.exchange_rate import vcb_exchange_rate

        try:
            with _suppress_print():
                result = vcb_exchange_rate(date=day)
        except Exception as exc:
            raise RuntimeError(f"VCB: lỗi truy xuất tỷ giá: {exc}") from exc
        return _normalize(result, VCB_COLUMNS, VCB_SOURCE)


def _validate_date(value: Optional[str], name: str) -> str:
    """None/"" → hôm nay; else strict YYYY-MM-DD, sai → ValueError."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return datetime.now().strftime(DATE_FMT)
    text = value.strip()
    try:
        datetime.strptime(text, DATE_FMT)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} phải định dạng YYYY-MM-DD. Nhận: {value!r}") from exc
    return text


def _normalize(result: Any, columns: List[str], source: str) -> pd.DataFrame:
    """Explorer None/rỗng → DF rỗng đúng schema; ngược lại ép schema + source."""
    if result is None:
        df = pd.DataFrame(columns=columns)
    elif isinstance(result, pd.DataFrame):
        df = result.copy() if not result.empty else pd.DataFrame(columns=columns)
        if not df.empty:
            for col in columns:
                if col not in df.columns and col != "source":
                    df[col] = pd.NA
            df = df[[c for c in columns if c in df.columns]]
    else:
        df = pd.DataFrame(columns=columns)
    df["source"] = source
    df.attrs["source"] = source
    ordered = [c for c in columns if c in df.columns]
    return df[ordered]


@contextlib.contextmanager
def _suppress_print() -> Any:
    """
    Chặn print legacy của explorer/misc (Scope OUT: không sửa explorer).
    Output bị chặn được chuyển sang logger.debug để không mất thông tin debug.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        yield
    captured = buf.getvalue()
    if captured.strip():
        _logger.debug("explorer output suppressed: %s", captured.strip())
