"""
Cross-provider capability test: test ACB across all providers and features.
Produces a capability matrix as a DataFrame and highlights gaps.

GATE (2026-09-28): module nay goi API THAT cua 6 provider (KBS/VCI/TCBS/DNSE/MSN/FMP)
o 7 capability x nhieu method = hang tram HTTP call. Khong co guard nen `pytest`
khong co tham so bi treo >15 phuc va 0.6 GB RAM bi nuot.

Suy ra lai trong bao cao kiem toan 2026-09-28: chay `pytest tests/unit` va
`pytest tests/integration` (CLAUDE.md:182) deu xanh trong <1 phut, nen khong ai
thay. Chi `pytest` chay ca `tests/` moi gap file nay.

Da sua theo dung convention da co san trong repo (vd
tests/unit/explorer/test_vci_quote_comprehensive.py:18-28): module-level skip
+ cung bien env `vnbroker_RUN_LIVE_INTEGRATION`. Muon chay:
    vnbroker_RUN_LIVE_INTEGRATION=1 pytest tests/test_acb_all_providers.py -s
"""

import sys, os, importlib, time, traceback
from datetime import datetime, timedelta
import pandas as pd

import pytest

RUN_LIVE_INTEGRATION = os.getenv("vnbroker_RUN_LIVE_INTEGRATION", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

if not RUN_LIVE_INTEGRATION:
    pytest.skip(
        "Live cross-provider capability benchmark is disabled by default "
        "(hundreds of real HTTP calls). Set vnbroker_RUN_LIVE_INTEGRATION=1 to run.",
        allow_module_level=True,
    )

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vnbroker.common.data import (
    Quote, Company, Finance, News, Trading, Listing, Screener, StockComponents
)

SYMBOL = "ACB"
PROVIDERS = {
    "quote":     {"KBS", "VCI", "TCBS", "DNSE", "MSN", "FMP"},
    "company":   {"KBS", "VCI", "TCBS", "DNSE", "MSN", "FMP"},
    "finance":   {"KBS", "VCI", "TCBS", "DNSE", "FMP"},
    "news":      {"KBS", "VCI", "TCBS", "DNSE"},
    "trading":   {"KBS", "VCI", "TCBS", "DNSE", "MSN"},
    "listing":   {"KBS", "VCI", "TCBS", "DNSE", "FMP"},
    "screener":  {"TCBS", "VCI", "KBS"},
}

METHODS = {
    "quote":     ["history", "intraday", "price_depth"],
    "company":   ["overview", "profile", "shareholders", "insider_deals",
                  "subsidiaries", "officers", "events", "dividends",
                  "affiliate", "trading_stats", "ratio_summary"],
    "finance":   ["balance_sheet", "income_statement", "cash_flow", "ratio"],
    "news":      ["latest", "by_symbol"],
    "trading":   ["price_board"],
    "listing":   ["all_symbols", "symbols_by_exchange", "symbols_by_group",
                  "industries_icb", "all_future_indices", "all_covered_warrant"],
    "screener":  ["stock"],
}

ENV_FALLBACK = {
    "DNSE_API_KEY":    os.environ.get("DNSE_API_KEY", ""),
    "DNSE_API_SECRET": os.environ.get("DNSE_API_SECRET", ""),
    "FMP_API_KEY":     os.environ.get("FMP_API_KEY", ""),
    "TCBS_AUTH_TOKEN": os.environ.get("TCBS_AUTH_TOKEN", ""),
}

def try_method(component, method_name, **kwargs):
    """Try calling a method on a component, return (success, result_or_error)."""
    try:
        method = getattr(component, method_name, None)
        if method is None:
            return False, NotImplementedError(f"Method {method_name} not found")
        result = method(**kwargs)
        if isinstance(result, pd.DataFrame):
            if result.empty:
                return "EMPTY", result
            return True, result
        return True, result
    except Exception as e:
        return False, e

def test_all():
    results = []

    # ---- Quote ----
    for provider in sorted(PROVIDERS["quote"]):
        needs_auth = provider in ("DNSE", "FMP", "TCBS")
        # Check auth
        if provider == "DNSE" and not ENV_FALLBACK["DNSE_API_KEY"]:
            results.append(("quote", provider, "history", "SKIP", "missing DNSE_API_KEY env"))
            for m in METHODS["quote"][1:]:
                results.append(("quote", provider, m, "SKIP", "missing DNSE_API_KEY env"))
            continue
        if provider == "FMP" and not ENV_FALLBACK["FMP_API_KEY"]:
            results.append(("quote", provider, "history", "SKIP", "missing FMP_API_KEY env"))
            for m in METHODS["quote"][1:]:
                results.append(("quote", provider, m, "SKIP", "missing FMP_API_KEY env"))
            continue

        try:
            kwargs = {}
            if provider == "DNSE":
                kwargs.update(api_key=ENV_FALLBACK["DNSE_API_KEY"],
                              api_secret=ENV_FALLBACK["DNSE_API_SECRET"])
            if provider == "FMP":
                kwargs["api_key"] = ENV_FALLBACK["FMP_API_KEY"]
            if provider == "TCBS":
                kwargs["auth_token"] = ENV_FALLBACK.get("TCBS_AUTH_TOKEN") or "test"

            comp = Quote(SYMBOL, source=provider, **kwargs)
            for method_name in METHODS["quote"]:
                t0 = time.time()
                ok, val = try_method(comp, method_name)
                elapsed = round(time.time() - t0, 2)
                status = "OK" if ok is True else ("EMPTY" if ok == "EMPTY" else "FAIL")
                detail = str(val)[:120] if not isinstance(val, bool) else ""
                results.append(("quote", provider, method_name, status, detail, elapsed))
        except Exception as e:
            for m in METHODS["quote"]:
                results.append(("quote", provider, m, "FAIL", str(e)[:120], 0))

    # ---- Company ----
    for provider in sorted(PROVIDERS["company"]):
        needs_auth = provider in ("DNSE", "FMP", "TCBS")
        if provider == "DNSE" and not ENV_FALLBACK["DNSE_API_KEY"]:
            for m in METHODS["company"]:
                results.append(("company", provider, m, "SKIP", "missing auth"))
            continue
        if provider == "FMP" and not ENV_FALLBACK["FMP_API_KEY"]:
            for m in METHODS["company"]:
                results.append(("company", provider, m, "SKIP", "missing auth"))
            continue
        if provider in ("MSN",) and provider in PROVIDERS["company"]:
            pass  # MSN is stub, will be tested

        try:
            kwargs = {}
            if provider == "DNSE":
                kwargs.update(api_key=ENV_FALLBACK["DNSE_API_KEY"] or "dummy",
                              api_secret=ENV_FALLBACK["DNSE_API_SECRET"] or "dummy")
            if provider == "FMP":
                kwargs["api_key"] = ENV_FALLBACK["FMP_API_KEY"]
            if provider == "TCBS":
                kwargs["auth_token"] = ENV_FALLBACK.get("TCBS_AUTH_TOKEN") or "test"

            comp = Company(SYMBOL, source=provider, **kwargs)
            for method_name in METHODS["company"]:
                t0 = time.time()
                ok, val = try_method(comp, method_name)
                elapsed = round(time.time() - t0, 2)
                status = "OK" if ok is True else ("EMPTY" if ok == "EMPTY" else "FAIL")
                detail = str(val)[:120] if not isinstance(val, bool) else ""
                results.append(("company", provider, method_name, status, detail, elapsed))
        except Exception as e:
            for m in METHODS["company"]:
                results.append(("company", provider, m, "FAIL", str(e)[:120], 0))

    # ---- Finance ----
    for provider in sorted(PROVIDERS["finance"]):
        if provider == "DNSE" and not ENV_FALLBACK["DNSE_API_KEY"]:
            for m in METHODS["finance"]:
                results.append(("finance", provider, m, "SKIP", "missing auth"))
            continue

        try:
            kwargs = {}
            if provider == "TCBS":
                kwargs["auth_token"] = ENV_FALLBACK.get("TCBS_AUTH_TOKEN") or "test"

            comp = Finance(SYMBOL, source=provider, **kwargs)
            for method_name in METHODS["finance"]:
                t0 = time.time()
                ok, val = try_method(comp, method_name, period="year")
                elapsed = round(time.time() - t0, 2)
                status = "OK" if ok is True else ("EMPTY" if ok == "EMPTY" else "FAIL")
                detail = str(val)[:120] if not isinstance(val, bool) else ""
                results.append(("finance", provider, method_name, status, detail, elapsed))
        except Exception as e:
            for m in METHODS["finance"]:
                results.append(("finance", provider, m, "FAIL", str(e)[:120], 0))

    # ---- News ----
    for provider in sorted(PROVIDERS["news"]):
        if provider == "DNSE" and not ENV_FALLBACK["DNSE_API_KEY"]:
            for m in METHODS["news"]:
                results.append(("news", provider, m, "SKIP", "missing auth"))
            continue

        try:
            kwargs = {}
            if provider == "TCBS":
                kwargs["auth_token"] = ENV_FALLBACK.get("TCBS_AUTH_TOKEN") or "test"

            comp = News(SYMBOL, source=provider, **kwargs)
            for method_name in METHODS["news"]:
                t0 = time.time()
                ok, val = try_method(comp, method_name, symbol=SYMBOL)
                elapsed = round(time.time() - t0, 2)
                status = "OK" if ok is True else ("EMPTY" if ok == "EMPTY" else "FAIL")
                detail = str(val)[:120] if not isinstance(val, bool) else ""
                results.append(("news", provider, method_name, status, detail, elapsed))
        except Exception as e:
            for m in METHODS["news"]:
                results.append(("news", provider, m, "FAIL", str(e)[:120], 0))

    # ---- Trading ----
    for provider in sorted(PROVIDERS["trading"]):
        if provider == "DNSE" and not ENV_FALLBACK["DNSE_API_KEY"]:
            for m in METHODS["trading"]:
                results.append(("trading", provider, m, "SKIP", "missing auth"))
            continue

        try:
            kwargs = {}
            if provider == "TCBS":
                kwargs["auth_token"] = ENV_FALLBACK.get("TCBS_AUTH_TOKEN") or "test"

            comp = Trading(SYMBOL, source=provider, **kwargs)
            for method_name in METHODS["trading"]:
                t0 = time.time()
                ok, val = try_method(comp, method_name, symbols_list=[SYMBOL, "VCB", "VNM"])
                elapsed = round(time.time() - t0, 2)
                status = "OK" if ok is True else ("EMPTY" if ok == "EMPTY" else "FAIL")
                detail = str(val)[:120] if not isinstance(val, bool) else ""
                results.append(("trading", provider, method_name, status, detail, elapsed))
        except Exception as e:
            for m in METHODS["trading"]:
                results.append(("trading", provider, m, "FAIL", str(e)[:120], 0))

    # ---- Listing ----
    for provider in sorted(PROVIDERS["listing"]):
        if provider == "DNSE" and not ENV_FALLBACK["DNSE_API_KEY"]:
            for m in METHODS["listing"]:
                results.append(("listing", provider, m, "SKIP", "missing auth"))
            continue
        if provider == "FMP" and not ENV_FALLBACK["FMP_API_KEY"]:
            for m in METHODS["listing"]:
                results.append(("listing", provider, m, "SKIP", "missing auth"))
            continue

        try:
            kwargs = {}
            if provider == "DNSE":
                kwargs.update(api_key=ENV_FALLBACK["DNSE_API_KEY"] or "dummy",
                              api_secret=ENV_FALLBACK["DNSE_API_SECRET"] or "dummy")
            if provider == "FMP":
                kwargs["api_key"] = ENV_FALLBACK["FMP_API_KEY"]

            comp = Listing(source=provider, **kwargs)
            for method_name in METHODS["listing"]:
                t0 = time.time()
                ok, val = try_method(comp, method_name)
                elapsed = round(time.time() - t0, 2)
                status = "OK" if ok is True else ("EMPTY" if ok == "EMPTY" else "FAIL")
                detail = str(val)[:120] if not isinstance(val, bool) else ""
                results.append(("listing", provider, method_name, status, detail, elapsed))
        except Exception as e:
            for m in METHODS["listing"]:
                results.append(("listing", provider, m, "FAIL", str(e)[:120], 0))

    # Build and display matrix
    df = pd.DataFrame(results, columns=["component", "provider", "method", "status", "detail", "elapsed"])
    print("\n" + "=" * 120)
    print("PROVIDER CAPABILITY MATRIX")
    print("=" * 120)

    # Pivot: rows=(component,method), columns=provider, values=status
    df["key"] = df["component"] + "." + df["method"]
    pivot = df.pivot_table(index="key", columns="provider", values="status", aggfunc="first")
    pivot = pivot.fillna("—")
    # Reorder columns
    col_order = ["KBS", "VCI", "TCBS", "DNSE", "MSN", "FMP"]
    pivot = pivot[[c for c in col_order if c in pivot.columns]]
    print(pivot.to_string())

    # Summary
    print("\n" + "=" * 120)
    print("SUMMARY")
    print("=" * 120)
    total = len(df)
    ok = (df["status"] == "OK").sum()
    empty = (df["status"] == "EMPTY").sum()
    fail = (df["status"] == "FAIL").sum()
    skip = (df["status"] == "SKIP").sum()
    print(f"  OK: {ok}/{total} ({ok/total*100:.1f}%)")
    print(f"  EMPTY: {empty}/{total} ({empty/total*100:.1f}%)")
    print(f"  FAIL: {fail}/{total} ({fail/total*100:.1f}%)")
    print(f"  SKIP: {skip}/{total} ({skip/total*100:.1f}%)")

    # Failed calls
    if fail:
        print("\nFAILED CALLS:")
        failed = df[df["status"] == "FAIL"]
        for _, row in failed.iterrows():
            print(f"  {row['component']}.{row['method']} ({row['provider']}): {row['detail']}")

    # Empty calls (stubs)
    if empty:
        print("\nSTUB (EMPTY) CALLS:")
        empty_df = df[df["status"] == "EMPTY"]
        for _, row in empty_df.iterrows():
            print(f"  {row['component']}.{row['method']} ({row['provider']})")

    return df

if __name__ == "__main__":
    df = test_all()
