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


class TestSSIP4Live:
    """P4 live evidence: 30m, datetime windows, indices, securities, screener."""

    def test_history_30m(self) -> None:
        from vnbroker.explorer.ssi.quote import SSIQuote

        q = SSIQuote("ACB", api_key=_API_KEY, api_secret=_API_SECRET)
        df = q.history(start="2024-01-02", end="2024-01-05", interval="30m")
        assert len(df) > 0
        assert df.attrs.get("source_used") == "SSI"

    def test_history_intraday_datetime_window(self) -> None:
        from vnbroker.explorer.ssi.quote import SSIQuote

        q = SSIQuote("ACB", api_key=_API_KEY, api_secret=_API_SECRET)
        df = q.history(
            start="2024-01-02 09:00:00",
            end="2024-01-02 15:00:00",
            interval="15m",
        )
        assert list(df.columns)[:6] == ["time", "open", "high", "low", "close", "volume"]

    def test_fetch_multiple(self) -> None:
        from vnbroker.explorer.ssi.quote import SSIQuote

        q = SSIQuote("ACB", api_key=_API_KEY, api_secret=_API_SECRET)
        out = q.fetch_multiple(["ACB", "VNM"], start="2024-01-02", end="2024-01-05")
        assert set(out) == {"ACB", "VNM"}
        assert len(out["ACB"]) > 0

    def test_indices_and_securities(self) -> None:
        from vnbroker.explorer.ssi.indices import SSIIndices
        from vnbroker.explorer.ssi.securities import SSISecurities

        idx = SSIIndices(api_key=_API_KEY, api_secret=_API_SECRET)
        members = idx.index_members("VN30")
        assert len(members) > 0
        sec = SSISecurities(api_key=_API_KEY, api_secret=_API_SECRET)
        room = sec.foreign_room(symbol="ACB", start="2024-01-02", end="2024-01-05")
        assert "remain_foreign_room" in room.columns

    def test_screener_smoke(self) -> None:
        from vnbroker.explorer.ssi.screener import SSIScreener

        s = SSIScreener(api_key=_API_KEY, api_secret=_API_SECRET)
        df = s.stock(params={"indexName": "VN30"}, limit=5)
        assert len(df) > 0

    def test_session_snapshot(self) -> None:
        from vnbroker.explorer.ssi.live import SSILive

        live = SSILive("ACB", api_key=_API_KEY, api_secret=_API_SECRET)
        df = live.session_snapshot(["ACB", "VNM"])
        assert "ref" in df.columns

    def test_ws_ticks_tolerant(self) -> None:
        """WS evidence: columns only (empty outside market hours is OK)."""
        from vnbroker.explorer.ssi.live import SSILive

        live = SSILive("ACB", api_key=_API_KEY, api_secret=_API_SECRET)
        df = live.intraday_ticks(timeout=10.0)
        assert list(df.columns) == ["time", "price", "volume", "side"]
        depth = live.depth_snapshot(timeout=10.0)
        assert list(depth.columns) == ["side", "price", "volume"]
