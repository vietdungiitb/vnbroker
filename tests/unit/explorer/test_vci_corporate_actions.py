"""Slice 1: VCI.corporate_actions() must call the raw feed and normalize it.

Fail-before: RED on old tree (method missing / wrong payload path).
"""
from unittest.mock import patch

from vnbroker.common.corporate_actions import CORPORATE_ACTION_COLUMNS
from vnbroker.explorer.vci.company import Company


RAW_ROWS = [
    {
        "id": 101,
        "eventCode": "DIV",
        "exRightDate": 1727145600000,  # 2024-09-24
        "eventTitleVi": "Đợt 4 2023 - 950 VND",
        "publicDate": 1726905600000,
    },
    {
        "id": 102,
        "eventCode": "DIV",
        "exRightDate": 1727145600000,
        "eventTitleVi": "Đợt 1 2024 - 1,500 VND",
        "publicDate": 1726905600000,
    },
]


class TestVCICorporateActions:
    def test_uses_raw_news_events_and_normalizes(self):
        with patch.object(Company, "_fetch_news_events", return_value=RAW_ROWS) as mock:
            df = Company("VNM").corporate_actions(from_date="20100101", to_date="20261120")
        mock.assert_called_once_with("20100101", "20261120", "DIV,ISS")
        assert len(df) == 2
        assert list(df.columns) == CORPORATE_ACTION_COLUMNS
        assert set(df["group_id"]) == {"VNM:2024-09-24"}
        assert df.iloc[0]["source"] == "VCI"

    def test_default_event_codes(self):
        with patch.object(Company, "_fetch_news_events", return_value=RAW_ROWS) as mock:
            Company("VNM").corporate_actions()
        assert mock.call_args.args[2] == "DIV,ISS"

    def test_empty_returns_typed_frame(self):
        with patch.object(Company, "_fetch_news_events", return_value=[]):
            df = Company("VNM").corporate_actions()
        assert df.empty
        assert list(df.columns) == CORPORATE_ACTION_COLUMNS
