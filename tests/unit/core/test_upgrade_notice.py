import pytest
from packaging import version as _version

from vnbroker.config import VERSION_REQUIREMENTS
from vnbroker.core.utils import upgrade


def _expected_channel_version() -> str:
    """Version cao nhat khai trong config — SSOT ma production code doc.

    KHONG hardcode "3.3.0"/"3.4.0": moi lan bump version la ca 3 test trong file
    nay cung hong mot luc (3.3.0 -> 3.4.0). Test phai khoa HANH VI, khong khoa
    con so.

    `check_version_sync.py` hien KHONG quet tests/, nen hardcode trong test lot
    qua gate — day la ly do drift khong bi bat.
    """
    return max((str(key).strip() for key in VERSION_REQUIREMENTS), key=_version.parse)


@pytest.mark.unit
@pytest.mark.core
def test_get_current_github_channel_version_uses_codebase_version(monkeypatch):
    # Metadata cua package van o 1.x; ham phai doc version trong code.
    monkeypatch.setattr(upgrade, "get_version", lambda package: "1.0.0")

    resolved = upgrade._get_current_github_channel_version()

    assert resolved == _expected_channel_version()
    assert resolved != "1.0.0"


@pytest.mark.unit
@pytest.mark.core
def test_get_github_version_diagnostics_reports_expected_fields(monkeypatch):
    monkeypatch.setattr(upgrade, "get_version", lambda package: "1.0.0")
    monkeypatch.setattr(upgrade, "_get_github_latest_release", lambda *args, **kwargs: "3.5.0")

    diagnostics = upgrade.get_github_version_diagnostics()

    assert diagnostics["package"] == "vnbroker"
    assert diagnostics["github_repo"] == "vietdungiitb/vnbroker"
    assert diagnostics["package_metadata_version"] == "1.0.0"
    assert diagnostics["current_github_channel_version"] == _expected_channel_version()
    assert diagnostics["latest_github_release"] == "3.5.0"


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
    monkeypatch.setattr(upgrade, "_get_github_latest_release", lambda *args, **kwargs: "3.5.0")
    monkeypatch.setattr(
        upgrade,
        "_display_message",
        lambda msg, environment, is_warning=False: messages.append(msg),
    )

    upgrade._check_version_updates()

    assert len(messages) == 1
    assert f"Current: {_expected_channel_version()}" in messages[0]
    assert "package metadata" not in messages[0]
    assert "git+https://github.com/vietdungiitb/vnbroker.git@v3.5.0#egg=vnbroker" in messages[0]
