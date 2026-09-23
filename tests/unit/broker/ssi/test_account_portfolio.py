"""
S2: SSI account/portfolio/money read + snapshot map tường minh. Mocked.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

import pandas as pd
import pytest

from vnbroker.broker.exceptions import (
    BrokerSessionExpiredError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.ssi._transport import SSIHttpClient
from vnbroker.broker.ssi.account import SSIAccountService
from vnbroker.broker.ssi.money import SSIMoneyService
from vnbroker.broker.ssi.portfolio import SSIPortfolioService

pytestmark = pytest.mark.ssi


class FakeResponse:
    def __init__(self, status_code: int, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers: Dict[str, str] = {}
        self.text = json.dumps(payload or {})

    def json(self) -> Any:
        return self._payload


class FakeSession:
    def __init__(self, script: List[Any]) -> None:
        self._script = list(script)
        self.headers: Dict[str, str] = {}
        self.calls: List[Dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        item = self._script.pop(0)
        assert isinstance(item, FakeResponse)
        return item

    def close(self) -> None:
        return None


def make_services(
    script: List[Any], monkeypatch: pytest.MonkeyPatch, **cfg: Any
) -> tuple:
    fake = FakeSession(script)
    monkeypatch.setattr("vnbroker.broker.ssi._transport.requests.Session", lambda: fake)
    base = {"api_key": "K", "api_secret": "S", "client_id": "C"}
    base.update(cfg)
    config = SSICredentialConfig.from_dict(base)
    session = BrokerSession(provider="SSI")
    session.set_token("T")
    transport = SSIHttpClient(base_url="https://api.ssi.com.vn", rate_limit_rps=0)
    transport.set_token("T")
    account = SSIAccountService(config, session, transport)
    money = SSIMoneyService(config, session, transport)
    portfolio = SSIPortfolioService(config, session, transport)
    return account, money, portfolio, fake, session


POSITIONS_BODY = {
    "equity": [
        {
            "accountNo": "A1",
            "symbol": "SSI",
            "quantity": 1000,
            "sellableQuantity": 800,
            "buyingQuantity": 0,
            "sellingQuantity": 0,
            "mortgageQuantity": 0,
            "costPrice": 24000.0,
            "t1SellQuantity": 100,
            "t2SellQuantity": 100,
        }
    ],
    "derivative": {
        "derOpenPositions": [
            {
                "accountNo": "A1",
                "symbol": "VN30F2601",
                "long": 2,
                "short": 0,
                "net": 2,
                "bidAvgPrice": 1400.0,
                "askAvgPrice": 0.0,
                "tradePrice": 1400.0,
                "floatingPL": 100.0,
                "tradingPL": 50.0,
            }
        ],
        "derClosePositions": [],
    },
}


class TestAccount:
    def test_list_raw(self, monkeypatch: pytest.MonkeyPatch) -> None:
        account, _, _, fake, _ = make_services(
            [FakeResponse(200, [{"accountNo": "A1", "accountType": "Cash"}])],
            monkeypatch,
        )
        out = account.list_accounts(raw=True)
        assert out == [{"accountNo": "A1", "accountType": "Cash"}]
        assert fake.calls[0]["url"].endswith("/api/v3/account/info")

    def test_list_df(self, monkeypatch: pytest.MonkeyPatch) -> None:
        account, _, _, _, _ = make_services(
            [
                FakeResponse(
                    200,
                    [
                        {"accountNo": "0123456789", "accountType": "Cash"},
                        {"accountNo": "X", "accountType": "Margin"},
                        {"accountNo": "Y", "accountType": "Derivative"},
                        {"accountNo": "Z", "accountType": "Weird"},
                    ],
                )
            ],
            monkeypatch,
        )
        df = account.list_accounts()
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["account_no", "account_type"]
        assert df.iloc[0]["account_no"] == "******6789"
        assert df.iloc[0]["account_type"] == "EQUITY"
        assert df.iloc[1]["account_type"] == "EQUITY_MARGIN"
        assert df.iloc[2]["account_type"] == "DERIVATIVE"
        assert df.iloc[3]["account_type"] == "Weird"

    def test_expired_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        account, _, _, _, session = make_services([FakeResponse(200, [])], monkeypatch)
        session.revoke()
        with pytest.raises(BrokerSessionExpiredError):
            account.list_accounts()


class TestMoney:
    def test_balance_df(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, money, _, fake, _ = make_services(
            [
                FakeResponse(
                    200,
                    {
                        "equity": {
                            "accountNo": "A1",
                            "accountBalance": 100.0,
                            "totalDebt": 5.0,
                            "withdrawable": 80.0,
                        }
                    },
                )
            ],
            monkeypatch,
        )
        df = money.get_balance("A1")
        assert isinstance(df, pd.DataFrame)
        assert df.iloc[0]["account_balance"] == 100.0
        assert df.iloc[0]["withdrawable"] == 80.0
        assert str(df["account_balance"].dtype) == "float64"
        assert fake.calls[0]["params"] == {"clientId": "C", "accountNo": "A1"}

    def test_balance_missing_equity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, money, _, _, _ = make_services(
            [FakeResponse(200, {"derivative": {}})], monkeypatch
        )
        df = money.get_balance("A1")
        assert isinstance(df, pd.DataFrame) and df.empty

    def test_balance_raw(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, money, _, _, _ = make_services(
            [FakeResponse(200, {"equity": {"accountNo": "A1"}})], monkeypatch
        )
        assert money.get_balance("A1", raw=True) == {"equity": {"accountNo": "A1"}}

    def test_derivative_balance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, money, _, _, _ = make_services(
            [
                FakeResponse(
                    200,
                    {"derivative": {"accountNo": "A1", "floatingPL": 10.0}},
                )
            ],
            monkeypatch,
        )
        df = money.get_derivative_balance("A1")
        assert df.iloc[0]["floating_pl"] == 10.0

    def test_ppmmr_full_columns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, money, _, _, _ = make_services(
            [
                FakeResponse(
                    200,
                    {
                        "equity": {
                            "accountNo": "A1",
                            "purchasingPower": 50.0,
                            "marginRatio": 60.0,
                        }
                    },
                )
            ],
            monkeypatch,
        )
        df = money.get_ppmmr("A1")
        assert df.iloc[0]["purchasing_power"] == 50.0
        assert df.iloc[0]["margin_ratio"] == 60.0
        assert df.iloc[0]["account_no"] == "A1"

    def test_max_buy_sell(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, money, _, fake, _ = make_services(
            [
                FakeResponse(
                    200,
                    {
                        "accountNo": "A1",
                        "maxBuyQty": 500,
                        "maxSellQty": 300,
                        "marginRatio": "60",
                        "purchasePower": "999",
                    },
                )
            ],
            monkeypatch,
        )
        df = money.get_max_buy_sell("A1", "ssi", 25000)
        assert df.iloc[0]["symbol"] == "SSI"
        assert df.iloc[0]["max_buy_quantity"] == 500
        assert fake.calls[0]["params"]["price"] == "25000"

    def test_max_buy_sell_market(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, money, _, fake, _ = make_services(
            [FakeResponse(200, {"accountNo": "A1"})], monkeypatch
        )
        money.get_max_buy_sell_at_market_price("A1", "SSI")
        assert "price" not in fake.calls[0]["params"]

    def test_max_buy_sell_bad_price(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, money, _, fake, _ = make_services([], monkeypatch)
        with pytest.raises(BrokerValidationError):
            money.get_max_buy_sell("A1", "SSI", 0)
        assert fake.calls == []

    def test_missing_client_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, money, _, fake, _ = make_services([], monkeypatch, client_id="")
        with pytest.raises(BrokerValidationError) as exc:
            money.get_balance("A1")
        assert exc.value.code == "CLIENT_ID_REQUIRED"
        assert fake.calls == []


class TestPortfolio:
    def test_equity_positions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, _, portfolio, _, _ = make_services(
            [FakeResponse(200, POSITIONS_BODY)], monkeypatch
        )
        df = portfolio.get_equity_positions("A1")
        assert df.iloc[0]["symbol"] == "SSI"
        assert df.iloc[0]["quantity"] == 1000
        assert df.iloc[0]["average_cost"] == 24000.0
        assert str(df["quantity"].dtype) == "Int64"

    def test_positions_raw(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, _, portfolio, _, _ = make_services(
            [FakeResponse(200, POSITIONS_BODY)], monkeypatch
        )
        assert portfolio.get_equity_positions("A1", raw=True) == POSITIONS_BODY

    def test_deriv_open_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, _, portfolio, _, _ = make_services(
            [FakeResponse(200, POSITIONS_BODY)], monkeypatch
        )
        df = portfolio.get_derivative_positions("A1", open_only=True)
        assert len(df) == 1
        assert df.iloc[0]["state"] == "OPEN"
        assert df.iloc[0]["net"] == 2

    def test_deriv_all_states(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = {
            "derivative": {
                "derOpenPositions": [{"symbol": "A", "long": 1, "short": 0, "net": 1}],
                "derClosePositions": [
                    {"symbol": "B", "long": 0, "short": 1, "net": -1}
                ],
            }
        }
        _, _, portfolio, _, _ = make_services([FakeResponse(200, body)], monkeypatch)
        df = portfolio.get_derivative_positions("A1")
        assert sorted(df["state"].tolist()) == ["CLOSED", "OPEN"]

    def test_today_orders(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = {
            "accountNo": "A1",
            "orderList": [
                {
                    "orderId": "O1",
                    "clientRequestId": "R1",
                    "symbol": "SSI",
                    "side": "B",
                    "orderType": "LO",
                    "price": 25000.0,
                    "avgPrice": 0.0,
                    "quantity": 100,
                    "osQuantity": 100,
                    "filledQuantity": 0,
                    "cancelQuantity": 0,
                    "orderStatus": "QU",
                    "inputTime": "t",
                    "modifiedTime": "",
                    "message": "",
                }
            ],
            "totalRecord": 1,
        }
        _, _, portfolio, fake, _ = make_services([FakeResponse(200, body)], monkeypatch)
        df = portfolio.get_today_orders("A1")
        assert df.iloc[0]["side"] == "BUY"
        assert df.iloc[0]["status"] == "QUEUED"
        assert df.iloc[0]["order_type"] == "LO"
        assert fake.calls[0]["params"]["from"] == fake.calls[0]["params"]["to"]

    def test_history_bad_date(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, _, portfolio, fake, _ = make_services([], monkeypatch)
        with pytest.raises(BrokerValidationError):
            portfolio.get_historical_orders("A1", "2026-01-01", "2026/01/31")
        assert fake.calls == []

    def test_snapshot(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, _, portfolio, _, _ = make_services(
            [
                FakeResponse(200, POSITIONS_BODY),
                FakeResponse(
                    200,
                    {
                        "equity": {
                            "accountNo": "A1",
                            "withdrawable": 80000.0,
                            "totalDebt": 0.0,
                        }
                    },
                ),
            ],
            monkeypatch,
        )
        out = portfolio.portfolio_snapshot("A1", market_prices={"SSI": 26000.0})
        assert out["num_positions"] == 1
        assert out["stock_value"] == pytest.approx(26000.0 * 1000)
        assert out["cash_balance"] == 80000.0
        assert out["total_unrealized_pnl"] == pytest.approx(2000.0 * 1000)
        assert out["top_holding"] == "SSI"

    def test_snapshot_missing_price_warns(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _, _, portfolio, _, _ = make_services(
            [
                FakeResponse(200, POSITIONS_BODY),
                FakeResponse(200, {"equity": {"accountNo": "A1"}}),
            ],
            monkeypatch,
        )
        with caplog.at_level(logging.WARNING, logger="vnbroker.broker.ssi.portfolio"):
            out = portfolio.portfolio_snapshot("A1", market_prices={})
        assert "thiếu giá thị trường" in caplog.text
        assert out["num_positions"] == 1

    def test_snapshot_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, _, portfolio, _, _ = make_services(
            [FakeResponse(200, {"equity": []})], monkeypatch
        )
        out = portfolio.portfolio_snapshot("A1")
        assert out["num_positions"] == 0
        assert out["top_holding"] is None
        assert out["holdings"].empty
