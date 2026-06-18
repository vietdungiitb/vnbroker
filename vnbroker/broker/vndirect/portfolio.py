"""
vnbroker.broker.vndirect.portfolio — VNDirect Portfolio Engine.

Pure compute engine for portfolio analytics (no I/O).
"""

from __future__ import annotations

import pandas as pd


class VNDirectPortfolioEngine:
    """
    Pure compute engine for VNDirect portfolio analytics.
    
    No I/O operations — only DataFrame transformations.
    """

    @staticmethod
    def holdings_snapshot(holdings_df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize and enrich holdings DataFrame.
        
        Args:
            holdings_df: Raw holdings DataFrame from VNDirect API
            
        Returns:
            Enriched holdings DataFrame with computed fields
        """
        if holdings_df.empty:
            return holdings_df
        
        df = holdings_df.copy()
        
        # Standardize column names
        column_mapping = {
            "symbol": "symbol",
            "quantity": "quantity",
            "avgPrice": "avg_price",
            "currentPrice": "current_price",
            "marketValue": "market_value",
            "pnl": "unrealized_pnl",
            "pnlPercent": "unrealized_pnl_pct",
        }
        
        # Rename columns that exist
        rename_dict = {k: v for k, v in column_mapping.items() if k in df.columns}
        if rename_dict:
            df = df.rename(columns=rename_dict)
        
        # Compute missing fields if we have the components
        if "quantity" in df.columns and "avg_price" in df.columns and "current_price" in df.columns:
            if "market_value" not in df.columns:
                df["market_value"] = df["quantity"] * df["current_price"]
            if "unrealized_pnl" not in df.columns:
                df["unrealized_pnl"] = (df["current_price"] - df["avg_price"]) * df["quantity"]
            if "unrealized_pnl_pct" not in df.columns:
                df["unrealized_pnl_pct"] = (
                    (df["current_price"] - df["avg_price"]) / df["avg_price"] * 100
                ).where(df["avg_price"] != 0, 0)
        
        return df

    @staticmethod
    def portfolio_summary(
        enriched_holdings: pd.DataFrame,
        balance_df: pd.DataFrame,
    ) -> dict:
        """
        Compute portfolio summary from holdings and balance.
        
        Args:
            enriched_holdings: Holdings DataFrame from holdings_snapshot()
            balance_df: Balance DataFrame from get_balance()
            
        Returns:
            Portfolio summary dictionary
        """
        total_market_value = 0.0
        total_unrealized_pnl = 0.0
        total_cost = 0.0
        
        if not enriched_holdings.empty:
            if "market_value" in enriched_holdings.columns:
                total_market_value = enriched_holdings["market_value"].sum()
            if "unrealized_pnl" in enriched_holdings.columns:
                total_unrealized_pnl = enriched_holdings["unrealized_pnl"].sum()
            if "quantity" in enriched_holdings.columns and "avg_price" in enriched_holdings.columns:
                total_cost = (enriched_holdings["quantity"] * enriched_holdings["avg_price"]).sum()
        
        # Extract cash balance
        cash_balance = 0.0
        if not balance_df.empty:
            # Try common cash balance column names
            for col in ["cashBalance", "cash_balance", "availableCash", "available_cash", "balance"]:
                if col in balance_df.columns:
                    cash_balance = balance_df[col].iloc[0] if len(balance_df) > 0 else 0.0
                    break
        
        total_assets = total_market_value + cash_balance
        total_pnl = total_unrealized_pnl
        total_return_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
        
        return {
            "total_market_value": total_market_value,
            "cash_balance": cash_balance,
            "total_assets": total_assets,
            "total_cost": total_cost,
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_return_pct": total_return_pct,
            "holdings_count": len(enriched_holdings) if not enriched_holdings.empty else 0,
        }