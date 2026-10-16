"""Hợp đồng capability phải giữ được với code thật, không chỉ với chính nó.

VNBROKER-REQ-003 yêu cầu vnbroker *khai báo trung thực* rằng cả 3 lane đều
không có API watchlist của user, để UI của phía tiêu thụ không bao giờ hứa
một thứ không tồn tại.

Khai báo trung thực chỉ có giá trị nếu nó được **kiểm tra lại bằng code thật**.
Nếu không, "capability" chỉ là một bảng văn xuôi hay đúng — và bảng văn xuôi
thì chính là thứ đã sai ở REQ-002, nơi một AC đòi thứ nguồn sự thật không có.

Vì vậy mọi test ở đây đối chiếu claim với ``inspect`` trên chính class thật.
Claim hỏng thì test đỏ, chứ không phải lời hứa sai.
"""
from __future__ import annotations

import inspect
import json

import pytest

from vnbroker.broker.registry import BrokerRegistry

LANES = ("tcbs", "ssi", "dnse")

_CLIENT_FOR_LANE = {
    "tcbs": "vnbroker.broker.tcbs.client:TCBSBrokerClient",
    "ssi": "vnbroker.broker.ssi.client:SSIBrokerClient",
    "dnse": "vnbroker.connector.dnse.client:DNSEClient",
}


def _client(provider: str) -> type:
    module_name, _, class_name = _CLIENT_FOR_LANE[provider].partition(":")
    return getattr(__import__(module_name, fromlist=[class_name]), class_name)


def _features(provider: str) -> dict:
    return BrokerRegistry.capabilities(provider)["features"]


# --- REQ-003(a): watchlist không được hứa ----------------------------------

@pytest.mark.parametrize("provider", LANES)
def test_watchlist_is_declared_unsupported_everywhere(provider):
    feature = _features(provider)["watchlist"]
    assert feature["supported"] is False
    assert feature["reason_code"]


@pytest.mark.parametrize("provider", LANES)
def test_watchlist_claim_matches_the_real_class(provider):
    """Không lane nào được phép có method watchlist mà claim lại là
    ``unsupported``. Kiểm bằng ``dir()`` trên class thật."""
    client = _client(provider)
    watchlist_methods = [
        name for name in dir(client) if "watchlist" in name.lower() and not name.startswith("_")
    ]
    assert watchlist_methods == [], f"{provider} có {watchlist_methods} nhưng claim là unsupported"


def test_the_tcbs_note_explains_the_naming_collision():
    """`explorer/tcbs/tcbs_compatibility.py` có sẵn một hàm tên là
    `get_watchlist` — nhưng là screener preview, không phải watchlist user.
    Ghi rõ trong capability để người đọc không tưởng nó là nguồn."""
    note = _features("tcbs")["watchlist"]["note"]
    assert "ligo" in note and "screener preview" in note


# --- REQ-002: claim "order history nhiều ngày" phải khớp signature thật -----

@pytest.mark.parametrize("provider", LANES)
def test_multi_day_claim_matches_the_real_signature(provider):
    """Claim này là con dao hai lưỡi: nếu khai sai thì phía tiêu thụ sẽ dựa
    vào nó. Ở đây nó được kiểm bằng ``inspect.signature`` — không tin lời khai
    trong bảng (L-P06)."""
    claim = _features(provider)["order_history_multi_day"]["supported"]
    method = getattr(_client(provider), "get_order_history", None)
    assert method is not None, provider
    params = inspect.signature(method).parameters
    really_multi_day = "from_date" in params and "to_date" in params
    assert claim == really_multi_day, (
        f"{provider}: claim={claim} nhưng signature thật có "
        f"from_date/to_date={really_multi_day}"
    )


def test_tcbs_multi_day_is_unsupported_with_a_named_reason():
    feature = _features("tcbs")["order_history_multi_day"]
    assert feature["supported"] is False
    assert "PATH_REMOVED_NOT_IN_SPEC" in feature["reason_code"]
    # Ghi rõ endpoint nào trong spec thực sự có fromDate/toDate, để người
    # đọc tự kiểm thay vì tin lời.
    assert "trans-hist-cashStatements" in feature["note"]


# --- Hình dạng dùng chung: client khác phải đọc được ----------------------

@pytest.mark.parametrize("provider", LANES)
def test_all_lanes_declare_the_same_feature_set(provider):
    reference = set(_features("tcbs"))
    assert set(_features(provider)) == reference


@pytest.mark.parametrize("provider", LANES)
def test_capability_is_json_serialisable(provider):
    """REQ-001 nói *"machine-readable"*. Nếu có object lạ trong dict thì nó
    không đi qua được IPC/cache mà phía tiêu thụ cần."""
    payload = BrokerRegistry.capabilities(provider)
    restored = json.loads(json.dumps(payload))
    assert restored["provider"] == provider


def test_version_matches_the_installed_library():
    """Client dùng ``version`` để phát hiện cache cũ — nên nó phải bằng đúng
    thứ mà chính thư viện đang báo, không phải một hằng khác."""
    import vnbroker

    assert BrokerRegistry.capabilities("tcbs")["version"] == vnbroker.__version__


def test_registered_flag_separates_registry_membership_from_availability():
    """DNSE không có trong ``BrokerRegistry`` (không phải
    ``BaseBrokerClient``) nhưng vẫn là một lane cần suy luận. Hai khái niệm
    này phải tách, nếu không người đọc tưởng DNSE không tồn tại."""
    flags = {p: BrokerRegistry.capabilities(p)["registered"] for p in LANES}
    assert flags["tcbs"] is True
    assert flags["ssi"] is True
    assert flags["dnse"] is False
