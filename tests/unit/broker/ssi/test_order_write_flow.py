"""
S3: SSI equity write — dry_run default, idempotency, ký RSA, price str. Mocked.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from vnbroker.broker.exceptions import (
    BrokerPermissionError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.ssi._transport import SSIHttpClient
from vnbroker.broker.ssi.equity import SSIEquityService

pytestmark = pytest.mark.ssi


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
    """RSA-1024 base64-XML hợp lệ cho write tests (test-only)."""
    import base64
    from xml.etree.ElementTree import Element, SubElement, tostring

    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    nums = key.private_numbers()

    def _b64(value: int) -> str:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return base64.b64encode(raw).decode("ascii")

    root = Element("RSAKeyValue")
    for tag, val in (
        ("Modulus", nums.public_numbers.n),
        ("D", nums.d),
    ):
        node = SubElement(root, tag)
        node.text = _b64(val)
    return base64.b64encode(tostring(root, encoding="unicode").encode()).decode()


def make_equity(
    script: List[Any], monkeypatch: pytest.MonkeyPatch, authed_write: bool = False
) -> tuple:
    fake = FakeSession(script)
    monkeypatch.setattr("vnbroker.broker.ssi._transport.requests.Session", lambda: fake)
    config = SSICredentialConfig.from_dict(
        {
            "api_key": "K",
            "api_secret": "S",
            "client_id": "C",
            "private_key": make_test_private_key(),
            "device_id": "DEV1",
        }
    )
    session = BrokerSession(provider="SSI")
    session.set_token("T")
    if authed_write:
        session.enable_write()
    transport = SSIHttpClient(base_url="https://api.ssi.com.vn", rate_limit_rps=0)
    return SSIEquityService(config, session, transport), fake, session


class TestDryRunGate:
    def test_dry_run_default_no_http(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake, _ = make_equity([], monkeypatch)
        out = svc.place_order("A1", "SSI", "BUY", "LO", 100, 25000.0)
        assert out["dry_run"] is True
        assert fake.calls == []

    def test_real_without_enable_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        svc, fake, _ = make_equity([], monkeypatch, authed_write=False)
        with pytest.raises(BrokerPermissionError) as exc:
            svc.place_order("A1", "SSI", "BUY", "LO", 100, 25000.0, dry_run=False)
        assert exc.value.code == "WRITE_NOT_ENABLED"
        assert fake.calls == []

    def test_validation_before_gate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake, session = make_equity([], monkeypatch)
        session.enable_write()
        with pytest.raises(BrokerValidationError):
            svc.place_order("A1", "SSI", "HOLD", "LO", 100, 1.0, dry_run=False)
        with pytest.raises(BrokerValidationError):
            svc.place_order("A1", "SSI", "BUY", "XXX", 100, 1.0, dry_run=False)
        with pytest.raises(BrokerValidationError):
            svc.place_order("A1", "SSI", "BUY", "LO", 0, 1.0, dry_run=False)
        with pytest.raises(BrokerValidationError):
            svc.place_order("A1", "SSI", "BUY", "LO", 100, 0, dry_run=False)
        assert fake.calls == []


class TestPlace:
    def test_signed_post(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake, _ = make_equity(
            [
                FakeResponse(
                    200, {"orderId": "O1", "clientRequestId": "R1", "orderStatus": "QU"}
                )
            ],
            monkeypatch,
            authed_write=True,
        )
        out = svc.place_order(
            "A1",
            "ssi",
            "BUY",
            "LO",
            100,
            25000.0,
            request_id="R1",
            dry_run=False,
        )
        assert out == {"order_id": "O1", "client_request_id": "R1", "status": "QU"}
        call = fake.calls[0]
        assert call["method"] == "POST"
        assert call["url"].endswith("/api/v3/trading/order")
        assert "X-Signature" in call["headers"]
        body = json.loads(call["data"].decode("utf-8"))
        assert body["symbol"] == "SSI"
        assert body["side"] == "B"
        assert body["price"] == "25000.0"  # wire ép string
        assert body["clientRequestId"] == "R1"
        assert body["deviceId"] == "DEV1"

    def test_request_id_autogen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake, _ = make_equity(
            [FakeResponse(200, {})], monkeypatch, authed_write=True
        )
        svc.place_order("A1", "SSI", "SELL", "LO", 10, 100.0, dry_run=False)
        body = json.loads(fake.calls[0]["data"].decode("utf-8"))
        assert len(body["clientRequestId"]) == 20
        assert body["side"] == "S"

    def test_aliases(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake, _ = make_equity(
            [FakeResponse(200, {})] * 4, monkeypatch, authed_write=True
        )
        svc.place_limit_order("A1", "SSI", "BUY", 10, 100.0, dry_run=False)
        svc.place_market_order("A1", "SSI", "BUY", 10, dry_run=False)
        svc.place_ato_order("A1", "SSI", "BUY", 10, dry_run=False)
        svc.place_atc_order("A1", "SSI", "BUY", 10, dry_run=False)
        types = [json.loads(c["data"].decode("utf-8"))["orderType"] for c in fake.calls]
        assert types == ["LO", "MTL", "ATO", "ATC"]
        assert json.loads(fake.calls[1]["data"].decode("utf-8"))["price"] == "0"

    def test_limit_zero_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake, _ = make_equity([], monkeypatch, authed_write=True)
        with pytest.raises(BrokerValidationError):
            svc.place_limit_order("A1", "SSI", "BUY", 10, 0, dry_run=False)
        assert fake.calls == []


class TestModifyCancel:
    def test_modify_price_by_order_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake, _ = make_equity(
            [
                FakeResponse(
                    200, {"clientModifyId": "M1", "orderId": "O1", "orderStatus": "QU"}
                )
            ],
            monkeypatch,
            authed_write=True,
        )
        out = svc.modify_order("A1", price=26000.0, order_id="O1", dry_run=False)
        assert out["client_modify_id"] == "M1"
        call = fake.calls[0]
        assert call["method"] == "PUT"
        body = json.loads(call["data"].decode("utf-8"))
        assert body["orderId"] == "O1"
        assert body["price"] == "26000.0"
        assert "quantity" not in body
        assert "clientModifyId" in body

    def test_modify_quantity_by_request_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        svc, fake, _ = make_equity(
            [FakeResponse(200, {})], monkeypatch, authed_write=True
        )
        svc.modify_order("A1", quantity=200, client_request_id="R1", dry_run=False)
        body = json.loads(fake.calls[0]["data"].decode("utf-8"))
        assert body["clientRequestId"] == "R1"
        assert body["quantity"] == 200
        assert "price" not in body

    def test_modify_both_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake, _ = make_equity([], monkeypatch, authed_write=True)
        with pytest.raises(BrokerValidationError) as exc:
            svc.modify_order("A1", quantity=1, price=1.0, order_id="O", dry_run=False)
        assert exc.value.code == "MUTUALLY_EXCLUSIVE"
        assert fake.calls == []

    def test_modify_no_identifier(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake, _ = make_equity([], monkeypatch, authed_write=True)
        with pytest.raises(BrokerValidationError):
            svc.modify_order("A1", price=1.0, dry_run=False)
        assert fake.calls == []

    def test_cancel_by_order_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake, _ = make_equity(
            [FakeResponse(200, {"orderId": "O1"})], monkeypatch, authed_write=True
        )
        out = svc.cancel_order("A1", order_id="O1", dry_run=False)
        assert out["order_id"] == "O1"
        call = fake.calls[0]
        assert call["method"] == "DELETE"
        body = json.loads(call["data"].decode("utf-8"))
        assert body["orderId"] == "O1"
        assert "clientCancelId" in body

    def test_cancel_dry_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake, _ = make_equity([], monkeypatch)
        out = svc.cancel_order("A1", client_request_id="R1")
        assert out["dry_run"] is True
        assert fake.calls == []
