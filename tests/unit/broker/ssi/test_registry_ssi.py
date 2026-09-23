"""
S7: registry + compliance + docs snippets (mocked).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from vnbroker import Vnbroker
from vnbroker.broker.registry import BrokerRegistry
from vnbroker.broker.session import SessionState
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


def patch_session(monkeypatch: pytest.MonkeyPatch, script: List[Any]) -> FakeSession:
    fake = FakeSession(script)
    monkeypatch.setattr("vnbroker.broker.ssi._transport.requests.Session", lambda: fake)
    return fake


class TestRegistry:
    def test_ssi_registered(self) -> None:
        assert BrokerRegistry.is_registered("ssi")
        assert BrokerRegistry.get("ssi") is SSIBrokerClient
        assert "ssi" in BrokerRegistry.list_providers()

    def test_vnbroker_factory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        patch_session(monkeypatch, [FakeResponse(200, dict(TOKEN))])
        vn = Vnbroker()
        client = vn.broker(provider="ssi", api_key="K", api_secret="S")
        assert isinstance(client, SSIBrokerClient)
        assert client.provider_name == "SSI"
        assert client.authenticate() == "T"

    def test_unknown_provider(self) -> None:
        with pytest.raises(KeyError):
            BrokerRegistry.create("nope_broker_xyz", api_key="K")


class TestCompliance:
    def test_authenticate_lifecycle(self, monkeypatch: pytest.MonkeyPatch) -> None:
        patch_session(monkeypatch, [FakeResponse(200, dict(TOKEN))])
        client = SSIBrokerClient(api_key="K", api_secret="S")
        assert client.is_authenticated is False
        assert client.authenticate(otp="1") == "T"
        assert client.is_authenticated is True
        assert client.is_token_valid() is True

    def test_account_list_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        patch_session(
            monkeypatch,
            [
                FakeResponse(200, dict(TOKEN)),
                FakeResponse(200, [{"accountNo": "A1", "accountType": "Cash"}]),
            ],
        )
        client = SSIBrokerClient(api_key="K", api_secret="S")
        client.authenticate()
        accounts = client.get_account_list()
        assert accounts == [{"accountNo": "A1", "accountType": "Cash"}]

    def test_account_balance_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        patch_session(
            monkeypatch,
            [
                FakeResponse(200, dict(TOKEN)),
                FakeResponse(200, {"equity": {"accountNo": "A1"}}),
            ],
        )
        client = SSIBrokerClient(api_key="K", api_secret="S", client_id="C")
        client.authenticate()
        assert client.get_account_balance("A1") == {"equity": {"accountNo": "A1"}}

    def test_close_and_repr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        patch_session(monkeypatch, [FakeResponse(200, dict(TOKEN))])
        client = SSIBrokerClient(api_key="K", api_secret="S")
        client.authenticate()
        assert repr(client) == "SSIBrokerClient(state='AUTHENTICATED_READ')"
        client.close()
        assert client.is_authenticated is False
        assert client.session.state == SessionState.REVOKED

    def test_enable_write(self, monkeypatch: pytest.MonkeyPatch) -> None:
        patch_session(monkeypatch, [FakeResponse(200, dict(TOKEN))])
        client = SSIBrokerClient(api_key="K", api_secret="S")
        client.authenticate()
        client.enable_write()
        assert client.session.state == SessionState.AUTHENTICATED_WRITE_ENABLED

    def test_stream_lazy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        patch_session(monkeypatch, [])
        client = SSIBrokerClient(api_key="K", api_secret="S")
        assert client._stream is None
        assert client.stream is not None
        assert client.stream is client.stream
