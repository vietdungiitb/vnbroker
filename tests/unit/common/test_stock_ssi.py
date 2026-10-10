"""Unit tests for stock() wiring with source="SSI" (extended per phase)."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from vnbroker.common.client import Vnbroker
from vnbroker.common.data import (
    Company,
    Finance,
    Listing,
    News,
    Quote,
    StockComponents,
    Trading,
)


@pytest.fixture()
def ssi_keys(monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    """Fake SSI credentials via env (never real secrets in tests)."""
    monkeypatch.setenv("VNBROKER_BROKER_SSI_API_KEY", "test-ssi-key")
    monkeypatch.setenv("VNBROKER_BROKER_SSI_API_SECRET", "test-ssi-secret")
    return ("test-ssi-key", "test-ssi-secret")


class TestSSIWiringP1:
    """AC-W1.1 (P1 scope: Vnbroker + Quote facade)."""

    def test_supported_sources(self) -> None:
        assert "SSI" in Vnbroker.SUPPORTED_SOURCES
        assert "SSI" in StockComponents.SUPPORTED_SOURCES
        assert "SSI" in Quote.SUPPORTED_SOURCES

    def test_quote_facade_loads_ssi(self, ssi_keys: tuple[str, str]) -> None:
        from vnbroker.explorer.ssi.quote import SSIQuote

        q = Quote("ACB", source="SSI", show_log=False)
        assert isinstance(q.data_source, SSIQuote)

    def test_quote_facade_missing_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_KEY", raising=False)
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_SECRET", raising=False)
        with pytest.raises(ValueError, match="SSI cần api_key và api_secret"):
            Quote("ACB", source="SSI", show_log=False)

    def test_quote_history_through_facade(self, ssi_keys: tuple[str, str]) -> None:
            """Facade chuẩn hoá kết quả provider theo hợp đồng tầng 1.

            GĐ2: provider trả tz-naive, nhưng tầng ``data.py`` gắn
            ``Asia/Ho_Chi_Minh`` để mọi provider ẩn danh cùng schema (xem
            ``vnbroker/core/utils/normalizer.py``).

            ⚠ Từ 2026-10-10 hợp đồng gồm **cả đơn vị lưu trữ**: tz-aware chưa
            đủ. pandas ≥ 2 giữ nguyên đơn vị của nguồn — `pd.to_datetime` cho
            ra `datetime64[us]`, các provider khác cho `[s]` — và
            ``DataFrame.concat`` giữa hai đơn vị rơi về ``dtype object``.
            Tầng chuẩn hoá vì thế ép về `datetime64[ns]`. Khẳng định cũ (chỉ
            `tz_localize` rồi so) xanh với *cả hai* hành vi nên không bắt được
            lỗi.
            """
            raw = pd.DataFrame(
                {
                    "time": pd.to_datetime(["2024-01-01"]),
                    "open": [25.0],
                    "high": [25.1],
                    "low": [24.9],
                    "close": [25.0],
                    "volume": [100],
                }
            )
            q = Quote("ACB", source="SSI", show_log=False)
            with patch(
                "vnbroker.explorer.ssi.quote.SSIQuote.history", return_value=raw
            ):
                out = q.history(start="2024-01-01", end="2024-01-31")

            expected = raw.copy()
            expected["time"] = (
                expected["time"].dt.tz_localize("Asia/Ho_Chi_Minh").dt.as_unit("ns")
            )
            pd.testing.assert_frame_equal(out, expected)

            # Hợp đồng tầng 1: kết quả qua facade luôn tz-aware.
            assert out["time"].dt.tz is not None


class TestSSIStockInit:
    """Full stock() init with source=SSI (offline construction)."""

    def test_stock_init_ssi(self, ssi_keys: tuple[str, str]) -> None:
        vn = Vnbroker(source="SSI", show_log=False)
        comps = vn.stock("ACB")
        assert isinstance(comps, StockComponents)
        assert comps.source == "SSI"

    def test_all_facades_accept_ssi(self) -> None:
        for cls in (Quote, Company, Finance, Listing, Trading, News):
            assert "SSI" in cls.SUPPORTED_SOURCES


class TestSSIFallback:
    """AC-CFN-2 / AC-N-2: SSI gaps served by KBS/VCI transparently."""

    def test_company_overview_falls_back_to_kbs(
        self, ssi_keys: tuple[str, str]
    ) -> None:
        from vnbroker.explorer.ssi.company import SSICompany

        assert Company.FALLBACK_MAP["SSI"] == ["KBS", "VCI"]
        # SSI provider itself is empty by design...
        assert SSICompany("ACB", show_log=False).overview().empty
        # ...so the facade skips it and serves KBS data (mocked, no network).
        fallback = pd.DataFrame([{"symbol": "ACB", "organ_name": "ACB Bank"}])
        with patch(
            "vnbroker.explorer.kbs.company.Company.overview", return_value=fallback
        ):
            out = Company("ACB", source="SSI", show_log=False).overview()
        pd.testing.assert_frame_equal(out, fallback)

    def test_finance_ratio_served_via_kbs(self, ssi_keys: tuple[str, str]) -> None:
        fallback = pd.DataFrame(
            [{"item": "PE", "item_en": "PE", "item_id": "pe", "2024": 10.5}]
        )
        with patch(
            "vnbroker.explorer.kbs.financial.Finance.ratio", return_value=fallback
        ):
            out = Finance("ACB", source="SSI", show_log=False).ratio()
        pd.testing.assert_frame_equal(out, fallback)

    def test_news_latest_annotated_vci(self, ssi_keys: tuple[str, str]) -> None:
        served = pd.DataFrame([{"title": "tin ACB"}])
        served.attrs["source"] = "VCI"
        with patch(
            "vnbroker.explorer.vci.news.News.latest", return_value=served
        ):
            out = News("ACB", source="SSI", show_log=False).latest()
        assert len(out) == 1
        assert out.attrs["source_used"] == "VCI"
        assert out.attrs["source_requested"] == "SSI"
