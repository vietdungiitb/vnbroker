#!/usr/bin/env bash
# Gate G1: chặn nếu không tìm thấy docs/PLAN_AUDIT*.md nào chứa verdict PASS.
# Exit 2 = chặn; Exit 0 = cho qua.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

# Tìm tất cả file PLAN_AUDIT*.md
AUDIT_FILES=$(ls docs/PLAN_AUDIT*.md 2>/dev/null)

if [ -z "$AUDIT_FILES" ]; then
  echo "GATE G1 BLOCK: không tìm thấy file docs/PLAN_AUDIT*.md nào."
  echo "Cần ít nhất một file PLAN_AUDIT*.md chứa verdict PASS."
  exit 2
fi

# Dùng grep -l để tìm file chứa "PASS" (dòng verdict)
PASS_FILES=$(grep -l "PASS" $AUDIT_FILES 2>/dev/null)

if [ -z "$PASS_FILES" ]; then
  echo "GATE G1 BLOCK: không file PLAN_AUDIT*.md nào chứa verdict PASS."
  echo "Các file tìm thấy: $AUDIT_FILES"
  echo "Cần ít nhất một file có dòng '## Verdict: PASS' hoặc tương đương."
  exit 2
fi

echo "GATE G1 OK: tìm thấy file audit PASS: $PASS_FILES"
exit 0
