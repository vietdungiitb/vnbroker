"""CafeF reference layer — unit tests (no live network: HTTP is mocked)."""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import pytest

from vnbroker.reference import CafefReference
from vnbroker.reference import client as cafef_client
from vnbroker.reference.parser import to_native_records
from vnbroker.reference.reconcile import reconcile

pytestmark = pytest.mark.unit

GOLDEN_XLSX = pd.DataFrame(
    [
        {
            "Mã": "TPB",
            "Ngày": "04/01/2022",
            "Giá đóng cửa": 42.75,
            "Giá điều chỉnh": 17.94,
            "Khối lượng khớp lệnh": 11034900,
            "Giá trị khớp lệnh": 467.26,
            "Khối lượng thỏa thuận": 0,
            "Giá trị thỏa thuận": 0.0,
            "Giá mở cửa": 41.5,
            "Giá cao nhất": 43.25,
            "Giá thấp nhất": 41.3,
            "Thay đổi": "+1,65 (+4,01%)",
        }
    ]
)

GOLDEN_JSON = {
    "Data": {
        "TotalCount": 1,
        "Data": [
            {
                "Symbol": "TPB",
                "Ngay": "04/01/2022",
                "GiaDongCua": 42.75,
                "GiaDieuChinh": 17.94,
                "GiaMoCua": 41.5,
                "GiaCaoNhat": 43.25,
                "GiaThapNhat": 41.3,
                "KhoiLuongKhopLenh": 11034900,
                "GiaTriKhopLenh": 467.26,
                "KLThoaThuan": 0,
                "GtThoaThuan": 0,
            }
        ],
    }
}


def _xlsx_bytes(frame: pd.DataFrame = GOLDEN_XLSX) -> bytes:
    buf = io.BytesIO()
    frame.to_excel(buf, index=False, sheet_name="LichSuGia")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, content: bytes, status: int = 200) -> None:
        self.content = content
        self.status_code = status
        self.headers: dict[str, str] = {}

    def json(self) -> Any:
        return json.loads(self.content.decode("utf-8"))

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def xlsx_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cafef_client.requests, "get", lambda *a, **kw: _FakeResponse(_xlsx_bytes())
    )


class TestCafefReference:
    def test_history_golden_from_xlsx(self, xlsx_ok: None) -> None:
        ref = CafefReference()
        df = ref.history("TPB", "2022-01-01", "2022-01-06")

        assert len(df) == 1
        row = df.iloc[0]
        assert row["close_raw"] == 42750.0
        assert row["close"] == 42750.0
        assert row["close_adjusted"] == 17940.0
        assert row["volume"] == 11034900
        assert row["value"] == 467_260_000_000
        assert row["time"].strftime("%Y-%m-%d") == "2022-01-04"
        assert row["source"] == "cafef"
        assert row["time"].tz is not None
        assert str(row["time"].tz) == "Asia/Ho_Chi_Minh"

    def test_fallback_to_json_when_xlsx_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = {"n": 0}

        def fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("XLSX down")
            return _FakeResponse(json.dumps(GOLDEN_JSON).encode("utf-8"))

        monkeypatch.setattr(cafef_client.requests, "get", fake_get)
        df = CafefReference().history("TPB", "2022-01-01", "2022-01-06")

        assert calls["n"] == 2
        assert df.iloc[0]["close_raw"] == 42750.0

    def test_request_date_must_be_mm_dd_yyyy(self, xlsx_ok: None) -> None:
        with pytest.raises(ValueError):
            CafefReference().history("TPB", "31/12/2022", "01/01/2023")

    def test_to_df_false_returns_json(self, xlsx_ok: None) -> None:
        out = CafefReference().history("TPB", "2022-01-01", "2022-01-06", to_df=False)
        assert isinstance(out, str)
        assert "42750" in out or "42.75" in out

    def test_native_records_formats(self, xlsx_ok: None) -> None:
        df = CafefReference().history("TPB", "2022-01-01", "2022-01-06")
        kbs = to_native_records(df, source="KBS")
        vci = to_native_records(df, source="VCI")
        assert kbs[0]["t"] == "2022-01-04 07:00"
        assert isinstance(vci[0]["t"], int)
        assert datetime.fromtimestamp(vci[0]["t"], tz=timezone.utc).date().isoformat() == "2022-01-04"

    def test_reconcile_does_not_mutate_input(self, xlsx_ok: None) -> None:
        cafef_df = CafefReference().history("TPB", "2022-01-01", "2022-01-06")
        provider = pd.DataFrame(
            {
                "time": cafef_df["time"],
                "open": [16700.0],
                "high": [17000.0],
                "low": [16500.0],
                "close": [16783.0],
                "volume": [11034900],
            }
        )
        before = provider.copy(deep=True)
        report = reconcile(provider, cafef_df, symbol="TPB")

        assert abs(report.ratio_mean - 16783.0 / 17940.0) < 1e-6
        pd.testing.assert_frame_equal(provider, before)
        assert report.verdict in {"adjusted_confirmed", "rebase_suspected", "double_adjust_suspected"}

    def test_reconcile_requires_symbol(self, xlsx_ok: None) -> None:
        with pytest.raises(ValueError, match="symbol"):
            CafefReference().reconcile(pd.DataFrame({"time": [], "close": []}))

    def test_reconcile_rejects_symbol_mismatch(self, xlsx_ok: None) -> None:
        frame = pd.DataFrame({"time": [], "close": []})
        frame.name = "VCB"
        with pytest.raises(ValueError, match="mismatch"):
            CafefReference().reconcile(frame, symbol="TPB")

    def test_facade_and_invalid_name(self) -> None:
        from vnbroker import Vnbroker

        assert isinstance(Vnbroker().reference("cafef"), CafefReference)
        with pytest.raises(ValueError):
            Vnbroker().reference("nope")
