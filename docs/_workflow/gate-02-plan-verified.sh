#!/usr/bin/env bash
# Gate G2: chặn nếu không có docs/PLAN_*.md, hoặc file mới nhất thiếu mục bắt buộc.
# Exit 2 = chặn; Exit 0 = cho qua.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

# Tìm tất cả file PLAN_*.md, LOẠI TRỪ PLAN_AUDIT*.md.
# SUA LOI (WP-CLEANUP-01): glob `docs/PLAN_*.md` khop luon `docs/PLAN_AUDIT.md`
# — do la BAN AUDIT chu khong phai ke hoach, va no khong co cac muc 1/2/6/9 nen
# cong chan nham du lieu hop le (false BLOCK).
PLAN_FILES=$(ls docs/PLAN_*.md 2>/dev/null | grep -v 'PLAN_AUDIT' || true)

if [ -z "$PLAN_FILES" ]; then
  echo "GATE G2 BLOCK: không tìm thấy file docs/PLAN_*.md nào."
  echo "Cần ít nhất một file plan để verify."
  exit 2
fi

# Lấy file plan MỚI NHẤT theo mtime.
# SUA LOI (WP-CLEANUP-01): ban truoc dung `sort -r | head -1` — sap xep theo
# ALPHABET, nen mot plan moi hon nhung ten dung truoc (vd `PLAN_AAA.md`) KHONG
# bao gio duoc kiem. Da chung minh: tao `PLAN_AAA.md` thieu het muc bat buoc,
# gate van chon `PLAN_WORKFLOW_REPAIR.md` va bao OK (exit 0) — cong kiem nham
# file, tuong duong cong chet.
# Uu tien tham so truyen vao de kiem dung plan cua tung WP.
LATEST_PLAN="${1:-}"
if [ -z "$LATEST_PLAN" ]; then
  LATEST_PLAN=$(ls -t $PLAN_FILES 2>/dev/null | head -1)
fi

if [ -z "$LATEST_PLAN" ] || [ ! -f "$LATEST_PLAN" ]; then
  echo "GATE G2 BLOCK: khong xac dinh duoc file plan de kiem."
  exit 2
fi

# Các mục bắt buộc
REQUIRED_SECTIONS=(
  "## 1. Mục tiêu"
  "## 2. In-scope"
  "## 6. Cách kiểm chứng"
  "## 9. Điều kiện Done"
)

MISSING_SECTIONS=()
for section in "${REQUIRED_SECTIONS[@]}"; do
  if ! grep -q "$section" "$LATEST_PLAN"; then
    MISSING_SECTIONS+=("$section")
  fi
done

if [ ${#MISSING_SECTIONS[@]} -gt 0 ]; then
  echo "GATE G2 BLOCK: file plan '$LATEST_PLAN' thiếu các mục bắt buộc:"
  for section in "${MISSING_SECTIONS[@]}"; do
    echo "  - $section"
  done
  exit 2
fi

echo "GATE G2 OK: file plan '$LATEST_PLAN' đủ các mục bắt buộc."
exit 0
