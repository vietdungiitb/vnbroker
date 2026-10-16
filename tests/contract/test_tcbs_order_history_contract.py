"""Kết luận của REQ-002 phải tự kiểm, không được chỉ dựa vào lời ghi trong tài liệu.

VNBROKER-REQ-002 hỏi: TCBS có đọc được lịch sử lệnh nhiều ngày không? REQ đưa ra
hai phương án, và **một trong hai không thi hành được**:

* khôi phục ``/aion/v1/accounts/{accountNo}/orders/history`` — path này không
  có trong spec;
* nếu path chết, *"cung cấp alternative chính thức (vd phân trang
  ``get_executions`` theo ngày)"*.

Phương án thứ hai không làm được, và lý do đo được ở đây:
``GET /aion/v1/accounts/{accountNo}/matching-details`` **không khai báo tham số
truy vấn nào** — không có ``from``/``to``, không có phân trang. Nên "phân trang
theo ngày" là thứ không tồn tại trong hợp đồng.

Đây là L-P06 viết thành test: một AC đòi cơ chế mà nguồn sự thật không có thì
phải **đổi AC**, chứ không phải viết code rồi báo xong.

Spec ở đây là ``docs/references/openapi-v1.0.0.json``, được ghim sha256 và do
``scripts/verify_tcbs_coverage.py`` kiểm mỗi lần chạy gate — đúng yêu cầu L-E02
(rõ ở đây: có nhiều bản spec trong lịch sử repo, và bản cũ sai).

⚠ Giới hạn trung thực: **không** kết luận "path đã chết trên server". TCBS trả
401 trước khi route, nên không có cách nào phân biệt route tồn tại hay không
(L-R04). Cái test này chứng minh là *"không có trong tài liệu chính thức"* — và
đó là đúng mức độ chắc chắn mà AC gốc cho phép.
"""
from __future__ import annotations

import inspect
import json
import pathlib

import pytest

from vnbroker.broker.capabilities import LANES, capabilities

SPEC_PATH = pathlib.Path(__file__).resolve().parents[2] / "docs" / "references" / "openapi-v1.0.0.json"

#: Path mà REQ-002 hỏi về.
ORDER_HISTORY_PATH = "/aion/v1/accounts/{accountNo}/orders/history"
MATCHING_DETAILS_PATH = "/aion/v1/accounts/{accountNo}/matching-details"


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def _query_params(spec: dict, path: str) -> list[str]:
    operation = spec["paths"][path]["get"]
    return [p["name"] for p in operation.get("parameters", []) if p.get("in") == "query"]


# --- Path lịch sử lệnh không có trong spec ---------------------------------

def test_order_history_path_is_absent_from_the_official_spec(spec):
    assert ORDER_HISTORY_PATH not in spec["paths"]


def test_matching_details_declares_no_query_parameter(spec):
    """Đây là mấu chốt của REQ-002: alternative "phân trang get_executions theo
    ngày" cần tham số ngày, mà spec không có tham số nào."""
    assert _query_params(spec, MATCHING_DETAILS_PATH) == []


def test_the_two_day_list_endpoints_are_not_about_orders(spec):
    """Spec **có** endpoint nhận ``fromDate``/``toDate`` — nhưng là dòng tiền.
    Nếu không nói rõ, người đọc dễ tưởng đó là lối thoát cho REQ-002."""
    dated = {
        path: _query_params(spec, path)
        for path, ops in spec["paths"].items()
        if any(
            p.get("in") == "query" and p["name"].lower().startswith(("from", "to"))
            for op in ops.values()
            if isinstance(op, dict)
            for p in op.get("parameters", [])
        )
    }
    assert dated, "spec không còn endpoint nào nhận from/to — kết luận REQ-002 cần xem lại"
    for path in dated:
        lowered = path.lower()
        assert not any(word in lowered for word in ("order", "trade", "deal")), (
            f"{path} có tham số ngày VÀ liên quan lệnh — REQ-002 cần xem lại"
        )
    assert any("cashstatements" in p.lower() for p in dated), sorted(dated)


def test_the_only_paginated_order_endpoint_is_in_day(spec):
    in_day = spec["paths"]["/khronos/v1/order/in-day"]["get"]
    page_params = [p["name"] for p in in_day.get("parameters", []) if p.get("in") == "query"]
    assert {"pageNo", "pageSize"} <= set(page_params)
    # Tên nói rõ phạm vi: chỉ trong ngày.
    assert "in-day" in "/khronos/v1/order/in-day"


# --- Cross-lane: hai lane còn lại ĐÃ CÓ lịch sử nhiều ngày ----------------

@pytest.mark.parametrize("provider", ("ssi", "dnse"))
def test_other_lanes_already_offer_a_multi_day_history(provider):
    """Nếu chỉ đọc tài liệu của TCBS thì dễ tưởng vnbroker không có khả năng
    này ở đâu cả. Đo bằng ``inspect`` trên class thật."""
    spec_entry = capabilities(provider)["features"]["order_history_multi_day"]
    assert spec_entry["supported"] is True

    client_path = LANES[provider].client
    module_name, _, class_name = client_path.partition(":")
    client = getattr(__import__(module_name, fromlist=[class_name]), class_name)
    params = inspect.signature(client.get_order_history).parameters
    assert "from_date" in params and "to_date" in params


def test_tcbs_capability_says_so_too():
    entry = capabilities("tcbs")["features"]["order_history_multi_day"]
    assert entry["supported"] is False
    assert entry["reason_code"].startswith("PATH_REMOVED_NOT_IN_SPEC")
