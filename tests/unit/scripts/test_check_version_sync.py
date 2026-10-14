"""Gate phải bắt được ``__version__`` lệch với ``pyproject.toml``.

Bối cảnh (đo 2026-10-14): ``vnbroker/__init__.py:8-10`` đọc version qua
``importlib.metadata.version("vnbroker")``. Cài **editable** thì ``dist-info``
KHÔNG được đóng lại khi bump version trong ``pyproject.toml``, nên:

    pyproject.toml            -> 3.7.2
    vnbroker.__version__      -> 3.4.0

``scripts/check_version_sync.py`` cũ báo xanh vì nó chỉ grep *literal* trong
pyproject / README / CLAUDE.md / config.py / tests — không chạm tới
``importlib.metadata``. Đó là loại gate "xanh vì kiểm sai mặt phẳng".

Vì vậy test ở đây khóa **hàm so sánh**, không khóa môi trường: phần môi trường
thuộc về gate (chạy trong ``check_all.ps1``), không nên làm test suite đỏ theo
máy.
"""
from __future__ import annotations

import importlib.metadata
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_version_sync import read_version, runtime_metadata_drift  # noqa: E402


def test_same_version_is_not_a_drift():
    assert runtime_metadata_drift(declared="3.7.2", installed="3.7.2") is None


def test_drift_is_reported_with_both_versions():
    reason = runtime_metadata_drift(declared="3.7.2", installed="3.4.0")
    assert reason is not None
    assert "3.7.2" in reason
    assert "3.4.0" in reason


def test_drift_message_says_how_to_fix_it():
    """Không đủ chỉ ra lệch — phải chỉ ra cách sửa, nếu không người đọc
    không biết phải làm gì và gate sẽ bị tắt."""
    reason = runtime_metadata_drift(declared="3.7.2", installed="3.4.0")
    assert reason is not None
    assert "pip install" in reason


def test_missing_distribution_is_not_a_drift():
    """Chưa cài (`PackageNotFoundError`) thì gate KHÔNG ĐO ĐƯỢC.

    Báo đỏ lúc đó là báo sai: mọi người đều có thể chạy test từ cây nguồn
    chưa cài. Đây cùng bậc với L-E04 — "không đo được" khác "đo ra sai".
    """
    assert runtime_metadata_drift(declared="3.7.2", installed=None) is None


def test_pyproject_still_parses_as_the_single_source():
    """Hàm đọc nguồn sự thật phải còn chạy được — gate mới đứng được trên nó."""
    version = read_version()
    assert version.count(".") == 2
    assert all(part.isdigit() for part in version.split("."))


def test_declared_version_matches_the_installed_distribution_or_the_gate_fails():
    """Fail-before/pass-after thật cho chính lỗi F-01.

    Đây là assertion duy nhất chạm môi trường: nó đọc
    ``importlib.metadata`` — cùng nguồn mà ``vnbroker.__version__`` đọc.
    Nếu ``pip install -e .`` cũ, dòng này đỏ và nói đúng nguyên nhân.
    Skip khi chưa cài: xem ``test_missing_distribution_is_not_a_drift``.
    """
    installed = importlib.metadata.version("vnbroker")
    assert runtime_metadata_drift(declared=read_version(), installed=installed) is None, (
        f"pyproject={read_version()} nhưng dist-info={installed}; "
        "chạy `pip install -e .` lại để đóng lại metadata"
    )
