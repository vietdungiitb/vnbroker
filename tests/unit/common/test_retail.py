"""
R0: Retail facade — gold SJC/BTMC + exchange rate VCB. Mocked HTTP/excel.
"""

from __future__ import annotations

import base64
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import pytest
import requests

from vnbroker.common.retail import (
    BTMC_COLUMNS,
    BTMC_SOURCE,
    SJC_COLUMNS,
    SJC_SOURCE,
    VCB_COLUMNS,
    VCB_SOURCE,
    Retail,
)

pytestmark = pytest.mark.retail

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "retail"


class FakeResp:
    def __init__(
        self,
        status_code: int = 200,
        payload: Any = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text or json.dumps(payload or {})

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def load(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def vcb_excel_b64(rows: List[List[str]]) -> str:
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="ExchangeRate", index=False, header=False)
    return base64.b64encode(buf.getvalue()).decode("ascii")


class TestGoldSjc:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: Dict[str, Any] = {}

        def _post(url: str, headers: Any = None, data: Any = None) -> FakeResp:
            calls["data"] = data
            return FakeResp(200, load("sjc"))

        monkeypatch.setattr("vnbroker.explorer.misc.gold_price.requests.post", _post)
        df = Retail().gold(source="sjc", date="2026-01-15")
        assert list(df.columns) == SJC_COLUMNS
        assert df.iloc[0]["name"] == "Vàng SJC 1L"
        assert df.iloc[0]["buy_price"] == 100.0
        assert df.iloc[0]["source"] == "SJC"
        assert df.attrs["source"] == "SJC"
        assert "toDate=15/01/2026" in calls["data"]

    def test_default_today(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: Dict[str, Any] = {}

        def _post(url: str, headers: Any = None, data: Any = None) -> FakeResp:
            calls["data"] = data
            return FakeResp(200, load("sjc"))

        monkeypatch.setattr("vnbroker.explorer.misc.gold_price.requests.post", _post)
        Retail().gold(source="SJC")
        today = datetime.now().strftime("%d/%m/%Y")
        assert f"toDate={today}" in calls["data"]

    def test_bad_date(self, monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
        called = []
        monkeypatch.setattr(
            "vnbroker.explorer.misc.gold_price.requests.post",
            lambda *a, **k: (called.append(1), FakeResp(200, {}))[1],
        )
        with pytest.raises(ValueError):
            Retail().gold(source="sjc", date="15-01-2026")
        assert called == []
        assert capsys.readouterr().out == ""

    def test_pre_min_date(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with pytest.raises(ValueError, match="2016-01-02"):
            Retail().gold(source="sjc", date="2016-01-01")

    def test_bad_source(self) -> None:
        with pytest.raises(ValueError, match="sjc"):
            Retail().gold(source="xyz")

    def test_api_unsuccessful_empty(
        self, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        monkeypatch.setattr(
            "vnbroker.explorer.misc.gold_price.requests.post",
            lambda *a, **k: FakeResp(200, {"success": False}),
        )
        df = Retail().gold(source="sjc", date="2026-01-15")
        assert list(df.columns) == SJC_COLUMNS and df.empty
        assert df.attrs["source"] == SJC_SOURCE
        assert capsys.readouterr().out == ""  # print legacy bị chặn

    def test_empty_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "vnbroker.explorer.misc.gold_price.requests.post",
            lambda *a, **k: FakeResp(200, {"success": True, "data": []}),
        )
        df = Retail().gold(source="sjc")
        assert df.empty

    def test_network_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom(*a: Any, **k: Any) -> FakeResp:
            raise requests.exceptions.ConnectionError("down")

        monkeypatch.setattr("vnbroker.explorer.misc.gold_price.requests.post", _boom)
        with pytest.raises(RuntimeError, match="SJC:"):
            Retail().gold(source="sjc")

    def test_non_200_suppressed(
        self, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        monkeypatch.setattr(
            "vnbroker.explorer.misc.gold_price.requests.post",
            lambda *a, **k: FakeResp(500, {}, text="err"),
        )
        df = Retail().gold(source="sjc", date="2026-01-15")
        assert df.empty
        assert capsys.readouterr().out == ""


class TestGoldBtmc:
    def test_ok_ignores_date(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "vnbroker.explorer.misc.gold_price.requests.get",
            lambda *a, **k: FakeResp(200, load("btmc")),
        )
        df = Retail().gold(source="btmc", date="2020-05-05")
        assert list(df.columns) == BTMC_COLUMNS
        assert df.iloc[0]["name"] == "Vàng Rồng Thăng Long"
        assert df.iloc[0]["source"] == "BTMC"
        assert df.attrs["source"] == BTMC_SOURCE

    def test_network_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom(*a: Any, **k: Any) -> FakeResp:
            raise requests.exceptions.Timeout("t")

        monkeypatch.setattr("vnbroker.explorer.misc.gold_price.requests.get", _boom)
        with pytest.raises(RuntimeError, match="BTMC:"):
            Retail().gold(source="btmc")

    def test_empty_returns_empty_df(
        self, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        # Explorer BTMC KeyError ở sort_values khi data rỗng → facade trả
        # DataFrame rỗng đúng schema (hợp đồng §2: không None, nhất quán SJC/VCB).
        monkeypatch.setattr(
            "vnbroker.explorer.misc.gold_price.requests.get",
            lambda *a, **k: FakeResp(200, {"DataList": {"Data": []}}),
        )
        df = Retail().gold(source="btmc")
        assert list(df.columns) == BTMC_COLUMNS and df.empty
        assert df.attrs["source"] == BTMC_SOURCE
        assert capsys.readouterr().out == ""


class TestExchangeRate:
    def _mock_vcb(
        self, monkeypatch: pytest.MonkeyPatch, calls: Optional[List[Any]] = None
    ) -> None:
        if calls is None:
            calls = []

        def _get(url: str, **k: Any) -> FakeResp:
            calls.append(url)
            return FakeResp(200, {"Data": vcb_excel_b64(load("vcb")["rows"])})

        monkeypatch.setattr("vnbroker.explorer.misc.exchange_rate.requests.get", _get)

    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_vcb(monkeypatch)
        df = Retail().exchange_rate(date="2026-01-15")
        assert list(df.columns) == VCB_COLUMNS
        assert df.iloc[0]["currency_code"] == "USD"
        assert df.iloc[0]["sell"] == "25300"
        assert df.iloc[0]["date"] == "2026-01-15"
        assert df.attrs["source"] == VCB_SOURCE

    def test_default_today_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: List[Any] = []
        self._mock_vcb(monkeypatch, calls)
        Retail().exchange_rate()
        today = datetime.now().strftime("%Y-%m-%d")
        assert f"date={today}" in calls[0]

    def test_bad_date(self, monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
        calls: List[Any] = []
        self._mock_vcb(monkeypatch, calls)
        with pytest.raises(ValueError):
            Retail().exchange_rate(date="2026/01/15")
        assert calls == []
        assert capsys.readouterr().out == ""

    def test_non_200_suppressed(
        self, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        monkeypatch.setattr(
            "vnbroker.explorer.misc.exchange_rate.requests.get",
            lambda *a, **k: FakeResp(404, {}, text="nope"),
        )
        df = Retail().exchange_rate(date="2026-01-15")
        assert list(df.columns) == VCB_COLUMNS and df.empty
        assert capsys.readouterr().out == ""

    def test_network_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom(*a: Any, **k: Any) -> FakeResp:
            raise requests.exceptions.ConnectionError("down")

        monkeypatch.setattr("vnbroker.explorer.misc.exchange_rate.requests.get", _boom)
        with pytest.raises(RuntimeError, match="VCB:"):
            Retail().exchange_rate()


class TestVnbrokerRetail:
    def test_factory(self) -> None:
        from vnbroker import Vnbroker

        retail = Vnbroker().retail()
        assert isinstance(retail, Retail)

    def test_fixture_files_valid(self) -> None:
        for name in ("sjc", "btmc", "vcb"):
            data = load(name)
            assert data is not None
