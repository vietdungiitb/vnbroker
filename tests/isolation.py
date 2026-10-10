"""Cô lập biến credential cho test tầng 1 — KHÔNG để `.env` của máy chen vào.

Vấn đề (đo 2026-10-10)
----------------------
`tests/conftest.py` nạp `.env` thật vào `os.environ`. Từ đó **mọi** test đọc
`ProviderPool` đều thấy credential thật của máy đang chạy. Hệ quả: các test
viết `assert get_auto_candidates('quote') == ['vci', 'kbs']` sẽ **đỏ trên máy
có credential** và **xanh trên máy không có** — cùng một commit, hai kết quả.

Đo được: `pytest tests/unit tests/contract` → 1873 passed, nhưng
`pytest tests/` → **14 failed**, đúng 14 test đó. Khác nhau chỉ ở *thứ tự
collect*, vì biến bị test khác đụng vào rồi trả lại.

Đây là loại test "xanh vì lý do sai" mà bộ test phải cấm: một test phải xanh vì
hành vi đúng, không phải vì máy không có key.

Cách sửa: fixture `autouse` ở đây **xoá** mọi biến mà `ProviderPool` đọc,
trước khi test chạy. Test nào cần credential thì tự `setenv` (đã có sẵn ở
`test_provider_pool.py`, `test_auto_candidates.py`, `test_tcbs_auth_env.py`).

⚠ Danh sách biến được **derive từ `ProviderPool.AUTH_PROVIDERS`** chứ không liệt
kê tay. Liệt kê tay chính là cách làm lỗi này quay lại: thêm provider mới và
quên thêm biến ⇒ test lại phụ thuộc máy.
"""
from __future__ import annotations

import pytest


def _credential_env_vars() -> tuple[str, ...]:
    from vnbroker.core.provider_pool import ProviderPool

    names: list[str] = []
    for config in ProviderPool.AUTH_PROVIDERS.values():
        for key in ("env_any", "env_all"):
            raw = config.get(key)
            if isinstance(raw, str):
                names.append(raw)
            elif isinstance(raw, (tuple, list)):
                names.extend(str(v) for v in raw)
    # chống trùng, giữ thứ tự ổn định
    return tuple(dict.fromkeys(names))


@pytest.fixture(autouse=True)
def _isolate_provider_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bỏ credential thật của máy khỏi `os.environ` cho mỗi test.

    Áp cho `tests/unit` và `tests/contract` — tức là mọi test không chạm mạng
    thật. `tests/integration` cố ý KHÔNG bị áp dụng: chúng cần credential thật
    và tự skip nếu thiếu.
    """
    for name in _credential_env_vars():
        monkeypatch.delenv(name, raising=False)