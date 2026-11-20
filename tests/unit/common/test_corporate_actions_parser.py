"""Unit tests for corporate action parsing and normalization (Slice 1).

Fail-before: these tests import the not-yet-existing module and call the real
functions. On the old tree they are RED (ImportError); after implementation
they are GREEN.
"""
from decimal import Decimal

from vnbroker.common.corporate_actions import (
    CORPORATE_ACTION_COLUMNS,
    normalize_events,
    parse_event_title,
)


class TestParseEventTitle:
    def test_parse_cash_with_comma_and_dot(self):
        assert parse_event_title(
            "Trả cổ tức bằng tiền mặt - Đợt 1 2024 - 1,500 VND", "DIV"
        ).cash_amount == Decimal("1500")
        assert parse_event_title(
            "Trả cổ tức bằng tiền mặt - Đợt 3 2024 - 2.000 VND", "DIV"
        ).cash_amount == Decimal("2000")

    def test_esop_pct_is_unparsed(self):
        # FPT probe 3.7.2: "Phát hành cho CBCNV tỉ lệ 0.5%/0.2%" — ESOP,
        # not a bonus issue. Must NOT become stock_ratio_pct.
        for pct in ("0.5", "0.2"):
            result = parse_event_title(
                f"Phát hành cổ phiếu - Phát hành cho CBCNV tỉ lệ {pct}%", "ISS"
            )
            assert result.stock_ratio_pct is None
            assert result.parse_status == "unparsed"
            assert result.is_esop is True

    def test_bonus_pct_parsed(self):
        result = parse_event_title(
            "Phát hành cổ phiếu - Cổ phiếu thưởng tỉ lệ 15.0%", "ISS"
        )
        assert result.stock_ratio_pct == Decimal("15.0")
        assert result.parse_status == "parsed_from_text"
        assert result.is_esop is False

    def test_dividend_in_shares_parsed(self):
        result = parse_event_title(
            "Trả cổ tức bằng Cổ phiếu tỉ lệ 49.5%", "ISS"
        )
        assert result.stock_ratio_pct == Decimal("49.5")

    def test_div_pct_ambiguous(self):
        # Cash dividend expressed as % of par value — NOT a share ratio.
        result = parse_event_title("Trả cổ tức bằng tiền mặt tỉ lệ 20%", "DIV")
        assert result.cash_amount is None
        assert result.stock_ratio_pct is None
        assert result.ambiguous_cash_pct is True
        assert result.parse_status == "unparsed"

    def test_no_amount_is_unparsed(self):
        result = parse_event_title("Phát hành riêng lẻ", "ISS")
        assert result.cash_amount is None
        assert result.stock_ratio_pct is None
        assert result.parse_status == "unparsed"


class TestNormalizeEvents:
    @staticmethod
    def _row(event_id, code, ex_date, title):
        return {
            "id": event_id,
            "eventCode": code,
            "exRightDate": ex_date,
            "eventTitleVi": title,
            "publicDate": "2024-09-01",
        }

    def test_two_div_same_ex_date(self):
        rows = [
            self._row(101, "DIV", "2024-09-24", "Đợt 4 2023 - 950 VND"),
            self._row(102, "DIV", "2024-09-24", "Đợt 1 2024 - 1,500 VND"),
        ]
        df = normalize_events(rows, "VNM")
        assert len(df) == 2  # kept as two rows, not deduped by title
        assert set(df["group_id"]) == {"VNM:2024-09-24"}
        assert sorted(df["cash_amount"].tolist()) == [Decimal("950"), Decimal("1500")]
        assert set(df["source_event_id"]) == {"101", "102"}
        assert list(df.columns) == CORPORATE_ACTION_COLUMNS

    def test_vnm_same_ex_date_pairs(self):
        # Three real same-ex-date pairs from probe (audit v1 C-03).
        for ex_date in ("2023-08-03", "2024-09-24", "2025-10-16"):
            rows = [
                self._row(ex_date + "-a", "DIV", ex_date, "Đợt A - 950 VND"),
                self._row(ex_date + "-b", "DIV", ex_date, "Đợt B - 1,500 VND"),
            ]
            df = normalize_events(rows, "VNM")
            assert len(df) == 2
            assert set(df["group_id"]) == {f"VNM:{ex_date}"}

    def test_vcb_different_ex_dates(self):
        rows = [
            self._row(201, "ISS", "2025-03-12", "Cổ phiếu thưởng tỉ lệ 49.5%"),
            self._row(202, "DIV", "2025-10-03", "Trả cổ tức 450 VND"),
        ]
        df = normalize_events(rows, "VCB")
        assert set(df["group_id"]) == {"VCB:2025-03-12", "VCB:2025-10-03"}

    def test_vci_null_dates_not_derived(self):
        rows = [self._row(301, "DIV", "2024-09-24", "950 VND")]
        df = normalize_events(rows, "VNM")
        # VCI has no record_date/payment_date; publicDate must NOT be copied.
        assert df.iloc[0]["record_date"] is None
        assert df.iloc[0]["payment_date"] is None

    def test_group_id_is_string(self):
        rows = [self._row(401, "ISS", "2024-10-09", "Cổ phiếu thưởng 15%")]
        df = normalize_events(rows, "FPT")
        assert isinstance(df.iloc[0]["group_id"], str)

    def test_idempotent_same_id(self):
        row = self._row(501, "ISS", "2024-10-09", "Cổ phiếu thưởng 15%")
        first = normalize_events([row], "FPT")
        second = normalize_events([row], "FPT")
        assert first["source_event_id"].tolist() == second["source_event_id"].tolist()

    def test_empty_rows_return_typed_frame(self):
        df = normalize_events([], "VNM")
        assert df.empty
        assert list(df.columns) == CORPORATE_ACTION_COLUMNS
