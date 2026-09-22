"""
S7: SSIBrokerClient facade passthrough — mọi nhóm method (mocked).
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List
from xml.etree.ElementTree import Element, SubElement, tostring

import pandas as pd
import pytest

from vnbroker.broker.ssi.client import SSIBrokerClient

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


def make_key() -> str:
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    nums = key.private_numbers()

    def _b64(value: int) -> str:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return base64.b64encode(raw).decode("ascii")

    root = Element("RSAKeyValue")
    for tag, val in (("Modulus", nums.public_numbers.n), ("D", nums.d)):
        node = SubElement(root, tag)
        node.text = _b64(val)
    return base64.b64encode(tostring(root, encoding="unicode").encode()).decode()


def make_client(monkeypatch: pytest.MonkeyPatch, script: List[Any], **kw: Any) -> tuple:
    fake = FakeSession(script)
    monkeypatch.setattr("vnbroker.broker.ssi._transport.requests.Session", lambda: fake)
    params = {
        "api_key": "K",
        "api_secret": "S",
        "client_id": "C",
        "private_key": make_key(),
    }
    params.update(kw)
    client = SSIBrokerClient(**params)
    client.authenticate()
    return client, fake


def R(payload: Any) -> FakeResponse:
    return FakeResponse(200, payload)


class TestFacadeReads:
    def test_auth_helpers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeSession([R(dict(TOKEN)), R({"transactionId": "tx"}), R(dict(TOKEN))])
        monkeypatch.setattr(
            "vnbroker.broker.ssi._transport.requests.Session", lambda: fake
        )
        client = SSIBrokerClient(api_key="K", api_secret="S")
        assert client.authenticate() == "T"
        assert client.request_otp() == {"transactionId": "tx"}
        assert client.refresh() == "T"
        assert client.ensure_authenticated() == "T"
        assert client.is_token_valid() is True
        client.revoke()
        assert client.is_token_valid() is False

    def test_account_money(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, _ = make_client(
            monkeypatch,
            [
                R(dict(TOKEN)),
                R([{"accountNo": "A1", "accountType": "Cash"}]),
                R({"equity": {"accountNo": "A1"}}),
                R({"derivative": {"accountNo": "A1"}}),
                R({"equity": {"accountNo": "A1", "purchasingPower": 1.0}}),
                R({"derivative": {"accountNo": "A1"}}),
                R({"accountNo": "A1", "maxBuyQty": 1, "maxSellQty": 2}),
            ],
        )
        assert isinstance(client.list_accounts(), pd.DataFrame)
        assert isinstance(client.get_balance("A1"), pd.DataFrame)
        assert isinstance(client.get_derivative_balance("A1"), pd.DataFrame)
        assert isinstance(client.get_ppmmr("A1"), pd.DataFrame)
        assert isinstance(client.get_derivative_ppmmr("A1"), pd.DataFrame)
        assert isinstance(client.get_purchasing_power("A1", "SSI", 1.0), pd.DataFrame)

    def test_portfolio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pos = {
            "equity": [{"symbol": "SSI", "quantity": 10}],
            "derivative": {"derOpenPositions": [], "derClosePositions": []},
        }
        client, _ = make_client(
            monkeypatch,
            [
                R(dict(TOKEN)),
                R(pos),
                R(pos),
                R({"accountNo": "A1", "orderList": [], "totalRecord": 0}),
                R({"accountNo": "A1", "orderList": [], "totalRecord": 0}),
                R(pos),
                R({"equity": {"accountNo": "A1"}}),
            ],
        )
        assert isinstance(client.get_holdings("A1"), pd.DataFrame)
        assert isinstance(client.get_derivative_positions("A1"), pd.DataFrame)
        assert isinstance(client.get_orders("A1"), pd.DataFrame)
        assert isinstance(
            client.get_order_history("A1", "2026/01/01", "2026/01/31"), pd.DataFrame
        )
        snap = client.portfolio_snapshot("A1", market_prices={"SSI": 10.0})
        assert snap["num_positions"] == 1

    def test_market(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bar = {
            "symbol": "SSI",
            "tradingDate": "2026/01/05",
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
            "volume": 1,
            "value": 1,
        }
        client, _ = make_client(
            monkeypatch,
            [
                R(dict(TOKEN)),
                R({"data": [bar]}),
                R([{"index": "VNINDEX"}]),
                R([{"tradingDate": "t"}]),
                R([{"tradingDate": "t"}]),
                R([{"symbol": "SSI"}]),
                R({"data": [bar]}),
                R({"data": [], "pagesCount": 1}),
            ],
        )
        assert isinstance(client.get_ohlc("SSI"), pd.DataFrame)
        assert isinstance(client.get_indexes(), pd.DataFrame)
        assert isinstance(client.get_index_summary("VNINDEX"), pd.DataFrame)
        assert isinstance(client.get_board_summary("HOSE"), pd.DataFrame)
        assert isinstance(client.get_securities_info(symbol="SSI"), pd.DataFrame)
        assert isinstance(client.get_securities_summary(symbol="SSI"), pd.DataFrame)
        assert isinstance(client.get_master_data(), pd.DataFrame)

    def test_raw_passthrough(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, _ = make_client(
            monkeypatch,
            [
                R(dict(TOKEN)),
                R({"data": []}),
                R([{"accountNo": "A1"}]),
                R({"data": []}),
            ],
        )
        assert client.get_ohlc("SSI", raw=True) == []
        assert client.list_accounts(raw=True) == [{"accountNo": "A1"}]
        assert client.get_orders("A1", raw=True) == []


class TestFacadeWrites:
    def test_equity_dry_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, fake = make_client(monkeypatch, [R(dict(TOKEN))])
        assert client.place_order("A1", "SSI", "BUY", "LO", 1, 1.0)["dry_run"]
        assert client.place_limit_order("A1", "SSI", "BUY", 1, 1.0)["dry_run"]
        assert client.place_market_order("A1", "SSI", "BUY", 1)["dry_run"]
        assert client.modify_order("A1", price=1.0, order_id="O")["dry_run"]
        assert client.cancel_order("A1", order_id="O")["dry_run"]
        assert fake.calls and len(fake.calls) == 1  # chỉ auth

    def test_equity_real(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, _ = make_client(
            monkeypatch,
            [
                R(dict(TOKEN)),
                R({"orderId": "O", "clientRequestId": "R", "orderStatus": "QU"}),
                R({"orderId": "O"}),
                R({"orderId": "O"}),
            ],
        )
        client.enable_write()
        out = client.place_order("A1", "SSI", "BUY", "LO", 1, 1.0, dry_run=False)
        assert out["order_id"] == "O"
        assert (
            client.modify_order("A1", price=2.0, order_id="O", dry_run=False)[
                "order_id"
            ]
            == "O"
        )
        assert client.cancel_order("A1", order_id="O", dry_run=False)["order_id"] == "O"

    def test_fco_all_dry_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, fake = make_client(monkeypatch, [R(dict(TOKEN))])
        from_date, to_date = "2026/01/05 00:00:00", "2026/01/12 23:00:00"
        assert client.place_fco_gtd("A", "S", "BUY", 1, 1, 0, from_date, to_date)[
            "dry_run"
        ]
        assert client.place_fco_stop(
            "A", "S", "BUY", 1, 1, "greater", from_date, to_date
        )["dry_run"]
        assert client.place_fco_stop_limit(
            "A", "S", "BUY", 1, 1, 0, 1, "greater", from_date, to_date
        )["dry_run"]
        assert client.place_fco_trailing_stop(
            "A", "S", "BUY", 1, 1, 1, from_date, to_date
        )["dry_run"]
        assert client.place_fco_trailing_stop_limit(
            "A", "S", "BUY", 1, 1, 1, 0, from_date, to_date
        )["dry_run"]
        assert client.place_fco_oco(
            "A", "S", "BUY", 1, 2, 1, from_date=from_date, to_date=to_date
        )["dry_run"]
        assert client.place_fco_bull_bear(
            "A", "S", "BUY", 1, 1, 0, 2, 1, 2, 1, 0, 0, from_date, to_date
        )["dry_run"]
        assert client.cancel_fco("F")["dry_run"]
        assert len(fake.calls) == 1

    def test_fco_real_and_query(self, monkeypatch: pytest.MonkeyPatch) -> None:
        item = {
            "fcoId": "F",
            "accountNo": "A",
            "symbol": "S",
            "type": "gtd",
            "side": "B",
            "quantity": 1,
            "status": "WAIT",
        }
        client, _ = make_client(
            monkeypatch,
            [
                R(dict(TOKEN)),
                R({"fcoId": "F"}),
                R({"fcoId": "F"}),
                R({"data": [item]}),
                R({"data": [item]}),
                R({"data": [item]}),
                R({"data": [item]}),
                R({"data": [item]}),
                R({"data": [item]}),
                R({"data": [{"fcoId": "F", "orderId": "O"}]}),
            ],
        )
        client.enable_write()
        from_date, to_date = "2026/01/05 00:00:00", "2026/01/12 23:00:00"
        assert client.place_fco_gtd(
            "A", "S", "BUY", 1, 1, 0, from_date, to_date, dry_run=False
        ) == {"fco_id": "F"}
        assert client.cancel_fco("F", dry_run=False) == {"fco_id": "F"}
        assert isinstance(client.get_fco_by_account_no("A"), pd.DataFrame)
        assert isinstance(client.get_fco_by_symbol("A", "S"), pd.DataFrame)
        assert isinstance(client.get_fco_by_status("A", "WAIT"), pd.DataFrame)
        assert isinstance(
            client.get_fco_by_date("A", "2026/01/01", "2026/01/31"), pd.DataFrame
        )
        assert client.get_fco_by_id("A", "F") is not None
        assert isinstance(client.get_fco_order_book("F"), pd.DataFrame)
