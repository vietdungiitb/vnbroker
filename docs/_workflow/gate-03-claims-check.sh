#!/usr/bin/env bash
# Gate G3: chặn nếu thiếu docs/CLAIMS.md, hoặc check-overlap.cjs exit ≠ 0.
# Exit 2 = chặn; Exit 0 = cho qua.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

# Kiểm tra CLAIMS.md tồn tại
if [ ! -f "docs/CLAIMS.md" ]; then
  echo "GATE G3 BLOCK: không tìm thấy docs/CLAIMS.md."
  echo "Cần file CLAIMS.md để quản lý claim giữa các agent."
  exit 2
fi

# Đường dẫn check-overlap.cjs (Node script trong skill multi-agent-workflow)
CHECK_OVERLAP="C:/Users/Pham Viet Dung/AppData/Local/hermes/skills/software-development/multi-agent-workflow/scripts/check-overlap.cjs"

if [ ! -f "$CHECK_OVERLAP" ]; then
  echo "GATE G3 BLOCK: không tìm thấy check-overlap.cjs tại:"
  echo "  $CHECK_OVERLAP"
  exit 2
fi

# Chạy check-overlap.cjs với node
# Node là chương trình Windows gốc nên dùng đường dẫn C:/... (không phải /c/...)
node "$CHECK_OVERLAP" --file docs/CLAIMS.md
OVERLAP_EXIT=$?

if [ $OVERLAP_EXIT -ne 0 ]; then
  echo "GATE G3 BLOCK: check-overlap.cjs exit $OVERLAP_EXIT (không phải 0)."
  echo "Có chồng lặp claim giữa các agent hoặc lỗi CLI."
  exit 2
fi

echo "GATE G3 OK: CLAIMS.md hợp lệ, không chồng lặp."
exit 0
