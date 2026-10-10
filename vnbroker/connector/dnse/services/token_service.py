from __future__ import annotations

from vnbroker.connector.dnse.core.http_client import DNSEHttpClient


class TokenService:
    def __init__(self, http: DNSEHttpClient):
        self._http = http

    def send_email_otp(self, dry_run: bool = False):
        # Path per the provider's own SDK (dnse-tech/openapi-sdk,
        # python/dnse/api/client.py:549-554): POST `/registration/send-email-otp`
        # with NO body. The previous `/registration/otp` + {"otpType": ...} was
        # the shape of the trading-token call, which is a different endpoint and
        # is already implemented below as create_trading_token.
        return self._http.request(
            "POST", "/registration/send-email-otp", dry_run=dry_run
        )

    def create_trading_token(self, otp_type: str, passcode: str, dry_run: bool = False):
        return self._http.request(
            "POST",
            "/registration/trading-token",
            body={"otpType": otp_type, "passcode": passcode},
            dry_run=dry_run,
        )
