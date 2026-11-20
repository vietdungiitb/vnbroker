"""Slice 2: unified Company.corporate_actions() facade.

Fail-before: RED on old tree (facade method missing).
"""
from unittest.mock import patch

import pytest

from vnbroker.api.company import Company
from vnbroker.common.corporate_actions import CORPORATE_ACTION_COLUMNS


def _frame(symbol="VNM"):
    from vnbroker.common.corporate_actions import normalize_events

    return normalize_events(
        [{"id": 1, "eventCode": "DIV", "exRightDate": "2024-09-24", "eventTitleVi": "950 VND"}],
        symbol,
    )


class TestCorporateActionsFacade:
    def test_vci_source_returns_contract(self):
        company = Company(source="VCI", symbol="VNM")
        # The adapter delegates to the explorer provider method; patch on the
        # real provider instance to keep the test offline.
        with patch.object(company.provider, "corporate_actions", return_value=_frame()) as mock:
            df = company.corporate_actions(from_date="20100101")
        mock.assert_called_once()
        assert list(df.columns) == CORPORATE_ACTION_COLUMNS
        assert df.iloc[0]["source"] == "VCI"

    def test_explicit_kbs_raises_not_implemented(self):
        # KBS has no corporate_actions(); explicit source must fail loudly,
        # never silently return an empty frame (audit C-06).
        company = Company(source="KBS", symbol="VNM")
        with pytest.raises(NotImplementedError, match="does not support 'corporate_actions'"):
            company.corporate_actions()

    def test_auto_fallback_to_vci(self):
        """AUTO goes through the real fallback path and annotates source=VCI.

        The initial provider is KBS (no corporate_actions); patching
        build_source_order to VCI simulates the failover decision without
        touching the shared common/data.py (audit C-06, claim w34-ratelimit).
        """
        company = Company(source="AUTO", symbol="VNM")
        with patch("vnbroker.base.build_source_order", return_value=["vci"]):
            df = company.corporate_actions(from_date="20100101")
        assert not df.empty
        assert list(df.columns) == CORPORATE_ACTION_COLUMNS
        assert df.iloc[0]["source"] == "VCI"
