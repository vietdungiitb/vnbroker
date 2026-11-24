"""Hợp đồng tham số ``adjusted`` cho history() của KBS/VCI.

- ``adjusted=True``  → provider chính (giá đã điều chỉnh).
- ``adjusted=False`` → route sang CafeF reference, trả GIÁ THÔ thật.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from vnbroker.api.quote import Quote as ApiQuote
from vnbroker.config import Config
from vnbroker.core.exceptions import ProviderBadRequestError
from vnbroker.explorer.kbs import quote as kbs_quote
from vnbroker.explorer.vci import quote as vci_quote
from vnbroker.reference import CafefReference
from vnbroker.reference.parser import REFERENCE_COLUMNS

pytestmark = pytest.mark.unit

MODULES = [
    pytest.param(kbs_quote, "KBS", id="kbs"),
    pytest.param(vci_quote, "VCI", id="vci"),
]


def _golden_reference_frame() -> pd.DataFrame:
    row = {col: None for col in REFERENCE_COLUMNS}
    row.update(
        {
            "time": pd.Timestamp("2022-01-04", tz="Asia/Ho_Chi_Minh"),
            "open": 41500.0,
            "high": 43250.0,
            "low": 41300.0,
            "close": 42750.0,
            "close_raw": 42750.0,
            "close_adjusted": 17940.0,
            "volume": 11034900,
            "value": 467_260_000_000,
            "put_through_volume": 0,
            "put_through_value": 0.0,
            "source": "cafef",
            "fetched_at": datetime.now().isoformat(),
        }
    )
    return pd.DataFrame([row], columns=REFERENCE_COLUMNS)


@pytest.fixture
def mock_cafef(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Patch the CafeF seam; record how many times it is called."""
    calls = {"n": 0}

    def fake_history(self: Any, symbol: str, start: Any = None, end: Any = None, **kwargs: Any) -> pd.DataFrame:
        calls["n"] += 1
        return _golden_reference_frame()

    monkeypatch.setattr(CafefReference, "history", fake_history)
    return calls


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("network must not be called when adjusted=False")

    monkeypatch.setattr(kbs_quote, "send_request", boom)
    monkeypatch.setattr(vci_quote, "send_request", boom)
    monkeypatch.setattr(vci_quote, "async_send_request", boom)


# ------------------------------------------------------------------ AC-5 / AC-5b


@pytest.mark.parametrize("module,source", MODULES)
def test_history_adjusted_false_returns_raw_from_cafef(
    monkeypatch: pytest.MonkeyPatch, mock_cafef: dict[str, int], module: Any, source: str
) -> None:
    _block_network(monkeypatch)
    frame = module.Quote("TPB", show_log=False).history(
        start="2022-01-01", end="2022-01-06", adjusted=False
    )

    assert mock_cafef["n"] == 1
    assert len(frame) == 1
    assert frame.iloc[0]["close"] == 42750.0
    assert pd.Timestamp(frame.iloc[0]["time"]).strftime("%Y-%m-%d") == "2022-01-04"
    assert set(["time", "open", "high", "low", "close", "volume"]).issubset(frame.columns)
    assert frame.attrs["source"] == "cafef"
    assert frame.attrs["data_origin"] == "cafef"


# ------------------------------------------------------------------ AC-3 (giữ)


@pytest.mark.parametrize("module,source", MODULES)
def test_history_default_keeps_original_behaviour(
    monkeypatch: pytest.MonkeyPatch, module: Any, source: str
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_send_request(**kwargs: Any) -> Any:
        calls.append(kwargs)
        if module is kbs_quote:
            return {
                "data_day": [
                    {"t": "2024-01-02 07:00", "o": 100, "h": 110, "l": 90, "c": 105, "v": 1000}
                ]
            }
        return [{"t": 1704153600, "o": 100, "h": 110, "l": 90, "c": 105, "v": 1000}]

    monkeypatch.setattr(module, "send_request", fake_send_request)
    frame = module.Quote("ACB", show_log=False).history(start="2024-01-01", end="2024-01-03")

    assert len(calls) == 1
    assert not frame.empty
    assert {"time", "open", "high", "low", "close", "volume"}.issubset(frame.columns)


@pytest.mark.parametrize("module,source", MODULES)
def test_history_explicit_none_keeps_default(
    monkeypatch: pytest.MonkeyPatch, module: Any, source: str
) -> None:
    def fake_send_request(**kwargs: Any) -> Any:
        if module is kbs_quote:
            return {
                "data_day": [
                    {"t": "2024-01-02 07:00", "o": 100, "h": 110, "l": 90, "c": 105, "v": 1000}
                ]
            }
        return [{"t": 1704153600, "o": 100, "h": 110, "l": 90, "c": 105, "v": 1000}]

    monkeypatch.setattr(module, "send_request", fake_send_request)
    frame = module.Quote("ACB", show_log=False).history(
        start="2024-01-01", end="2024-01-03", adjusted=None
    )

    assert not frame.empty


# ------------------------------------------------------------------ AC-7 (explorer fetch_multiple)


@pytest.mark.parametrize("module,source", MODULES)
def test_fetch_multiple_adjusted_false_routes_each_symbol(
    monkeypatch: pytest.MonkeyPatch, mock_cafef: dict[str, int], module: Any, source: str
) -> None:
    _block_network(monkeypatch)
    call = module.Quote.fetch_multiple(symbols=["TPB"], start="2022-01-01", end="2022-01-06", adjusted=False)
    if asyncio.iscoroutine(call):
        frames = asyncio.run(call)
    else:
        frames = call

    assert mock_cafef["n"] >= 1
    assert frames and frames[0].iloc[0]["close"] == 42750.0


@pytest.mark.parametrize("module,source", MODULES)
def test_parallel_history_adjusted_false_routes_through_fetch_multiple(
    monkeypatch: pytest.MonkeyPatch, mock_cafef: dict[str, int], module: Any, source: str
) -> None:
    _block_network(monkeypatch)
    frames = module.Quote("TPB", show_log=False).history(
        adjusted=False, parallel=True, symbols=["TPB"], start="2022-01-01", end="2022-01-06"
    )

    assert mock_cafef["n"] >= 1
    assert frames[0].iloc[0]["close"] == 42750.0


def test_vci_history_async_adjusted_false_routes(
    monkeypatch: pytest.MonkeyPatch, mock_cafef: dict[str, int]
) -> None:
    _block_network(monkeypatch)
    frame = asyncio.run(
        vci_quote.Quote("TPB", show_log=False).history_async(
            start="2022-01-01", end="2022-01-06", adjusted=False
        )
    )

    assert mock_cafef["n"] == 1
    assert frame.iloc[0]["close"] == 42750.0
    assert pd.Timestamp(frame.iloc[0]["time"]).strftime("%Y-%m-%d") == "2022-01-04"
    assert frame.attrs["data_origin"] == "cafef"
    assert frame.source == "cafef"


# ------------------------------------------------------------------ AC-8 / AC-12


@pytest.mark.parametrize("module,source", MODULES)
def test_adjusted_false_rejects_non_daily_interval(
    module: Any, source: str, mock_cafef: dict[str, int]
) -> None:
    with pytest.raises(ProviderBadRequestError, match="daily"):
        module.Quote("TPB", show_log=False).history(
            start="2022-01-01", end="2022-01-06", interval="1H", adjusted=False
        )


def test_adjusted_false_to_df_false_returns_json(
    monkeypatch: pytest.MonkeyPatch, mock_cafef: dict[str, int]
) -> None:
    _block_network(monkeypatch)
    out = kbs_quote.Quote("TPB", show_log=False).history(
        start="2022-01-01", end="2022-01-06", adjusted=False, to_df=False
    )
    assert isinstance(out, str)
    assert "42750" in out or "41500" in out


# ------------------------------------------------------------------ AC-10 (real behaviour)


def test_api_quote_history_adjusted_false_returns_raw(
    monkeypatch: pytest.MonkeyPatch, mock_cafef: dict[str, int]
) -> None:
    from tenacity import RetryError

    quote = ApiQuote(symbol="TPB", source="KBS", show_log=False)
    frame = quote.history(start="2022-01-01", end="2022-01-06", adjusted=False)

    assert not isinstance(frame, RetryError)
    # Rows must survive the tier-1 Normalizer's [start, end] boundary filter.
    # Without the epoch-seconds fix this frame had a 1970 date and became empty.
    assert len(frame) == 1
    assert pd.Timestamp(frame.iloc[0]["time"]).strftime("%Y-%m-%d") == "2022-01-04"
    assert frame.iloc[0]["close"] == 42750.0
    assert mock_cafef["n"] == 1


def test_api_quote_history_still_retries_network_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tenacity.nap.sleep", lambda _seconds: None)
    calls: list[int] = []

    def fake_provider_history(adjusted: bool = True, **kwargs: Any) -> None:
        calls.append(1)
        raise ConnectionError("network down")

    quote = ApiQuote(symbol="ACB", source="KBS", show_log=False)
    monkeypatch.setattr(quote, "_provider", SimpleNamespace(history=fake_provider_history))

    with pytest.raises(ConnectionError):
        quote.history()

    assert len(calls) == Config.RETRIES
