"""
vnbroker.broker.ssi.account — SSIAccountService: read-only danh sách tài khoản.

  GET /api/v3/account/info → list_accounts()

RULE: Không có write method. PII (account_no) mask khi raw=False.
"""

from __future__ import annotations

import logging
from typing import Any, List, Union

import pandas as pd

from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.security.redaction import Redactor
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.ssi import _paths
from vnbroker.broker.ssi._enums import AccountType, safe_parse
from vnbroker.broker.ssi._transport import SSIHttpClient

_logger = logging.getLogger("vnbroker.broker.ssi.account")


class SSIAccountService:
    """Read-only account service cho SSI broker."""

    def __init__(
        self,
        config: SSICredentialConfig,
        session: BrokerSession,
        transport: SSIHttpClient,
    ) -> None:
        self._config = config
        self._session = session
        self._transport = transport

    def list_accounts(self, raw: bool = False) -> Union[pd.DataFrame, List[Any]]:
        """
        GET /api/v3/account/info — danh sách tài khoản của user.

        Args:
            raw: True → list gốc [{accountNo, accountType}].
                 False → DataFrame, account_no masked.

        Returns:
            DataFrame columns (raw=False): account_no (str, masked),
            account_type (category: EQUITY/EQUITY_MARGIN/DERIVATIVE).
        """
        _ = self._session.token  # raise nếu session hết hạn
        data = self._transport.request("GET", _paths.EP_ACCOUNT_INFO)
        records = data.get("data", data) if isinstance(data, dict) else data
        if not isinstance(records, list):
            records = []

        if raw:
            return records

        rows = [
            {
                "account_no": Redactor.mask_account_no(str(r.get("accountNo", ""))),
                "account_type": _map_account_type(r.get("accountType")),
            }
            for r in records
            if isinstance(r, dict)
        ]
        df = pd.DataFrame(rows, columns=["account_no", "account_type"])
        if not df.empty:
            df["account_type"] = df["account_type"].astype("category")
        return df


def _map_account_type(value: object) -> str:
    """Cash/Margin/Derivative → EQUITY/EQUITY_MARGIN/DERIVATIVE; lạ → giữ gốc."""
    parsed = safe_parse(AccountType, value)
    if parsed is not None:
        return parsed.name
    text = str(value).strip() if value is not None else ""
    return text if text else "UNKNOWN"
