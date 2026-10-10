"""Tương thích pandas: `fillna(None)` không được phụ thuộc version pandas.

Bối cảnh (phát hiện từ CI)
--------------------------
CI chạy trên Python 3.10–3.13 với pandas 2.x, máy local dùng pandas 3.0.2.

`_normalize_company_insider_deals_df` gọi:

    _pick_first_existing(normalized, ["symbol", "ticker"]).fillna(symbol)

Khi `symbol=None` (caller không truyền):

- pandas **2.x**: ``ValueError: Must specify a fill 'value' or 'method'.``
- pandas **3.x**: im lặng bỏ qua → xanh

Nghĩa là test pass ở máy tôi nhưng đỏ trên CI — và nguy hiểm hơn: **hàm chỉ chạy được
trên pandas 3** trong khi `pyproject.toml` khai báo hỗ trợ mọi version.

Hợp đồng: hàm không được phụ thuộc hành vi khác nhau giữa các major version của
pandas. Test chặn bằng cách kiểm tra KHÔNG gọi `fillna` với giá trị rỗng/None.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from vnbroker.common.data import _normalize_company_insider_deals_df

DATA_PY = Path(__file__).resolve().parents[3] / "vnbroker" / "common" / "data.py"


def _frame() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "symbol": ["VCB"],
            "action": ["MUA"],
            "quantity": [1000],
            "custom_col": ["keep_me"],
        }
    )
    df.attrs["source"] = "KBS"
    return df


def test_works_without_symbol_argument() -> None:
    """Gọi không truyền `symbol` không được ném — đây là case CI gặp."""
    out = _normalize_company_insider_deals_df(_frame())
    assert out.loc[0, "action"] == "BUY"
    assert out.loc[0, "custom_col"] == "keep_me"


def test_works_with_symbol_argument() -> None:
    out = _normalize_company_insider_deals_df(_frame(), symbol="VCB")
    assert out.loc[0, "symbol"] == "VCB"


def test_empty_dataframe_path_still_works() -> None:
    out = _normalize_company_insider_deals_df(pd.DataFrame())
    assert out.empty


def test_no_fillna_with_none_or_empty_literal_in_source() -> None:
    """Không được gọi `.fillna(None)` hoặc `.fillna("")`.

    Đây là nguyên nhân gốc: hành vi khác nhau giữa pandas 2.x và 3.x. Chặn ở
    mức source (AST) vì test runtime ở máy local (pandas 3) không bắt được —
    đó chính là lý do lỗi lọt tới CI.
    """
    tree = ast.parse(DATA_PY.read_text(encoding="utf-8"))
    offenders: list[str] = []

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in {"fillna", "ffill", "bfill"}:
            continue
        if not node.args:
            # .fillna() không đối số -> pandas 2.x ném ValueError.
            offenders.append(f"dòng {node.lineno}: .{node.func.attr}() không đối số")
            continue
        for arg in node.args:
            # .fillna(None) / .fillna("") -> pandas 2.x ném ValueError,
            # pandas 3.x bỏ qua. Dạng literal là thứ gây khác biệt.
            if isinstance(arg, ast.Constant) and arg.value in (None, ""):
                offenders.append(
                    f"dòng {node.lineno}: .{node.func.attr}({arg.value!r}) — "
                    f"pandas 2.x ném ValueError, pandas 3.x bỏ qua"
                )

    assert not offenders, (
        "Phụ thuộc hành vi khác nhau giữa các major version của pandas:\n  "
        + "\n  ".join(offenders)
    )


def test_pandas_3_is_declared_but_older_supported() -> None:
    """Nhắc lại ràng buộc: phải chạy được trên pandas 2.x, không chỉ 3.x."""
    pyproject = (
        DATA_PY.parents[2] / "pyproject.toml"
    ).read_text(encoding="utf-8")
    if "pandas" not in pyproject:
        pytest.skip("pyproject không khai báo pandas ràng buộc")
    # Không được pin chặt `pandas>=3` khi code còn dùng API đổi hành vi ở 2.x.
    assert "pandas>=3" not in pyproject, (
        "Không được yêu cầu pandas>=3 trong khi còn hỗ trợ 2.x theo classifiers."
    )