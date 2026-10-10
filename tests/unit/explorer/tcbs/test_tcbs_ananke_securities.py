"""
tests.unit.explorer.tcbs.test_tcbs_ananke_securities
=====================================================
Unit test cho `Listing.get_securities_info()` — `GET /ananke/v1/securities`.

Nguồn chuẩn: `docs/references/openapi-v1.0.0.json` (sha256 7f97d27b…42bd4a)
- Query param: ``fields`` (tuỳ chọn), ``filter`` (tuỳ chọn, dạng ``field=value``)
- ``responses.200`` **không có** ``content`` ⇒ shape **chưa được tài liệu hoá**,
  KHÔNG phải schema rỗng. Vì vậy hàm trả **raw dict**, không ép DataFrame.

Test categories:
  - TestPathTrongSpec       (path + 2 query param đúng tên, `in: query`)
  - TestQueryParam          (E2 — fields/filter là query param, bỏ trống ⇒ không gửi)
  - TestRawDict             (E5 — trả raw dict, không ép DataFrame)
  - TestResponseThieuField  (E5 — thiếu field / rỗng ⇒ không KeyError)
  - TestDocstring
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from vnbroker.core.utils import client
from vnbroker.explorer.tcbs.listing import Listing

SPEC_PATH = Path(__file__).resolve().parents[4] / "docs" / "references" / "openapi-v1.0.0.json"
SPEC_PATH_TEXT = "/ananke/v1/securities"


def _spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def _listing() -> Listing:
    return Listing(show_log=False)


# ── TestPathTrongSpec ───────────────────────────────────────────────────────


class TestPathTrongSpec:
    def test_path_ton_tai_trong_spec(self):
        assert SPEC_PATH_TEXT in _spec()["paths"]

    def test_verb_la_get(self):
        assert "get" in _spec()["paths"][SPEC_PATH_TEXT]

    def test_hai_query_param_dung_ten(self):
        params = _spec()["paths"][SPEC_PATH_TEXT]["get"]["parameters"]
        assert {p["name"] for p in params} == {"fields", "filter"}
        assert all(p["in"] == "query" for p in params)

    def test_cau_hinh_dung_base_url_va_path(self):
        lst = _listing()
        with patch.object(client, "send_request", return_value={}) as m:
            lst.get_securities_info()
        url = m.call_args.kwargs["url"]
        assert url.endswith(SPEC_PATH_TEXT)
        assert url.startswith(lst.base_url)


# ── TestQueryParam (E2) ─────────────────────────────────────────────────────


class TestQueryParam:
    def test_fields_va_filter_la_query_param_khong_phai_payload(self):
        with patch.object(client, "send_request", return_value={}) as m:
            _listing().get_securities_info(fields="symbol,exchange", filter_expr="symbol=TCB")
        kwargs = m.call_args.kwargs
        assert kwargs["method"] == "GET"
        assert kwargs["params"] == {"fields": "symbol,exchange", "filter": "symbol=TCB"}
        assert kwargs.get("payload") is None

    def test_bang_trong_khong_gui_param(self):
        with patch.object(client, "send_request", return_value={}) as m:
            _listing().get_securities_info()
        assert m.call_args.kwargs["params"] == {}

    def test_chuoi_rong_khong_gui_param(self):
        with patch.object(client, "send_request", return_value={}) as m:
            _listing().get_securities_info(fields="", filter_expr="")
        assert m.call_args.kwargs["params"] == {}

    def test_chi_gui_fields(self):
        with patch.object(client, "send_request", return_value={}) as m:
            _listing().get_securities_info(fields="symbol")
        assert m.call_args.kwargs["params"] == {"fields": "symbol"}

    def test_chi_gui_filter(self):
        with patch.object(client, "send_request", return_value={}) as m:
            _listing().get_securities_info(filter_expr="symbol=TCB")
        assert m.call_args.kwargs["params"] == {"filter": "symbol=TCB"}

    def test_ten_tham_so_khong_che_tien_filter(self):
        """`filter` là builtin — tham số phải đổi tên, giá trị vẫn là `symbol=TCB`."""
        params = inspect.signature(Listing.get_securities_info).parameters
        assert "filter" not in params
        assert "filter_expr" in params


# ── TestRawDict (E5) ────────────────────────────────────────────────────────


class TestRawDict:
    def test_tra_ve_raw_dict_nguyen_ban(self):
        payload = {"data": [{"symbol": "TCB", "exchange": "HOSE", "odd": 1.5}]}
        with patch.object(client, "send_request", return_value=payload):
            result = _listing().get_securities_info(filter_expr="symbol=TCB")
        assert isinstance(result, dict)
        assert not isinstance(result, pd.DataFrame)
        assert result == payload

    def test_khong_ep_dataframe(self):
        payload = {"data": [{"a": 1}, {"a": 2}]}
        with patch.object(client, "send_request", return_value=payload):
            result = _listing().get_securities_info()
        assert isinstance(result, dict)
        assert isinstance(result.get("data"), list)

    def test_khong_tao_cot(self):
        """Bịa cột là hư cấu — mọi key trả về phải có thật trong response."""
        payload = {"data": [{"symbol": "TCB"}]}
        with patch.object(client, "send_request", return_value=payload):
            result = _listing().get_securities_info()
        assert set(result.keys()) == {"data"}
        assert set(result["data"][0].keys()) == {"symbol"}

    def test_response_la_list_duoc_boc(self):
        with patch.object(client, "send_request", return_value=[{"symbol": "TCB"}]):
            result = _listing().get_securities_info()
        assert result == {"data": [{"symbol": "TCB"}]}


# ── TestResponseThieuField (E5) ────────────────────────────────────────────


class TestResponseThieuField:
    def test_response_rong(self):
        with patch.object(client, "send_request", return_value={}):
            assert _listing().get_securities_info() == {}

    def test_response_khong_co_key_data(self):
        with patch.object(client, "send_request", return_value={"total": 0}):
            assert _listing().get_securities_info() == {"total": 0}

    def test_response_data_rong(self):
        with patch.object(client, "send_request", return_value={"data": []}):
            assert _listing().get_securities_info() == {"data": []}

    def test_response_record_thieu_field(self):
        payload = {"data": [{"symbol": "TCB"}, {}, {"exchange": "HNX"}]}
        with patch.object(client, "send_request", return_value=payload):
            result = _listing().get_securities_info()
        assert result == payload

    def test_request_loi_tra_rong_khong_nang(self):
        with patch.object(client, "send_request", side_effect=ConnectionError("boom")):
            assert _listing().get_securities_info() == {}


# ── TestDocstring ───────────────────────────────────────────────────────────


class TestDocstring:
    def test_docstring_ghi_shape_chua_duoc_tai_lieu_hoa(self):
        doc = inspect.getdoc(Listing.get_securities_info) or ""
        assert "chưa được tài liệu hoá" in doc