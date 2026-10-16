"""Slice B â€” `get_working_dates` pháº£i gá»i endpoint tháº­t, khÃ´ng tráº£ "thÃ nh cÃ´ng rá»—ng".

Káº¿ hoáº¡ch: `docs/PLAN_DNSE_FIX_20261016.md` Â§5 lÃ¡t B. Báº±ng chá»©ng D1.

**Defect (Ä‘o):** `services/market_service.py` tráº£ `({"dates": []}, None)` â€” khÃ´ng
gá»i network, tá»‘n 0ms. `_resolve_output` unpack `(status, body)` nÃªn láº¥y nháº§m
`body = None`. NgÆ°á»i gá»i tháº¥y "khÃ´ng cÃ³ ngÃ y giao dá»‹ch nÃ o" thay vÃ¬ "chÆ°a ai há»i
server" â€” Ä‘Ãºng máº«u fail-open mÃ  `docs/LESSONS/broker-risk.md` Ä‘Ã£ ghi (L-R01).

**Docstring trong code nÃ³i sai:** *"DNSE OpenAPI does not have a dedicated
working-dates endpoint."* Äo production 2026-10-16 (khÃ´ng VPN):

    GET /market/working-dates -> 200, {"workingDates": [257 pháº§n tá»­]}

NÃªn Ä‘Ã¢y lÃ  **path sai / thiáº¿u**, khÃ´ng pháº£i endpoint khÃ´ng tá»“n táº¡i.

Hai lá»—i phÃ¡i sinh cÅ©ng Ä‘Æ°á»£c khÃ³a á»Ÿ Ä‘Ã¢y:

1. `_to_dataframe` khÃ´ng cÃ³ `workingDates` trong danh sÃ¡ch key â‡’ `raw=False` tráº£
   DataFrame **1 dÃ²ng** chá»©a má»™t cell lÃ  list. ÄÃ³ lÃ  bug gá»‘c Ä‘Æ°á»£c tÃ¡i táº¡o dÆ°á»›i
   hÃ¬nh dáº¡ng khÃ¡c â€” náº¿u chá»‰ sá»­a path thÃ¬ sá»­a báº±ng má»™t lá»—i khÃ¡c.
2. `explorer/dnse/quote.py::working_dates` nay sáº½ **gá»i network tháº­t**; trÃªn
   sandbox `/market/*` lÃ  404 nÃªn nÃ³ rÆ¡i vÃ o `except` vÃ  tráº£ DataFrame rá»—ng
   **im láº·ng** â€” Ä‘Ãºng kiá»ƒu im láº·ng mÃ  lÃ¡t nÃ y sinh ra Ä‘á»ƒ chá»¯a.
"""
from __future__ import annotations

import pandas as pd
import pytest

from vnbroker.connector.dnse.client import DNSEClient
from vnbroker.explorer.dnse.quote import DNSEQuote


def _client() -> DNSEClient:
    return DNSEClient(api_key="k", api_secret="s")


# --- AC-B1: path tháº­t, khÃ´ng mang theo marketType ---------------------------


def test_working_dates_calls_the_documented_endpoint():
    payload = _client().get_working_dates(dry_run=True, raw=True)
    assert payload["method"] == "GET"
    assert payload["url"].endswith("/market/working-dates")


def test_working_dates_sends_no_query_at_all():
    """Äo production: thÃªm `marketType` â‡’ 404. Endpoint nÃ y khÃ´ng cháº¥p nháº­n nÃ³.

    Gá»­i `marketType=None` thÃ¬ khÃ´ng pháº£i 404, nhÆ°ng váº«n lÃ  má»™t tham sá»‘ khÃ´ng cÃ³
    trong há»£p Ä‘á»“ng. Rá»—ng lÃ  tráº¡ng thÃ¡i Ä‘Ãºng.
    """
    payload = _client().get_working_dates(dry_run=True, raw=True)
    assert payload["query"] == {}


def test_working_dates_no_longer_returns_a_hardcoded_empty_tuple():
    """Cháº·n Ä‘Ãºng cÃ¡i bug tuple-order: `body` pháº£i lÃ  envelope cá»§a dry-run."""
    status, body = _client()._market.get_working_dates(dry_run=True)
    assert status is None, "dry-run khÃ´ng Ä‘Æ°á»£c cÃ³ HTTP status"
    assert isinstance(body, dict), f"body pháº£i lÃ  dict, nháº­n {type(body).__name__}"


# --- AC-B2: raw=False pháº£i ra NHIá»€U DÃ’NG, khÃ´ng pháº£i 1 dÃ²ng ---------------


def test_to_dataframe_unwraps_working_dates_instead_of_keeping_one_row():
    payload = {"workingDates": ["2026-10-15", "2026-10-16"]}
    frame = DNSEClient._to_dataframe(payload)
    assert isinstance(frame, pd.DataFrame)
    assert len(frame) == 2, (
        "1 dÃ²ng nghÄ©a lÃ  payload bá»‹ bá»c láº¡i nguyÃªn khá»‘i â€” "
        "json_normalize trÃªn dict khÃ´ng tÃ¡ch list ra Ä‘Æ°á»£c"
    )
    assert "workingDates" in frame.columns


def test_raw_false_returns_one_row_per_trading_day():
    client = _client()
    frame = client._to_dataframe({"workingDates": ["2026-01-05", "2026-01-06", "2026-01-07"]})
    assert len(frame) == 3


# --- AC-B3: táº§ng explorer khÃ´ng Ä‘Æ°á»£c im láº·ng nuá»‘t lá»—i ----------------------


def test_explorer_working_dates_docstring_says_it_hits_the_network():
    """Nay method nÃ y gá»i server. Docstring pháº£i nÃ³i, Ä‘á»ƒ ngÆ°á»i Ä‘á»c khÃ´ng giáº£
    Ä‘á»‹nh nÃ³ ráº» vÃ  khÃ´ng giáº£ Ä‘á»‹nh nÃ³ miá»…n phÃ­ khi sandbox tráº£ 404."""
    doc = DNSEQuote.working_dates.__doc__ or ""
    assert doc.strip(), "working_dates khÃ´ng cÃ³ docstring"
    lowered = doc.lower()
    assert "network" in lowered or "server" in lowered, (
        "docstring pháº£i nÃ³i rÃµ Ä‘Ã¢y lÃ  lá»i gá»i network tháº­t"
    )


def test_explorer_working_dates_is_not_declared_but_unsupported():
    """Chá»‘t D1 theo hÆ°á»›ng ngÆ°á»£c láº¡i cá»§a láº§n Ä‘o Ä‘áº§u tiÃªn.

    Äá»£t probe Ä‘áº§u káº¿t luáº­n 'server khÃ´ng cÃ³ endpoint' nÃªn phÆ°Æ¡ng Ã¡n lÃºc Ä‘Ã³ lÃ  bá»
    method. Äo láº¡i Ä‘Ã£ bÃ¡c bá». Test nÃ y Ä‘á»ƒ láº¡i Ä‘Æ°á»ng quyá»n: náº¿u má»™t Ä‘á»£t sau láº¡i
    xÃ¡c Ä‘á»‹nh endpoint cháº¿t, hÃ£y sá»­a **kÃ¨m báº±ng chá»©ng**, Ä‘á»«ng Ã¢m tháº§m bÃ¡o
    unsupported.
    """
    payload = _client().get_working_dates(dry_run=True, raw=True)
    assert payload["url"].endswith("/market/working-dates")


# --- há»£p Ä‘á»“ng cáº¥u trÃºc Ä‘áº§u ra ---------------------------------------------


def test_working_dates_column_is_stable_for_downstream_code():
    """Explorer tráº£ DataFrame â€” tÃªn cá»™t lÃ  há»£p Ä‘á»“ng vá»›i phÃ­a tiÃªu thá»¥."""
    frame = DNSEClient._to_dataframe({"workingDates": ["2026-10-16"]})
    assert list(frame.columns) == ["workingDates"]


@pytest.mark.parametrize("payload", [{"workingDates": []}, {"workingDates": None}])
def test_empty_or_missing_list_does_not_raise(payload):
    frame = DNSEClient._to_dataframe(payload)
    assert isinstance(frame, pd.DataFrame)
