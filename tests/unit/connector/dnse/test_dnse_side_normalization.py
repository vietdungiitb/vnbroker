import pytest
from unittest.mock import patch, MagicMock

from vnbroker.connector.dnse.trade import Trade


def _write_enabled_trade() -> Trade:
    """Trade đã bật quyền ghi.

    P0-2: `place_order` giờ qua hàng rào `enable_write()` + `dry_run`. Các test
    này kiểm tra logic chuẩn hoá `side` (buy/sell → NB/NS), nên phải bật quyền
    và truyền `dry_run=False` — nếu không, lệnh dừng ở hàng rào và test không
    còn kiểm chứng được gì.
    """
    trade = Trade()
    trade.token = "fake_token"
    trade.enable_write()
    return trade


@pytest.mark.unit
def test_dnse_place_order_side_normalization_buy():
    trade = _write_enabled_trade()
    
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
                quantity=100,
                dry_run=False,
            )
            # Verify the posted payload had side: "NB"
            call_kwargs = mock_post.call_args.kwargs
            payload = call_kwargs["json"]
            assert payload["side"] == "NB", f"Failed for side: {buy_side}"


@pytest.mark.unit
def test_dnse_place_order_side_normalization_sell():
    trade = _write_enabled_trade()
    
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
                quantity=100,
                dry_run=False,
            )
            call_kwargs = mock_post.call_args.kwargs
            payload = call_kwargs["json"]
            assert payload["side"] == "NS", f"Failed for side: {sell_side}"


@pytest.mark.unit
def test_dnse_place_order_invalid_side():
    trade = _write_enabled_trade()
    
    with pytest.raises(ValueError, match="không hợp lệ"):
        trade.place_order(
            sub_account="0001",
            symbol="ACB",
            side="INVALID_SIDE",
            order_type="LO",
            price=25000,
            quantity=100
        )
