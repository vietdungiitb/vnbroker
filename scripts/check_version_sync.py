"""Fail CI when version declarations drift from pyproject.toml (single source).

Checks:
- ``pyproject.toml`` ``version`` (source of truth; runtime uses importlib.metadata).
- ``README.md`` first version badge (``> **vX.Y.Z**``).
- ``CLAUDE.md`` ``Current version: **X.Y.Z**`` (allows a ``(vA.B-dev ...)`` suffix note).
- ``vnbroker/config.py`` ``VERSION_REQUIREMENTS`` keys include the version.

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

    print(f"version-sync OK: {version} (pyproject, README, CLAUDE.md, config.py)")


if __name__ == "__main__":
    sys.exit(main())
