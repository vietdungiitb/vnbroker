"""
S4: SSI FCO — 7 place + cancel + query vòng đời. Mocked.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pandas as pd
import pytest

from vnbroker.broker.exceptions import BrokerPermissionError, BrokerValidationError
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.ssi._transport import SSIHttpClient
from vnbroker.broker.ssi.fco import SSIFCOService

pytestmark = pytest.mark.ssi

FROM = "2026/01/01 00:00:00"
TO = "2026/01/08 23:00:00"

FCO_ITEM = {
    "fcoId": "F1",
    "username": "U",
    "accountNo": "A1",
    "quantity": 100,
    "price": "25000",
    "priceSlip": 0,
    "symbol": "SSI",
    "type": "gtd",
    "side": "B",
    "from": FROM,
    "to": TO,
    "matchedQuantity": 0,
    "isPlaceOrder": False,
    "status": "WAIT",
    "detail": "",
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


def make_test_private_key() -> str:
    import base64
    from xml.etree.ElementTree import Element, SubElement, tostring

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


def make_fco(
    script: List[Any], monkeypatch: pytest.MonkeyPatch, write: bool = False
) -> tuple:
    fake = FakeSession(script)
    monkeypatch.setattr("vnbroker.broker.ssi._transport.requests.Session", lambda: fake)
    config = SSICredentialConfig.from_dict(
        {"api_key": "K", "api_secret": "S", "private_key": make_test_private_key()}
    )
    session = BrokerSession(provider="SSI")
    session.set_token("T")
    if write:
        session.enable_write()
    transport = SSIHttpClient(base_url="https://api.ssi.com.vn", rate_limit_rps=0)
    return SSIFCOService(config, session, transport), fake


def body_of(fake: FakeSession, i: int = 0) -> Dict[str, Any]:
    return json.loads(fake.calls[i]["data"].decode("utf-8"))


class TestPlaceFco:
    def test_gtd_numeric(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([FakeResponse(200, {"fcoId": "F9"})], monkeypatch, True)
        out = svc.place_fco_gtd(
            "A1", "SSI", "BUY", 100, 25000, 0.5, FROM, TO, dry_run=False
        )
        assert out == {"fco_id": "F9"}
        body = body_of(fake)
        assert body["type"] == "gtd"
        assert body["price"] == "25000" and body["priceSlip"] == 0.5
        assert body["side"] == "B"
        assert "X-Signature" in fake.calls[0]["headers"]

    def test_gtd_enum_price(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([FakeResponse(200, {})], monkeypatch, True)
        svc.place_fco_gtd("A1", "SSI", "BUY", 100, "MTL", 0.5, FROM, TO, dry_run=False)
        body = body_of(fake)
        assert body["price"] == "MTL" and body["priceSlip"] == 0

    def test_stop_forces_mtl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([FakeResponse(200, {})], monkeypatch, True)
        svc.place_fco_stop(
            "A1", "SSI", "BUY", 100, 20000, "greater_or_equal", FROM, TO, dry_run=False
        )
        body = body_of(fake)
        assert body["type"] == "stop"
        assert body["price"] == "MTL" and body["priceSlip"] == 0
        assert body["stopPrice"] == 20000
        assert body["operator"] == "greater_or_equal"

    def test_stop_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([FakeResponse(200, {})], monkeypatch, True)
        svc.place_fco_stop_limit(
            "A1",
            "SSI",
            "BUY",
            100,
            20500,
            0.5,
            20000,
            "greater_or_equal",
            FROM,
            TO,
            dry_run=False,
        )
        body = body_of(fake)
        assert body["type"] == "stop_limit"
        assert body["price"] == "20500"

    def test_trailing_stop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([FakeResponse(200, {})], monkeypatch, True)
        svc.place_fco_trailing_stop(
            "A1", "SSI", "BUY", 100, 20000, 1000, FROM, TO, dry_run=False
        )
        body = body_of(fake)
        assert body["type"] == "trailing_stop"
        assert body["price"] == "MTL"

    def test_trailing_stop_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([FakeResponse(200, {})], monkeypatch, True)
        svc.place_fco_trailing_stop_limit(
            "A1", "SSI", "BUY", 100, 20000, 1000, 500, FROM, TO, dry_run=False
        )
        body = body_of(fake)
        assert body["type"] == "trailing_stop_limit"
        assert body["priceSlip"] == 500

    def test_oco_hardcode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([FakeResponse(200, {})], monkeypatch, True)
        svc.place_fco_oco(
            "A1",
            "SSI",
            "BUY",
            100,
            30000,
            20000,
            "MP",
            "MP",
            0.1,
            0,
            FROM,
            TO,
            dry_run=False,
        )
        body = body_of(fake)
        assert body["type"] == "oco"
        assert body["price"] == "MP" and body["priceSlip"] == 0
        assert body["tpActivePrice"] == 30000

    def test_bull_bear(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([FakeResponse(200, {})], monkeypatch, True)
        svc.place_fco_bull_bear(
            "A1",
            "SSI",
            "BUY",
            100,
            25000,
            10,
            30000,
            20000,
            30000,
            20000,
            0.1,
            0,
            FROM,
            TO,
            dry_run=False,
        )
        body = body_of(fake)
        assert body["type"] == "bullbear"
        assert body["price"] == "25000"

    def test_dry_run_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([], monkeypatch)
        out = svc.place_fco_gtd("A1", "SSI", "BUY", 100, 1, 0, FROM, TO)
        assert out["dry_run"] is True
        assert fake.calls == []

    def test_no_write_permission(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([], monkeypatch, write=False)
        with pytest.raises(BrokerPermissionError):
            svc.place_fco_gtd("A1", "SSI", "BUY", 100, 1, 0, FROM, TO, dry_run=False)
        assert fake.calls == []

    def test_bad_operator(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([], monkeypatch, write=True)
        with pytest.raises(BrokerValidationError):
            svc.place_fco_stop(
                "A1", "SSI", "BUY", 100, 1, "near", FROM, TO, dry_run=False
            )
        assert fake.calls == []

    def test_bad_datetime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([], monkeypatch, write=True)
        with pytest.raises(BrokerValidationError):
            svc.place_fco_gtd(
                "A1", "SSI", "BUY", 100, 1, 0, "2026-01-01", TO, dry_run=False
            )
        assert fake.calls == []


class TestCancelQuery:
    def test_cancel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([FakeResponse(200, {"fcoId": "F1"})], monkeypatch, True)
        assert svc.cancel_fco("F1", dry_run=False) == {"fco_id": "F1"}
        assert fake.calls[0]["method"] == "DELETE"
        assert body_of(fake) == {"fcoId": "F1"}

    def test_cancel_dry_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([], monkeypatch)
        assert svc.cancel_fco("F1")["dry_run"] is True
        assert fake.calls == []

    def test_list_df(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([FakeResponse(200, {"data": [FCO_ITEM]})], monkeypatch)
        df = svc.get_fco_by_account_no("A1")
        assert isinstance(df, pd.DataFrame)
        assert df.iloc[0]["fco_id"] == "F1"
        assert df.iloc[0]["type"] == "GTD"
        assert df.iloc[0]["status"] == "WAIT"
        assert df.iloc[0]["side"] == "BUY"
        assert fake.calls[0]["params"]["accountNo"] == "A1"

    def test_list_raw(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, _ = make_fco([FakeResponse(200, [FCO_ITEM])], monkeypatch)
        assert svc.get_fco_by_account_no("A1", raw=True) == [FCO_ITEM]

    def test_by_symbol_status_date(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco(
            [FakeResponse(200, []), FakeResponse(200, []), FakeResponse(200, [])],
            monkeypatch,
        )
        svc.get_fco_by_symbol("A1", "ssi")
        svc.get_fco_by_status("A1", "TRIT")
        svc.get_fco_by_date("A1", "2026/01/01", "2026/01/31")
        assert fake.calls[0]["params"]["symbol"] == "SSI"
        assert fake.calls[1]["params"]["processStatus"] == "TRIT"
        assert fake.calls[2]["params"]["from"] == "2026/01/01"

    def test_bad_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_fco([], monkeypatch)
        with pytest.raises(BrokerValidationError):
            svc.get_fco_by_status("A1", "NOPE")
        assert fake.calls == []

    def test_by_id_found_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, _ = make_fco(
            [FakeResponse(200, {"data": [FCO_ITEM]}), FakeResponse(200, [])],
            monkeypatch,
        )
        got = svc.get_fco_by_id("A1", "F1")
        assert got is not None and got["fco_id"] == "F1"
        assert got["type"] == "GTD"
        assert svc.get_fco_by_id("A1", "ZZ") is None

    def test_order_book(self, monkeypatch: pytest.MonkeyPatch) -> None:
        entry = {
            "fcoId": "F1",
            "orderId": "O1",
            "accountNo": "A1",
            "symbol": "SSI",
            "side": "B",
            "orderType": "LO",
            "quantity": 100,
            "matchedQuantity": 40,
            "osQuantity": 60,
            "avgPrice": 25000.0,
            "price": "25000",
            "status": "FF",
            "isMainOrder": True,
            "isAttachedOrder": False,
            "createdTime": "t1",
            "updatedTime": "t2",
        }
        svc, fake = make_fco([FakeResponse(200, {"data": [entry]})], monkeypatch)
        df = svc.get_fco_order_book("F1")
        assert df.iloc[0]["status"] == "FILLED"
        assert df.iloc[0]["matched_quantity"] == 40.0
        assert fake.calls[0]["params"]["pageIndex"] == 1

    def test_gtd_then_cancel_pattern(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pattern an toàn AGENT.md: đặt GTD rồi hủy ngay (trên mock)."""
        svc, fake = make_fco(
            [FakeResponse(200, {"fcoId": "FX"}), FakeResponse(200, {"fcoId": "FX"})],
            monkeypatch,
            True,
        )
        placed = svc.place_fco_gtd(
            "A1", "SSI", "BUY", 100, "MTL", 0, FROM, TO, dry_run=False
        )
        cancelled = svc.cancel_fco(placed["fco_id"], dry_run=False)
        assert cancelled == {"fco_id": "FX"}
        assert [c["method"] for c in fake.calls] == ["POST", "DELETE"]
