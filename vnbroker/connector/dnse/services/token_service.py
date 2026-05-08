from __future__ import annotations

from vnbroker.connector.dnse.core.http_client import DNSEHttpClient


class TokenService:
    def __init__(self, http: DNSEHttpClient):
        self._http = http

    def send_email_otp(self, dry_run: bool = False):
        return self._http.request("POST", "/registration/otp", body={"otpType": "email_otp"}, dry_run=dry_run)

    def create_trading_token(self, otp_type: str, passcode: str, dry_run: bool = False):
        return self._http.request(
            "POST",
            "/registration/trading-token",
            body={"otpType": otp_type, "passcode": passcode},
            dry_run=dry_run,
        )
