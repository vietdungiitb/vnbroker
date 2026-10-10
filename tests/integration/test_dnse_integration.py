"""Integration tests for DNSE client.

These tests require DNSE credentials in environment variables.

**Vấn đề mà file này vừa gặp — và cách sửa**

Bản gốc đọc credential từ `os.getenv` mà không nạp `.env`, nên trên máy đã có
key trong `.env` thì vẫn **skip vĩnh viễn**:

    $ pytest tests/integration/test_dnse_integration.py -q
    4 skipped — Missing DNSE env vars: DNSE_API_KEY, DNSE_API_SECRET, DNSE_ACCOUNT_NO

Test luôn xanh mà chưa từng chạm DNSE là tệ hơn không có test: nó tạo cảm giác
đã kiểm chứng. Ba nguyên nhân, cả ba đều sửa ở đây:

1. `.env` không được nạp → thêm :func:`_load_repo_env`.
2. `DNSE_ACCOUNT_NO` không tồn tại trong `.env` → suy ra từ ``get_accounts()``
   thay vì đòi biến không ai đặt.
3. Chỉ có một cặp key production nhưng production không thông từ máy này →
   ưu tiên cặp sandbox ``SB_API_KEY``/``SB_API_SECRET`` (trả 200).

``test_the_env_is_actually_visible`` chốt lại: nếu ``.env`` có credential mà
module này vẫn không thấy thì phải **fail**, không được skip trong im lặng.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from vnbroker.connector.dnse.client import DNSEClient


SANDBOX_URL = "https://sb-openapi.dnse.com.vn"
PRODUCTION_URL = "https://openapi.dnse.com.vn"


def _load_repo_env() -> Path | None:
    """Nạp ``.env`` của repo vào ``os.environ`` (không đè biến đã có sẵn).

    Test khác trong repo dùng ``patch.dict(os.environ, ...)``; ở đây cần giữ
    credential thật nên đọc file. Trả về path đã đọc, hoặc ``None`` nếu không có.
    """
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return None
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Không đè: biến do CI/người chạy đặt tay luôn thắng file.
        os.environ.setdefault(key, value)
    return env_path


_ENV_FILE = _load_repo_env()


#: Những biến thiếu thì mới được phép skip. `DNSE_ACCOUNT_NO` cố ý KHÔNG nằm
#: ở đây — nó được suy ra từ `get_accounts()`.
_MISSING_ENFORCED: tuple[str, ...] = ("DNSE_API_KEY", "DNSE_API_SECRET")


def _missing_env() -> list[str]:
    return [key for key in _MISSING_ENFORCED if not os.getenv(key)]


def _missing_reason() -> str:
    where = _ENV_FILE if _ENV_FILE else "khong tim thay file .env o goc repo"
    return (
        f"Thieu credential DNSE. Da tim o bien moi truong va {where}. "
        "Dat DNSE_API_KEY / DNSE_API_SECRET, hoac SB_API_KEY / SB_API_SECRET "
        "de chay tren sandbox."
    )


def _pick_credentials() -> tuple[str, str, str]:
    """Chọn cặp key dùng được.

    Ưu tiên sandbox: production ``openapi.dnse.com.vn`` không trả lời từ máy
    này (đo 2026-10-09: read timeout / connection reset), còn sandbox trả 200.
    """
    sb_key, sb_secret = os.getenv("SB_API_KEY"), os.getenv("SB_API_SECRET")
    if sb_key and sb_secret:
        return sb_key, sb_secret, SANDBOX_URL
    return (
        os.getenv("DNSE_API_KEY", ""),
        os.getenv("DNSE_API_SECRET", ""),
        os.getenv("DNSE_BASE_URL", PRODUCTION_URL),
    )


@pytest.mark.integration
@pytest.mark.smoke
class TestDNSEIntegration:
    @pytest.fixture(scope="class")
    def client(self):
        missing = _missing_env()
        if missing and not (os.getenv("SB_API_KEY") and os.getenv("SB_API_SECRET")):
            pytest.skip(_missing_reason())
        key, secret, base_url = _pick_credentials()
        return DNSEClient(
            api_key=key,
            api_secret=secret,
            base_url=base_url,
            timeout_seconds=20.0,
            show_log=False,
        )

    @pytest.fixture(scope="class")
    def account_no(self, client: DNSEClient) -> str:
        """Số tiểu khoản: lấy từ biến môi trường, nếu không thì hỏi DNSE.

        ``DNSE_ACCOUNT_NO`` không có trong ``.env`` — đòi nó là lý do khiến cả
        module skip dù đã có key. ``get_accounts()`` trả về số tiểu khoản nên
        suy ra được thay vì bắt người dùng đặt thêm biến.
"""
        configured = os.getenv("DNSE_ACCOUNT_NO")
        if configured:
            return configured
        # ⚠ BỌC LỚI BẢO VỆ (2026-10-10): lỗi mạng ở đây sinh ra **ERROR**,
        # không phải FAILED — pytest báo lỗi fixture, chạy tiếp cả class, và
        # `_skip_if_transport_failure` trong thân test KHÔNG BAO GIỜ chạy tới.
        # Đã gặp thật: `ConnectionResetError` từ DNSE làm `pytest-full` đỏ
        # 2 case dù code hoàn toàn không liên quan.
        try:
            payload = client.get_accounts(raw=True)
        except Exception as exc:  # noqa: BLE001 - chuyển qua bộ lọc bên dưới
            _skip_if_transport_failure(exc)
        if not isinstance(payload, dict):
            pytest.skip("get_accounts() khong tra ve dict de suy ra so tieu khoan")
        for entry in payload.get("accounts") or []:
            if isinstance(entry, dict) and entry.get("id"):
                return str(entry["id"])
        pytest.skip("get_accounts() khong co truong 'id' de suy ra so tieu khoan")

    def test_get_accounts_raw(self, client: DNSEClient):
        try:
            payload = client.get_accounts(raw=True)
        except Exception as exc:
            _skip_if_transport_failure(exc)
        assert payload is not None

    def test_get_balances_raw(self, client: DNSEClient, account_no: str):
        try:
            payload = client.get_balances(account_no=account_no, raw=True)
        except Exception as exc:
            _skip_if_transport_failure(exc)
        assert payload is not None

    def test_market_read_raw(self, client: DNSEClient):
        """Đọc dữ liệu thị trường — nhóm duy nhất sandbox KHÔNG implement.

        Đo thật: ``GET /price/{symbol}/secdef`` trả ``404 page not found`` trên
        ``sb-openapi.dnse.com.vn``, trong khi ``/accounts*`` trả 200. Đây là
        giới hạn của sandbox, không phải lỗi client.

        Vì vậy test không giả vờ: trên sandbox nó kiểm chứng điều còn kiểm
        chứng được — client dựng đúng URL và phân loại đúng lỗi. Trên
        production nó đòi dữ liệu thật.
        """
        from vnbroker.connector.dnse.core.errors import DNSEBaseError, DNSETransportError

        on_sandbox = client._config.base_url == SANDBOX_URL
        try:
            payload = client.get_security_definition(symbol="HPG", raw=True)
        except DNSETransportError as exc:
            _skip_if_transport_failure(exc)
        except DNSEBaseError as exc:
            assert on_sandbox, (
                f"production phai tra du lieu thay vi loi: {exc}"
            )
            assert exc.status_code == 404, (
                f"tren sandbox ky vong 404 (endpoint chua implement), "
                f"nhan {exc.status_code}: {exc}"
            )
            return
        assert not on_sandbox, (
            "sandbox bao cao co du lieu /price/* -- neu dung, bo khu vuc nay "
            "va chay lai de xac nhan mot lan nua"
        )
        assert payload is not None

    def test_order_book_raw(self, client: DNSEClient, account_no: str):
        try:
            payload = client.get_orders(
                account_no=account_no,
                market_type=os.getenv("DNSE_MARKET_TYPE", "STOCK"),
                raw=True,
            )
        except Exception as exc:
            _skip_if_transport_failure(exc)
        assert payload is not None


def _skip_if_transport_failure(exc: BaseException) -> None:
    """Chuyển lỗi mạng thành skip có lý do rõ, KHÔNG nuốt lỗi dữ liệu.

    Bật test gọi mạng thật vào gate mặc định là một đánh đổi: DNSE sập hoặc
    rớt mạng một lần thì gate đỏ dù code đúng. Lần chạy 2026-10-09 gặp đúng
    trường hợp đó (``1 failed, 2 errors`` trong 17:39) rồi chạy lại thì xanh
    hoàn toàn — dấu hiệu của flake mạng chứ không phải hồi quy.

    Ranh giới: **chỉ lỗi vận chuyển** mới được skip. Lỗi HTTP có nghĩa (404,
    400, 403) vẫn phải fail, vì đó là hành vi đang được kiểm chứng.
    """
    from vnbroker.connector.dnse.core.errors import DNSETransportError

    if isinstance(exc, DNSETransportError):
        pytest.skip(f"DNSE khong phan hoi ( loi van chuyen ): {exc}")
    raise exc


class TestEnvVisibility:
    """Chống lại đúng lỗi vừa gặp: có credential nhưng module không thấy."""

    def test_the_env_is_actually_visible(self):
        """Nếu ``.env`` có credential thì test này phải thấy — fail chứ không skip.

        ``pytest.skip`` trong một test gác cờ sẽ báo xanh và che mất đúng vấn đề
        cần phát hiện. Ở đây ta cố tình **fail** để thấy ngay khi ai đó xoá
        dòng nạp ``.env``.
        """
        if _ENV_FILE is not None:
            assert os.getenv("DNSE_API_KEY"), (
                f"{_ENV_FILE} co DNSE_API_KEY nhung os.environ khong co — "
                "_load_repo_env() da bi goi xoa"
            )
        assert os.getenv("DNSE_API_SECRET"), (
            "khong thay DNSE_API_SECRET trong moi truong"
        )

    def test_env_file_was_found_or_reason_is_clear(self):
        """Không có ``.env`` cũng được, nhưng phải nói rõ đang tìm ở đâu."""
        if _ENV_FILE is None:
            assert "khong tim thay file .env" in _missing_reason()
        else:
            assert _ENV_FILE.is_file()

    def test_account_no_is_not_a_hard_requirement(self):
        """``DNSE_ACCOUNT_NO`` không tồn tại trong ``.env`` — không được dùng nó
        làm điều kiện skip.

        Bản gốc đưa nó vào danh sách biến bắt buộc nên **cả module luôn skip**
        dù đã có key. Số tiểu khoản phải được suy ra từ ``get_accounts()``.
        """
        assert "DNSE_ACCOUNT_NO" not in _MISSING_ENFORCED
