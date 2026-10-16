"""Fail CI when version declarations drift from pyproject.toml (single source).

Checks:
- ``pyproject.toml`` ``version`` (source of truth; runtime uses importlib.metadata).
- ``README.md`` first version badge (``> **vX.Y.Z**``).
- ``CLAUDE.md`` ``Current version: **X.Y.Z**`` (allows a ``(vA.B-dev ...)`` suffix note).
- ``vnbroker/config.py`` ``VERSION_REQUIREMENTS`` keys include the version.
- ``tests/**/*.py`` contains no hardcoded version literal (GĐ4).
- **installed distribution metadata** matches ``pyproject.toml`` (F-01, 2026-10-14).

Usage:
    python scripts/check_version_sync.py
"""

from __future__ import annotations

import re
import sys
import tomllib
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Console Windows mặc định là cp1252, in ra sẽ `UnicodeEncodeError` ngay giữa
# lúc gate đang cần nói lý do đỏ. Thông điệp thất bại mà không in được thì
# mất tác dụng — vì vậy ép UTF-8 với fallback `replace` TRƯỚC khi in bất cứ thứ gì.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")


def read_version() -> str:
    with open(ROOT / "pyproject.toml", "rb") as fh:
        data = tomllib.load(fh)
    version = str(data["project"]["version"]).strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"pyproject version is not X.Y.Z: {version!r}")
    return version


def fail(message: str) -> None:
    print(f"version-sync FAILED: {message}")
    raise SystemExit(1)


def runtime_metadata_drift(declared: str, installed: str | None) -> str | None:
    """So ``pyproject.toml`` với ``importlib.metadata`` — mặt phẳng còn thiếu.

    ``vnbroker/__init__.py`` đọc version qua ``importlib.metadata``. Cài
    **editable** thì ``dist-info`` không được đóng lại khi bump version, nên
    ``vnbroker.__version__`` có thể thấp hơn thật nhiều bản (đo 2026-10-14:
    pyproject 3.7.2 vs ``__version__`` 3.4.0). Người dùng đọc version sai sẽ
    cache sai — nên đây là lỗi dữ liệu, không phải lỗi trình bày.

    Args:
        declared: version khai trong ``pyproject.toml``.
        installed: version đọc được từ distribution, hoặc ``None`` nếu chưa cài.

    Returns:
        Chuỗi mô tả lệch (kèm cách sửa), hoặc ``None`` khi không lệch /
        không đo được.
    """
    if installed is None:
        # Chưa cài => KHÔNG ĐO ĐƯỢC. Báo đỏ ở đây là báo sai, vì mọi người đều
        # có thể chạy test/gate từ cây nguồn chưa cài. Cùng bậc L-E04.
        return None
    if declared == installed:
        return None
    return (
        f"pyproject.toml khai {declared} nhưng distribution đang cài là "
        f"{installed} — `vnbroker.__version__` sẽ trả {installed}. "
        f"Đây là metadata của bản cài editable không được đóng lại khi bump "
        f"version. Sửa: `pip install -e .` (hoặc `pip install --force-reinstall "
        f"-e .`) rồi chạy lại gate."
    )


def check_runtime_metadata(declared: str) -> None:
    """Fail khi metadata bản cài lệch version khai trong ``pyproject.toml``."""
    try:
        installed = _distribution_version("vnbroker")
    except PackageNotFoundError:
        print(
            "version-sync: CHƯA CÀI distribution `vnbroker` — bỏ qua kiểm tra "
            "metadata (không đo được, không phải lệch)."
        )
        return
    reason = runtime_metadata_drift(declared=declared, installed=installed)
    if reason is not None:
        fail(reason)


def main() -> None:
    version = read_version()

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"> \*\*v(\d+\.\d+\.\d+)\*\*", readme)
    if match is None:
        fail("README.md has no '> **vX.Y.Z**' badge line")
    if match.group(1) != version:
        fail(f"README.md says v{match.group(1)}, pyproject says {version}")

    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    match = re.search(r"Current version:\s*\*\*(\d+\.\d+\.\d+)\*\*", claude)
    if match is None:
        fail("CLAUDE.md has no 'Current version: **X.Y.Z**' line")
    if match.group(1) != version:
        fail(f"CLAUDE.md says {match.group(1)}, pyproject says {version}")

    config = (ROOT / "vnbroker" / "config.py").read_text(encoding="utf-8")
    if f'"{version}"' not in config:
        fail(f"vnbroker/config.py has no VERSION_REQUIREMENTS entry for {version}")

    check_tests_derive_version(version)
    check_runtime_metadata(version)

    print(
        f"version-sync OK: {version} "
        f"(pyproject, README, CLAUDE.md, config.py, tests/, dist metadata)"
    )


def check_tests_derive_version(version: str) -> None:
    """Fail khi test khai báo phiên bản hiện tại bằng literal.

    Bài học từ lần làm sai đầu tiên: KHÔNG thể quét mọi literal ``"X.Y.Z"``
    trong ``tests/`` — phần lớn là dữ liệu test hợp lệ (monkeypatch giả lập
    ``1.0.0``, release giả lập ``3.5.0``). Báo đỏ chúng là báo nhầm, và một
    gate báo nhầm thì không còn tác dụng.

    Lỗi thật cần chặn có đặc điểm riêng: test khẳng định phiên bản hiện tại bằng
    literal so sánh (``== "3.4.0"``, ``"Current: 3.4.0"`` trong chuỗi), hoặc dùng
    hàm ``_get_current_github_channel_version()`` mà không có helper derive.

    Args:
        version: Phiên bản hiện tại theo ``pyproject.toml``.
    """
    derive_fn = "_get_current_github_channel_version"
    helper = "_expected_channel_version"
    offenders = []
    eq_pat = re.compile(r'==\s*"' + re.escape(version) + r'"')
    cur_pat = re.compile(r'"Current:\s*' + re.escape(version))
    fstring_pat = re.compile('f["\']Current:')

    for path in sorted((ROOT / "tests").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        rel = path.relative_to(ROOT)

        for lineno, line in enumerate(lines, start=1):
            if line.strip().startswith("#"):
                continue
            if fstring_pat.search(line):
                continue  # đã derive bằng f-string
            if eq_pat.search(line):
                offenders.append(
                    "%s:%d: so sánh version bằng literal %r — hãy derive từ nguồn"
                    % (rel, lineno, version)
                )
            elif cur_pat.search(line):
                offenders.append(
                    "%s:%d: chứa literal 'Current: %s' — hãy dùng f-string derive"
                    % (rel, lineno, version)
                )

        if derive_fn in text and helper not in text:
            lineno = next(
                (i for i, ln in enumerate(lines, start=1) if derive_fn in ln), 0
            )
            offenders.append(
                "%s:%d: gọi %s() mà không có helper derive — sẽ đỏ mỗi lần bump version"
                % (rel, lineno, derive_fn)
            )

    if offenders:
        fail(
            "tests/ khai báo phiên bản hiện tại bằng literal:\n  "
            + "\n  ".join(offenders)
        )


if __name__ == "__main__":
    sys.exit(main())
