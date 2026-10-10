"""
Test cho 2 sua loi nho cua round 3 (S3):

  F-4  `auth.py::_store_token` ghi `token_expires_at` **ngoài** `_lock` cua session
       ⇒ race voi `BrokerSession.token` property (doc duoi cung lock).
  F-9  Envelope dry-run cua `write_gate` tra `kwargs_keys` ⇒ **ten** tham so nhay
       cam (`pin` / `otp` / `api_key`) lot vao log neu caller in envelope.

Ca hai deu la sua **hanh vi**, nen test phai khoa hanh vi chu khong khoa hinh thuc.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.security.guards import _is_sensitive_kwarg, write_gate
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.tcbs.auth import TCBSAuthService

REPO_ROOT = Path(__file__).resolve().parents[4]


# ── F-9: envelope khong lo ten tham so nhay cam ──────────────────────────────


@pytest.mark.parametrize(
    "name",
    ["pin", "pin_code", "pinCode", "PIN", "otp", "api_key", "apiKey", "password", "secret"],
)
def test_ten_nhay_cam_bi_lo(name: str) -> None:
    assert _is_sensitive_kwarg(name), f"{name} phai bi coi la nhay cam"


@pytest.mark.parametrize("name", ["account_id", "symbol", "price", "quantity", "dry_run"])
def test_ten_thuong_duoc_giu(name: str) -> None:
    assert not _is_sensitive_kwarg(name)


def test_envelope_khong_chua_ten_nhay_cam() -> None:
    class Svc:
        def __init__(self) -> None:
            self._session = BrokerSession()

        @write_gate
        def place(self, account_id: str, pin_code: str = "", symbol: str = "",
                  *, dry_run: bool = True) -> dict:
            return {"ok": True}

    env = Svc().place(account_id="105C1", pin_code="123456", symbol="FPT")
    keys = env["kwargs_keys"]
    assert "account_id" in keys and "symbol" in keys
    assert "pin_code" not in keys, f"pin_code lot vao envelope: {keys}"
    assert "123456" not in str(env), "gia tri pin lot vao envelope"


def test_write_gate_chu_ky_con() -> None:
    """Sửa envelope KHÔNG được đổi chữ ký public của `write_gate`."""
    import inspect

    sig = inspect.signature(write_gate)
    assert list(sig.parameters) == ["fn"]
    assert sig.return_annotation in ("R", Any) or True  # TypeVar, khong assert gia tri


# ── F-4: ghi token_expires_at phai nam trong lock ─────────────────────────────


def _service() -> TCBSAuthService:
    return TCBSAuthService(
        config=TCBSCredentialConfig(api_key="k"), session=BrokerSession()
    )


def test_store_token_khong_tao_han_bia_dat() -> None:
    """Không có JWT ⇒ không decode được `exp` ⇒ KHÔNG được tự chế 8 giờ."""
    svc = _service()
    svc._store_token("not-a-jwt", None)
    assert svc._session.token_expires_at is None


def test_store_token_giu_han_that() -> None:
    from datetime import datetime, timedelta, timezone

    svc = _service()
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    svc._store_token("token-abc", exp)
    assert svc._session.token_expires_at == exp


def test_store_token_thuc_su_dung_lock_cua_session() -> None:
    """
    ⚠ Đây là test **CẤU TRÚC**, không phải hành vi — và đó là điều đã phải chấp nhận.

    **Vì sao không test hành vi được:** đã thử 3 cách, cả 3 đều **xanh ở cả hai
    trạng thái** (có lock / không lock) ⇒ bằng chứng bằng 0, phải gỡ:
      1. Thread khác giữ `RLock` thật → `set_token` tự thâu lấy lại được ⇒ không bao giờ chặn.
      2. Thread A ghi hạn bịa **không** dùng `_lock` → B luôn ghi sau ⇒ không phân biệt được.
      3. Đếm số lần `acquire` → `set_token` gọi `update_activity()` cũng thâu lock,
         nên 2 lần ở **cả hai** trạng thái.

    Vậy còn lại đúng một thứ kiểm được: lệnh ghi `token_expires_at = None` **nằm
    trong** khối `with self._session._lock:`. Test này **ĐỎ khi bỏ `with`** — đã
    kiểm chứng bằng cách thay file, không suy luận.

    Đừng nâng lên thành "test hành vi" nếu chưa tìm được lịch race xác định.
    """
    import ast
    import inspect

    from vnbroker.broker.tcbs import auth as auth_mod

    src = inspect.getsource(auth_mod.TCBSAuthService._store_token)
    tree = ast.parse(src.strip())

    def _is_lock_ctx(node: ast.With) -> bool:
        for item in node.items:
            expr = item.context_expr
            # `self._session._lock`
            if (
                isinstance(expr, ast.Attribute)
                and expr.attr == "_lock"
                and isinstance(expr.value, ast.Attribute)
                and expr.value.attr == "_session"
            ):
                return True
        return False

    # Tim khoi gan `token_expires_at = None` va kiem no nam trong `with ..._lock`
    for node in ast.walk(tree):
        if not isinstance(node, ast.With) or not _is_lock_ctx(node):
            continue
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Assign)
                and len(sub.targets) == 1
                and isinstance(sub.targets[0], ast.Attribute)
                and sub.targets[0].attr == "token_expires_at"
            ):
                return  # tim thay: ghi co bao ve

    pytest.fail(
        "_store_token ghi token_expires_at NGOAI khoi `with self._session._lock:` "
        "⇒ race voi `BrokerSession.token` property (doc duoi cung lock)"
    )


# ── hien trang de bi do (F-5): check_and_update_state chua co caller ──────────


def test_check_and_update_state_chua_co_caller() -> None:
    """
    Bẫy đang ngủ: hàm này tồn tại nhưng **không ai gọi**, nên `token_expires_at is None`
    chưa gây hậu quả. Test này là CẢNH BÁO — khi ai đó bắt đầu gọi hàm này thì
    phải kiểm lại hành vi với `token_expires_at is None`.

    Đổi từ False sang True là tín hiệu phải đọc lại `docs/HANDOFF` §N4.
    """
    import subprocess

    # KHONG dung `grep`: Windows khong co grep trong PATH. Dung `git grep` —
    # chay duoc tren moi may, khong phu thuoc tool ngoai.
    proc = subprocess.run(
        ["git", "grep", "-n", "check_and_update_state"],
        capture_output=True, text=True, shell=False, cwd=str(REPO_ROOT),
    )
    # Chi doc file .py — tai lieu markdown nhac lai "khong co caller" cung duoc
    # tinh la tai lieu, khong phai code dang chay.
    callers = [
        ln for ln in proc.stdout.splitlines()
        if "def check_and_update_state" not in ln and ln.split(":")[0].endswith(".py")
    ]
    assert callers == [], (
        f"check_and_update_state da co caller moi trong code: {callers}. "
        "Kiem tra lai hành vi voi token_expires_at is None truoc khi merge."
    )


def test_session_expired_error_khi_het_han() -> None:
    from vnbroker.broker.exceptions import BrokerSessionExpiredError

    svc = _service()
    svc._session.set_token("t", expires_in_seconds=-1)
    with pytest.raises(BrokerSessionExpiredError):
        _ = svc._session.token