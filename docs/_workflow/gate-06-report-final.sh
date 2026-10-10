#!/usr/bin/env bash
# Gate G6: chặn nếu thiếu docs/REPORT_FINAL.md, hoặc file không chứa chuỗi GATE.
# Exit 2 = chặn; Exit 0 = cho qua.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

# Kiểm tra REPORT_FINAL.md tồn tại
if [ ! -f "docs/REPORT_FINAL.md" ]; then
  echo "GATE G6 BLOCK: không tìm thấy docs/REPORT_FINAL.md."
  echo "Cần file báo cáo cuối cùng để xác nhận gate."
  exit 2
fi

# Kiểm tra file chứa chuỗi "GATE" (xác nhận gate)
if ! grep -q "GATE" "docs/REPORT_FINAL.md"; then
  echo "GATE G6 BLOCK: docs/REPORT_FINAL.md không chứa chuỗi 'GATE'."
  echo "File báo cáo cần xác nhận đã qua các gate."
  exit 2
fi

echo "GATE G6 OK: REPORT_FINAL.md tồn tại và chứa xác nhận GATE."
exit 0
