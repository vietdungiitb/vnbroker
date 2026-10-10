"""Centralized normalization for all provider results.

This module is the SINGLE enforcement point of the tier-1 data contract. Every
public path that hands a provider DataFrame to the user goes through
:class:`Normalizer`, so a provider added tomorrow complies without being edited.

Two defects made the contract invisible to users before this module was the
only implementation; both are recorded here because they are easy to
reintroduce:

1. **Timezone *resolution*.** ``Asia/Ho_Chi_Minh`` tz-awareness alone is not
   enough. pandas 3 keeps whatever unit the source used, so KBS yields
   ``datetime64[us, Asia/Ho_Chi_Minh]`` and VCI yields
   ``datetime64[s, Asia/Ho_Chi_Minh]``. Concatenating two *DataFrames* with
   mismatched units produces ``dtype=object`` — every downstream time
   operation silently breaks and no exception is raised. Measured live on
   ``TCB`` intraday at ``9d5db1d``.

2. **``match_type`` vocabulary.** ``process_match_types``
   (``core/utils/transform.py``) already maps every provider's spelling to
   ``Buy``/``Sell``/``unknown``, but ``explorer/kbs/quote.py`` lower-cased the
   result on the very next line, so ``df[df.match_type == "Buy"]`` returned 0
   rows from KBS and 67 from VCI for the same session.

Normalization never mutates the provider's frame (asserted by
``tests/contract/test_layer_normalization.py::test_data_layer_preserves_columns_and_does_not_mutate_input``).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytz

#: Storage unit every normalized ``time`` column is cast to. One unit for all
#: providers is what makes ``pd.concat`` produce a datetime instead of object.
CANONICAL_TIME_UNIT = "ns"

#: Biên của `datetime64[ns]`. Ngoài khoảng này `as_unit` ném
#: `OutOfBoundsDatetime`; những dòng đó bị đổi thành `NaT` rồi loại.
_NS_MIN = "1677-09-21 00:00:00"
_NS_MAX = "2262-04-11 23:47:16"


def _canonical_tz() -> Any:
    """Timezone chuẩn của thị trường Việt Nam (giờ giao dịch)."""
    return pytz.timezone("Asia/Ho_Chi_Minh")


def _to_canonical_unit(series: pd.Series) -> pd.Series:
    """Ép cột ``time`` về đơn vị lưu trữ ``CANONICAL_TIME_UNIT``.

    pandas >= 2 giữ nguyên đơn vị nguồn (``[s]``, ``ms``, ``[us]``, ``[ns]``) trong
    ``Series.dtype``. Hai frame đều tz-aware nhưng khác đơn vị không thể
    ``concat`` thành datetime: ``DataFrame.concat`` không tìm thấy dtype chung
    nên rơi về ``object``.

    Timestamp nằm ngoài phạm vi của ``ns`` (ví dụ năm 3000) không nâng được và
    sẽ làm hỏng chính cái hợp đồng này. Những dòng đó thành ``NaT`` để bị điều
    kiện lọc ở ``_normalize_frame`` loại bỏ — đúng như xử lý timestamp không
    parse được. **Không** trả nguyên series: làm vậy là để lọt ra một đơn vị
    lệch và tái tạo đúng lỗi ta đang sửa.
    """
    try:
        return series.dt.as_unit(CANONICAL_TIME_UNIT)
    except (AttributeError, TypeError, ValueError, OverflowError):
        pass

    # Biên của datetime64[ns]; ngoài khoảng này `as_unit` ném
    # OutOfBoundsDatetime (đo 2026-10-10 với năm 3000). Dựng biên ở UTC:
    # so sánh Timestamp giữa hai múi giờ khác nhau vẫn hợp lệ, còn
    # `tz_localize` mốc năm 1677 vào giờ VN sẽ vướng quy tắc LMT/DST của pytz.
    low = pd.Timestamp(_NS_MIN, tz="UTC")
    high = pd.Timestamp(_NS_MAX, tz="UTC")
    masked = series.mask((series < low) | (series > high))
    try:
        return masked.dt.as_unit(CANONICAL_TIME_UNIT)
    except (AttributeError, TypeError, ValueError, OverflowError):
        # pandas >= 2 luôn có `.dt.as_unit`, nên nhánh này gần như không tới.
        # Trả `masked` chứ KHÔNG trả `series`: `masked` đã loại dòng vô dụng,
        # còn `series` thì vẫn mang đơn vị lệch và phá hỏng `concat`.
        return masked


def _to_canonical_tz(series: pd.Series) -> pd.Series:
    """Chuẩn hoá cột ``time`` thành tz-aware Asia/Ho_Chi_Minh, một đơn vị duy nhất.

    Naive được hiểu là **giờ Việt Nam**, không phải UTC: provider trả
    ``'2024-01-02 09:00'`` nghĩa là 09:00 VN. Localize UTC rồi convert sang VN
    sẽ thành 16:00 — sai 7 tiổng mà vẫn là timestamp hợp lệ, nên rất khó phát
    hiện.

    Frame đã tz-aware nhưng ở **vùng khác** thì ``tz_convert``, không
    ``tz_localize``: đây là cùng một *thời điểm* nên phải giữ nguyên mốc thời
    gian, chỉ đổi nhãn múi giờ. Để y như cũ thì frame UTC lọt xuống dưới với
    ``datetime64[ns, UTC]`` — trái hợp đồng "tz-aware Asia/Ho_Chi_Minh" và
    ``concat`` với frame Việt Nam lại ra ``object``.
    """
    tz = getattr(series.dt, "tz", None)
    if tz is None:
        series = series.dt.tz_localize(_canonical_tz())
    elif str(tz) != str(_canonical_tz()):
        series = series.dt.tz_convert(_canonical_tz())
    return _to_canonical_unit(series)


def _parse_boundary(value: Any, *, inclusive_end: bool) -> pd.Timestamp | None:
    """Parse ngày biên của lời gọi. Trả None nếu thiếu/không parse được."""
    if value is None or value == "":
        return None
    try:
        ts = pd.to_datetime(value)
    except (ValueError, TypeError):
        return None
    if pd.isna(ts):
        return None
    if getattr(ts, "tzinfo", None) is None:
        ts = ts.tz_localize(_canonical_tz())
    if inclusive_end and ts.hour == 0 and ts.minute == 0 and ts.second == 0:
        # Người dùng truyền '2024-01-31' nghĩa là hết ngày đó, không phải 00:00.
        ts = ts + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return ts


def _normalize_match_type(df: pd.DataFrame) -> pd.DataFrame:
    """Đưa ``match_type`` về đúng tập giá trị ``{Buy, Sell, ATO, ATC, unknown}``.

    Dùng lại bảng mapping của ``process_match_types`` thay vì viết bảng thứ
    hai. KHÔNG chạy lại heuristic ATO/ATC ở tầng này: nó cần ``time.dt``,
    thêm cột ``date`` rồi ``groupby.apply`` — đó là phán đoán tầng provider và
    KBS/VCI đã chạy sẵn. Ở đây chỉ bảo đảm **từ vựng**.
    """
    if "match_type" not in df.columns:
        return df

    # Import trong hàm: `core.utils.transform` nặng hơn và import ở module
    # scope sẽ tạo vòng với `core.utils.__init__`.
    from vnbroker.core.utils.transform import _MATCH_TYPE_MAP, _MATCH_TYPE_UNKNOWN

    raw = df["match_type"]
    key = raw.astype("string").str.strip().str.upper()
    canonical = key.map(_MATCH_TYPE_MAP).fillna(_MATCH_TYPE_UNKNOWN)

    # `process_match_types` đã gán ATO/ATC cho giao dịch định kỳ; giữ nguyên
    # hai nhãn đó thay vì hạ về `unknown` khi chạy qua tầng chuẩn hoá.
    canonical = canonical.mask(
        key.isin({"ATO", "ATC"}), key
    )
    # `assign` trả về frame MỚI: hàm này không được mutate frame của người gọi.
    # Trước đây nó gán thẳng `df["match_type"] = ...` và sửa tại chỗ — vô hại
    # vì `_normalize_frame` đã copy trước, nhưng docstring của module hứa "không
    # bao giờ mutate" thì hàm private này là ngoại lệ chưa được nói ra.
    return df.assign(match_type=canonical)


class Normalizer:
    """Centralized normalization for all provider results."""

    @staticmethod
    def normalize_history(result: Any, start: Any = None, end: Any = None) -> Any:
        """Normalize history result (DataFrame or list[DataFrame])."""
        if isinstance(result, list):
            return [Normalizer._normalize_frame(f, start, end) for f in result]
        return Normalizer._normalize_frame(result, start, end)

    @staticmethod
    def normalize_intraday(result: Any) -> Any:
        """Normalize intraday result (tz + đơn vị + ``match_type``, không lọc biên).

        Intraday trả dữ liệu trong phiên; lọc theo ngày là việc của provider,
        nên không truyền ``start``/``end``.
        """
        return Normalizer._normalize_frame(result, None, None)

    @staticmethod
    def _normalize_frame(df: pd.DataFrame, start: Any, end: Any) -> pd.DataFrame:
        """Normalize a single DataFrame: tz-aware, one unit, vocabulary, bounds, sort."""
        if not isinstance(df, pd.DataFrame) or "time" not in df.columns:
            return df

        # Copy to avoid mutation
        df = df.copy()

        # Convert time to Asia/Ho_Chi_Minh (tz-aware) AND to one storage unit.
        df["time"] = _to_canonical_tz(pd.to_datetime(df["time"], errors="coerce"))
        # Drop rows with unparseable timestamps
        df = df[df["time"].notna()]

        # Same vocabulary from every provider
        df = _normalize_match_type(df)

        # Filter by start/end boundaries
        lo = _parse_boundary(start, inclusive_end=False)
        if lo is not None:
            df = df[df["time"] >= lo]

        hi = _parse_boundary(end, inclusive_end=True)
        if hi is not None:
            df = df[df["time"] <= hi]

        # Sort by time and reset index
        return df.sort_values("time").reset_index(drop=True)
