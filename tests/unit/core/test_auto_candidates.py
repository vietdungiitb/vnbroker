"""`get_auto_candidates()` không được trả `[]` khi có provider dùng được.

Đo 2026-10-10 (`dev @ 9d5db1d`, có `.env` thật):

    get_auto_candidates('screener') -> []
    ProviderRegistry.list_available('screener') -> ['kbs', 'ssi', 'vci']

Nghĩa là `source="AUTO"` cho `screener` chết ngay từ đầu, **không báo lỗi** —
người dùng chỉ thấy một danh sách rỗng. Nguyên nhân: `OPEN_SOURCE_CANDIDATES`
là danh sách viết tay, không ai đối chiếu với registry.

Bổ nhiệm: hàm giờ hỏi `ProviderPool` cho phần còn thiếu.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from vnbroker.core.provider_pool import ProviderPool
from vnbroker.core.registry import ProviderRegistry
from vnbroker.core.source_router import get_auto_candidates

AUTH_ENV_VARS = tuple(
    name
    for config in ProviderPool.AUTH_PROVIDERS.values()
    for name in tuple(config["env_any"]) + tuple(config["env_all"])
)

NO_CREDENTIALS = {name: "" for name in AUTH_ENV_VARS}


@pytest.fixture(autouse=True)
def _explorers_loaded():
    """Registry rỗng thì mọi khẳng định dưới đây đều vô nghĩa."""
    import vnbroker

    vnbroker._ensure_explorer_modules_loaded()


def test_no_auth_providers_still_enter_auto():
    """KBS/VCI không cần credential mà vẫn phải vào AUTO."""
    with patch.dict("os.environ", NO_CREDENTIALS, clear=False):
        for module in ("quote", "company", "financial", "listing", "trading", "news"):
            candidates = [c.lower() for c in get_auto_candidates(module)]
            assert candidates, f"AUTO rong cho module '{module}'"


def test_module_with_usable_provider_is_never_empty():
    """AC-5: registry có provider **và** pool xác nhận dùng được ⇒ AUTO ≠ []."""
    with patch.dict("os.environ", NO_CREDENTIALS, clear=False):
        for module in ("quote", "company", "financial", "listing", "trading",
                       "news", "screener"):
            registered = {p.lower() for p in ProviderRegistry.list_available(module)}
            usable = {
                p.lower() for p in ProviderPool().get_available_providers(module)
            } & registered
            if not usable:
                continue
            candidates = [c.lower() for c in get_auto_candidates(module)]
            assert candidates, (
                f"module '{module}' co provider dung duoc {sorted(usable)} "
                f"nhung get_auto_candidates tra [] — source='AUTO' chet ngay."
            )


def test_screener_is_no_longer_dead():
    """Lỗi cụ thể đã đo: `screener` có kbs+vci nhưng AUTO = []."""
    with patch.dict("os.environ", NO_CREDENTIALS, clear=False):
        assert [c.lower() for c in get_auto_candidates("screener")]


def test_auto_candidates_never_name_a_provider_that_is_not_registered():
    """AC-5/C3: tên chết trong AUTO ⇒ failover gọi thẳng vào hư không."""
    with patch.dict("os.environ", NO_CREDENTIALS, clear=False):
        for module in ("quote", "company", "financial", "listing", "trading",
                       "news", "screener", "snapshot"):
            registered = {p.lower() for p in ProviderRegistry.list_available(module)}
            candidates = {c.lower() for c in get_auto_candidates(module)}
            unknown = candidates - registered
            assert not unknown, (
                f"module '{module}': AUTO tra {sorted(unknown)} khong co trong "
                f"registry {sorted(registered)}."
            )


def test_credentialed_provider_does_not_displace_the_priority_table():
    """AC-4: có credential KHÔNG đồng nghĩa được chen vào bảng ưu tiên.

    `OPEN_SOURCE_CANDIDATES` là bảng ưu tiên **có chủ ý** — `trading` đặt `kbs`
    trước vì benchmark cho thấy ổn định hơn dưới tải. Tự động nhét thêm
    provider có credential vào giữa danh sách đó là thay đổi thiết kế định
    tuyến không có số đo nào đứng sau, và nó đã làm hỏng 13 test của
    `test_bulk_router.py` / `test_source_router_ssi.py` khi thử làm vậy
    (đo 2026-10-10).

    Thêm provider có credential vào `PRIMARY_SOURCE_POOLS` cần một phép đo riêng.
    """
    with patch.dict(
        "os.environ",
        {**NO_CREDENTIALS, "TCBS_JWT_TOKEN": "a.b.c", "DNSE_API_KEY": "k",
         "DNSE_API_SECRET": "s"},
        clear=False,
    ):
        for module in ("quote", "company", "financial", "listing", "trading", "news"):
            candidates = [c.lower() for c in get_auto_candidates(module)]
            assert "tcbs" not in candidates, (
                f"'{module}' đã có mục riêng trong OPEN_SOURCE_CANDIDATES — "
                f"provider có credential không được tự chen vào bảng ưu tiên."
            )


def test_gap_filled_module_gets_its_usable_providers():
    """Module **không có** mục nào thì pool quyết định — đây là chỗ trống thật.

    `screener` là ví dụ: trước đây nó trả `[]` dù registry có `kbs`/`vci`/`ssi`.
    Hôm nay không provider nào có credential hỗ trợ `screener` (TCBS chưa đăng
    ký screener, DNSE không khai hỗ trợ), nên kết quả đúng là `['vci','kbs']` —
    khác `[]` ở bản cũ, và khác "chết" ở giữa.
    """
    from vnbroker.core.source_router import OPEN_SOURCE_CANDIDATES

    assert "screener" not in OPEN_SOURCE_CANDIDATES, (
        "Nếu screener đã có mục riêng thì test này không còn kiểm gì — "
        "đây là bảo đảm điều kiện tiên quyết, không phải khẳng định hành vi."
    )
    with patch.dict("os.environ", NO_CREDENTIALS, clear=False):
        candidates = [c.lower() for c in get_auto_candidates("screener")]
    assert candidates == ["kbs", "vci"] or set(candidates) == {"vci", "kbs"}

    registered = {p.lower() for p in ProviderRegistry.list_available("screener")}
    usable = {
        p.lower() for p in ProviderPool().get_available_providers("screener")
    } & registered
    assert set(candidates) == usable, (
        f"module lấp chỗ trống phải khớp đúng tập provider dùng được: "
        f"AUTO={candidates} usable={sorted(usable)}"
    )


def test_no_auth_providers_survive_the_gap_fill():
    """Module lấp chỗ trống vẫn phải nhận provider không cần auth (vci/kbs)."""
    with patch.dict("os.environ", NO_CREDENTIALS, clear=False):
        candidates = [c.lower() for c in get_auto_candidates("screener")]
    assert "vci" in candidates and "kbs" in candidates


def test_module_without_any_registered_provider_stays_empty():
    """`snapshot` không provider nào ⇒ AUTO = [] là ĐÚNG, không phải lỗi."""
    assert ProviderRegistry.list_available("snapshot") == []
    with patch.dict("os.environ", NO_CREDENTIALS, clear=False):
        assert get_auto_candidates("snapshot") == []
