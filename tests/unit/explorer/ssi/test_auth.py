"""Unit tests for SSI explorer auth session (mock-only, no network)."""

from __future__ import annotations

import threading

import pytest

from vnbroker.broker.session import BrokerSession
from vnbroker.broker.ssi.exceptions import BrokerAuthError, BrokerError
from vnbroker.explorer.ssi._auth import (
    SSIExplorerSession,
    get_shared_session,
    reset_shared_sessions,
)


class _FakeAuth:
    """Minimal SSIAuthService double driving a real BrokerSession."""

    def __init__(self, session: BrokerSession) -> None:
        self._session = session
        self.authenticate_calls = 0
        self.refresh_calls = 0
        self.fail_refresh = False

    def authenticate(self) -> str:
        self.authenticate_calls += 1
        self._session.set_token("fake-token", expires_in_seconds=3600)
        return "fake-token"

    def refresh(self) -> str:
        self.refresh_calls += 1
        if self.fail_refresh:
            raise BrokerAuthError(
                message="refresh failed",
                code="NO_REFRESH_TOKEN",
                http_status=401,
            )
        self._session.set_token("fake-token-refreshed", expires_in_seconds=3600)
        return "fake-token-refreshed"


def _make_session() -> tuple[BrokerSession, _FakeAuth, SSIExplorerSession]:
    session = BrokerSession(provider="SSI")
    fake = _FakeAuth(session)
    explorer = SSIExplorerSession(
        api_key="test-ssi-key",
        api_secret="test-ssi-secret",
        _session=session,
        _auth_service=fake,  # type: ignore[arg-type]
    )
    return session, fake, explorer


class TestSSIExplorerSessionInit:
    """Credential resolution tests."""

    def test_raises_without_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing key/secret must fail fast with guidance."""
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_KEY", raising=False)
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_SECRET", raising=False)
        with pytest.raises(ValueError, match="SSI cần api_key và api_secret"):
            SSIExplorerSession()

    def test_accepts_direct_credentials(self) -> None:
        explorer = SSIExplorerSession(api_key="k", api_secret="s")
        assert explorer.has_credentials

    def test_accepts_env_credentials(
        self, ssi_keys: tuple[str, str]
    ) -> None:
        explorer = SSIExplorerSession()
        assert explorer.has_credentials


class TestEnsureToken:
    """Lazy token lifecycle tests (AC-A1.1-A1.3)."""

    def test_authenticate_once_for_two_calls(self) -> None:
        """2 ensure_token calls hit the service exactly once (AC-A1.2)."""
        _, fake, explorer = _make_session()
        first = explorer.ensure_token()
        second = explorer.ensure_token()
        assert first == second == "fake-token"
        assert fake.authenticate_calls == 1
        assert fake.refresh_calls == 0

    def test_expired_token_triggers_refresh(self) -> None:
        """Expired token uses refresh, not full authenticate (AC-A1.3)."""
        session, fake, explorer = _make_session()
        assert explorer.ensure_token() == "fake-token"
        session.set_token("old", expires_in_seconds=-10)
        assert explorer.ensure_token() == "fake-token-refreshed"
        assert fake.refresh_calls == 1
        assert fake.authenticate_calls == 1

    def test_failed_refresh_falls_back_to_authenticate(self) -> None:
        """Broken refresh re-authenticates instead of raising."""
        session, fake, explorer = _make_session()
        assert explorer.ensure_token() == "fake-token"
        fake.fail_refresh = True
        session.set_token("old", expires_in_seconds=-10)
        assert explorer.ensure_token() == "fake-token"
        assert fake.refresh_calls == 1
        assert fake.authenticate_calls == 2

    def test_broker_error_from_auth_propagates(self) -> None:
        """Real auth failures are not swallowed."""

        class _FailAuth(_FakeAuth):
            def authenticate(self) -> str:
                raise BrokerAuthError(
                    message="denied", code="DENIED", http_status=401
                )

        session = BrokerSession(provider="SSI")
        explorer = SSIExplorerSession(
            api_key="k",
            api_secret="s",
            _session=session,
            _auth_service=_FailAuth(session),  # type: ignore[arg-type]
        )
        with pytest.raises(BrokerError):
            explorer.ensure_token()

    def test_thread_safe_single_auth(self) -> None:
        """Concurrent ensure_token calls authenticate exactly once."""
        _, fake, explorer = _make_session()
        errors: list[BaseException] = []

        def _worker() -> None:
            try:
                explorer.ensure_token()
            except BaseException as exc:  # pragma: no cover - safety net
                errors.append(exc)

        threads = [threading.Thread(target=_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert fake.authenticate_calls == 1


class TestSharedSession:
    """Module-level shared session cache tests."""

    def test_same_credentials_share_instance(
        self, ssi_keys: tuple[str, str]
    ) -> None:
        reset_shared_sessions()
        try:
            first = get_shared_session()
            second = get_shared_session()
            assert first is second
        finally:
            reset_shared_sessions()

    def test_different_credentials_isolated(self) -> None:
        reset_shared_sessions()
        try:
            first = get_shared_session(api_key="k1", api_secret="s1")
            second = get_shared_session(api_key="k2", api_secret="s2")
            assert first is not second
        finally:
            reset_shared_sessions()
