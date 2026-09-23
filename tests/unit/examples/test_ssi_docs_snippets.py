"""
S7: chạy 3 snippets trong docs/SSI_USAGE_GUIDE.md trên mock (không mạng).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from vnbroker import Vnbroker

pytestmark = pytest.mark.ssi

TOKEN = {
    "accessToken": "T",
    "tokenType": "Bearer",
    "expiresAt": 9999999999,
    "refreshToken": "R",
    "refreshExpiresAt": 9999999999,
}


class FakeResponse:
    def __init__(self, status_code: int, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers: Dict[str, str] = {}
        self.text = json.dumps(payload or {})

    def json(self) -> Any:
        return self._payload


class FakeSession:
    def __init__(self, script: List[Any]) -> None:
        self._script = list(script)
        self.headers: Dict[str, str] = {}
        self.calls: List[Dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        item = self._script.pop(0)
        assert isinstance(item, FakeResponse)
        return item

    def close(self) -> None:
        return None


def patch_session(monkeypatch: pytest.MonkeyPatch, script: List[Any]) -> FakeSession:
    fake = FakeSession(script)
    monkeypatch.setattr("vnbroker.broker.ssi._transport.requests.Session", lambda: fake)
    return fake


def test_snippet_market_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Snippet §1 usage guide."""
    patch_session(
        monkeypatch,
        [
            FakeResponse(200, dict(TOKEN)),
            FakeResponse(
                200,
                {
                    "data": [
                        {
                            "symbol": "SSI",
                            "tradingDate": "2026/01/05",
                            "open": 1,
                            "high": 2,
                            "low": 1,
                            "close": 2,
                            "volume": 10,
                            "value": 20,
                        }
                    ]
                },
            ),
            FakeResponse(200, {"data": [], "pagesCount": 1}),
        ],
    )
    vn = Vnbroker()
    ssi = vn.broker(provider="ssi", api_key="K", api_secret="S")
    ssi.authenticate()
    ohlc = ssi.get_ohlc(
        "SSI", timeframe="1d", from_date="2026/01/01", to_date="2026/01/31"
    )
    assert list(ohlc[["trading_date", "close", "volume"]].columns) == [
        "trading_date",
        "close",
        "volume",
    ]
    master = ssi.get_master_data()
    assert list(master.columns)[:4] == ["board", "symbol", "trading_date", "ceiling"]


def test_snippet_auth_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """Snippet §2 usage guide."""
    patch_session(
        monkeypatch,
        [
            FakeResponse(200, dict(TOKEN)),
            FakeResponse(200, [{"accountNo": "A1", "accountType": "Cash"}]),
            FakeResponse(200, {"equity": {"accountNo": "A1"}}),
            FakeResponse(200, {"equity": []}),
            FakeResponse(200, {"accountNo": "A1", "orderList": [], "totalRecord": 0}),
            FakeResponse(200, {"equity": []}),
        ],
    )
    vn = Vnbroker()
    ssi = vn.broker(
        provider="ssi", client_id="C", api_key="K", api_secret="S", private_key="P"
    )
    ssi.authenticate(otp="123456")
    assert len(ssi.list_accounts()) == 1
    assert ssi.get_balance("A1").iloc[0]["account_no"] == "A1"
    assert ssi.get_holdings("A1").empty
    assert ssi.get_orders("A1").empty
    snap = ssi.portfolio_snapshot("A1", market_prices={"SSI": 26000.0})
    assert snap["num_positions"] == 0


def test_snippet_fco_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Snippet §3 usage guide: dry-run trước, không HTTP."""
    fake = patch_session(monkeypatch, [])
    vn = Vnbroker()
    ssi = vn.broker(provider="ssi", api_key="K", api_secret="S")
    dry = ssi.place_fco_gtd(
        "A1",
        "SSI",
        "BUY",
        100,
        25000,
        0.5,
        "2026/01/05 00:00:00",
        "2026/01/12 23:00:00",
    )
    assert dry["dry_run"] is True
    assert fake.calls == []
