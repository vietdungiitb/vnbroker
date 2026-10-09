from __future__ import annotations

from typing import Any

import pandas as pd

from vnbroker.connector.dnse.core.config import DNSEConfig
from vnbroker.connector.dnse.core.http_client import DNSEHttpClient
from vnbroker.connector.dnse.services import (
    AccountService,
    MarketService,
    OrderService,
    PositionService,
    TokenService,
)


class DNSEClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://openapi.dnse.com.vn",
        api_version: str = "2026-05-07",
        algorithm: str = "hmac-sha256",
        hmac_nonce_enabled: bool = True,
        timeout_seconds: float = 30.0,
        show_log: bool = False,
        write_enabled: bool = False,
    ):
        self._config = DNSEConfig(
            api_key=api_key,
            api_secret=api_secret,
            base_url=base_url,
            api_version=api_version,
            algorithm=algorithm,
            hmac_nonce_enabled=hmac_nonce_enabled,
            timeout_seconds=timeout_seconds,
            show_log=show_log,
        )
        # `write_enabled` is off by default and enforced inside
        # `DNSEHttpClient.request`, the one place every request passes through.
        self._http = DNSEHttpClient(self._config, write_enabled=write_enabled)
        self._account = AccountService(self._http)
        self._market = MarketService(self._http)
        self._order = OrderService(self._http)
        self._position = PositionService(self._http)
        self._token = TokenService(self._http)

    def enable_write(self, enabled: bool = True) -> None:
        """Allow (or forbid) state-changing requests.

        Required before ``post_order``, ``put_order``, ``cancel_order``,
        ``replace_order``, ``close_position`` or ``create_trading_token``
        actually reaches the provider. Reads and ``dry_run=True`` need no
        permission.

        Example:
            >>> client.enable_write()
            >>> client.post_order("STOCK", payload, trading_token)
        """
        self._http.enable_write(enabled)

    @staticmethod
    def _to_dataframe(payload: Any):
        if payload is None:
            return pd.DataFrame()
        if isinstance(payload, list):
            return pd.json_normalize(payload)
        if isinstance(payload, dict):
            for key in (
                "data", "items", "orders", "accounts", "loanPackages",
                "positions", "reports",
                # Market data keys
                "bars", "candles", "ohlc", "trades", "instruments", "securities",
            ):
                value = payload.get(key)
                if isinstance(value, list):
                    return pd.json_normalize(value)
            return pd.json_normalize(payload)
        return payload

    def _resolve_output(self, response: tuple[int | None, Any], raw: bool):
        _, body = response
        return body if raw else self._to_dataframe(body)

    def get_accounts(self, dry_run: bool = False, raw: bool = False):
        return self._resolve_output(self._account.get_accounts(dry_run=dry_run), raw=raw)

    def get_balances(self, account_no: str, dry_run: bool = False, raw: bool = False):
        return self._resolve_output(self._account.get_balances(account_no=account_no, dry_run=dry_run), raw=raw)

    def get_loan_packages(
        self,
        account_no: str,
        market_type: str,
        symbol: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._account.get_loan_packages(
                account_no=account_no,
                market_type=market_type,
                symbol=symbol,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_ppse(
        self,
        account_no: str,
        market_type: str,
        symbol: str,
        price: float,
        loan_package_id: int,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._account.get_ppse(
                account_no=account_no,
                market_type=market_type,
                symbol=symbol,
                price=price,
                loan_package_id=loan_package_id,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_orders(
        self,
        account_no: str,
        market_type: str,
        order_category: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._order.get_orders(
                account_no=account_no,
                market_type=market_type,
                order_category=order_category,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_order_detail(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        order_category: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._order.get_order_detail(
                account_no=account_no,
                order_id=order_id,
                market_type=market_type,
                order_category=order_category,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_execution_detail(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        order_category: str = "NORMAL",
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._order.get_execution_detail(
                account_no=account_no,
                order_id=order_id,
                market_type=market_type,
                order_category=order_category,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_order_history(
        self,
        account_no: str,
        market_type: str,
        from_date: str | None = None,
        to_date: str | None = None,
        page_size: int | None = None,
        page_index: int | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._order.get_order_history(
                account_no=account_no,
                market_type=market_type,
                from_date=from_date,
                to_date=to_date,
                page_size=page_size,
                page_index=page_index,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def post_order(
        self,
        market_type: str,
        payload: dict,
        trading_token: str,
        order_category: str = "NORMAL",
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._order.post_order(
                market_type=market_type,
                payload=payload,
                trading_token=trading_token,
                order_category=order_category,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def put_order(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        payload: dict,
        trading_token: str,
        order_category: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._order.put_order(
                account_no=account_no,
                order_id=order_id,
                market_type=market_type,
                payload=payload,
                trading_token=trading_token,
                order_category=order_category,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def cancel_order(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        trading_token: str,
        order_category: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._order.cancel_order(
                account_no=account_no,
                order_id=order_id,
                market_type=market_type,
                trading_token=trading_token,
                order_category=order_category,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def send_email_otp(self, dry_run: bool = False, raw: bool = False):
        return self._resolve_output(self._token.send_email_otp(dry_run=dry_run), raw=raw)

    def create_trading_token(
        self,
        otp_type: str,
        passcode: str,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._token.create_trading_token(otp_type=otp_type, passcode=passcode, dry_run=dry_run),
            raw=raw,
        )

    def get_positions(
        self,
        account_no: str,
        market_type: str,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._position.get_positions(account_no=account_no, market_type=market_type, dry_run=dry_run),
            raw=raw,
        )

    def get_position_by_id(
        self,
        market_type: str,
        position_id: str,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._position.get_position_by_id(market_type=market_type, position_id=position_id, dry_run=dry_run),
            raw=raw,
        )

    def close_position(
        self,
        position_id: str,
        market_type: str,
        trading_token: str,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._position.close_position(
                position_id=position_id,
                market_type=market_type,
                trading_token=trading_token,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_security_definition(
        self,
        symbol: str,
        board_id: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._market.get_security_definition(
                symbol=symbol,
                board_id=board_id,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_ohlc(self, bar_type: str, query: dict | None = None, dry_run: bool = False, raw: bool = False):
        return self._resolve_output(
            self._market.get_ohlc(bar_type=bar_type, query=query, dry_run=dry_run),
            raw=raw,
        )

    def get_trades(
        self,
        symbol: str,
        board_id: str | None = None,
        from_date: int | None = None,
        to_date: int | None = None,
        limit: int | None = None,
        order: str | None = None,
        next_page_token: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._market.get_trades(
                symbol=symbol,
                board_id=board_id,
                from_date=from_date,
                to_date=to_date,
                limit=limit,
                order=order,
                next_page_token=next_page_token,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_instruments(
        self,
        symbol: str | None = None,
        market_id: str | None = None,
        security_group_id: str | None = None,
        index_name: str | None = None,
        limit: int | None = None,
        page: int | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._market.get_instruments(
                symbol=symbol,
                market_id=market_id,
                security_group_id=security_group_id,
                index_name=index_name,
                limit=limit,
                page=page,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def get_close_price(self, symbol: str, dry_run: bool = False, raw: bool = False):
        return self._resolve_output(
            self._market.get_close_price(symbol=symbol, dry_run=dry_run), raw=raw
        )

    def get_latest_trade(self, symbol: str, dry_run: bool = False, raw: bool = False):
        return self._resolve_output(
            self._market.get_latest_trade(symbol=symbol, dry_run=dry_run), raw=raw
        )

    def get_working_dates(self, dry_run: bool = False, raw: bool = False):
        return self._resolve_output(
            self._market.get_working_dates(dry_run=dry_run), raw=raw
        )

    def get_corporate_action_history(
        self,
        account_no: str,
        market_type: str,
        from_date: str | None = None,
        to_date: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._account.get_corporate_action_history(
                account_no=account_no,
                market_type=market_type,
                from_date=from_date,
                to_date=to_date,
                dry_run=dry_run,
            ),
            raw=raw,
        )

    def replace_order(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        payload: dict,
        trading_token: str,
        order_category: str | None = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._resolve_output(
            self._order.replace_order(
                account_no=account_no,
                order_id=order_id,
                market_type=market_type,
                payload=payload,
                trading_token=trading_token,
                order_category=order_category,
                dry_run=dry_run,
            ),
            raw=raw,
        )
