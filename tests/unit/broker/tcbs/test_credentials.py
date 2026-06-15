"""
Unit tests S2: TCBSCredentialConfig, resolve_tcbs_credentials, Redactor.
"""
import os
import pytest

from vnbroker.broker.security.credentials import (
    TCBSCredentialConfig,
    resolve_tcbs_credentials,
    _ENV_PRIORITY,
    _DEFAULT_BASE_URL,
)
from vnbroker.broker.security.redaction import Redactor


# ─── TCBSCredentialConfig ────────────────────────────────────────────────────

class TestTCBSCredentialConfig:
    def test_creates_with_required_api_key(self):
        cfg = TCBSCredentialConfig(api_key="test-key")
        assert cfg.api_key == "test-key"
        assert cfg.base_url == _DEFAULT_BASE_URL
        assert cfg.timeout_seconds == 30.0
        assert cfg.auth_token is None

    def test_repr_does_not_expose_api_key(self):
        cfg = TCBSCredentialConfig(api_key="super-secret-key")
        repr_str = repr(cfg)
        assert "super-secret-key" not in repr_str
        assert "REDACTED" in repr_str

    def test_custom_base_url(self):
        cfg = TCBSCredentialConfig(api_key="k", base_url="https://custom.example.com")
        assert cfg.base_url == "https://custom.example.com"

    def test_auth_token_not_in_repr(self):
        cfg = TCBSCredentialConfig(api_key="k", auth_token="jwt-token")
        repr_str = repr(cfg)
        assert "jwt-token" not in repr_str


# ─── resolve_tcbs_credentials ────────────────────────────────────────────────

class TestResolveTCBSCredentials:
    def setup_method(self):
        """Xoá tất cả TCBS env vars trước mỗi test."""
        for var in _ENV_PRIORITY:
            os.environ.pop(var, None)

    def test_uses_explicit_api_key(self):
        cfg = resolve_tcbs_credentials(api_key="explicit-key")
        assert cfg.api_key == "explicit-key"

    def test_raises_when_no_api_key_available(self):
        with pytest.raises(ValueError, match="TCBS API key"):
            resolve_tcbs_credentials()

    def test_reads_primary_env_var(self):
        os.environ["VNBROKER_BROKER_TCBS_API_KEY"] = "from-primary-env"
        cfg = resolve_tcbs_credentials()
        assert cfg.api_key == "from-primary-env"
        del os.environ["VNBROKER_BROKER_TCBS_API_KEY"]

    def test_fallback_env_priority_order(self):
        """Chỉ set env var thứ 3 — phải đọc được nó khi 1 và 2 không có."""
        os.environ["TCBS_OPENAPI_API_KEY"] = "from-fallback-3"
        cfg = resolve_tcbs_credentials()
        assert cfg.api_key == "from-fallback-3"
        del os.environ["TCBS_OPENAPI_API_KEY"]

    def test_explicit_overrides_env(self):
        os.environ["VNBROKER_BROKER_TCBS_API_KEY"] = "env-key"
        cfg = resolve_tcbs_credentials(api_key="explicit-key")
        assert cfg.api_key == "explicit-key"
        del os.environ["VNBROKER_BROKER_TCBS_API_KEY"]

    def test_custom_base_url_passed_through(self):
        cfg = resolve_tcbs_credentials(api_key="k", base_url="https://staging.example.com")
        assert cfg.base_url == "https://staging.example.com"

    def test_default_base_url_when_not_provided(self):
        cfg = resolve_tcbs_credentials(api_key="k")
        assert cfg.base_url == _DEFAULT_BASE_URL

    def test_error_message_mentions_env_var_name(self):
        with pytest.raises(ValueError) as exc:
            resolve_tcbs_credentials()
        assert "VNBROKER_BROKER_TCBS_API_KEY" in str(exc.value)

    def test_whitespace_only_env_var_treated_as_missing(self):
        os.environ["VNBROKER_BROKER_TCBS_API_KEY"] = "   "
        with pytest.raises(ValueError, match="TCBS API key"):
            resolve_tcbs_credentials()
        del os.environ["VNBROKER_BROKER_TCBS_API_KEY"]

    def test_auth_token_passed_through(self):
        cfg = resolve_tcbs_credentials(api_key="k", auth_token="jwt.123")
        assert cfg.auth_token == "jwt.123"


# ─── Redactor ────────────────────────────────────────────────────────────────

class TestRedactorDict:
    def test_redacts_sensitive_key_lowercase(self):
        result = Redactor.redact_dict({"api_key": "secret", "symbol": "VNM"})
        assert result["api_key"] == Redactor.REDACTED
        assert result["symbol"] == "VNM"

    def test_redacts_case_insensitive(self):
        result = Redactor.redact_dict({"ApiKey": "secret", "OTP": "123456"})
        assert result["ApiKey"] == Redactor.REDACTED
        assert result["OTP"] == Redactor.REDACTED

    def test_does_not_mutate_original(self):
        original = {"api_key": "secret", "x": 1}
        Redactor.redact_dict(original)
        assert original["api_key"] == "secret"  # Không thay đổi gốc

    def test_nested_dict_redacted_recursively(self):
        data = {"outer": {"api_key": "secret", "safe": "ok"}}
        result = Redactor.redact_dict(data)
        assert result["outer"]["api_key"] == Redactor.REDACTED
        assert result["outer"]["safe"] == "ok"

    def test_list_values_with_nested_dicts(self):
        data = {"orders": [{"otp": "999"}, {"symbol": "VNM"}]}
        result = Redactor.redact_dict(data)
        assert result["orders"][0]["otp"] == Redactor.REDACTED
        assert result["orders"][1]["symbol"] == "VNM"

    def test_non_sensitive_keys_preserved(self):
        data = {"symbol": "VNM", "quantity": 100, "price": 80000.0}
        result = Redactor.redact_dict(data)
        assert result == data

    def test_empty_dict_returns_empty(self):
        assert Redactor.redact_dict({}) == {}

    def test_authorization_key_redacted(self):
        result = Redactor.redact_dict({"Authorization": "Bearer jwt.xxx"})
        assert result["Authorization"] == Redactor.REDACTED


class TestRedactorHeaders:
    def test_redacts_authorization_header(self):
        headers = {"Authorization": "Bearer jwt.xxx", "Content-Type": "application/json"}
        result = Redactor.redact_headers(headers)
        assert result["Authorization"] == Redactor.REDACTED
        assert result["Content-Type"] == "application/json"

    def test_preserves_other_headers(self):
        headers = {"X-Custom": "value", "Accept": "application/json"}
        result = Redactor.redact_headers(headers)
        assert result == headers

    def test_case_insensitive_authorization(self):
        headers = {"authorization": "Bearer jwt.xxx"}
        result = Redactor.redact_headers(headers)
        assert result["authorization"] == Redactor.REDACTED


class TestRedactorMaskAccountNo:
    def test_masks_long_account_no(self):
        masked = Redactor.mask_account_no("0123456789")
        assert masked == "******6789"
        assert "0123" not in masked

    def test_short_account_no_fully_masked(self):
        assert Redactor.mask_account_no("abc") == "****"

    def test_exactly_4_chars_fully_masked(self):
        assert Redactor.mask_account_no("6789") == "****"

    def test_last_4_chars_visible(self):
        masked = Redactor.mask_account_no("XY99887766")
        assert masked.endswith("7766")
