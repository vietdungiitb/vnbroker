"""
R2: InstrumentType (lowercase, str-Enum) + get_asset_type dedup. Behavior-locked.
"""

from __future__ import annotations

import pytest

from vnbroker.core.utils.parser import InstrumentType, get_asset_type

pytestmark = pytest.mark.core


class TestMembers:
    def test_exact_five_members(self) -> None:
        assert [(m.name, m.value) for m in InstrumentType] == [
            ("STOCK", "stock"),
            ("INDEX", "index"),
            ("DERIVATIVE", "derivative"),
            ("BOND", "bond"),
            ("COVERED_WARRANT", "coveredWarr"),
        ]

    def test_str_compat(self) -> None:
        assert InstrumentType.INDEX == "index"
        assert isinstance(InstrumentType.STOCK, str)


class TestBehavior:
    @pytest.mark.parametrize(
        ("symbol", "expected"),
        [
            ("VNINDEX", InstrumentType.INDEX),
            ("vnindex", InstrumentType.INDEX),
            ("HNXINDEX", InstrumentType.INDEX),
            ("VN30", InstrumentType.INDEX),
            ("SSI", InstrumentType.STOCK),
            ("ACB", InstrumentType.STOCK),
            ("VN30F1M", InstrumentType.DERIVATIVE),
            ("VN30F2606", InstrumentType.DERIVATIVE),
            ("VN100F1M", InstrumentType.DERIVATIVE),
            ("GB10F2024", InstrumentType.BOND),
            ("CMSN2401", InstrumentType.COVERED_WARRANT),
        ],
    )
    def test_values(self, symbol: str, expected: InstrumentType) -> None:
        out = get_asset_type(symbol)
        assert out is expected
        assert out == expected.value

    def test_etf_quirk_locked(self) -> None:
        # Bug hiện hữu: ETF 8 ký tự (FUESSVFL) trả coveredWarr — khóa lại,
        # cấm sửa trong R2 (fix riêng phase sau).
        assert get_asset_type("FUESSVFL") == "coveredWarr"
        assert get_asset_type("E1VFVN30") == "coveredWarr"

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            get_asset_type("TOOLONGXX")
        with pytest.raises(ValueError):
            get_asset_type("AB")

    def test_single_definition(self) -> None:
        import vnbroker.core.utils.parser as parser_mod

        assert parser_mod.get_asset_type.__module__ == parser_mod.__name__
        # Chỉ còn 1 def trong source
        import inspect

        src = inspect.getsource(parser_mod)
        assert src.count("def get_asset_type(") == 1
