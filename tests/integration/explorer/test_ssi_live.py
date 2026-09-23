"""Live SSI explorer tests (gated: vnbroker_RUN_LIVE_INTEGRATION=1 + real keys).

Never commit secrets. Run locally only:
    $env:vnbroker_RUN_LIVE_INTEGRATION='1'; pytest tests/integration/explorer/test_ssi_live.py -v
"""

from __future__ import annotations

import os

import pytest

from vnbroker import Vnbroker

_API_KEY = os.getenv("VNBROKER_BROKER_SSI_API_KEY") or ""
_API_SECRET = os.getenv("VNBROKER_BROKER_SSI_API_SECRET") or ""
_LIVE = os.getenv("vnbroker_RUN_LIVE_INTEGRATION") == "1" and bool(
    _API_KEY.strip() and _API_SECRET.strip()
)

pytestmark = pytest.mark.skipif(
    not _LIVE, reason="SSI live test needs vnbroker_RUN_LIVE_INTEGRATION=1 + SSI keys"
)


class TestSSILive:
    """Live evidence: history + listing + price_board (schema only, no values)."""

    def test_history_acb(self) -> None:
        vn = Vnbroker(source="SSI", show_log=False)
        df = vn.stock("ACB").quote.history(start="2024-01-01", end="2024-01-31")
        assert list(df.columns)[:6] == ["time", "open", "high", "low", "close", "volume"]
        assert len(df) > 0
        assert df.attrs.get("source_used") == "SSI"

    def test_all_symbols(self) -> None:
        vn = Vnbroker(source="SSI", show_log=False)
        df = vn.stock("ACB").listing.all_symbols()
        assert list(df.columns) == ["symbol", "organ_name"]
        assert len(df) > 100

    def test_price_board_3_symbols(self) -> None:
        vn = Vnbroker(source="SSI", show_log=False)
        df = vn.stock("ACB").trading.price_board(["ACB", "VNM", "HPG"])
        assert len(df) == 3
        assert "ceiling_price" in df.columns
        assert df.attrs.get("source_used") == "SSI"
