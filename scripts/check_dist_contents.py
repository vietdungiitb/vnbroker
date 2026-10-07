"""Fail CI when a built wheel/sdist ships anything but the library package.

Cổng này tồn tại vì một lỗi thật của v3.5.0: `[tool.setuptools] packages =
{ find = {} }` bị setuptools phân giải thành PEP420 namespace finder, mà finder
đó có ``DEFAULT_EXCLUDE = []`` — nên `tests/` và `scripts/` lọt vào top-level
``site-packages`` của người dùng, và cây ``build/`` cũ trên máy dev bị quét
theo khiến cùng một commit sinh hai artifact khác nhau.

`twine check` KHÔNG bắt được lỗi này: nó kiểm metadata và README render, không
kiểm danh sách file. Vì vậy cần cổng riêng, chạy trên artifact thật.

Usage:
    python scripts/check_dist_contents.py dist/
"""

from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path

# Chỉ những top-level này được phép có mặt trong wheel.
ALLOWED_WHEEL_TOP = {"vnbroker"}

# Top-level trong sdist: file gốc của dự án + package thư viện + metadata build.
# `scripts/` nằm trong sdist vì setuptools tự thêm (dự án có package `scripts`
# theo nghĩa namespace); đó là script CI, không phải code người dùng import.
ALLOWED_SDIST_TOP = {
    "vnbroker",  # package
    "PKG-INFO",
    "pyproject.toml",
    "setup.cfg",  # setuptools tự sinh trong sdist
    "README.md",
    "LICENSE.md",
    "MANIFEST.in",
    "scripts",  # script CI (check_version_sync, check_mypy_baseline)
    "tests",  # giữ lại có chủ đích: sdist cần test để đóng gói lại
}

# Tên file bị cấm ở BẤT KỲ đâu trong artifact (rác dev / bí mật).
FORBIDDEN_NAME_PATTERNS = (
    ".env",
    ".venv",
    "debug_",
    "login_",
    "smoke_test",
    "regression_test",
    "test_with_jwt",
    ".sqlite",
    ".jwt",
)


def _fail(lines: list[str]) -> None:
    print("dist-contents FAILED:")
    for line in lines:
        print(f"  {line}")
    raise SystemExit(1)


def check_wheel(path: Path) -> list[str]:
    """Trả về danh sách lỗi của một wheel."""
    problems: list[str] = []
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()

    tops = {n.split("/")[0] for n in names}
    for top in sorted(tops):
        # dist-info của chính package này là hợp lệ.
        if top.endswith(".dist-info"):
            continue
        if top not in ALLOWED_WHEEL_TOP:
            problems.append(
                f"{path.name}: top-level {top!r} không được phép trong wheel "
                f"(chỉ cho phép {sorted(ALLOWED_WHEEL_TOP)} + *.dist-info)"
            )

    for name in names:
        base = name.rsplit("/", 1)[-1]
        for pattern in FORBIDDEN_NAME_PATTERNS:
            if pattern in base:
                problems.append(f"{path.name}: file bị cấm {name!r} (khớp {pattern!r})")
    return problems


def check_sdist(path: Path) -> list[str]:
    """Trả về danh sách lỗi của một sdist."""
    problems: list[str] = []
    with tarfile.open(path) as tf:
        names = tf.getnames()

    # Bỏ qua thư mục gốc dạng 'vnbroker-3.5.0/'.
    tops: set[str] = set()
    for name in names:
        parts = name.split("/")
        if len(parts) > 1:
            tops.add(parts[1])
    # Egg-info do setuptools sinh ra trong sdist.
    tops = {t for t in tops if not t.endswith(".egg-info")}

    for top in sorted(tops):
        if top not in ALLOWED_SDIST_TOP:
            problems.append(
                f"{path.name}: top-level {top!r} không được phép trong sdist "
                f"(cho phép {sorted(ALLOWED_SDIST_TOP)} + *.egg-info)"
            )

    for name in names:
        base = name.rsplit("/", 1)[-1]
        for pattern in FORBIDDEN_NAME_PATTERNS:
            if pattern in base:
                problems.append(f"{path.name}: file bị cấm {name!r} (khớp {pattern!r})")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2

    dist_dir = Path(argv[1])
    if not dist_dir.is_dir():
        _fail([f"{dist_dir} không phải thư mục"])

    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if not wheels and not sdists:
        _fail([f"{dist_dir} không có .whl hoặc .tar.gz nào"])

    problems: list[str] = []
    for wheel in wheels:
        problems.extend(check_wheel(wheel))
    for sdist in sdists:
        problems.extend(check_sdist(sdist))

    if problems:
        _fail(problems)

    print(
        f"dist-contents OK: {len(wheels)} wheel, {len(sdists)} sdist "
        f"— không có top-level lạ, không có file bị cấm"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
