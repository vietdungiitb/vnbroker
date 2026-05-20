"""
tests.unit.broker.tcbs.test_portfolio
======================================
Unit tests cho TCBSPortfolioEngine.

Test categories:
  - TestHoldingsSnapshot    (8 tests)
  - TestCashSnapshot        (4 tests)
  - TestRealizedPnl         (7 tests)
  - TestPortfolioSummary    (5 tests)
  - TestReconcile           (8 tests)
"""
from __future__ import annotations

import pandas as pd
import pytest

from vnbroker.broker.tcbs.portfolio import TCBSPortfolioEngine

# ── Fixtures ─────────────────────────────────────────────────────────────────

def _holdings_df(**overrides) -> pd.DataFrame:
    data = {
        "symbol": ["VNM", "HPG"],
        "quantity": [500, 1000],
        "available_quantity": [400, 900],
        "average_cost": [79500.0, 25000.0],
        "current_price": [80200.0, 26000.0],
        "market_value": [40100000.0, 26000000.0],
        "unrealized_pnl": [350000.0, 1000000.0],
    }
    data.update(overrides)
    return pd.DataFrame(data)


def _balance_df() -> pd.DataFrame:
    return pd.DataFrame([{
        "account_no": "0123456789",
        "total_asset": 100_000_000.0,
        "cash_balance": 20_000_000.0,
        "stock_value": 80_000_000.0,
        "debt_balance": 0.0,
        "available_advance_amount": 15_000_000.0,
    }])


def _executions_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "execution_id": "EXE1",
            "order_id": "ORD1",
            "symbol": "VNM",
            "side": "SELL",
            "executed_quantity": 100,
            "executed_price": 82000.0,
            "executed_at": "2026-05-19T10:30:00+07:00",
            "fee": 820.0,
            "tax": 164.0,
        },
        {
            "execution_id": "EXE2",
            "order_id": "ORD2",
            "symbol": "HPG",
            "side": "BUY",
            "executed_quantity": 200,
            "executed_price": 25500.0,
            "executed_at": "2026-05-19T11:00:00+07:00",
            "fee": 510.0,
            "tax": 0.0,
        },
    ])


# ── TestHoldingsSnapshot ──────────────────────────────────────────────────────

class TestHoldingsSnapshot:
    def test_returns_dataframe_with_weight_pct(self):
        df = TCBSPortfolioEngine.holdings_snapshot(_holdings_df())
        assert "weight_pct" in df.columns
        assert df["weight_pct"].dtype == "float64"

    def test_weight_pct_sums_to_100(self):
        df = TCBSPortfolioEngine.holdings_snapshot(_holdings_df())
        total = df["weight_pct"].sum()
        assert abs(total - 100.0) < 0.01

    def test_adds_cost_basis_column(self):
        df = TCBSPortfolioEngine.holdings_snapshot(_holdings_df())
        assert "cost_basis" in df.columns
        # VNM: 79500 * 500 = 39750000
        vnm = df[df["symbol"] == "VNM"]["cost_basis"].iloc[0]
        assert abs(vnm - 39_750_000.0) < 1.0

    def test_computes_unrealized_pnl_pct_when_missing(self):
        h = _holdings_df()
        df = TCBSPortfolioEngine.holdings_snapshot(h)
        assert "unrealized_pnl_pct" in df.columns
        # VNM: 350000 / 39750000 * 100 ≈ 0.88
        vnm_pct = df[df["symbol"] == "VNM"]["unrealized_pnl_pct"].iloc[0]
        assert abs(vnm_pct - 0.88) < 0.1

    def test_empty_input_returns_empty_df_with_columns(self):
        result = TCBSPortfolioEngine.holdings_snapshot(pd.DataFrame())
        assert isinstance(result, pd.DataFrame)
        assert result.empty
        assert "weight_pct" in result.columns

    def test_missing_required_columns_returns_empty(self):
        bad = pd.DataFrame({"symbol": ["VNM"], "quantity": [100]})
        result = TCBSPortfolioEngine.holdings_snapshot(bad)
        assert result.empty

    def test_single_position_weight_100_pct(self):
        h = _holdings_df(symbol=["VNM"], quantity=[500], average_cost=[79500.0],
                         current_price=[80200.0], market_value=[40100000.0],
                         unrealized_pnl=[350000.0], available_quantity=[400])
        df = TCBSPortfolioEngine.holdings_snapshot(h)
        assert df["weight_pct"].iloc[0] == pytest.approx(100.0, abs=0.01)

    def test_existing_unrealized_pnl_pct_preserved_when_provided(self):
        """Nếu API đã cung cấp unrealized_pnl_pct → giữ nguyên, không tính lại."""
        h = _holdings_df()
        h["unrealized_pnl_pct"] = [0.88, 4.0]  # pre-provided
        df = TCBSPortfolioEngine.holdings_snapshot(h)
        assert df[df["symbol"] == "HPG"]["unrealized_pnl_pct"].iloc[0] == pytest.approx(4.0)


# ── TestCashSnapshot ──────────────────────────────────────────────────────────

class TestCashSnapshot:
    def test_returns_balance_columns(self):
        result = TCBSPortfolioEngine.cash_snapshot(_balance_df())
        assert "cash_balance" in result.columns
        assert "total_asset" in result.columns

    def test_merges_purchasing_power_when_provided(self):
        pp = pd.DataFrame([{
            "account_no": "0123456789",
            "purchasing_power": 12_000_000.0,
            "margin_ratio": 0.0,
        }])
        result = TCBSPortfolioEngine.cash_snapshot(_balance_df(), pp)
        assert "purchasing_power" in result.columns
        assert result["purchasing_power"].iloc[0] == 12_000_000.0

    def test_no_purchasing_power_does_not_add_column(self):
        result = TCBSPortfolioEngine.cash_snapshot(_balance_df())
        assert "purchasing_power" not in result.columns

    def test_empty_balance_returns_empty_df(self):
        result = TCBSPortfolioEngine.cash_snapshot(pd.DataFrame())
        assert result.empty


# ── TestRealizedPnl ───────────────────────────────────────────────────────────

class TestRealizedPnl:
    def test_only_sell_executions_included(self):
        cost_map = {"VNM": 79500.0, "HPG": 25000.0}
        result = TCBSPortfolioEngine.realized_pnl(_executions_df(), cost_map)
        assert len(result) == 1  # only SELL VNM
        assert result["symbol"].iloc[0] == "VNM"

    def test_gross_pnl_correct(self):
        # VNM: (82000 - 79500) * 100 = 250000
        cost_map = {"VNM": 79500.0}
        result = TCBSPortfolioEngine.realized_pnl(_executions_df(), cost_map)
        assert result["gross_pnl"].iloc[0] == pytest.approx(250_000.0)

    def test_net_pnl_deducts_fee_and_tax(self):
        # VNM: 250000 - 820 - 164 = 249016
        cost_map = {"VNM": 79500.0}
        result = TCBSPortfolioEngine.realized_pnl(_executions_df(), cost_map)
        assert result["net_pnl"].iloc[0] == pytest.approx(249_016.0)

    def test_pnl_not_available_when_no_cost_map(self):
        result = TCBSPortfolioEngine.realized_pnl(_executions_df())
        assert len(result) == 1
        assert result["pnl_available"].iloc[0] == False  # noqa: E712

    def test_empty_executions_returns_empty_df(self):
        result = TCBSPortfolioEngine.realized_pnl(pd.DataFrame())
        assert result.empty
        assert "net_pnl" in result.columns

    def test_no_sell_executions_returns_empty(self):
        buys_only = _executions_df()[_executions_df()["side"] == "BUY"].copy()
        result = TCBSPortfolioEngine.realized_pnl(buys_only, {"HPG": 25000.0})
        assert result.empty

    def test_pnl_available_true_when_cost_map_provided(self):
        cost_map = {"VNM": 79500.0}
        result = TCBSPortfolioEngine.realized_pnl(_executions_df(), cost_map)
        assert result["pnl_available"].iloc[0] == True  # noqa: E712


# ── TestPortfolioSummary ──────────────────────────────────────────────────────

class TestPortfolioSummary:
    def test_returns_dict(self):
        result = TCBSPortfolioEngine.portfolio_summary(_holdings_df(), _balance_df())
        assert isinstance(result, dict)

    def test_total_asset_from_balance(self):
        result = TCBSPortfolioEngine.portfolio_summary(_holdings_df(), _balance_df())
        assert result["total_asset"] == 100_000_000.0

    def test_num_positions_from_holdings(self):
        result = TCBSPortfolioEngine.portfolio_summary(_holdings_df(), _balance_df())
        assert result["num_positions"] == 2

    def test_total_unrealized_pnl_sum(self):
        result = TCBSPortfolioEngine.portfolio_summary(_holdings_df(), _balance_df())
        assert result["total_unrealized_pnl"] == pytest.approx(1_350_000.0)

    def test_top_holding_is_highest_market_value(self):
        result = TCBSPortfolioEngine.portfolio_summary(_holdings_df(), _balance_df())
        # VNM: 40100000 > HPG: 26000000
        assert result["top_holding"] == "VNM"


# ── TestReconcile ─────────────────────────────────────────────────────────────

class TestReconcile:
    def _broker(self):
        return pd.DataFrame({
            "symbol": ["VNM", "HPG", "FPT"],
            "quantity": [500, 1000, 200],
        })

    def _local(self):
        return pd.DataFrame({
            "symbol": ["VNM", "HPG", "ACB"],
            "quantity": [500, 900, 300],
        })

    def test_returns_dataframe_with_status_column(self):
        result = TCBSPortfolioEngine.reconcile(self._broker(), self._local())
        assert "status" in result.columns
        assert result["status"].dtype.name == "category"

    def test_match_status_when_quantities_equal(self):
        result = TCBSPortfolioEngine.reconcile(self._broker(), self._local())
        vnm = result[result["symbol"] == "VNM"]["status"].iloc[0]
        assert vnm == "MATCH"

    def test_qty_mismatch_when_quantities_differ(self):
        result = TCBSPortfolioEngine.reconcile(self._broker(), self._local())
        hpg = result[result["symbol"] == "HPG"]["status"].iloc[0]
        assert hpg == "QTY_MISMATCH"

    def test_broker_only_when_not_in_local(self):
        result = TCBSPortfolioEngine.reconcile(self._broker(), self._local())
        fpt = result[result["symbol"] == "FPT"]["status"].iloc[0]
        assert fpt == "BROKER_ONLY"

    def test_local_only_when_not_in_broker(self):
        result = TCBSPortfolioEngine.reconcile(self._broker(), self._local())
        acb = result[result["symbol"] == "ACB"]["status"].iloc[0]
        assert acb == "LOCAL_ONLY"

    def test_qty_diff_correct_for_mismatch(self):
        result = TCBSPortfolioEngine.reconcile(self._broker(), self._local())
        hpg = result[result["symbol"] == "HPG"]
        # broker: 1000, local: 900 → diff = 100
        assert hpg["qty_diff"].iloc[0] == pytest.approx(100.0)

    def test_empty_local_all_broker_only(self):
        result = TCBSPortfolioEngine.reconcile(self._broker(), pd.DataFrame())
        assert (result["status"] == "BROKER_ONLY").all()

    def test_both_empty_returns_empty_df(self):
        result = TCBSPortfolioEngine.reconcile(pd.DataFrame(), pd.DataFrame())
        assert result.empty
        assert "status" in result.columns
