"""
vnbroker.broker.tcbs.portfolio — TCBSPortfolioEngine: compute PnL & reconcile.

INPUT DATA SOURCES (đều từ S5/S6 services — không HTTP mới trong engine này):
  - TCBSAccountService.get_holdings()    → DataFrame holdings cơ sở
  - TCBSAccountService.get_balance()     → DataFrame tổng tài sản
  - TCBSEquityService.get_executions()   → DataFrame lịch sử khớp lệnh

OUTPUTS:
  - holdings_snapshot()   → DataFrame holdings với unrealized PnL, weight%
  - cash_snapshot()       → DataFrame cash/buying power/debt
  - realized_pnl()        → DataFrame realized PnL từ executions
  - portfolio_summary()   → dict tổng hợp
  - reconcile()           → DataFrame so sánh broker holdings vs local ledger

PURE COMPUTE: Không gửi HTTP. Nhận DataFrames làm input.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


class TCBSPortfolioEngine:
    """
    Portfolio engine: tính PnL, reconcile, portfolio summary.

    Không inject session/config — chỉ nhận DataFrames đã lấy từ services.
    Caller tự quyết khi nào fetch, engine chỉ compute.
    """

    # ── Holdings snapshot ────────────────────────────────────────────────────

    @staticmethod
    def holdings_snapshot(holdings_df: pd.DataFrame) -> pd.DataFrame:
        """
        Thêm weight%, unrealized_pnl_pct (nếu chưa có) vào holdings DataFrame.

        Input: DataFrame từ TCBSAccountService.get_holdings()
        Columns bắt buộc: symbol, quantity, average_cost, current_price,
                          market_value, unrealized_pnl

        Output thêm:
          - weight_pct (float64): % giá trị so với tổng portfolio
          - unrealized_pnl_pct (float64): % PnL so với cost basis

        Returns empty DataFrame với đúng columns nếu input rỗng.
        """
        required = {"symbol", "quantity", "average_cost", "current_price", "market_value", "unrealized_pnl"}
        if holdings_df.empty or not required.issubset(holdings_df.columns):
            return _empty_holdings_snapshot()

        df = holdings_df.copy()

        # Đảm bảo numeric
        for col in ("market_value", "average_cost", "current_price", "unrealized_pnl", "quantity"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

        total_market_value = df["market_value"].sum()
        if total_market_value > 0:
            df["weight_pct"] = (df["market_value"] / total_market_value * 100).round(4)
        else:
            df["weight_pct"] = 0.0

        # cost_basis = average_cost * quantity
        df["cost_basis"] = (df["average_cost"] * df["quantity"]).where(
            df["average_cost"].notna() & df["quantity"].notna(), other=0.0
        )

        # unrealized_pnl_pct theo cost basis nếu API không cung cấp
        if "unrealized_pnl_pct" not in df.columns or df["unrealized_pnl_pct"].isna().all():
            df["unrealized_pnl_pct"] = (
                df["unrealized_pnl"] / df["cost_basis"].replace(0, float("nan")) * 100
            ).round(4)

        df["weight_pct"] = df["weight_pct"].astype("float64")
        df["unrealized_pnl_pct"] = df["unrealized_pnl_pct"].astype("float64")
        return df

    # ── Cash snapshot ─────────────────────────────────────────────────────────

    @staticmethod
    def cash_snapshot(
        balance_df: pd.DataFrame,
        purchasing_power_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Tổng hợp cash position từ balance + purchasing_power.

        Input:
          balance_df: DataFrame từ TCBSAccountService.get_balance()
          purchasing_power_df: optional, từ get_purchasing_power()

        Output columns:
          account_no, total_asset, cash_balance, stock_value,
          debt_balance, available_advance_amount,
          purchasing_power (nếu có), margin_ratio (nếu có)
        """
        if balance_df.empty:
            return pd.DataFrame()

        df = balance_df.copy()

        if purchasing_power_df is not None and not purchasing_power_df.empty:
            pp = purchasing_power_df[["account_no", "purchasing_power", "margin_ratio"]].copy()
            df = df.merge(pp, on="account_no", how="left")

        return df

    # ── Realized PnL ──────────────────────────────────────────────────────────

    @staticmethod
    def realized_pnl(
        executions_df: pd.DataFrame,
        cost_map: Optional[dict[str, float]] = None,
    ) -> pd.DataFrame:
        """
        Tính realized PnL từ lịch sử khớp lệnh.

        SELL execution:
          realized_pnl = (executed_price - avg_cost) * executed_quantity - fee - tax
          Nếu cost_map không có symbol → pnl_available = False (không tính được)

        Input:
          executions_df: DataFrame từ TCBSEquityService.get_executions()
            columns cần: symbol, side, executed_quantity, executed_price, fee, tax
          cost_map: {symbol: average_cost} — có thể từ holdings hoặc ledger ngoài

        Output columns:
          symbol, executed_at, side, executed_quantity, executed_price,
          fee, tax, avg_cost, gross_pnl, net_pnl, pnl_available (bool)
        """
        if executions_df.empty:
            return _empty_realized_pnl()

        df = executions_df.copy()
        for col in ("executed_quantity", "executed_price", "fee", "tax"):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        sells = df[df["side"].astype(str).str.upper() == "SELL"].copy()
        if sells.empty:
            return _empty_realized_pnl()

        cost_map = cost_map or {}

        def _calc_row(row):
            sym = row["symbol"]
            avg_cost = cost_map.get(sym)
            if avg_cost is None:
                return pd.Series({
                    "avg_cost": float("nan"),
                    "gross_pnl": float("nan"),
                    "net_pnl": float("nan"),
                    "pnl_available": False,
                })
            gross = (row["executed_price"] - avg_cost) * row["executed_quantity"]
            net = gross - row["fee"] - row["tax"]
            return pd.Series({
                "avg_cost": float(avg_cost),
                "gross_pnl": float(gross),
                "net_pnl": float(net),
                "pnl_available": True,
            })

        pnl_cols = sells.apply(_calc_row, axis=1)
        result = pd.concat([sells.reset_index(drop=True), pnl_cols.reset_index(drop=True)], axis=1)

        keep = [c for c in (
            "symbol", "executed_at", "side", "executed_quantity",
            "executed_price", "fee", "tax",
            "avg_cost", "gross_pnl", "net_pnl", "pnl_available",
        ) if c in result.columns]
        return result[keep].astype({"pnl_available": bool})

    # ── Portfolio summary ────────────────────────────────────────────────────

    @staticmethod
    def portfolio_summary(
        holdings_df: pd.DataFrame,
        balance_df: pd.DataFrame,
    ) -> dict:
        """
        Dict tổng hợp portfolio: total_asset, stock_value, cash_balance,
        debt_balance, num_positions, total_unrealized_pnl, top_holding.

        Input: DataFrames từ holdings_snapshot() và balance_df.
        """
        summary: dict = {
            "total_asset": 0.0,
            "stock_value": 0.0,
            "cash_balance": 0.0,
            "debt_balance": 0.0,
            "num_positions": 0,
            "total_unrealized_pnl": 0.0,
            "top_holding": None,
        }

        if not balance_df.empty:
            row = balance_df.iloc[0]
            summary["total_asset"] = float(row.get("total_asset", 0) or 0)
            summary["stock_value"] = float(row.get("stock_value", 0) or 0)
            summary["cash_balance"] = float(row.get("cash_balance", 0) or 0)
            summary["debt_balance"] = float(row.get("debt_balance", 0) or 0)

        if not holdings_df.empty:
            summary["num_positions"] = len(holdings_df)
            if "unrealized_pnl" in holdings_df.columns:
                summary["total_unrealized_pnl"] = float(
                    pd.to_numeric(holdings_df["unrealized_pnl"], errors="coerce").sum()
                )
            if "market_value" in holdings_df.columns:
                mv_series = pd.to_numeric(holdings_df["market_value"], errors="coerce").dropna()
                if not mv_series.empty:
                    idx = mv_series.idxmax()
                    summary["top_holding"] = holdings_df.loc[idx, "symbol"]

        return summary

    # ── Reconciliation ───────────────────────────────────────────────────────

    @staticmethod
    def reconcile(
        broker_holdings_df: pd.DataFrame,
        local_ledger_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        So sánh holdings từ broker API vs local ledger.

        Input:
          broker_holdings_df: DataFrame từ get_holdings(), cột quan trọng: symbol, quantity
          local_ledger_df: DataFrame local, cùng schema. Nếu None/empty → tất cả là BROKER_ONLY

        Output columns:
          symbol, broker_qty, local_qty, qty_diff, status
            status values:
              MATCH       — broker_qty == local_qty
              QTY_MISMATCH — qty khác nhau
              BROKER_ONLY  — có trong broker nhưng không có trong local
              LOCAL_ONLY   — có trong local nhưng không có trong broker
        """
        if broker_holdings_df.empty and (local_ledger_df is None or local_ledger_df.empty):
            return _empty_reconcile()

        b = _normalize_for_reconcile(broker_holdings_df, "broker_qty")
        l = _normalize_for_reconcile(local_ledger_df, "local_qty")

        merged = b.merge(l, on="symbol", how="outer")

        merged["broker_qty"] = pd.to_numeric(merged["broker_qty"], errors="coerce")
        merged["local_qty"] = pd.to_numeric(merged["local_qty"], errors="coerce")
        merged["qty_diff"] = merged["broker_qty"].fillna(0) - merged["local_qty"].fillna(0)

        def _status(row):
            b_null = pd.isna(row["broker_qty"])
            l_null = pd.isna(row["local_qty"])
            if b_null:
                return "LOCAL_ONLY"
            if l_null:
                return "BROKER_ONLY"
            if row["broker_qty"] == row["local_qty"]:
                return "MATCH"
            return "QTY_MISMATCH"

        merged["status"] = merged.apply(_status, axis=1).astype("category")
        return merged[["symbol", "broker_qty", "local_qty", "qty_diff", "status"]]


# ── Private helpers ───────────────────────────────────────────────────────────

def _empty_holdings_snapshot() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "symbol", "quantity", "available_quantity", "average_cost",
        "current_price", "market_value", "unrealized_pnl",
        "unrealized_pnl_pct", "weight_pct", "cost_basis",
    ])


def _empty_realized_pnl() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "symbol", "executed_at", "side", "executed_quantity",
        "executed_price", "fee", "tax",
        "avg_cost", "gross_pnl", "net_pnl", "pnl_available",
    ])


def _empty_reconcile() -> pd.DataFrame:
    return pd.DataFrame(columns=["symbol", "broker_qty", "local_qty", "qty_diff", "status"])


def _normalize_for_reconcile(df: Optional[pd.DataFrame], qty_col: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["symbol", qty_col])
    out = df[["symbol"]].copy()
    out[qty_col] = pd.to_numeric(df.get("quantity", pd.Series(dtype="float64")), errors="coerce")
    return out
