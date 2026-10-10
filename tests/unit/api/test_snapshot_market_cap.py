"""`market_cap` phải là **vốn hoá thật**, không phải con số nhân nhầm 1000 lần.

Lỗi (đo live 2026-10-10, KBS, mã VCB, `dev @ 9d5db1d`)
------------------------------------------------------
`_compute_market_cap` dùng ``multiplier = 1_000`` khi ``price_unit is None``,
với docstring khẳng định *"None → giá đang ở nghìn VND"*. Đo thì ra ngược lại:

    price_board(price_unit=None) -> attrs['price_unit']='VND', close_price=56700
    price_board(price_unit='VND') -> attrs['price_unit']='VND', close_price=56700

Hai lệnh cho **cùng một con số**. ``None`` chỉ có nghĩa là *"không ép đơn vị"*,
nên provider rơi về mặc định ``vnbroker_PRICE_UNIT`` (= ``VND``). Hệ quả:

    _compute_market_cap(price_unit=None) -> 473 766 777.83  tỷ
    _compute_market_cap(price_unit='VND') ->     473 766.78  tỷ
    56700 x 8 355 675 094 / 1e9          ->     473 766.78  tỷ   ← đúng

VCB vốn hoá ~474 nghìn tỷ VND. Sai 1000 lần mà **vẫn là một con số hợp lệ**,
nên rất khó phát hiện bằng mắt — đó là loại lỗi đắt nhất.

Cách sửa: đọc ``df.attrs['price_unit']`` — nhãn **chính provider** dán lúc
chuẩn hoá giá — thay vì suy từ tham số của caller.
"""

from __future__ import annotations

import pandas as pd
import pytest

from vnbroker.api.snapshot import MarketSnapshot


def _price_board(unit: str = "VND") -> pd.DataFrame:
    """Bảng giá có hình dạng như `price_board(get_all=True)` trả về."""
    df = pd.DataFrame(
        {
            "symbol": ["VCB", "TCB"],
            # Giá VND thật, đo từ KBS ngày 2026-10-10
            "close_price": [56700.0, 32350.0],
            "reference_price": [56600.0, 32500.0],
            "listed_shares": [8_355_675_094, 7_091_829_277],
            "volume_accumulated": [3_049_500, 1_000_000],
        }
    )
    df.attrs["price_unit"] = unit
    return df


def _truth(board: pd.DataFrame) -> pd.Series:
    """Vốn hoá chuẩn, tính thẳng từ VND."""
    return (
        pd.to_numeric(board["close_price"], errors="coerce")
        * pd.to_numeric(board["listed_shares"], errors="coerce")
        / 1e9
    ).round(2)


@pytest.mark.parametrize("unit_arg", [None, "VND"])
def test_market_cap_matches_hand_computed_value(unit_arg):
    """AC-3: `price_unit=None` và `"VND"` phải cho **cùng** kết quả đúng.

    ĐỎ trước ở `unit_arg=None`: lệch 99 899.9995%.
    """
    board = _price_board()
    out = MarketSnapshot()._compute_market_cap(board.copy(), unit_arg)
    truth = _truth(board)

    rel = ((out["market_cap"] - truth).abs() / truth * 100).max()
    assert rel < 0.01, (
        f"price_unit={unit_arg!r}: market_cap lech {rel:.4f}% so voi "
        f"close_price x listed_shares / 1e9.\n"
        f"  got   = {out['market_cap'].tolist()}\n"
        f"  truth = {truth.tolist()}"
    )


def test_market_cap_is_invariant_to_the_requested_price_unit():
    """Bất biến quan trọng nhất: đổi đơn vị **hiển thị** không được đổi vốn hoá.

    `market_cap_unit` luôn là `"tỷ VND"`, nên giá trị vật lý phải giống nhau dù
    caller xin giá theo VND hay nghìn VND. Đây là bất biến mà một test
    so-với-truth đơn lẻ không bắt được: cả hai nhánh có thể cùng sai.
    """
    snap = MarketSnapshot()
    results = {}
    for unit_arg in (None, "VND", "THOUSAND_VND"):
        board = _price_board("THOUSAND_VND" if unit_arg == "THOUSAND_VND" else "VND")
        # Đơn vị thật phải bám theo frame, nên phải sửa frame chứ không sửa tham số
        if unit_arg == "THOUSAND_VND":
            board["close_price"] = board["close_price"] / 1000.0
        results[unit_arg] = snap._compute_market_cap(board, unit_arg)["market_cap"]

    base = results[None]
    for unit_arg, series in results.items():
        rel = ((series - base).abs() / base * 100).max()
        assert rel < 0.01, (
            f"market_cap lech {rel:.4f}% khi price_unit={unit_arg!r} so voi None. "
            f"market_cap_unit la 'ty VND' nen gia tri vat ly phai giong nhau."
        )


def test_thousand_vnd_frame_gets_the_1000x_multiplier():
    """Khi frame **thật sự** ở nghìn VND thì phải nhân 1000 để về VND.

    Nhánh này là lý do công thức cũ tồn tại; nó chỉ sai vì áp nhầm vào frame
    đang ở VND.
    """
    board = _price_board("THOUSAND_VND")
    board["close_price"] = board["close_price"] / 1000.0
    out = MarketSnapshot()._compute_market_cap(board, "THOUSAND_VND")
    truth = _truth(_price_board("VND"))
    assert ((out["market_cap"] - truth).abs() / truth * 100).max() < 0.01


def test_effective_unit_reads_the_frame_not_the_argument():
    """Đơn vị lấy từ `attrs`, không từ tham số — và mặc định là VND."""
    snap = MarketSnapshot()
    assert snap._effective_price_unit(_price_board("VND")) == "VND"
    assert snap._effective_price_unit(_price_board("THOUSAND_VND")) == "THOUSAND_VND"
    assert snap._effective_price_unit(_price_board("K")) == "THOUSAND_VND"
    assert snap._effective_price_unit(_price_board("nghìn VND")) == "THOUSAND_VND"
    # Không có nhãn => VND, vì đó là mặc định thật của thư viện
    # (`transform._resolve_target_price_unit`), chọn ngược lại là phóng đại 1000 lần.
    bare = _price_board()
    bare.attrs.pop("price_unit", None)
    assert snap._effective_price_unit(bare) == "VND"


def test_missing_columns_do_not_raise():
    """Thiếu cột thì ghi `None` + cảnh báo, không ném lỗi lên người dùng."""
    board = pd.DataFrame({"symbol": ["VCB"], "close_price": [56700.0]})
    out = MarketSnapshot()._compute_market_cap(board, None)
    assert out["market_cap"].isna().all()


def test_listed_shares_as_string_is_coerced():
    """Provider trả `listed_shares` kiểu chuỗi — phải ép được, không ra NaN."""
    board = _price_board()
    board["listed_shares"] = board["listed_shares"].astype(str)
    out = MarketSnapshot()._compute_market_cap(board, None)
    assert out["market_cap"].notna().all()
    assert ((out["market_cap"] - _truth(_price_board())).abs()).max() < 0.01
