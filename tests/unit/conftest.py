"""conftest cho `tests/unit` — cô lập credential thật của máy.

Nạp fixture `_isolate_provider_credentials` từ `tests/isolation.py`.

Đặt ở đây (thay vì `tests/conftest.py`) để `tests/integration` **không** bị
áp dụng: test tích phân cần credential thật và tự skip khi thiếu.
"""
from tests.isolation import _isolate_provider_credentials  # noqa: F401