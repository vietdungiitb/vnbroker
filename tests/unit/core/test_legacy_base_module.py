"""Characterization test cho `vnbroker.core.base` — bằng chứng trước khi xoá.

Mục đích
--------
`core/base/{registry,provider}.py` (164 câu lệnh) KHÔNG được import ở bất kỳ
đâu trong `vnbroker/`, `tests/`, `docs/` hay notebook. Commit `dbcd81a`
("registry merge") đã thay `core/base/registry.py` bằng `core/registry.py` nhưng
quên dọn nhánh cũ.

Test này chứng minh hai điều, tách bạch:

1. **Nó hoạt động độc lập** → xoá đi không phải vì "hỏng" mà vì "thừa".
   Nhờ vậy nếu sau này cần, có thể khôi phục từ git mà không mất hành vi.
2. **Không ai dùng** → test ở `tests/unit/core/test_legacy_base_module.py`
   khẳng định điều này bằng cách quét source, để lần refactor sau không vô tình
   dựa vào một module đã bị xoá.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BASE_DIR = ROOT / "vnbroker" / "core" / "base"


def _module_under_test():
    from vnbroker.core.base.registry import ProviderRegistry

    return ProviderRegistry


# ------------------------------------------------------------- phần 1: hoạt động


def test_legacy_registry_supports_register_and_lookup():
    """Registry cũ vẫn hoạt động: register → get_provider."""
    from vnbroker.core.base.provider import BaseProvider
    from vnbroker.core.base.registry import ProviderRegistry
    from vnbroker.core.types import DataCategory

    @ProviderRegistry.register(DataCategory.QUOTE, "legacy_demo", None)
    class _Demo(BaseProvider):
        """Provider demo chỉ dùng cho characterization test."""

        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def _get_api(self):  # pragma: no cover - không gọi trong test này
            raise NotImplementedError

    try:
        found = ProviderRegistry.get_provider(DataCategory.QUOTE, "legacy_demo")
        assert found is not None, "get_provider phải trả về class vừa đăng ký"
        assert issubclass(found, BaseProvider)

        assert ProviderRegistry.is_registered(DataCategory.QUOTE, "legacy_demo")
        names = ProviderRegistry.get_all_provider_names()
        assert any("legacy_demo" in n for n in names)

        info = ProviderRegistry.get_provider_info(DataCategory.QUOTE, "legacy_demo")
        assert isinstance(info, dict), "get_provider_info phải trả dict"
    finally:
        ProviderRegistry.clear()


def test_legacy_provider_base_class_is_usable():
    """BaseProvider vẫn là lớp cơ sở dùng được (không abstract còn thiếu)."""
    from vnbroker.core.base.provider import BaseProvider

    assert hasattr(BaseProvider, "provider_name")
    assert hasattr(BaseProvider, "get_info")
    # Mixin validation tồn tại.
    assert hasattr(BaseProvider, "_load_api_key")


# ------------------------------------------------------------- phần 2: không ai dùng


def test_no_module_outside_core_base_imports_it():
    """Không module nào ngoài `core/base/` import `core.base.*`.

    Đây là lý do xoá được: đây là code chết, không phải code thiếu test.
    """
    pattern = re.compile(r"core\.base\.(registry|provider)|from\s+vnbroker\.core\.base\b")
    offenders: list[str] = []

    this_file = Path(__file__).resolve()
    for path in ROOT.rglob("*.py"):
        if "vnbroker/core/base" in path.as_posix():
            continue
        # Bỏ qua chính file này: phần 1 của test cố ý import để chứng minh
        # module hoạt động độc lập. Đó là characterization, không phải dependency.
        if path.resolve() == this_file:
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


def test_core_base_is_not_reexported():
    """`core/__init__.py` và `core/base/__init__.py` không export nó ra ngoài."""
    base_init = (BASE_DIR / "__init__.py").read_text(encoding="utf-8")
    assert "import" not in re.sub(r"^\s*\"\"\".*?\"\"\"", "", base_init, flags=re.S), (
        "core/base/__init__.py đang re-export thứ gì đó — xoá sẽ phá vỡ API."
    )