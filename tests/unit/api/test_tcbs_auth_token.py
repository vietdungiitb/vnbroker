import pytest

from vnbroker import Vnbroker
from vnbroker.api.quote import Quote
from vnbroker.explorer.tcbs import auth
from vnbroker.explorer.tcbs.auth import resolve_auth_token


@pytest.mark.unit
@pytest.mark.api
class TestTCBSAuthToken:
    def test_resolve_auth_token_prefers_explicit_value(self, monkeypatch):
        monkeypatch.setenv("vnbroker_TCBS_AUTH_TOKEN", "env-token")
        assert resolve_auth_token("explicit-token") == "explicit-token"

    def test_resolve_auth_token_reads_environment(self, monkeypatch):
        monkeypatch.delenv("vnbroker_TCBS_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("TCBS_AUTH_TOKEN", "env-token")
        assert resolve_auth_token() == "env-token"

    def test_resolve_openapi_api_key_reads_environment(self, monkeypatch):
        monkeypatch.delenv("vnbroker_TCBS_OPENAPI_API_KEY", raising=False)
        monkeypatch.setenv("TCBS_OPENAPI_API_KEY", "api-key-env")
        assert auth.resolve_openapi_api_key() == "api-key-env"

    def test_request_openapi_token_returns_jwt(self, monkeypatch):
        captured = {}

        def fake_send_request(**kwargs):
            captured.update(kwargs)
            return {"token": "jwt-token-123"}

        monkeypatch.setattr(auth.client, "send_request", fake_send_request)

        token = auth.request_openapi_token(
            otp="111111",
            api_key="api-key-123",
        )

        assert token == "jwt-token-123"
        assert captured["url"] == (
            "https://openapi.tcbs.com.vn/gaia/v1/oauth2/openapi/token"
        )
        assert captured["method"] == "POST"
        assert captured["payload"] == {
            "apiKey": "api-key-123",
            "otp": "111111",
        }

    def test_request_openapi_token_raises_api_error(self, monkeypatch):
        def fake_send_request(**kwargs):
            return {
                "code": "203074",
                "message": "The API Key is invalid",
            }

        monkeypatch.setattr(auth.client, "send_request", fake_send_request)

        with pytest.raises(ConnectionError, match="203074"):
            auth.request_openapi_token(otp="111111", api_key="bad-key")


