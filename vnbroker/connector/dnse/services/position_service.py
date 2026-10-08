from __future__ import annotations

from vnbroker.connector.dnse.core.http_client import DNSEHttpClient


class PositionService:
    def __init__(self, http: DNSEHttpClient):
        self._http = http

    def get_positions(self, account_no: str, market_type: str, dry_run: bool = False):
        return self._http.request(
            "GET",
            f"/accounts/{account_no}/positions",
            query={"marketType": market_type},
            dry_run=dry_run,
        )

    def get_position_by_id(self, market_type: str, position_id: str, dry_run: bool = False):
        # Path per the provider's own SDK (dnse-tech/openapi-sdk,
        # python/dnse/api/client.py:98-105): the by-id form is
        # `/positions/{id}`, NOT `/accounts/positions/{id}`. Only the LIST form
        # is account-scoped (`/accounts/{account_no}/positions`, client.py:90).
        return self._http.request(
            "GET",
            f"/positions/{position_id}",
            query={"marketType": market_type},
            dry_run=dry_run,
        )

    def close_position(
        self,
        position_id: str,
        market_type: str,
        trading_token: str,
        dry_run: bool = False,
    ):
        # Path per the provider's SDK (client.py:556-566): `/positions/{id}/close`.
        return self._http.request(
            "POST",
            f"/positions/{position_id}/close",
            query={"marketType": market_type},
            headers={"trading-token": trading_token},
            dry_run=dry_run,
        )
