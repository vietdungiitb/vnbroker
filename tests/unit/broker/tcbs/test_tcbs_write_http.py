"""
Test cho `_write_http` — helper POST dùng chung (thêm ở round 2, audit F-1).

Bối cảnh: trước khi có helper này, `money.py._post` chỉ map 401/403/5xx, nên
**400/404/422/429 rơi qua và `resp.json()` được trả về y như thành công**. Với
write động tiền (nạp/rút/chuyển margin) đó là lỗi nghiêm trọng.

Test ở đây chốt **hành vi đúng** bằng chứng thực thi, không chỉ đọc code.
"""
from __future__ import annotations

from typing import Any, Optional

import pytest
import requests

from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerError,
    BrokerNetworkError,
    BrokerOrderError,
    BrokerPermissionError,
    BrokerRateLimitError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.tcbs._write_http import (
    describe_business_code,
    post_json,
    raise_for_status,
)

_PATH = "/khronos/v1/cash/deposit/update"


class _Resp:
    """Rút gọn requests.Response — chỉ cần status_code, text, json()."""

    def __init__(self, status: int, body: Any, text: str = "") -> None:
        self.status_code = status
        self._body = body
        self.text = text or str(body)

    def json(self) -> Any:
        return self._body


def _session_with_token() -> BrokerSession:
    session = BrokerSession()
    session.set_token("test-token", expires_in_seconds=3600)
    return session


# ── raise_for_status: mọi 4xx/5xx phải raise, không lọt ─────────────────────────


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, BrokerValidationError),
        (401, BrokerAuthError),
        (403, BrokerPermissionError),
        (404, BrokerValidationError),
        (422, BrokerOrderError),
        (429, BrokerRateLimitError),
        (500, BrokerNetworkError),
        (503, BrokerNetworkError),
    ],
)
def test_moi_loi_http_deu_raise(status: int, expected: type) -> None:
    """F-1: KHÔNG status nào được trả về body lỗi như thành công."""
    with pytest.raises(expected):
        raise_for_status(_Resp(status, {"rc": "0"}, text="loi"))


def test_http_200_khong_raise() -> None:
    raise_for_status(_Resp(200, {"rc": "1"}))


def test_ten_loi_khong_co_body_json() -> None:
    """Lỗi không kèm body JSON vẫn phải raise, không ném KeyError/ValueError."""
    resp = _Resp(400, None, text="Bad Request")
    with pytest.raises(BrokerValidationError) as exc:
        raise_for_status(resp)
    assert "Bad Request" in str(exc.value)


# ── post_json ───────────────────────────────────────────────────────────────────


def test_post_json_thanh_conhang_tra_nguyen_van(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 200 + mã nghiệp vụ lỗi vẫn trả nguyên văn — caller tự kiểm `rc`."""
    calls: list = []

    def _fake_post(url: str, **kwargs: Any) -> _Resp:
        calls.append((url, kwargs))
        return _Resp(200, {"cmd": "deposit", "rc": "0", "rs": "khong du tien"})

    monkeypatch.setattr(requests, "post", _fake_post)

    result = post_json(
        _session_with_token(),
        TCBSCredentialConfig(api_key="k", base_url="https://openapi.tcbs.com.vn"),
        _PATH,
        {"accountId": "105C1", "subAccountId": "D1", "amount": 1000.0},
    )

    assert result == {"cmd": "deposit", "rc": "0", "rs": "khong du tien"}
    assert describe_business_code(result) == "0"
    url, kwargs = calls[0]
    assert url.endswith(_PATH)
    assert kwargs["headers"]["Authorization"] == "Bearer test-token"


@pytest.mark.parametrize("status", [400, 404, 422, 429])
def test_post_json_loi_http_khong_tra_body(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """F-1 tái lập trực tiếp trên `post_json`: lỗi phải raise, không trả body."""
    monkeypatch.setattr(
        requests, "post", lambda *a, **k: _Resp(status, {"rc": "0"}, text="loi")
    )
    with pytest.raises((BrokerValidationError, BrokerOrderError, BrokerRateLimitError)):
        post_json(
            _session_with_token(),
            TCBSCredentialConfig(api_key="k"),
            _PATH,
            {"accountId": "105C1"},
        )


def test_post_json_chua_authenticate() -> None:
    """
    Session chưa có token: `BrokerSession.token` **ném** `BrokerSessionExpiredError`
    (`session.py:129-130`) chứ không trả None — nên nhánh `if not token` trong
    `post_json` là defensive, không reachable từ session trống. Test chốt hành vi
    thật chứ không chốt hành vi lý tưởng.
    """
    from vnbroker.broker.exceptions import BrokerSessionExpiredError

    with pytest.raises(BrokerSessionExpiredError):
        post_json(BrokerSession(), TCBSCredentialConfig(api_key="k"), _PATH, {})


def test_session_da_het_han_thi_raise() -> None:
    """Token đã hết hạn → session chặn trước khi gọi HTTP."""
    from vnbroker.broker.exceptions import BrokerSessionExpiredError

    session = BrokerSession()
    session.set_token("test-token", expires_in_seconds=-1)

    called: list = []
    import unittest.mock as mock

    with mock.patch.object(requests, "post", lambda *a, **k: called.append(a) or _Resp(200, {})):
        with pytest.raises(BrokerSessionExpiredError):
            post_json(session, TCBSCredentialConfig(api_key="k"), _PATH, {})
    assert called == [], "không được gọi HTTP khi session đã hết hạn"


def test_post_json_timeout() -> None:
    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise requests.exceptions.Timeout()

    import unittest.mock as mock

    with mock.patch.object(requests, "post", _boom):
        with pytest.raises(BrokerNetworkError) as exc:
            post_json(
                _session_with_token(), TCBSCredentialConfig(api_key="k"), _PATH, {}
            )
    assert exc.value.code == "NETWORK_TIMEOUT"


def test_post_json_khong_log_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Payload có số tiền + tài khoản — không được rò ra log ở bất kỳ level nào."""
    calls: list = []

    def _fake_post(url: str, **kwargs: Any) -> _Resp:
        calls.append((url, kwargs))
        return _Resp(200, {"rc": "1"})

    monkeypatch.setattr(requests, "post", _fake_post)
    secret = {"accountId": "105CSECRET", "amount": 987654321.0}

    import logging

    records: list = []

    class _Cap(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    logger = logging.getLogger("vnbroker.broker.tcbs")
    handler = _Cap()
    logger.addHandler(handler)
    try:
        post_json(
            _session_with_token(), TCBSCredentialConfig(api_key="k"), _PATH, secret
        )
    finally:
        logger.removeHandler(handler)

    blob = " ".join(records)
    assert "105CSECRET" not in blob
    assert "987654321" not in blob


# ── describe_business_code ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"rc": "1"}, "1"),
        ({"rc": "0"}, "0"),
        ({"code": "200"}, "200"),
        ({"rc": None}, None),
        ({}, None),
        (None, None),
        ([{"rc": "1"}], None),
    ],
)
def test_describe_business_code(payload: Any, expected: Optional[str]) -> None:
    assert describe_business_code(payload) == expected


# ── Hợp đồng money.py dùng helper này ────────────────────────────────────────────


def test_money_post_ủy_quyền_helper() -> None:
    """money.py phải đi qua `post_json` — chốt lại để không quay về bản cũ."""
    import inspect

    from vnbroker.broker.tcbs import money

    src = inspect.getsource(money.TCBSMoneyService._post)
    assert "post_json" in src
    # Bản cũ map thiếu 4xx; bản mới phải không còn nhánh trả resp.json() trần.
    assert "resp.status_code >= 400" not in src


# ── Bằng chứng fail-trước/pass-sau cho chính lỗi F-1 ─────────────────────────────
# Test dưới đây chạy trên `TCBSMoneyService` thật. Trên `money.py` bản cũ
# (90ead64, chỉ map 401/403/5xx) chúng **ĐỎ**: thân lỗi 400 bị trả về y như
# thành công. Trên bản mới chúng xanh.


@pytest.mark.parametrize("status", [400, 404, 422, 429])
def test_deposit_margin_loi_http_phai_raise(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """F-1, tái lập qua lớp service: write động tiền không được nuốt lỗi."""
    from vnbroker.broker.tcbs.money import TCBSMoneyService

    monkeypatch.setattr(
        requests, "post", lambda *a, **k: _Resp(status, {"rc": "0"}, text="loi")
    )
    service = TCBSMoneyService(
        config=TCBSCredentialConfig(api_key="k"), session=_session_with_token()
    )
    service._session.enable_write()

    with pytest.raises(BrokerError):
        service.deposit_margin(
            account_id="105C1", sub_account_id="D1", amount=1000.0, dry_run=False
        )


def test_deposit_margin_thanh_conhang_tra_nguyen_van(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 200 + rc='0' vẫn trả nguyên văn — thư viện không tự raise theo rc."""
    from vnbroker.broker.tcbs.money import TCBSMoneyService

    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: _Resp(200, {"cmd": "deposit", "rc": "0", "rs": "tu choi"}),
    )
    service = TCBSMoneyService(
        config=TCBSCredentialConfig(api_key="k"), session=_session_with_token()
    )
    service._session.enable_write()

    result = service.deposit_margin(
        account_id="105C1", sub_account_id="D1", amount=1000.0, dry_run=False
    )
    assert result["rc"] == "0"
    assert describe_business_code(result) == "0"