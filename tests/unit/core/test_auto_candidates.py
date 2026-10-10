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


def test_credentialed_provider_is_appended_and_never_displaces():
    """Provider có credential được **nối cuối**, không chen vào bảng ưu tiên.

    `OPEN_SOURCE_CANDIDATES` là bảng ưu tiên có chủ ý — `trading` đặt `kbs`
    trước vì benchmark cho thấy ổn định hơn dưới tải. Không có phép đo
    hiệu năng thì không ai được lên đầu. Đây cũng là ngữ nghĩa mà
    `SSI_AUTO_CANDIDATES` đã dùng từ trước.

    ⚠ Một bản vá trước chỉ "lấp chỗ trống cho module chưa có mục nào" thì
    **không bao giờ** đưa TCBS vào AUTO: TCBS khai hỗ trợ `quote, trading,
    listing, financial, company` — cả 5 đều đã có mục. Đo lại sau khi sửa
    xong: `tcbs_in_auto=False` ở cả 10 module. Sửa lỗi mà không sửa được lỗi.
    Cổng `check_provider_consistency.py` quy tắc **C5** giữ điều này.
    """
    with patch.dict(
        "os.environ",
        {**NO_CREDENTIALS, "TCBS_JWT_TOKEN": "a.b.c", "DNSE_API_KEY": "k",
         "DNSE_API_SECRET": "s"},
        clear=False,
    ):
        for module in ("quote", "company", "financial", "listing", "trading"):
            candidates = [c.lower() for c in get_auto_candidates(module)]
            head = [c for c in candidates if c in {"vci", "kbs"}]
            tail = [c for c in candidates if c not in {"vci", "kbs", "rss_cafef",
                                                      "rss_vneconomy", "ssi"}]
            assert tail, f"'{module}': provider co credential phai duoc noi vao, {candidates}"
            assert candidates[: len(head)] == head, (
                f"'{module}': provider co credential chen vao giua bang uu tien: "
                f"{candidates}"
            )
            if "tcbs" in candidates:
                assert candidates.index("tcbs") >= len(head), (
                    f"'{module}': tcbs phai o CUOI, dang o vi tri "
                    f"{candidates.index('tcbs')} trong {candidates}"
                )


def test_every_usable_provider_reaches_auto():
    """C5: pool phục vụ được provider nào cho module đó thì AUTO phải có nó.

    Không chỉ "AUTO không rỗng" — phải là **từng provider** pool xác nhận.
    """
    with patch.dict(
        "os.environ",
        {**NO_CREDENTIALS, "TCBS_JWT_TOKEN": "a.b.c", "DNSE_API_KEY": "k",
         "DNSE_API_SECRET": "s"},
        clear=False,
    ):
        pool = ProviderPool()
        for module in ("quote", "company", "financial", "listing", "trading", "news"):
            registered = {p.lower() for p in ProviderRegistry.list_available(module)}
            usable = {p.lower() for p in pool.get_available_providers(module)} & registered
            candidates = {c.lower() for c in get_auto_candidates(module)}
            missing = usable - candidates
            assert not missing, (
                f"module '{module}': pool phuc vu duoc {sorted(missing)} nhung "
                f"AUTO khong co ({sorted(candidates)})."
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
