"""
Unit tests for vnbroker API broker module.

Tests the get_broker factory function and broker client interface.
"""

import pytest
from unittest.mock import patch, MagicMock

from vnbroker.api.broker import get_broker


@pytest.mark.unit
@pytest.mark.api
class TestBrokerAPI:
    """Test suite for broker API factory and client."""

    @patch("vnbroker.broker.tcbs.client.TCBSBrokerClient")
    def test_broker_api_init_tcbs(self, mock_client_class):
        """Test get_broker returns TCBS client for tcbs provider."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        client = get_broker(provider="tcbs", api_key="test_key")

        assert client is mock_instance
        mock_client_class.assert_called_once_with(api_key="test_key", base_url=None)

    @patch("vnbroker.broker.tcbs.client.TCBSBrokerClient")
    def test_broker_api_init_default_provider(self, mock_client_class):
        """Test get_broker defaults to tcbs provider."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        client = get_broker(api_key="test_key")

        assert client is mock_instance
        mock_client_class.assert_called_once_with(api_key="test_key", base_url=None)

    @patch("vnbroker.broker.tcbs.client.TCBSBrokerClient")
    def test_broker_api_init_with_base_url(self, mock_client_class):
        """Test get_broker passes base_url to client."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        get_broker(
            provider="tcbs",
            api_key="test_key",
            base_url="https://custom.api.com",
        )

        mock_client_class.assert_called_once_with(
            api_key="test_key",
            base_url="https://custom.api.com",
        )

    @patch("vnbroker.broker.tcbs.client.TCBSBrokerClient")
    def test_broker_api_has_methods(self, mock_client_class):
        """Test broker client has expected methods."""
        mock_instance = MagicMock()
        mock_instance.authenticate = MagicMock(return_value="jwt_token")
        mock_instance.get_account_list = MagicMock(return_value=[])
        mock_instance.get_account_balance = MagicMock(return_value={})
        mock_instance.close = MagicMock()
        mock_instance.is_authenticated = False
        mock_client_class.return_value = mock_instance

        client = get_broker(provider="tcbs", api_key="test_key")

        assert hasattr(client, "authenticate")
        assert callable(client.authenticate)
        assert hasattr(client, "get_account_list")
        assert callable(client.get_account_list)
        assert hasattr(client, "get_account_balance")
        assert callable(client.get_account_balance)
        assert hasattr(client, "close")
        assert callable(client.close)
        assert hasattr(client, "is_authenticated")

    @patch("vnbroker.broker.tcbs.client.TCBSBrokerClient")
    def test_broker_api_authenticate(self, mock_client_class):
        """Test broker client authenticate method works."""
        mock_instance = MagicMock()
        mock_instance.authenticate = MagicMock(return_value="jwt_token_123")
        mock_client_class.return_value = mock_instance

        client = get_broker(provider="tcbs", api_key="test_key")
        token = client.authenticate(otp="123456")

        assert token == "jwt_token_123"
        mock_instance.authenticate.assert_called_once_with(otp="123456")

    @patch("vnbroker.broker.tcbs.client.TCBSBrokerClient")
    def test_broker_api_get_account_list(self, mock_client_class):
        """Test broker client get_account_list method works."""
        mock_instance = MagicMock()
        mock_instance.get_account_list = MagicMock(return_value=[
            {"account_no": "0123456789", "type": "cash"}
        ])
        mock_client_class.return_value = mock_instance

        client = get_broker(provider="tcbs", api_key="test_key")
        accounts = client.get_account_list()

        assert isinstance(accounts, list)
        assert len(accounts) == 1
        assert accounts[0]["account_no"] == "0123456789"

    @patch("vnbroker.broker.tcbs.client.TCBSBrokerClient")
    def test_broker_api_get_account_balance(self, mock_client_class):
        """Test broker client get_account_balance method works."""
        mock_instance = MagicMock()
        mock_instance.get_account_balance = MagicMock(return_value={
            "account_no": "0123456789",
            "balance": 1000000,
        })
        mock_client_class.return_value = mock_instance

        client = get_broker(provider="tcbs", api_key="test_key")
        balance = client.get_account_balance(account_no="0123456789")

        assert balance["account_no"] == "0123456789"
        assert balance["balance"] == 1000000

    @patch("vnbroker.broker.tcbs.client.TCBSBrokerClient")
    def test_broker_api_close(self, mock_client_class):
        """Test broker client close method works."""
        mock_instance = MagicMock()
        mock_instance.close = MagicMock()
        mock_client_class.return_value = mock_instance

        client = get_broker(provider="tcbs", api_key="test_key")
        client.close()

        mock_instance.close.assert_called_once()

    @patch("vnbroker.broker.registry.BrokerRegistry")
    def test_broker_api_unknown_provider(self, mock_registry):
        """Test get_broker falls back to registry for unknown provider."""
        mock_client_class = MagicMock()
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_registry.get.return_value = mock_client_class

        client = get_broker(provider="unknown_broker", api_key="test_key")

        mock_registry.get.assert_called_once_with("unknown_broker")
        assert client is mock_instance
