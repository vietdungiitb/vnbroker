"""Gate ngăn `vnbroker.core.base` tái sinh — 164 câu lệnh code chết đã xoá.

Bối cảnh
--------
`core/base/{registry,provider}.py` từng là registry đầu tiên của dự án. Commit
`dbcd81a` ("registry merge") thay nó bằng `core/registry.py` — cái đang chạy thật
(48 registration, `ProviderRegistry.get("quote", "vci")`) — nhưng quên dọn nhánh cũ.
Hai registry cùng tên, khác API, 0% coverage, không ai import: bẫy cho người đọc mới.

Bằng chứng đã thu thập TRƯỚC khi xoá, ở commit `f5de70d`:
- nó hoạt động độc lập (register → get_provider → get_provider_info);
- không module nào ngoài `core/base/` import nó.

File này giữ lại phần thứ hai dưới dạng gate: nếu ai đó vô tình tạo lại import
`core.base.*`, test đỏ ngay. Nếu cần hành vi cũ, khôi phục từ `git show f5de70d`.

Xem `docs/audit/AUDIT_REPORT_2026-10-01.md` §8 loại trừ đã kiểm chứng.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE_DIR = ROOT / "vnbroker" / "core" / "base"


# ------------------------------------------------------------- phần 2: không ai dùng


def test_no_module_outside_core_base_imports_it():
    """Không module nào ngoài `core/base/` import `core.base.*`.

    Đây là lý do xoá được: đây là code chết, không phải code thiếu test.
    """
    pattern = re.compile(r"core\.base\.(registry|provider)|from\s+vnbroker\.core\.base\b")
    offenders: list[str] = []

    for path in ROOT.rglob("*.py"):
        if "vnbroker/core/base" in path.as_posix():
            continue
        if any(
            part in {".venv", "__pycache__", "node_modules", ".git"}
            for part in path.parts
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if line.strip().startswith("#"):
                continue
            if pattern.search(line) and "__future__" not in line:
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()[:70]}")

    assert not offenders, (
        "Có module ĐANG DÙNG core.base — không được xoá:\n  "
        + "\n  ".join(offenders)
    )


def test_core_base_directory_is_gone():
    """Thư mục `core/base/` không được tồn tại — nếu quay lại là bẫy cũ."""
    assert not BASE_DIR.exists(), (
        f"{BASE_DIR.relative_to(ROOT)} đã xoá (commit f5de70d + bước dọn sau). "
        f"Nếu cần hành vi cũ: git show f5de70d — đừng tạo lại nhánh registry thứ hai."
    )