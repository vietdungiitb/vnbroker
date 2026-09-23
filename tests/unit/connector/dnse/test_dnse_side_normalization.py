import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from vnbroker.connector.dnse.trade import Trade


@pytest.mark.unit
def test_dnse_place_order_side_normalization_buy():
    trade = Trade()
    trade.token = "fake_token"
    
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"orderId": "12345"}
        mock_post.return_value = mock_response
        
        for buy_side in ["buy", "BUY", "nb", "NB", "b", "mua", " MUA "]:
            trade.place_order(
                sub_account="0001",
                symbol="ACB",
                side=buy_side,
                order_type="LO",
                price=25000,
                quantity=100
            )
            # Verify the posted payload had side: "NB"
            call_kwargs = mock_post.call_args.kwargs
            payload = call_kwargs["json"]
            assert payload["side"] == "NB", f"Failed for side: {buy_side}"


@pytest.mark.unit
def test_dnse_place_order_side_normalization_sell():
    trade = Trade()
    trade.token = "fake_token"
    
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"orderId": "12345"}
        mock_post.return_value = mock_response
        
        for sell_side in ["sell", "SELL", "ns", "NS", "s", "ban", "bán", " BAN "]:
            trade.place_order(
                sub_account="0001",
                symbol="ACB",
                side=sell_side,
                order_type="LO",
                price=25000,
                quantity=100
            )
            call_kwargs = mock_post.call_args.kwargs
            payload = call_kwargs["json"]
            assert payload["side"] == "NS", f"Failed for side: {sell_side}"


@pytest.mark.unit
def test_dnse_place_order_invalid_side():
    trade = Trade()
    trade.token = "fake_token"
    
    with pytest.raises(ValueError, match="không hợp lệ"):
        trade.place_order(
            sub_account="0001",
            symbol="ACB",
            side="INVALID_SIDE",
            order_type="LO",
            price=25000,
            quantity=100
        )
