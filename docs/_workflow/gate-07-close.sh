#!/usr/bin/env bash
# Gate G7: kiem tra REPORT_FINAL.md co du GATE 1-5
set -u
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

REPORT="docs/REPORT_FINAL.md"

if [ ! -f "$REPORT" ]; then
  echo "G7 BLOCK: thieu $REPORT"
  exit 2
fi

MISSING=""
for g in "GATE 1" "GATE 2" "GATE 3" "GATE 4" "GATE 5"; do
  if ! grep -q "$g" "$REPORT"; then
    MISSING="$MISSING $g"
  fi
done

if [ -n "$MISSING" ]; then
  echo "G7 BLOCK: $REPORT thieu:$MISSING"
  exit 2
fi

echo "G7 OK: $REPORT co du GATE 1-5"
exit 0
