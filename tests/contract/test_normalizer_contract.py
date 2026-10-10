"""Hợp đồng chuẩn hoá tầng 1 — đo bằng dữ liệu provider thật, không gọi mạng.

Ba lỗi dưới đây đều **đang xảy ra với người dùng**, đều im lặng (không ném
lỗi), và đều đo được trên `TCB` ngày 2026-10-10 ở `dev @ 9d5db1d`:

1. **Đơn vị lưu trữ của ``time``.** pandas >= 2 giữ nguyên đơn vị nguồn:
   KBS trả ``datetime64[us, Asia/Ho_Chi_Minh]``, VCI trả
   ``datetime64[s, Asia/Ho_Chi_Minh]``. ``DataFrame.concat`` hai frame lệch
   đơn vị rơi về ``dtype object`` — mọi phép tính thời gian phía dưới hỏng mà
   không ném lỗi. (Chỉ tz-aware chưa đủ.)

2. **Từ vựng ``match_type``.** ``process_match_types`` đã gom mọi cách viết
   về ``Buy``/``Sell``/``unknown``, nhưng ``explorer/kbs/quote.py`` gọi
   ``.str.lower()`` ngay dòng sau và phá lại hợp đồng: KBS ``buy/sell/atc`` vs
   VCI ``Buy/Sell/ATC``. Đo: ``df[df.match_type == "Buy"]`` → KBS **0** dòng,
   VCI **67** dòng, cùng một phiên giao dịch.

3. **Hai bản chuẩn hoá trùng nhau.** ``core/utils/normalizer.py`` và
   ``common/data.py`` từng có một bản, và ``api/quote.py`` không đi qua bản nào.

Các test ở đây dựng frame **đúng hình dạng provider trả về** (đơn vị + casing
khác nhau) rồi chạy hàm thật. Không kiểm hình thức.
"""

from __future__ import annotations

import pandas as pd
import pytest

from vnbroker.core.utils.normalizer import CANONICAL_TIME_UNIT, Normalizer

TZ = "Asia/Ho_Chi_Minh"


def _intraday_like(unit: str, match_values) -> pd.DataFrame:
    """Frame intraday có hình dạng như provider tương ứng.

    KBS: ``datetime64[us, Asia/Ho_Chi_Minh]`` + ``buy/sell/atc``.
    VCI: ``datetime64[s, Asia/Ho_Chi_Minh]`` + ``Buy/Sell/ATC``.

    ``match_values`` nhận một chuỗi (phát ra cho mọi dòng) hoặc một danh sách
    khớp số dòng.
    """
    base = pd.to_datetime(
        ["2026-09-01 09:00:00", "2026-09-01 09:01:00", "2026-09-01 09:02:00"]
    )
    aware = base.tz_localize(TZ).astype(f"datetime64[{unit}, {TZ}]")
    n = len(aware)
    values = (
        [match_values] * n
        if isinstance(match_values, str)
        else list(match_values)
    )
    if len(values) != n:
        raise ValueError(f"can {len(values)} gia tri cho {n} dong")
    return pd.DataFrame(
        {
            "time": aware,
            "price": [56_700.0, 56_750.0, 56_800.0],
            "volume": [100, 200, 300],
            "match_type": values,
        }
    )


KBS_LIKE = _intraday_like("us", ["buy", "sell", "buy"])
VCI_LIKE = _intraday_like("s", ["Buy", "Sell", "Buy"])

# ---------------------------------------------------------------- đơn vị time


def test_both_providers_land_on_one_storage_unit():
    """AC-2: cùng một đơn vị lưu trữ, không phải một đơn vị mỗi provider.

    **Đây là bằng chứng đỏ-trước.** Trên `9d5db1d`, chạy đúng hai lệnh này:

        _normalize_quote_result(frame("us", ...))["time"].dtype
            -> datetime64[us,  Asia/Ho_Chi_Minh]
        _normalize_quote_result(frame("s",  ...))["time"].dtype
            -> datetime64[s,   Asia/Ho_Chi_Minh]

    và ghép hai frame đó lại trên dữ liệu thật cho `dtype=object`.
    """
    kbs = Normalizer.normalize_intraday(KBS_LIKE)
    vci = Normalizer.normalize_intraday(VCI_LIKE)

    assert str(kbs["time"].dtype) == f"datetime64[{CANONICAL_TIME_UNIT}, {TZ}]"
    assert str(vci["time"].dtype) == f"datetime64[{CANONICAL_TIME_UNIT}, {TZ}]", (
        f"VCI phai ra cung don vi voi KBS, thuc te {vci['time'].dtype}. "
        "Neu don vi lech, DataFrame.concat se ra object dtype."
    )


def test_concat_across_providers_is_a_datetime_not_object():
    """Hệ quả người dùng thấy: `pd.concat` phải ra datetime.

    ⚠ **Test chốt hồi quy, KHÔNG phải bằng chứng đỏ-trước.** Chạy trên bản cũ
    (`9d5db1d`) test này **XANH**: hai frame tổng hợp `[us]` + `[s]` vào
    `pd.concat` ra `[us]`, không phải `object`. Bằng chứng đỏ-trước cho lỗi
    này là `test_both_providers_land_on_one_storage_unit`.

    Đo được trên dữ liệu THẬT ở `9d5db1d` thì khác: `pd.concat` hai frame
    intraday thật của KBS và VCI ra `object`. Ta chưa cô lập được điều kiện nào
    bên cạnh đơn vị kích hoạt nó (xem `docs/REPORT_FINAL_TIER1_WAVE12.md` §
    "Câu hỏi mở"). Vì vậy khẳng định ở đây là hành vi **mong muốn**, và test giữ
    nó lại để đổi tên dtype trong tương lai phải cố ý mới đi qua được.
    """
    vci_other = _intraday_like("s", ["Sell", "Buy", "Sell"]).assign(
        time=lambda d: d["time"] + pd.Timedelta(days=1)
    )
    merged = pd.concat(
        [
            Normalizer.normalize_intraday(KBS_LIKE),
            Normalizer.normalize_intraday(vci_other),
        ],
        ignore_index=True,
    )
    assert merged["time"].dtype != object, (
        "pd.concat giua KBS va VCI ra dtype=object — moi phep tinh thoi gian "
        "phia duoi deu hong ma khong nem loi."
    )
    assert str(merged["time"].dtype) == f"datetime64[{CANONICAL_TIME_UNIT}, {TZ}]"
    assert len(merged) == 6
    assert merged["time"].is_monotonic_increasing


def test_already_canonical_frame_is_left_at_the_same_unit():
    """Không hồi quy: frame đã đúng không bị đổi đơn vị."""
    out = Normalizer.normalize_intraday(VCI_LIKE)
    assert out["time"].iloc[0] == VCI_LIKE["time"].iloc[0]


# ---------------------------------------------------------------- match_type


def test_match_type_vocabulary_is_identical_across_providers():
    """AC-1: cùng một tập giá trị, không phân biệt provider."""
    kbs = Normalizer.normalize_intraday(KBS_LIKE)
    vci = Normalizer.normalize_intraday(VCI_LIKE)

    assert set(kbs["match_type"]) == set(vci["match_type"]) == {"Buy", "Sell"}


def test_filtering_on_buy_returns_rows_from_both_providers():
    """AC-1 ở dạng người dùng viết: `df[df.match_type == "Buy"]`.

    Bằng chứng đỏ-trước: KBS trả **0** dòng ở `9d5db1d`. Assert "0 dòng" là
    bằng chứng vô giá trị — nó xanh cả trước và sau lỗi.
    """
    kbs = Normalizer.normalize_intraday(KBS_LIKE)
    vci = Normalizer.normalize_intraday(VCI_LIKE)

    assert len(kbs[kbs["match_type"] == "Buy"]) == 2
    assert len(vci[vci["match_type"] == "Buy"]) == 2

def test_lower_and_upper_case_spellings_meet():
    """Cách viết khác nhau của cùng một nghĩa phải gặp nhau ở một giá trị."""
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-09-01 09:00:00"]).tz_localize(TZ),
            "match_type": ["b"],
        }
    )
    out = Normalizer.normalize_intraday(df)
    assert out["match_type"].iloc[0] == "Buy"


def test_ato_atc_labels_survive_normalization():
    """`process_match_types` gán ATO/ATC cho giao dịch định kỳ.

    Chạy qua tầng chuẩn hoá KHÔNG được hạ chúng về `unknown` — nếu không,
    người dùng mất thông tin giao dịch định kỳ mà không có cảnh báo.
    """
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(
                ["2026-09-01 09:14:00", "2026-09-01 14:45:00"]
            ).tz_localize(TZ),
            "match_type": ["ATO", "ATC"],
        }
    )
    out = Normalizer.normalize_intraday(df)
    assert out["match_type"].tolist() == ["ATO", "ATC"]


def test_missing_match_type_becomes_unknown_not_nan():
    """NaN làm `df[df.match_type == "Buy"]` cho kết quả khác nhau giữa provider."""
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-09-01 09:00:00"]).tz_localize(TZ),
            "match_type": [None],
        }
    )
    out = Normalizer.normalize_intraday(df)
    assert not out["match_type"].isna().any()
    assert out["match_type"].iloc[0] == "unknown"


def test_frame_without_match_type_column_is_untouched():
    """`history` không có `match_type` — không được tự thêm cột."""
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-09-01"]).tz_localize(TZ),
            "close": [56_700.0],
        }
    )
    out = Normalizer.normalize_history(df, "2026-09-01", "2026-09-30")
    assert list(out.columns) == ["time", "close"]


# ------------------------------------------------------- không mutate + biên


@pytest.mark.parametrize("frame_name", ["history", "intraday"])
def test_provider_frame_is_never_mutated(frame_name):
    """Frame của provider không được đổi trong lúc chuẩn hoá."""
    df = _intraday_like("us", "buy")
    df.attrs["symbol"] = "TCB"
    snapshot = df.copy(deep=True)

    if frame_name == "history":
        Normalizer.normalize_history(df, "2026-09-01", "2026-09-30")
    else:
        Normalizer.normalize_intraday(df)

    assert df["time"].dtype == snapshot["time"].dtype
    assert df["match_type"].tolist() == snapshot["match_type"].tolist()
    assert df.attrs.get("symbol") == "TCB"


def test_normalizer_is_the_single_implementation():
    """W2.5: `common.data._normalize_quote_result` phải UỎY THAC, không viết lại.

    Trước đây có hai bản trùng nhau và chúng có thể trôi lệch nhau mà không
    gate nào bắt. Test này khoá hành vi ủy thác bằng cách kiểm chứng **kết quả**,
    không kiểm tra tên hàm — một cách kiểm hình thức sẽ xanh kể cả khi ai đó
    viết lại bản thứ hai.
    """
    from vnbroker.common.data import _normalize_quote_result

    out = _normalize_quote_result(KBS_LIKE)
    assert str(out["time"].dtype) == f"datetime64[{CANONICAL_TIME_UNIT}, {TZ}]"
    assert out["match_type"].tolist() == ["Buy", "Sell", "Buy"]


def test_non_dataframe_input_passes_through():
    """Provider trả kiểu khác (dict/list) thì không được ném lỗi lên người dùng."""
    payload = {"a": 1}
    assert Normalizer.normalize_history(payload, None, None) is payload
    assert Normalizer.normalize_intraday([1, 2, 3]) == [1, 2, 3]


def test_list_of_frames_is_normalized_elementwise():
    """`fetch_multiple` trả list frame — list cũng phải tuân thủ hợp đồng."""
    out = Normalizer.normalize_history([KBS_LIKE, VCI_LIKE], None, None)
    assert isinstance(out, list) and len(out) == 2
    for frame in out:
        assert str(frame["time"].dtype) == f"datetime64[{CANONICAL_TIME_UNIT}, {TZ}]"
