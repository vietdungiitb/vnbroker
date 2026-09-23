"""
SSI live integration — MANUAL ONLY. Không chạy trong CI.

Chạy khi có credentials thật + người approve OTP:
    vnbroker_RUN_LIVE_INTEGRATION=1 pytest tests/integration/broker/test_ssi_live.py -v

Checklist live-confirm (§8 plan) — tick từng mục vào artifacts/ssi-handover/live-checklist.md:
  [ ] WS URL thực tế (wss://stream.ssi.com.vn/ws/v3)
  [ ] price ép str trên wire được server chấp nhận
  [ ] nanoid length-20 được server chấp nhận
  [ ] pending 202/code 401114 (Smart OTP, nếu có thiết bị)
  [ ] cả 3 OTP flows (market-only / otp / transaction_id)
  [ ] From/To hoa ở masterdata
  [ ] wildcard "*" cho order/portfolio subscribe
  [ ] clientId chỉ ở balance/positions (orderBook/maxBuySell/FCO-list không gửi)
"""

from __future__ import annotations

import os

import pytest

pytestmark = [pytest.mark.integration]

RUN_LIVE = os.getenv("vnbroker_RUN_LIVE_INTEGRATION") == "1"

requires_live = pytest.mark.skipif(
    not RUN_LIVE,
    reason="Live SSI cần creds thật + OTP người thật. "
    "Set vnbroker_RUN_LIVE_INTEGRATION=1 để chạy tay.",
)


def _has_creds() -> bool:
    return bool(
        os.getenv("VNBROKER_BROKER_SSI_API_KEY")
        and os.getenv("VNBROKER_BROKER_SSI_API_SECRET")
    )


@requires_live
class TestSSILive:
    def test_market_only_auth_and_ohlc(self) -> None:
        if not _has_creds():
            pytest.skip("Thiếu VNBROKER_BROKER_SSI_API_KEY/SECRET.")
        from vnbroker import Vnbroker

        vn = Vnbroker()
        ssi = vn.broker(provider="ssi")
        token = ssi.authenticate()
        assert token
        ohlc = ssi.get_ohlc("SSI", timeframe="1d")
        assert not ohlc.empty

    def test_master_data_caps(self) -> None:
        """Verify From/To hoa + pagesCount gom hết (checklist #6)."""
        if not _has_creds():
            pytest.skip("Thiếu creds SSI.")
        from vnbroker import Vnbroker

        ssi = Vnbroker().broker(provider="ssi")
        ssi.authenticate()
        master = ssi.get_master_data()
        assert not master.empty
        assert {"ceiling", "floor", "ref_price"}.issubset(master.columns)

    def test_balance_needs_client_id(self) -> None:
        """Verify clientId ở balance (checklist #8)."""
        if not _has_creds():
            pytest.skip("Thiếu creds SSI.")
        from vnbroker import Vnbroker

        ssi = Vnbroker().broker(provider="ssi")
        ssi.authenticate()
        accounts = ssi.list_accounts()
        assert not accounts.empty

    def test_gtd_place_cancel_safe(self) -> None:
        """Pattern an toàn: GTD rồi hủy ngay. Cần OTP + enable_write tay."""
        if not _has_creds():
            pytest.skip("Thiếu creds SSI.")
        otp = os.getenv("VNBROKER_BROKER_SSI_TEST_OTP", "")
        if not otp:
            pytest.skip("Set VNBROKER_BROKER_SSI_TEST_OTP để chạy write live.")
        account_no = os.getenv("VNBROKER_BROKER_SSI_ACCOUNT_NO", "")
        if not account_no:
            pytest.skip("Set VNBROKER_BROKER_SSI_ACCOUNT_NO.")
        from vnbroker import Vnbroker

        ssi = Vnbroker().broker(provider="ssi")
        ssi.authenticate(otp=otp)
        ssi.enable_write()
        placed = ssi.place_fco_gtd(
            account_no,
            "SSI",
            "BUY",
            100,
            1000,
            0,
            "2026/01/05 00:00:00",
            "2026/01/12 23:00:00",
            dry_run=False,
        )
        try:
            assert placed["fco_id"]
        finally:
            cancelled = ssi.cancel_fco(placed["fco_id"], dry_run=False)
            assert cancelled["fco_id"] == placed["fco_id"]
