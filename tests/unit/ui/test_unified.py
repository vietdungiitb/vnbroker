"""
R1: Unified UI — delegate mỏng + show_api snapshot + show_doc. Mocked components.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from vnbroker.ui import Fundamental, Market, Reference, Retail, show_api, show_doc
from vnbroker.ui.registry import render_api_tree

pytestmark = pytest.mark.ui

SNAPSHOT = Path(__file__).resolve().parents[2] / "fixtures" / "ui" / "api_tree.txt"


class TestDelegate:
    def test_market_equity(self) -> None:
        with patch("vnbroker.ui.market.Quote", autospec=True) as mock_quote:
            mock_quote.return_value = MagicMock(name="Quote")
            out = Market(source="VCI", show_log=False).equity("SSI")
            mock_quote.assert_called_once_with("SSI", "VCI", show_log=False)
            assert out is mock_quote.return_value

    def test_market_default_source(self) -> None:
        with patch("vnbroker.ui.market.Quote", autospec=True) as mock_quote:
            Market().equity("SSI")
            mock_quote.assert_called_once_with("SSI", "KBS", show_log=True)

    def test_reference_company(self) -> None:
        with patch("vnbroker.ui.reference.Company", autospec=True) as mock_cls:
            Reference().company("SSI")
            mock_cls.assert_called_once_with("SSI", source="KBS", show_log=True)

    def test_reference_listing(self) -> None:
        with patch("vnbroker.ui.reference.Listing", autospec=True) as mock_cls:
            Reference(source="TCBS").listing()
            mock_cls.assert_called_once_with(source="TCBS", show_log=True)

    def test_fundamental_equity(self) -> None:
        with patch("vnbroker.ui.fundamental.Finance", autospec=True) as mock_cls:
            Fundamental().equity("SSI")
            mock_cls.assert_called_once_with("SSI", source="KBS", show_log=True)

    def test_retail_is_common(self) -> None:
        from vnbroker.common.retail import Retail as CommonRetail

        assert issubclass(Retail, CommonRetail)
        assert isinstance(Retail(), CommonRetail)

    def test_bad_source_passthrough(self) -> None:
        with pytest.raises(ValueError, match="Supported sources"):
            with patch(
                "vnbroker.ui.market.Quote",
                side_effect=ValueError("Supported sources: VCI. Got: NOPE"),
            ):
                Market(source="NOPE").equity("SSI")


class TestShowApi:
    def test_snapshot(self) -> None:
        expected = SNAPSHOT.read_text(encoding="utf-8")
        assert render_api_tree() == expected

    def test_show_api_stdout(self, capsys: Any) -> None:
        show_api()
        out = capsys.readouterr().out
        assert out == SNAPSHOT.read_text(encoding="utf-8")
        assert "Market" in out and "Retail" in out

    def test_show_doc(self, capsys: Any) -> None:
        show_doc("Market.equity.history")
        out = capsys.readouterr().out
        assert "historical price" in out.lower()

    def test_show_doc_unknown(self) -> None:
        with pytest.raises(KeyError, match="Valid"):
            show_doc("Nope.nope")
