"""``BrokerRegistry.capabilities()`` — hợp đồng máy đọc được cho 3 lane.

VNBROKER-REQ-001: phía vninvest cần biết method nào thật, method nào đã gỡ,
mà không có API chính thức — hiện chỉ phát hiện bằng ``try/except`` lúc chạy.
Cách đó là fail-open: chạy tới đâu mới biết tới đó, và "không có exception"
không phải "có dữ liệu".

Ba lỗi trong AC gốc của REQ đã sửa ở đây, và mỗi lỗi có một test:

1. *"3 lane"* nhưng ``BrokerRegistry`` chỉ đăng ký ``tcbs``/``ssi`` — DNSE
   nằm ở ``connector/dnse`` và không phải ``BaseBrokerClient``. Nếu chỉ đọc
   registry thì ``capabilities("dnse")`` ném KeyError, tức chính lane mà
   vninvest đang retry mù lại không hỏi được.
2. *"gọi không cần credential"* — ``DNSEClient.__init__`` bắt buộc
   ``api_key``/``api_secret``. Nên phải dựng ở **cấp class**, không
   instantiate. Test chứng minh bằng cách chặn ``__init__``.
3. ``BaseBrokerClient`` chỉ có 4 method công khai
   (``authenticate``, ``close``, ``get_account_balance``, ``get_account_list``)
   — danh mục thật phải lấy từ class cụ thể, không lấy từ lớp cơ sở.
"""
from __future__ import annotations

import pytest

from vnbroker.broker.registry import BrokerRegistry

LANES = ("tcbs", "ssi", "dnse")


@pytest.fixture(autouse=True)
def _registered():
    """Đảm bảo 2 provider của registry thật sự đã đăng ký.

    ``vnbroker.broker.__init__`` nuốt lỗi import bằng ``except Exception:
    pass``, nên provider có thể vắng mặt mà không ai biết. Capability phải
    nói "chưa đăng ký" khác với "đăng ký nhưng không có method" — nên test
    này chủ động nạp lại để không phụ thuộc thứ tự import.
    """
    import vnbroker.broker  # noqa: F401

    assert BrokerRegistry.is_registered("tcbs")
    assert BrokerRegistry.is_registered("ssi")


def _cap(provider: str) -> dict:
    return BrokerRegistry.capabilities(provider)


# --- Bề mặt hợp đồng ------------------------------------------------------

@pytest.mark.parametrize("provider", LANES)
def test_every_lane_answers(provider):
    """Lỗi 1: nếu chỉ đọc registry thì `dnse` không có ở đây."""
    assert _cap(provider)["provider"] == provider


@pytest.mark.parametrize("provider", LANES)
def test_shape_is_identical_across_lanes(provider):
    cap = _cap(provider)
    assert set(cap) >= {"version", "provider", "methods", "features"}
    assert isinstance(cap["version"], str) and cap["version"]
    assert cap["methods"], "một lane không thể không có method nào"


@pytest.mark.parametrize("provider", LANES)
def test_every_method_entry_has_supported_and_reason_code(provider):
    """``reason_code`` phải có mặt ở **mọi** entry, kể cả khi hỗ trợ — để
    người đọc không phải dò xem key có thiếu không, và để client so sánh được."""
    for name, entry in _cap(provider)["methods"].items():
        assert set(entry) >= {"supported", "reason_code"}, name
        assert isinstance(entry["supported"], bool)
        if entry["supported"]:
            assert entry["reason_code"] is None, name
        else:
            assert isinstance(entry["reason_code"], str) and entry["reason_code"]


def test_unknown_provider_raises_with_the_available_list():
    with pytest.raises(KeyError) as excinfo:
        BrokerRegistry.capabilities("vndirect")
    assert "tcbs" in str(excinfo.value)


# --- Đúng 100% danh sách method đã gỡ (điều kiện nghiệm thu của REQ) -------

def _removed_entries(provider: str) -> dict[str, str]:
    cap = _cap(provider)
    return {
        name: entry["reason_code"]
        for name, entry in cap["methods"].items()
        if not entry["supported"]
    }


def test_tcbs_marks_exactly_the_removed_paths_as_unsupported():
    """Điều kiện nghiệm thu: *đúng 100%* ``_REMOVED_PATHS`` hiện tại.

    Số đo bằng script chứ không đếm mắt: ``equity.py`` 5 + ``account.py`` 13
    = 18 method.
    """
    from vnbroker.broker.tcbs import account as account_mod
    from vnbroker.broker.tcbs import equity as equity_mod

    expected = set(equity_mod._REMOVED_PATHS) | set(account_mod._REMOVED_PATHS)
    assert len(expected) == 18
    assert set(_removed_entries("tcbs")) == expected


def test_the_reason_code_names_the_path_that_was_removed():
    """Lý do phải dẫn được người đọc tới tài liệu, không phải chữ "removed"."""
    from vnbroker.broker.capabilities import PATH_REMOVED_NOT_IN_SPEC
    from vnbroker.broker.tcbs import equity as equity_mod

    entries = _removed_entries("tcbs")
    code = entries["get_order_history"]
    assert code.startswith(f"{PATH_REMOVED_NOT_IN_SPEC}:")
    assert code.split(":", 1)[1] == equity_mod._REMOVED_PATHS["get_order_history"]
    assert code.endswith("/orders/history")


def test_no_other_lane_reports_a_removed_method():
    """SSI/DNSE không có bảng path đã gỡ — trả về 0 là đúng. Nếu tương lai
    chúng có, test này đỏ và buộc phải cập nhật."""
    assert _removed_entries("ssi") == {}
    assert _removed_entries("dnse") == {}


def test_ssi_exposes_a_multi_day_order_history_and_tcbs_does_not():
    """Bằng chứng chéo cho REQ-002, ghim ở đây để khỏi phải đo lại tay:
    đọc signature thật, không tin lời khai trong tài liệu."""
    tcbs = _cap("tcbs")["methods"]["get_order_history"]
    ssi = _cap("ssi")["methods"]["get_order_history"]
    assert tcbs["supported"] is False
    assert ssi["supported"] is True


# --- Không được instantiate (điều kiện "không cần credential") ------------

def test_capabilities_never_constructs_a_client(monkeypatch):
    """Lỗi 2: ``DNSEClient.__init__`` bắt buộc credential, nên mọi đường
    đọc capability phải ở cấp class.

    Cách thử: làm ``__init__`` nổ nhưng giữ nguyên class. Nếu
    ``capabilities()`` instantiate, nó nhận ngay AssertionError; nếu chỉ
    introspect, danh mục method vẫn ra đủ.
    """

    def _boom(*args, **kwargs):
        raise AssertionError("capabilities() đã khởi tạo client — cần credential")

    for module, cls_name in (
        ("vnbroker.broker.tcbs.client", "TCBSBrokerClient"),
        ("vnbroker.broker.ssi.client", "SSIBrokerClient"),
        ("vnbroker.connector.dnse.client", "DNSEClient"),
    ):
        cls = getattr(__import__(module, fromlist=[cls_name]), cls_name)
        monkeypatch.setattr(cls, "__init__", _boom, raising=True)

    for provider in LANES:
        assert _cap(provider)["methods"], provider


# --- Danh mục phải lấy từ class cụ thể, không phải lớp cơ sở ---------------

def test_method_catalogue_is_wider_than_the_abstract_base():
    """Lỗi 3: ``BaseBrokerClient`` chỉ có 4 method. Nếu ai đó dựng danh mục
    từ lớp cơ sở thì phần lớn method của TCBS biến mất khỏi capability."""
    from vnbroker.broker.base import BaseBrokerClient
    from vnbroker.broker.tcbs.client import TCBSBrokerClient

    base_names = {
        name
        for name in dir(BaseBrokerClient)
        if not name.startswith("_") and callable(getattr(BaseBrokerClient, name))
    }
    cap_names = set(_cap("tcbs")["methods"])
    assert len(cap_names) > len(base_names) * 5
    assert cap_names >= {"place_order", "get_orders", "get_holdings"}
    assert len(cap_names) == len(
        [
            n
            for n in dir(TCBSBrokerClient)
            if not n.startswith("_") and callable(getattr(TCBSBrokerClient, n, None))
        ]
    )
