#!/usr/bin/env bash
# Gate G8: kiem LESSONS.md khong con STUB (dung dang loi, khong phai moi lan nhac)
#
# LUU Y THIET KE: LESSONS.md HOP LE khi nhac chuoi "eoffice-be" trong phan bai hoc
# (no mo ta chinh cai bug template mang ten du an khac). Vi vay KHONG duoc chan
# theo kieu `grep -q "eoffice-be"` — lam vay cong do VINH VIEN (bao nham), va mot
# cong bao nham se bi nguoi dung tat di trong mot tuan.
#
# Dang loi that can chan la DONG TIEU DE STUB: file bat dau bang
#   # Bai hoc tu quy trinh cho du an eoffice-be
# Tuc la dong KHONG-comment dau tien phai noi ve vnbroker.
set -u
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

LESSONS="docs/_workflow/LESSONS.md"

if [ ! -f "$LESSONS" ]; then
  echo "G8 BLOCK: thieu $LESSONS"
  exit 2
fi

# Dong khong-TRONG dau tien = dong phan biet stub voi ban da sua.
# KHONG duoc loc ca dong bat dau bang '#' — tieu de stub chinh la mot dong '# ...',
# va tieu de ban da sua cung vay. Chi loc dong trong.
FIRST_LINE="$(grep -vE '^[[:space:]]*$' "$LESSONS" | head -1)"

case "$FIRST_LINE" in
  *eoffice-be*)
    echo "G8 BLOCK: $LESSONS van la stub cho du an khac -> '$FIRST_LINE'"
    exit 2
    ;;
esac

if ! printf '%s' "$FIRST_LINE" | grep -qi "vnbroker"; then
  echo "G8 BLOCK: dong dau $LESSONS khong nhan vnbroker -> '$FIRST_LINE'"
  exit 2
fi

echo "G8 OK: $LESSONS da cap nhat cho vnbroker"
exit 0
