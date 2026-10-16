from __future__ import annotations

from vnbroker.connector.dnse.constants import validate_market_type
from vnbroker.connector.dnse.core.errors import DNSEValidationError
from vnbroker.connector.dnse.core.http_client import DNSEHttpClient


def _require_numeric_id(position_id: object, param: str) -> str:
    """Chặn id không phải số **trước khi** gửi.

    Đo production 2026-10-16: `GET /positions/fake` ⇒
    `500 For input string: "fake"`. Đó là lỗi máy chủ sinh ra từ dữ liệu rác của
    phía gọi — loại lỗi dễ bị nhầm thành "endpoint hỏng". Chặn ở đây là đúng
    bản chất, không phải che lỗi.

    Cố ý **chỉ** kiểm hình thức, không kiểm giá trị: `0` là hình thức hợp lệ và
    server trả `404 deal not found` — đó là câu trả lời có nghĩa, không phải lỗi
    input. Chặn cả `0` sẽ biến câu trả lời hữu ích thành exception vô nghĩa.

    Raises:
        DNSEValidationError: ``error_code == "INVALID_POSITION_ID"``.
    """
    text = str(position_id).strip()
    # `str.isdigit()` riêng không đủ: "²".isdigit() là True còn int("²") ném
    # ValueError — tức guard lọt và lỗi 500 vẫn quay lại. Giới hạn cả ASCII.
    if text.isascii() and text.isdigit():
        return text
    raise DNSEValidationError(
        message=(
            f"{param}={position_id!r} không phải số. Endpoint này đặt id thẳng "
            f"vào path, và server trả `500 For input string` cho bất kỳ giá trị "
            f"nào không parse được thành số. Chỉ kiểm **hình thức** — id không tồn "
            f"tại vẫn hợp lệ và server sẽ trả `404 deal not found`."
        ),
        error_code="INVALID_POSITION_ID",
        status_code=400,
    )


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

    def get_position_by_id(
        self,
        market_type: str,
        position_id: str | int,
        dry_run: bool = False,
    ) -> tuple[int | None, object]:
        """Một deal theo id. Path theo SDK `client.py:98-105`: `/positions/{id}`
        — KHÔNG account-scoped (chỉ dạng LIST mới là
        `/accounts/{account_no}/positions`).

        ⚠ **Thứ tự kiểm tra cố ý: `marketType` trước, `position_id` sau.**
        `tests/unit/connector/dnse/test_market_type_validation.py` parametrize
        trên mọi method có `market_type`, điền tham số bắt buộc bằng `"x"` và
        đòi `error_code == "INVALID_MARKET_TYPE"`. Nếu đảo thứ tự, `error_code`
        đầu tiên sẽ là của `position_id` và test đỏ. Khớp chính sách "validation
        TRƯỚC gate" ở `core/http_client.py:83-90`.

        Raises:
            DNSEValidationError: `INVALID_MARKET_TYPE` khi `marketType` sai;
                `INVALID_POSITION_ID` khi `position_id` không phải số.
        """
        validate_market_type(market_type)
        numeric_id = _require_numeric_id(position_id, "position_id")
        return self._http.request(
            "GET",
            f"/positions/{numeric_id}",
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
