"""Slice E — path `corporate-action-history` + chặn `position_id` không phải số (D5, D6).

Kế hoạch: `docs/PLAN_DNSE_FIX_20261016.md` §5 lát E. Đo production 2026-10-16:

- **D5** — `GET /accounts/{no}/corporate-actions` ⇒ `404 API ROUTE NOT FOUND`.
  `GET /accounts/{no}/corporate-action-history` ⇒ **200**, body
  `{accountNo, data, pagination}`. Đây là **path sai**, không phải endpoint
  không tồn tại — nên sửa path, không xoá method.
- **D6** — `GET /positions/{id}` với `id="fake"` ⇒ `500 For input string: "fake"`.
  `id=0`/`id=1` ⇒ `404 deal not found` (path **đúng**). `id=999999` ⇒ `403` (biên
  quyền, **chưa rõ** — không kết luận).

Về thứ tự guard
---------------
`tests/unit/connector/dnse/test_market_type_validation.py` parametrize trên **mọi**
method công khai có `market_type`, điền mọi tham số bắt buộc bằng `"x"` và đòi
`error_code == "INVALID_MARKET_TYPE"`. Nếu guard `position_id` chạy trước thì
`error_code` khác và test đỏ. Vì vậy thứ tự là **marketType trước, position_id
sau** — khớp chính sách "validation TRƯỚC gate" ở `core/http_client.py:83-90`.
Đây là chốt của audit B3, được ghim bằng AC-E4 chứ không để kiểm thử ngầm.
"""
from __future__ import annotations

import pytest
import requests

from vnbroker.connector.dnse.client import DNSEClient
from vnbroker.connector.dnse.core.errors import DNSEValidationError

ACCOUNT = "0003724720"


class _NoEgress:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __enter__(self) -> "_NoEgress":
        self._original = requests.Session.request
        guard = self

        def _spy(_self, method, url, *args, **kwargs):
            guard.calls.append(f"{method} {url}")
            raise AssertionError(f"request đã đi ra dù tham số sai: {method} {url}")

        requests.Session.request = _spy  # type: ignore[method-assign]
        return self

    def __exit__(self, *_exc) -> None:
        requests.Session.request = self._original  # type: ignore[method-assign]


def _client() -> DNSEClient:
    return DNSEClient(api_key="k", api_secret="s")


# --- AC-E1: path đúng -------------------------------------------------------


def test_corporate_action_history_uses_the_path_that_actually_responds():
    payload = _client().get_corporate_action_history(
        ACCOUNT, "STOCK", dry_run=True, raw=True
    )
    assert "corporate-action-history" in payload["url"]


def test_the_dead_path_is_gone():
    """`/corporate-actions` trả 404. Nếu nó quay lại, test này đỏ."""
    payload = _client().get_corporate_action_history(
        ACCOUNT, "STOCK", dry_run=True, raw=True
    )
    assert "corporate-actions" not in payload["url"]


def test_corporate_action_history_keeps_its_signature():
    """Chữ ký không đổi — chỉ path bên trong thân là đổi."""
    import inspect

    params = list(inspect.signature(DNSEClient.get_corporate_action_history).parameters)
    assert params == ["self", "account_no", "market_type", "from_date", "to_date",
                      "dry_run", "raw"], params


# --- AC-E2: position_id không phải số -> chặn trước network ----------------


def test_non_numeric_position_id_raises_before_the_network():
    """Đo: `id="fake"` ⇒ `500 For input string: "fake"`. Đó là lỗi server do
    input rác; vnbroker không nên gửi."""
    with _NoEgress() as egress, pytest.raises(DNSEValidationError) as excinfo:
        _client().get_position_by_id(market_type="STOCK", position_id="fake", dry_run=True)
    assert excinfo.value.error_code == "INVALID_POSITION_ID"
    assert egress.calls == []


def test_the_message_shows_the_offending_value():
    with pytest.raises(DNSEValidationError) as excinfo:
        _client().get_position_by_id(market_type="STOCK", position_id="POS1", dry_run=True)
    assert "POS1" in str(excinfo.value)


@pytest.mark.parametrize("bad", ["POS1", "1.5", "abc", "1;drop", ""])
def test_various_non_numeric_ids_are_all_rejected(bad):
    with pytest.raises(DNSEValidationError):
        _client().get_position_by_id(market_type="STOCK", position_id=bad, dry_run=True)


# --- AC-E3: chỉ chặn sai KIỂ, không chặn sai GIÁ TRỊ ------------------------


def test_zero_is_a_well_formed_id_even_if_the_server_reports_not_found():
    """Đo: `id=0` ⇒ `404 deal not found` — đó **là** câu trả lời có nghĩa của
    server, không phải lỗi input. Không được chặn ở client.

    Chặn cả `0` sẽ biến một câu trả lời hữu ích thành exception vô nghĩa."""
    payload = _client().get_position_by_id(
        market_type="STOCK", position_id="0", dry_run=True, raw=True
    )
    assert payload["url"].endswith("/positions/0?marketType=STOCK")


def test_a_numeric_string_is_accepted():
    payload = _client().get_position_by_id(
        market_type="STOCK", position_id="12345", dry_run=True, raw=True
    )
    assert "/positions/12345" in payload["url"]


def test_a_real_integer_is_accepted_too():
    payload = _client().get_position_by_id(
        market_type="STOCK", position_id=42, dry_run=True, raw=True
    )
    assert "/positions/42" in payload["url"]


# --- AC-E4: marketType thắng (chốt audit B3) -------------------------------


def test_market_type_is_validated_before_position_id():
    with pytest.raises(DNSEValidationError) as excinfo:
        _client().get_position_by_id(market_type="ALL", position_id="fake", dry_run=True)
    assert excinfo.value.error_code == "INVALID_MARKET_TYPE", (
        "marketType phải được kiểm trước, nếu không test parametrize ở "
        "test_market_type_validation.py sẽ đỏ"
    )


# --- close_position dùng chung position_id ---------------------------------


def test_close_position_is_left_alone():
    """Write path nằm ngoài phạm vi đợt này (không chạm money lane).

    Test này chỉ để chứng minh đây là **quyết định có chủ ý**, không phải sót.
    Lưu ý `close_position` chưa có guard số ⇒ nó vẫn có thể gửi `position_id`
    rác và nhận 500. Ghi ở đây để lát sau biết phải xử lý, không phải vô tình."""
    import inspect

    params = inspect.signature(DNSEClient.close_position).parameters
    assert "position_id" in params
    assert inspect.signature(
        type(_client()._position).close_position
    ).parameters["position_id"].annotation == "str"