"""
R3: kwargs-filtering ở Quote — hẹp thì lọc, VAR_KEYWORD thì passthrough,
show_log luôn giữ. Fake provider (không mạng).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import pytest

from vnbroker.common.data import Quote

pytestmark = pytest.mark.quote


class NarrowProvider:
    """Signature hẹp, không **kwargs (như KBS/VCI/TCBS)."""

    def __init__(self) -> None:
        self.calls: Dict[str, Dict[str, Any]] = {}

    def history(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        show_log: bool = False,
    ) -> str:
        self.calls["history"] = {"start": start, "end": end, "show_log": show_log}
        return "HIST"

    def intraday(self, show_log: bool = False) -> str:
        self.calls["intraday"] = {"show_log": show_log}
        return "INTRA"

    def price_depth(self, show_log: bool = False) -> str:
        self.calls["price_depth"] = {"show_log": show_log}
        return "DEPTH"


class KwargsProvider:
    """Có **kwargs (như DNSE) → passthrough."""

    def __init__(self) -> None:
        self.calls: Dict[str, Dict[str, Any]] = {}

    def history(self, symbol: Any = None, **kwargs: Any) -> str:
        self.calls["history"] = dict(kwargs)
        return "HIST"

    def intraday(self, symbol: Any = None, **kwargs: Any) -> str:
        self.calls["intraday"] = dict(kwargs)
        return "INTRA"

    def price_depth(self, symbol: Any = None, **kwargs: Any) -> str:
        self.calls["price_depth"] = dict(kwargs)
        return "DEPTH"


def make_quote(monkeypatch: pytest.MonkeyPatch, provider: Any) -> Quote:
    q = Quote("SSI", source="KBS", show_log=False)
    monkeypatch.setattr(q, "data_source", provider)
    return q


class TestNarrow:
    def test_unknown_dropped_with_debug(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        provider = NarrowProvider()
        q = make_quote(monkeypatch, provider)
        with caplog.at_level(logging.DEBUG, logger="vnbroker.common.data"):
            assert q.history(start="2026-01-01", no_such_param=1) == "HIST"
        assert provider.calls["history"] == {
            "start": "2026-01-01",
            "end": None,
            "show_log": False,
        }
        assert "no_such_param" in caplog.text

    def test_valid_passthrough(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider = NarrowProvider()
        q = make_quote(monkeypatch, provider)
        q.history(start="a", end="b", show_log=True)
        assert provider.calls["history"]["show_log"] is True
        q.intraday()
        q.price_depth()
        assert provider.calls["intraday"] == {"show_log": False}


class TestVarKeyword:
    def test_passthrough_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider = KwargsProvider()
        q = make_quote(monkeypatch, provider)
        q.history(start="a", anything=123, show_log=True)
        assert provider.calls["history"] == {
            "start": "a",
            "anything": 123,
            "show_log": True,
        }
        q.price_depth(custom="x")
        assert provider.calls["price_depth"] == {"custom": "x"}
