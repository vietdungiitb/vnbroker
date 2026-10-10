import pytest

from vnbroker.explorer.tcbs import auth
from vnbroker.explorer.tcbs.auth import resolve_auth_token


@pytest.mark.unit
@pytest.mark.api
class TestTCBSAuthToken:
    def test_resolve_auth_token_prefers_explicit_value(self, monkeypatch):
        monkeypatch.setenv("vnbroker_TCBS_AUTH_TOKEN", "env-token")
        monkeypatch.setenv("TCBS_JWT_TOKEN", "env-jwt")
        assert resolve_auth_token("explicit-token") == "explicit-token"

    def test_resolve_auth_token_prefers_jwt_over_non_jwt(self, monkeypatch):
        """JWT thật phải thắng token 48 ký tự — đo live 2026-10-10.

        `TCBS_AUTH_TOKEN` **không** phải JWT: server trả
        `401 {"code":"validate.token.error"}` khi dùng nó làm Bearer cho
        `/tartarus/*` (4/4 endpoint). Bản cũ chỉ đọc biến này nên
        `Quote.history()` ném `ConnectionError` trong khi máy đã có JWT chạy
        được.
        """
        for var in ("vnbroker_TCBS_JWT_TOKEN", "vnbroker_TCBS_AUTH_TOKEN"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("TCBS_JWT_TOKEN", "aaa.bbb.ccc")
        monkeypatch.setenv("TCBS_AUTH_TOKEN", "short-non-jwt")
        assert resolve_auth_token() == "aaa.bbb.ccc"

    def test_resolve_auth_token_falls_back_to_non_jwt(self, monkeypatch):
        """Không có JWT thì dùng token cũ — hành vi cũ không bị bỏ rơi."""
        for var in ("vnbroker_TCBS_JWT_TOKEN", "TCBS_JWT_TOKEN"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("vnbroker_TCBS_AUTH_TOKEN", "")
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


