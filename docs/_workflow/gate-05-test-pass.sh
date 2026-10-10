#!/usr/bin/env bash
# Gate G5: chay pytest that cho vnbroker (~140s)
# Uu tien .venv/Scripts/python.exe, fallback python
set -u
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

if [ -x ".venv/Scripts/python.exe" ]; then
  PY=".venv/Scripts/python.exe"
else
  PY="python"
fi

# Luu y: cong nay chay ~140s
"$PY" -m pytest tests/ -q --timeout=180
RC=$?

if [ "$RC" -ne 0 ]; then
  echo "G5 BLOCK: pytest exit=$RC"
  exit 2
fi

echo "G5 OK: pytest passed"
exit 0
