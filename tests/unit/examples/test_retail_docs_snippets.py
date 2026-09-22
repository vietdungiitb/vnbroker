"""
R4: chạy 4 snippets trong docs/RETAIL_USAGE.md trên mock (không mạng).
"""

from __future__ import annotations

import base64
import io
import json
from typing import Any

import pandas as pd
import pytest

from vnbroker import Vnbroker
from vnbroker.ui import Fundamental, Market, Reference, Retail

pytestmark = pytest.mark.retail


class FakeResp:
    def __init__(self, status_code: int = 200, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload or {})

    def json(self) -> Any:
        return self._payload


def test_snippet_sjc(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "success": True,
        "data": [
            {
                "TypeName": "SJC 1L",
                "BranchName": "HCM",
                "BuyValue": 100.0,
                "SellValue": 102.0,
            }
        ],
    }
    monkeypatch.setattr(
        "vnbroker.explorer.misc.gold_price.requests.post",
        lambda *a, **k: FakeResp(200, payload),
    )
    retail = Vnbroker().retail()
    sjc = retail.gold(source="sjc", date="2026-01-15")
    assert list(sjc[["name", "branch", "buy_price", "sell_price"]].columns) == [
        "name",
        "branch",
        "buy_price",
        "sell_price",
    ]


def test_snippet_btmc(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "DataList": {
            "Data": [
                {
                    "@row": 1,
                    "@n_1": "Rồng",
                    "@k_1": "24K",
                    "@h_1": "99",
                    "@pb_1": "100",
                    "@ps_1": "102",
                    "@pt_1": "90",
                    "@d_1": "2026-01-15",
                }
            ]
        }
    }
    monkeypatch.setattr(
        "vnbroker.explorer.misc.gold_price.requests.get",
        lambda *a, **k: FakeResp(200, payload),
    )
    retail = Vnbroker().retail()
    btmc = retail.gold(source="btmc")
    assert list(btmc[["name", "karat", "buy_price", "sell_price"]].columns) == [
        "name",
        "karat",
        "buy_price",
        "sell_price",
    ]


def test_snippet_vcb(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [["H"] * 5] + [["X"] * 5] * 2 + [["USD", "Dollar", "1", "2", "3"]]
    rows += [["F"] * 5] * 4
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="ExchangeRate", index=False, header=False)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    monkeypatch.setattr(
        "vnbroker.explorer.misc.exchange_rate.requests.get",
        lambda *a, **k: FakeResp(200, {"Data": b64}),
    )
    fx = Vnbroker().retail().exchange_rate(date="2026-01-15")
    assert list(fx[["currency_code", "currency_name", "buy_cash", "sell"]].columns)


def test_snippet_unified_ui(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import patch

    with patch("vnbroker.ui.market.Quote", autospec=True) as q:
        Market().equity("SSI").history(start="2026-01-01")
        assert q.called
    with patch("vnbroker.ui.reference.Company", autospec=True) as c:
        Reference().company("SSI").profile()
        assert c.called
    with patch("vnbroker.ui.fundamental.Finance", autospec=True) as f:
        Fundamental().equity("SSI").balance_sheet(period="year")
        assert f.called
    assert isinstance(Retail(), Retail)
