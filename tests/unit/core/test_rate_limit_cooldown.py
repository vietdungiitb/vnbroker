"""W3 — 429 thật: không retry, chuyển provider, cooldown theo ``Retry-After``.

Bám theo `docs/PLAN_TIER1_WAVE34.md` §2 (AC-3.1 … AC-3.5) và §4 (W3.0–W3.6).

**Vì sao test này đi qua `send_request_direct` thật chứ không ném exception giả.**
Ở `4cd0f2d` một HTTP 429 đi ra khỏi tầng transport là `ConnectionError`; sau
W3.1 nó mới thành `RateLimitError`. Nếu test ném `RateLimitError` bằng tay thì
nó đo cái mình vừa viết, không đo cái server thật làm — và ở `4cd0f2d` sẽ xanh
(bằng chứng vô giá trị, L-E06). Ở đây provider giả **gọi đúng hàm transport thật**
với một response 429 thật, nên:

* trên `4cd0f2d` → `ConnectionError` → AC-3.2/3.3 đỏ (3 và 6 lần thử),
* sau W3 → `RateLimitError` → 1 lần thử/provider, cooldown theo header.

Không test nào gọi mạng. Router state được reset trước/sau mỗi test vì
`tests/unit/core/test_source_router_circuit_breaker.py` và test contract dùng
chung một health store.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import pytest
from requests.structures import CaseInsensitiveDict

from vnbroker.common.data import Quote
from vnbroker.core import source_router
from vnbroker.core.exceptions import NetworkError, RateLimitError, vnbrokerError
from vnbroker.core.utils import client as client_mod
from vnbroker.core.utils.client import send_request_direct

try:  # `parse_retry_after` là hàm MỚI của W3.1
    from vnbroker.core.utils.client import parse_retry_after
except ImportError:  # ở `4cd0f2d` hàm chưa tồn tại
    # KHÔNG để ImportError giết cả module: khi đó test khác không collect được
    # và ta mất bằng chứng đỏ-riêng-lẻ cho AC-3.1/3.2/3.3/3.5. Test con của nó
    # sẽ đỏ ngay trong thân hàm — đó mới là bằng chứng đúng.
    parse_retry_after = None  # type: ignore[assignment]

CANONICAL_TZ = "Asia/Ho_Chi_Minh"

URL = "https://quotes.example/api/history"

# `cooldown_remaining_sec` được đo **tại lúc đọc**, nên đã trôi vài chục ms kể
# từ lúc `record_failure` chạy. Vì vậy so sánh "≥ 120" phải chừa sai số đo.
# Mốc 120-1 vẫn cao hơn **24 lần** giá trị 5s của hành vi cũ — tức là test
# không thể xanh nhầm vì đồng hồ.
COOLDOWN_TOLERANCE_SEC = 1.0


@pytest.fixture(autouse=True)
def _clean_router(monkeypatch):
    monkeypatch.setenv("vnbroker_ROUTER_HEALTH_DB", "memory")
    source_router.reload_store()
    source_router.reset_router_state()
    yield
    source_router.reset_router_state()
    source_router.reload_store()


# --------------------------------------------------------------------- fake


class _FakeResponse:
    """Response HTTP giả — chỉ có những gì `send_request_direct` thật sự đọc."""

    def __init__(
        self,
        status_code: int,
        *,
        headers: Optional[Dict[str, str]] = None,
        payload: Optional[Dict[str, Any]] = None,
        reason: str = "Too Many Requests",
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self.reason = reason
        self._payload = payload or {}

    def json(self) -> Dict[str, Any]:
        return self._payload


class _FakeSession:
    """Session giả trả về `response` đã dựng. Không chạm mạng."""

    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.requests = 0

    def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.requests += 1
        return self._response


class _ThrottledSource:
    """Provider giả đi qua ĐÚNG tầng transport thật (`send_request_direct`).

    `calls` đếm số lần provider được gọi — đây là "số HTTP attempt" mà AC-3.2
    và AC-3.3 nói tới, đếm bằng call counter chứ không đếm bằng mắt.
    """

    symbol = "ACB"

    def __init__(self) -> None:
        self.calls = 0

    def history(self, **kw: Any) -> Any:
        self.calls += 1
        return send_request_direct(URL, {"Accept": "application/json"})


class _OkSource:
    """Provider giả trả dữ liệu hợp lệ (đúng schema tầng 1)."""

    symbol = "ACB"

    def __init__(self) -> None:
        self.calls = 0

    def history(self, **kw: Any) -> Any:
        self.calls += 1
        idx = pd.to_datetime(["2024-01-02", "2024-01-03"]).tz_localize(CANONICAL_TZ)
        return pd.DataFrame(
            {
                "time": idx,
                "open": [1.0, 2.0],
                "high": [1.0, 2.0],
                "low": [1.0, 2.0],
                "close": [1.0, 2.0],
                "volume": [10, 20],
            }
        )


class _BugSource:
    """Provider giả ném lỗi lập trình — loại lỗi KHÔNG được retry/che."""

    symbol = "ACB"

    def __init__(self) -> None:
        self.calls = 0

    def history(self, **kw: Any) -> Any:
        self.calls += 1
        raise TypeError("bug trong provider")


def _install_429(monkeypatch, *, headers: Optional[Dict[str, str]] = None) -> _FakeSession:
    """Cắm session giả trả 429 cho mọi request đi qua `send_request_direct`."""
    session = _FakeSession(_FakeResponse(429, headers=headers or {}))
    monkeypatch.setattr(client_mod, "_get_thread_session", lambda: session)
    return session


def _auto_quote(sources: Dict[str, Any], order: List[str]) -> Quote:
    """Dựng `Quote` ở chế độ AUTO với lớp failover thật, chỉ thay provider.

    Ghim thứ tự provider bằng `_fixed_source_order` (đường móc có sẵn, xem
    `tests/contract/test_failover_tier1.py`) để test có tính xác định — mặc
    định `build_source_order` hash-shard theo symbol nên thứ tự có thể đảo.
    """
    q = Quote("ACB", "AUTO")
    q._auto_sources = sources  # type: ignore[attr-defined]

    def _fixed_order(module_name: str, symbol: Optional[str] = None) -> List[str]:
        return [s for s in order if s in sources]

    q._fixed_source_order = _fixed_order  # type: ignore[attr-defined]
    return q


# ------------------------------------------------- W3.0 / AC-3.5: lớp lỗi


def test_ac_3_5_rate_limit_error_triggers_failover():
    """AC-3.5 — `should_failover(RateLimitError(...))` phải là `True`.

    ĐỎ ở `4cd0f2d`: lớp chỉ kế thừa `NetworkError` nên không phải `OSError`, mà
    chuỗi `"temporarily throttled requests"` cũng không chứa marker `"429"` /
    `"rate limit"` ⇒ `should_failover` trả `False` ⇒ `base.py` **raise** thay vì
    chuyển provider. Sửa kế thừa (thêm `ConnectionError`) thay vì sửa hàm.
    """
    exc = RateLimitError("kbs", retry_after=120)

    assert source_router.should_failover(exc) is True
    # Hệ quả bắt buộc: `should_failover` xét `OSError` trước marker chuỗi, nên
    # chỉ kế thừa thêm mà không có `OSError` thì AC này vẫn đỏ.
    assert isinstance(exc, OSError) is True
    # ... và người dùng đang bắt `except ConnectionError` không bị hỏng.
    assert isinstance(exc, ConnectionError) is True
    # Giữ `NetworkError` để không phá `except vnbrokerError` đang có.
    assert isinstance(exc, NetworkError) is True
    assert isinstance(exc, vnbrokerError) is True


def test_rate_limit_error_exposes_typed_retry_after():
    """W3.0 — `retry_after` là thuộc tính có kiểu, không chỉ nằm trong `details`.

    ĐỎ ở `4cd0f2d`: `RateLimitError` không có thuộc tính này; `record_failure`
    không lấy được đâu ngoài `details` (mà không ai đọc).
    """
    exc = RateLimitError("kbs", retry_after=120)

    assert exc.retry_after == 120
    assert exc.details["retry_after"] == 120
    assert RateLimitError("kbs").retry_after is None
    # `Retry-After: 0` = không giới hạn thực tế -> coi như không có thông tin,
    # KHÔNG phải "chờ 0 giây" (nếu không, cooldown sẽ bị kẹp ở sàn 1s).
    assert RateLimitError("kbs", retry_after=0).retry_after is None


# ---------------------------------------------------------- W3.1: transport


def test_ac_3_1_transport_429_carries_retry_after(monkeypatch):
    """W3.1 — 429 phải ra `RateLimitError` kèm `retry_after` đọc từ header.

    ĐỎ ở `4cd0f2d`: mọi status != 200 (kể cả 429) đều ra `ConnectionError`
    chung, không đọc `response.headers` lần nào.
    """
    _install_429(monkeypatch, headers={"Retry-After": "120"})

    with pytest.raises(RateLimitError) as caught:
        send_request_direct(URL, {})

    assert caught.value.retry_after == 120
    assert isinstance(caught.value, ConnectionError)  # không phá code cũ


@pytest.mark.parametrize(
    "headers, expected",
    [
        ({"Retry-After": "120"}, 120.0),
        ({"Retry-After": " 7 "}, 7.0),
        # Header HTTP không phân biệt hoa/thường (RFC 9110 §5.1) và `requests`
        # cho ta `CaseInsensitiveDict` — dùng đúng loại đó, không dùng dict thường.
        (CaseInsensitiveDict({"retry-after": "30"}), 30.0),
        ({}, None),
        ({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, None),  # dạng HTTP-date
        ({"Retry-After": "banana"}, None),
        ({"Retry-After": "-5"}, None),
    ],
)
def test_parse_retry_after(headers, expected):
    """Chỉ đọc `Retry-After`; giá trị không parse được = "không có thông tin".

    ĐỎ ở `4cd0f2d`: hàm `parse_retry_after` không tồn tại ⇒ `parse_retry_after
    is None` fail ngay, cả 7 ca.
    """
    assert parse_retry_after is not None, (
        "W3.1 chưa có parse_retry_after: header Retry-After không được đọc"
    )
    assert parse_retry_after(headers) == expected


def test_parse_retry_after_handles_garbage_container():
    """Response không phải mapping (fake/response lạ) không được ném ngoại lệ."""
    assert parse_retry_after(None) is None
    assert parse_retry_after(object()) is None


def test_non_429_status_keeps_plain_connection_error(monkeypatch):
    """Chỉ 429 đổi kiểu lỗi; 403/500 vẫn là `ConnectionError` như cũ."""
    session = _FakeSession(_FakeResponse(500, reason="Internal Server Error"))
    monkeypatch.setattr(client_mod, "_get_thread_session", lambda: session)

    with pytest.raises(ConnectionError) as caught:
        send_request_direct(URL, {})

    assert not isinstance(caught.value, RateLimitError)
    assert "500" in str(caught.value)


# ----------------------------------------- W3.2 + W3.6: cooldown theo server


def test_ac_3_1_auto_429_sets_cooldown_from_retry_after(monkeypatch):
    """AC-3.1 — AUTO + 429 + ``Retry-After: 120`` ⇒ cooldown **≥ 120 giây**.

    ĐỎ ở `4cd0f2d`: cooldown chỉ lớn theo suy đoán `5 * 2**(failures-1)` = 5s,
    vì `record_failure` ở `common/data.py` được gọi với đúng 2 đối số nên
    không truyền được `retry_after` (và transport cũ không đọc header).
    """
    _install_429(monkeypatch, headers={"Retry-After": "120"})
    kbs, vci = _ThrottledSource(), _OkSource()

    _auto_quote({"kbs": kbs, "vci": vci}, order=["kbs", "vci"]).history()

    remaining = source_router.get_source_health_snapshot("quote")["KBS"][
        "cooldown_remaining_sec"
    ]
    assert remaining >= 120 - COOLDOWN_TOLERANCE_SEC, (
        f"cooldown phải theo Retry-After server (>=120s), thực tế {remaining}"
    )


def test_record_failure_without_retry_after_keeps_legacy_backoff():
    """W3.2 — server im lặng thì cooldown phải **y hệt** hành vi cũ.

    Chặn việc lỡ tay nới trần của phần suy đoán: 5, 10, 20, 40, 80, 90, 90.
    """
    for failures, expected in enumerate([5.0, 10.0, 20.0, 40.0, 80.0, 90.0, 90.0], 1):
        assert source_router.compute_cooldown_seconds(failures) == expected


def test_record_failure_uses_max_of_guess_and_retry_after():
    """W3.2 — cooldown = max(suy đoán, Retry-After), kẹp ở trần cấu hình."""
    compute = source_router.compute_cooldown_seconds

    assert compute(1, 120) == 120.0      # server nói nhiều hơn -> nghe server
    assert compute(1, 5) == 5.0          # server nói ít hơn -> không hạ cooldown
    assert compute(1, 1e9) == 900.0      # quá trần -> kẹp, không treo 24h
    assert compute(1, -5) == 5.0         # rác -> coi như không có thông tin


# ------------------------------------------------------- W3.3/W3.6: attempt


def test_ac_3_2_fixed_source_429_is_attempted_exactly_once(monkeypatch):
    """AC-3.2 — source cố định trả 429 ⇒ **đúng 1** attempt cho một lệnh.

    ĐỎ ở `4cd0f2d`: đo được **3** attempt (tenacity trong
    `_run_with_failover` retry `ConnectionError` vì 429 lúc đó ra
    `ConnectionError`). Người dùng gọi `history()` một lần và bị bắn 3 phát
    vào một server vừa dặn "chậm lại".
    """
    _install_429(monkeypatch, headers={"Retry-After": "120"})
    kbs = _ThrottledSource()

    q = Quote("ACB", "KBS")
    q.data_source = kbs  # thay provider, giữ nguyên lớp failover thật

    with pytest.raises(RateLimitError):
        q.history()

    assert kbs.calls == 1, f"429 không được retry, thực tế {kbs.calls} lần"


def test_ac_3_3_auto_all_providers_429_is_attempted_exactly_twice(monkeypatch):
    """AC-3.3 — AUTO, cả hai provider trả 429 ⇒ **đúng 2** attempt (1/provider).

    ĐỎ ở `4cd0f2d`: đo được **6** (3 lần/provider). Đây là hậu quả nặng nhất:
    session thị trường bị bắn 6 request vào 2 server vừa trả 429.
    """
    _install_429(monkeypatch, headers={"Retry-After": "120"})
    kbs, vci = _ThrottledSource(), _ThrottledSource()

    with pytest.raises(RateLimitError):
        _auto_quote({"kbs": kbs, "vci": vci}, order=["kbs", "vci"]).history()

    assert (kbs.calls, vci.calls) == (1, 1), (
        f"mỗi provider đúng 1 lần, thực tế kbs={kbs.calls} vci={vci.calls}"
    )


def test_other_network_errors_are_still_retried(monkeypatch):
    """Chặn sửa quá tay: 500 vẫn retry 3 lần như cũ (chỉ 429 mới bị loại).

    Cùng bộ test này chặn cả việc dùng
    `retry_if_not_exception_type(RateLimitError)` thuần như plan §4 W3.3 ghi:
    dạng đó nới retry ra mọi exception còn lại, kể cả lỗi lập trình.
    """
    session = _FakeSession(_FakeResponse(500, reason="Internal Server Error"))
    monkeypatch.setattr(client_mod, "_get_thread_session", lambda: session)
    kbs = _ThrottledSource()

    q = Quote("ACB", "KBS")
    q.data_source = kbs

    with pytest.raises(ConnectionError):
        q.history()

    assert kbs.calls == 3, f"lỗi mạng khác 429 vẫn retry, thực tế {kbs.calls} lần"


def test_programming_error_is_not_retried_or_swallowed(monkeypatch):
    """Lỗi lập trình vẫn ném ngay lần 1, không retry, không che.

    Đây là lý do W3.3 dùng **giao** của hai điều kiện thay vì
    `retry_if_not_exception_type(RateLimitError)` thuần.
    """
    bug = _BugSource()

    q = Quote("ACB", "KBS")
    q.data_source = bug

    with pytest.raises(TypeError):
        q.history()

    assert bug.calls == 1, f"lỗi lập trình không được retry, thực tế {bug.calls} lần"
    state = source_router.get_source_health_snapshot("quote").get("KBS") or {}
    assert int(state.get("failures", 0)) == 0


# -------------------------------------------------------------- failover


def test_ac_3_4_429_on_a_falls_back_to_b(monkeypatch):
    """AC-3.4 — A trả 429, B có dữ liệu ⇒ ``source_used == "B"``, A có failure.

    ⚠ **AC HỒI QUY — xanh sẵn ở `4cd0f2d`, KHÔNG phải bằng chứng fix.** Đo ở
    base: `ConnectionError("...429...")` lọt qua marker `"429"` nên đã failover
    đúng. Giữ lại để chặn W3.0 (đổi kế thừa của `RateLimitError`) không làm
    hỏng failover. Test này **cố ý không** assert cooldown — phần cooldown là
    AC-3.1; trộn vào đây sẽ làm đỏ giả một AC hồi quy.
    """
    _install_429(monkeypatch, headers={"Retry-After": "120"})
    kbs = _ThrottledSource()
    vci = _OkSource()

    df = _auto_quote({"kbs": kbs, "vci": vci}, order=["kbs", "vci"]).history()

    assert df.attrs.get("source_used") == "VCI"
    assert vci.calls == 1
    snapshot = source_router.get_source_health_snapshot("quote")["KBS"]
    assert int(snapshot["failures"]) >= 1


def test_ac_3_4_fixed_source_429_surfaces_to_caller(monkeypatch):
    """Nguồn cố định không có provider thứ hai ⇒ lỗi gốc ném ra, không DataFrame rỗng.

    Frame rỗng khiến người dùng tưởng "hôm nay không giao dịch" thay vì "đã bị
    throttle" — đó là lỗi âm thầm nguy hiểm nhất của tầng dữ liệu.
    """
    _install_429(monkeypatch, headers={"Retry-After": "120"})
    kbs = _ThrottledSource()

    q = Quote("ACB", "KBS")
    q.data_source = kbs

    with pytest.raises(RateLimitError) as caught:
        q.history()

    assert caught.value.retry_after == 120
    assert kbs.calls == 1