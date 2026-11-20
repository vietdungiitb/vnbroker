"""Slice 3: TCBS token docs/message must point to TCBS_JWT_TOKEN (audit C-04)."""
from pathlib import Path
from unittest.mock import patch

import pytest

from vnbroker.explorer.tcbs.company import Company as TCBSCompany


DOCS = [
    Path("vnbroker/explorer/tcbs/IMPLEMENTATION_SUMMARY.md"),
    Path("vnbroker/explorer/tcbs/MIGRATION_GUIDE.md"),
]


class TestTcbsTokenDocs:
    @pytest.mark.parametrize("doc", DOCS)
    def test_docs_mention_jwt_env(self, doc):
        text = doc.read_text(encoding="utf-8")
        assert "TCBS_JWT_TOKEN" in text


class TestDividendsAuthMessage:
    def test_error_mentions_jwt_env(self):
        company = TCBSCompany("VCB")
        with patch("vnbroker.explorer.tcbs.company.client.send_request", side_effect=RuntimeError("401")):
            with pytest.raises(RuntimeError, match="TCBS_JWT_TOKEN"):
                company.dividends()

    def test_docstring_mentions_jwt_env(self):
        assert "TCBS_JWT_TOKEN" in (TCBSCompany.dividends.__doc__ or "")
