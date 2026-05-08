"""Regression tests to prevent legacy guest quota messaging from returning."""

from __future__ import annotations

from pathlib import Path


BANNED_RUNTIME_PHRASES = (
    "rate limit exceeded",
    "20 requests/phÃºt",
    "20 requests/minute",
    "guest (20 requests/phÃºt)",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").lower()


def test_legacy_quota_auth_source_file_is_not_present_in_workspace():
    legacy_auth_module = _repo_root() / "vnbroker" / "core" / "utils" / "auth.py"

    assert not legacy_auth_module.exists()


def test_exceptions_source_no_longer_contains_legacy_phrase():
    exceptions_file = _repo_root() / "vnbroker" / "core" / "exceptions.py"
    content = _read_text(exceptions_file)

    assert "rate limit exceeded" not in content
    assert "temporarily throttled" in content


def test_fmp_source_uses_throttled_message_instead_of_legacy_phrase():
    fmp_config_file = _repo_root() / "vnbroker" / "connector" / "fmp" / "config.py"
    content = _read_text(fmp_config_file)

    assert "rate limit exceeded" not in content
    assert "temporarily throttled requests" in content


def test_runtime_package_source_does_not_contain_guest_quota_text():
    package_root = _repo_root() / "vnbroker"

    for py_file in package_root.rglob("*.py"):
        content = _read_text(py_file)
        for phrase in BANNED_RUNTIME_PHRASES:
            assert phrase not in content, (
                f"Found banned phrase '{phrase}' in {py_file}"
            )
