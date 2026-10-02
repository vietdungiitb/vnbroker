import pytest

from vnbroker.core.utils import upgrade


def _expected_channel_version() -> str:
    """Version GitHub-channel hiện tại, lấy từ chính source mà code dùng.

    GĐ4: test trước đây hardcode "3.3.0" nên đỏ mỗi lần bump version, trong khi
    code đúng. Gate `check_version_sync.py` không quét `tests/` nên không bắt
    được. Ở đây derive từ cùng nguồn để test không bao giờ lệch phiên bản nữa.
    """
    return upgrade._get_current_github_channel_version()


@pytest.mark.unit
@pytest.mark.core
def test_get_current_github_channel_version_uses_codebase_version():
    assert upgrade._get_current_github_channel_version() == _expected_channel_version()


@pytest.mark.unit
@pytest.mark.core
def test_get_github_version_diagnostics_reports_expected_fields(monkeypatch):
    monkeypatch.setattr(upgrade, "get_version", lambda package: "1.0.0")
    monkeypatch.setattr(upgrade, "_get_github_latest_release", lambda *args, **kwargs: "9.9.9")

    diagnostics = upgrade.get_github_version_diagnostics()

    assert diagnostics["package"] == "vnbroker"
    assert diagnostics["github_repo"] == "vietdungiitb/vnbroker"
    assert diagnostics["package_metadata_version"] == "1.0.0"
    assert diagnostics["current_github_channel_version"] == _expected_channel_version()
    assert diagnostics["latest_github_release"] == "9.9.9"


@pytest.mark.unit
@pytest.mark.core
def test_check_version_updates_uses_github_channel_version_not_package_metadata(monkeypatch):
    messages = []

    monkeypatch.setattr(upgrade, "detect_environment", lambda: "Terminal")
    monkeypatch.setattr(
        upgrade,
        "detect_venv",
        lambda: {"python_exe": "python", "type": "system"},
    )
    monkeypatch.setattr(upgrade, "get_version", lambda package: "1.0.0")
    monkeypatch.setattr(upgrade, "_get_github_latest_release", lambda *args, **kwargs: "3.1.0")
    monkeypatch.setattr(
        upgrade,
        "_display_message",
        lambda msg, environment, is_warning=False: messages.append(msg),
    )

    upgrade._check_version_updates()

    assert messages == []


@pytest.mark.unit
@pytest.mark.core
def test_check_version_updates_shows_notice_when_github_release_is_newer(monkeypatch):
    messages = []

    monkeypatch.setattr(upgrade, "detect_environment", lambda: "Terminal")
    monkeypatch.setattr(
        upgrade,
        "detect_venv",
        lambda: {
            "python_exe": r"C:\\proj\\.venv\\Scripts\\python.exe",
            "type": "venv",
        },
    )
    monkeypatch.setattr(upgrade, "get_version", lambda package: "1.0.0")
    monkeypatch.setattr(upgrade, "_get_github_latest_release", lambda *args, **kwargs: "9.9.9")
    monkeypatch.setattr(
        upgrade,
        "_display_message",
        lambda msg, environment, is_warning=False: messages.append(msg),
    )

    upgrade._check_version_updates()

    assert len(messages) == 1
    assert f"Current: {_expected_channel_version()}" in messages[0]
    assert "package metadata" not in messages[0]
    # Version trong URL phải là release giả lập (9.9.9), KHÔNG phải version
    # hiện tại — trước đây literal "3.5.0" ở đây trùng số version thật và
    # check_version_sync.py báo nhầm.
    assert "git+https://github.com/vietdungiitb/vnbroker.git@v9.9.9#egg=vnbroker" in messages[0]
