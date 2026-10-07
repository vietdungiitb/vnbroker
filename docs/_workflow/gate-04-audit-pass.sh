#!/usr/bin/env bash
# Gate G4: kiem tra audit gan nhat co Verdict PASS + confidence high
#
# Cach dung:  bash gate-04-audit-pass.sh [duong_dan_audit]
#   - Co tham so    -> kiem dung file do (dung cho audit cua tung WP).
#   - Khong tham so -> chon file audit MOI NHAT trong CA HAI noi:
#     docs/AUDIT_*.md va docs/audit/*.md.
#
# SUA LOI (WP-CLEANUP-01): ban truoc chi glob `docs/AUDIT_*.md` nen
#   1) bo sot toan bo `docs/audit/` (chu thuong), va
#   2) chon nham file audit cu tu 2026-09-23 roi bao BLOCK sai.
# Cong bao nham te hon cong chet: no day nguoi dung di truy nguyen nham cho.
set -u
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

AUDIT_FILE="${1:-}"
if [ -z "$AUDIT_FILE" ]; then
  AUDIT_FILE="$(ls -t docs/AUDIT_*.md docs/audit/*.md 2>/dev/null | head -1)"
fi

if [ -z "$AUDIT_FILE" ] || [ ! -f "$AUDIT_FILE" ]; then
  echo "G4 BLOCK: khong tim thay file audit (da tim docs/AUDIT_*.md va docs/audit/*.md)"
  exit 2
fi

if ! grep -qi "Verdict" "$AUDIT_FILE" || ! grep -qi "PASS" "$AUDIT_FILE"; then
  echo "G4 BLOCK: $AUDIT_FILE khong co Verdict PASS"
  exit 2
fi

if ! grep -qi "confidence" "$AUDIT_FILE" || ! grep -qi "high" "$AUDIT_FILE"; then
  echo "G4 BLOCK: $AUDIT_FILE khong co confidence high"
  exit 2
fi

echo "G4 OK: $AUDIT_FILE — Verdict PASS, confidence high"
exit 0
