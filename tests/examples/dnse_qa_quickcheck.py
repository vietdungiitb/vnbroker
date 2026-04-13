"""Run DNSE integration test + smoke in one command.

Usage:
- python -m tests.examples.dnse_qa_quickcheck
"""

from __future__ import annotations

import os
import subprocess
import sys


_REQUIRED_ENV = ["DNSE_API_KEY", "DNSE_API_SECRET", "DNSE_ACCOUNT_NO"]


def _missing_env() -> list[str]:
    return [key for key in _REQUIRED_ENV if not os.getenv(key)]


def _run(cmd: list[str]) -> int:
    print("$", " ".join(cmd))
    proc = subprocess.run(cmd, check=False)
    return proc.returncode


def main() -> int:
    missing = _missing_env()
    if missing:
        print("Missing required environment variables:")
        for name in missing:
            print(f"- {name}")
        print("See .env.dnse.example for required keys.")
        return 2

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/integration/test_dnse_integration.py",
        "-q",
    ]
    smoke_cmd = [sys.executable, "-m", "tests.examples.dnse_e2e_smoke"]

    test_code = _run(pytest_cmd)
    smoke_code = _run(smoke_cmd)

    if test_code != 0 or smoke_code != 0:
        print(f"DNSE quickcheck failed: pytest={test_code}, smoke={smoke_code}")
        return 1

    print("DNSE quickcheck passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
