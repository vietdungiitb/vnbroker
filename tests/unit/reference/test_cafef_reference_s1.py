"""S1 fail-before tests — 4 CafeF reference bugs from vninvest plan S0-S7.

Each test targets a concrete bug verified on 2026-11-26:
1. bulk_year sends future EndDate (12/31/current year) -> HTTP 400.
2. unbounded _BULK_CACHE in long-running Celery workers.
3. reconcile_prices cannot pass exchange (HNX/UPCOM symbols -> 400).
4. parser frame has no 'date' and no 'change_pct' -> vninvest importer KeyError.
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any

import pandas as pd
import pytest

from vnbroker import Vnbroker
from vnbroker.reference import client as cafef_client
from vnbroker.reference.parser import parse_records

pytestmark = pytest.mark.unit

XLSX_ROWS = [
    {
        "Mã": "TPB",
        "Ngày": "04/01/2022",
        "Giá mở cửa": 41.5,
        "Giá cao nhất": 43.25,
        "Giá thấp nhất": 41.3,
        "Giá đóng cửa": 42.75,
        "Giá điều chỉnh": 17.94,
        "Khối lượng khớp lệnh": 11034900,
        "Giá trị khớp lệnh": 467.26,
        "Khối lượng thỏa thuận": 0,
        "Giá trị thỏa thuận": 0.0,
        "Thay đổi": "+1,65 (+4,01%)",
    }
]


class _FakeResponse:
    status_code = 200
    headers: dict[str, str] = {}

    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


def _xlsx_bytes() -> bytes:
    buf = io.BytesIO()
    pd.DataFrame(XLSX_ROWS).to_excel(buf, index=False, sheet_name="LichSuGia")
    return buf.getvalue()


def test_bulk_year_clamps_end_date_to_today(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_get(_url: str, *, params: dict[str, Any], **_kw: Any) -> _FakeResponse:
        seen.update(params)
        return _FakeResponse(_xlsx_bytes())

    monkeypatch.setattr(cafef_client.requests, "get", fake_get)
    cafef_client.bulk_year(
        "HOSE", 2026, end_date=date(2026, 11, 26), use_cache=False
    )

    assert seen.get("EndDate") == "11/26/2026"
    assert seen.get("EndDate") != "12/31/2026"


def test_bulk_year_use_cache_false_refetches(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake_get(*_a: Any, **_kw: Any) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(_xlsx_bytes())

    monkeypatch.setattr(cafef_client.requests, "get", fake_get)
    cafef_client.bulk_year("HOSE", 2022, use_cache=False)
    cafef_client.bulk_year("HOSE", 2022, use_cache=False)

    assert calls["n"] == 2


def test_reconcile_prices_passes_exchange(monkeypatch: pytest.MonkeyPatch) -> None:
    import vnbroker.reference as reference_pkg

    seen: dict[str, Any] = {}

    class FakeRef:
        def __init__(self, exchange: str = "HOSE", show_log: bool = False) -> None:
            seen["exchange"] = exchange

        def reconcile(self, *_a: Any, **_kw: Any) -> str:
            return "ok"

    monkeypatch.setattr(reference_pkg, "CafefReference", FakeRef)
    Vnbroker().reconcile_prices(pd.DataFrame(), symbol="VIT", exchange="HNX")

    assert seen.get("exchange") == "HNX"


def test_parse_records_exposes_date_and_change_pct() -> None:
    frame = parse_records(
        [
            {
                "date": "2022-01-04",
                "symbol": "TPB",
                "close_raw": 42.75,
                "close_adjusted": 17.94,
                "open": 41.5,
                "high": 43.25,
                "low": 41.3,
                "volume": 11034900,
                "value": 467.26,
                "put_through_volume": 0,
                "put_through_value": 0.0,
                "change_pct": 4.01,
            }
        ],
        "TPB",
    )

    assert "date" in frame.columns
    assert frame.iloc[0]["date"] == date(2022, 1, 4)
    assert "change_pct" in frame.columns
    assert frame.iloc[0]["change_pct"] == pytest.approx(4.01)
