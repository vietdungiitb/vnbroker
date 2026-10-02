"""Fail CI when version declarations drift from pyproject.toml (single source).

Checks:
- ``pyproject.toml`` ``version`` (source of truth; runtime uses importlib.metadata).
- ``README.md`` first version badge (``> **vX.Y.Z**``).
- ``CLAUDE.md`` ``Current version: **X.Y.Z**`` (allows a ``(vA.B-dev ...)`` suffix note).
- ``vnbroker/config.py`` ``VERSION_REQUIREMENTS`` keys include the version.
- ``tests/**/*.py`` contains no hardcoded version literal (GĐ4).

Usage:
    python scripts/check_version_sync.py
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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

    print(
        f"version-sync OK: {version} "
        f"(pyproject, README, CLAUDE.md, config.py, tests/)"
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
