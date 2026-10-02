"""Hợp đồng `match_type` — mọi provider phải trả CÙNG một tập giá trị.

Vấn đề (S2-B08)
---------------
`process_match_types` chỉ có nhánh cho `VCI`/`MAS`/`TCBS`/`KBS`, mỗi provider một
cách viết khác nhau:

- VCI:  ``'b'`` → ``'Buy'``  (chữ thường)
- TCBS: ``'BU'`` → ``'Buy'``
- KBS:  ``'B'``  → ``'Buy'``
- **DNSE / SSI: không có nhánh nào** → giữ nguyên giá trị provider trả về.

Hệ quả: cùng một câu lệnh ``df[df.match_type == "Buy"]`` cho kết quả khác nhau
tuỳ provider, và sai **âm thầm** — không có lỗi nào được ném. Đây đúng là lớp
lỗi đã xử lý ở GĐ2 (schema lệch làm hỏng phép tính phía downstream).

Hợp đồng
--------
1. Tập giá trị chuẩn: ``Buy`` / ``Sell`` / ``unknown``.
2. Mọi biến thể casing/abbreviation của provider đều về một giá trị chuẩn.
3. Provider **chưa** có nhánh riêng vẫn được chuẩn hoá (không phụ thuộc source).
"""

from __future__ import annotations

import pandas as pd
import pytest

from vnbroker.core.utils.transform import process_match_types

CANONICAL = {"Buy", "Sell", "unknown"}


def _frame(values: list, *, source: str, asset_type: str = "stock") -> pd.DataFrame:
    df = pd.DataFrame(
        {
            # base + giờ tăng dần; KHÔNG dùng f"{i+1}" trong ngày vì >9 ngày
            # sẽ ra "2024-01-010" (sai định dạng).
            "time": pd.date_range("2024-01-01 09:10:00", periods=len(values), freq="1h"),
            "match_type": values,
        }
    )
    return process_match_types(df, asset_type, source)


# ---------------------------------------------------- mapping từng provider


@pytest.mark.parametrize("raw,expected", [
    # VCI dùng chữ thường
    ("b", "Buy"), ("s", "Sell"), ("Buy", "Buy"), ("Sell", "Sell"),
    # TCBS dùng 2 ký tự
    ("BU", "Buy"), ("SD", "Sell"),
    # KBS dùng 1 chữ hoa
    ("B", "Buy"), ("S", "Sell"),
    # các biến thể khác gặp thực tế
    ("BUY", "Buy"), ("SELL", "Sell"), ("buy", "Buy"), ("sell", "Sell"),
    ("NB", "Buy"), ("NS", "Sell"), ("n", "Buy"), ("ns", "Sell"),
    ("A", "unknown"), ("D", "unknown"), ("", "unknown"), (None, "unknown"),
])
def test_every_variant_maps_to_canonical(raw, expected) -> None:
    """Mọi biến thể của match_type đều về đúng giá trị chuẩn."""
    df = _frame([raw], source="TCBS")
    assert df["match_type"].iloc[0] == expected


@pytest.mark.parametrize("source", ["VCI", "KBS", "TCBS", "DNSE", "SSI", "MAS"])
def test_result_only_contains_canonical_values(source: str) -> None:
    """Sau chuẩn hoá, chỉ còn Buy/Sell/unknown — không còn giá trị lạ."""
    df = _frame(["b", "s", "B", "S", "BU", "SD", "nb", "NS", "X", "", None], source=source)
    observed = set(df["match_type"].dropna().unique())
    unknown = observed - CANONICAL
    assert not unknown, (
        f"{source}: còn giá trị ngoài tập chuẩn {sorted(CANONICAL)}: "
        f"{sorted(unknown)}"
    )


@pytest.mark.parametrize("source", ["DNSE", "SSI"])
def test_provider_without_dedicated_branch_is_normalized(source: str) -> None:
    """Provider KHÔNG có nhánh riêng vẫn phải được chuẩn hoá.

    Đây chính là lỗi đang tồn tại: DNSE/SSI không có nhánh trong
    `process_match_types`, nên `match_type` trả về nguyên giá trị provider.
    """
    df = _frame(["b", "s", "BU", "SD"], source=source)
    assert set(df["match_type"].unique()) <= {"Buy", "Sell"}


def test_missing_values_become_unknown_not_nan() -> None:
    """Thiếu dữ liệu phải thành `unknown`, không để NaN lọt ra ngoài.

    NaN là nguyên nhân khiến `df[df.match_type == "Buy"]` cho kết quả khác nhau
    giữa provider — và `.unique()` trả cả NaN.
    """
    df = _frame(["b", None, "s", ""], source="VCI")
    assert not df["match_type"].isna().any(), (
        f"còn NaN trong match_type: {df['match_type'].tolist()}"
    )


def test_column_does_not_mutate_caller_frame() -> None:
    """Không được mutate DataFrame gốc của provider."""
    original = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-02 09:15:00"]),
            "match_type": ["b"],
        }
    )
    snapshot = original.copy()
    process_match_types(original, "stock", "VCI")

    assert original["match_type"].tolist() == snapshot["match_type"].tolist()
    assert original["time"].dtype == snapshot["time"].dtype


def test_empty_frame_is_safe() -> None:
    df = _frame([], source="VCI")
    assert df.empty